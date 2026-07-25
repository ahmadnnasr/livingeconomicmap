from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
import json
import uuid

from .db import QueueDatabase
from .models import Job, WorkerRegistration


def now_dt() -> datetime:
    return datetime.now(timezone.utc)


def now() -> str:
    return now_dt().isoformat()


class JobRepository:
    def __init__(self, db: QueueDatabase) -> None:
        self.db = db

    def enqueue(
        self,
        queue_name: str,
        job_type: str,
        payload: dict,
        *,
        priority: int = 100,
        max_attempts: int = 5,
        available_at: Optional[str] = None,
        dedupe_key: Optional[str] = None,
        parent_job_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        job_id = str(uuid.uuid4())
        trace_id = trace_id or str(uuid.uuid4())
        timestamp = now()
        with self.db.transaction() as conn:
            if dedupe_key:
                existing = conn.execute(
                    """
                    SELECT job_id FROM jobs
                    WHERE queue_name=? AND dedupe_key=?
                    """,
                    (queue_name, dedupe_key),
                ).fetchone()
                if existing:
                    return existing["job_id"]

            conn.execute(
                """
                INSERT INTO jobs(
                    job_id, queue_name, job_type, payload_json, status,
                    priority, attempt_count, max_attempts, available_at,
                    leased_until, worker_id, dedupe_key, parent_job_id,
                    trace_id, last_error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 'pending', ?, 0, ?, ?, NULL, NULL, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    job_id, queue_name, job_type,
                    json.dumps(payload, sort_keys=True),
                    priority, max_attempts, available_at or timestamp,
                    dedupe_key, parent_job_id, trace_id, timestamp, timestamp
                ),
            )
        return job_id

    def claim(
        self,
        queue_name: str,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> Optional[Job]:
        with self.db.transaction(immediate=True) as conn:
            timestamp = now()
            row = conn.execute(
                """
                SELECT * FROM jobs
                WHERE queue_name=?
                  AND status IN ('pending', 'retry')
                  AND available_at <= ?
                  AND (leased_until IS NULL OR leased_until <= ?)
                ORDER BY priority ASC, created_at ASC
                LIMIT 1
                """,
                (queue_name, timestamp, timestamp),
            ).fetchone()

            if row is None:
                return None

            leased_until = (now_dt() + timedelta(seconds=lease_seconds)).isoformat()
            conn.execute(
                """
                UPDATE jobs
                SET status='running',
                    worker_id=?,
                    leased_until=?,
                    attempt_count=attempt_count+1,
                    updated_at=?
                WHERE job_id=?
                """,
                (worker_id, leased_until, timestamp, row["job_id"]),
            )
            attempt_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO job_attempts(
                    attempt_id, job_id, worker_id, started_at, status
                )
                VALUES (?, ?, ?, ?, 'running')
                """,
                (attempt_id, row["job_id"], worker_id, timestamp),
            )

            updated = conn.execute(
                "SELECT * FROM jobs WHERE job_id=?",
                (row["job_id"],),
            ).fetchone()
            return self._to_job(updated)

    def complete(self, job_id: str, worker_id: str, output: dict) -> None:
        with self.db.transaction() as conn:
            timestamp = now()
            conn.execute(
                """
                UPDATE jobs
                SET status='completed', leased_until=NULL, updated_at=?
                WHERE job_id=? AND worker_id=?
                """,
                (timestamp, job_id, worker_id),
            )
            conn.execute(
                """
                UPDATE job_attempts
                SET status='completed', finished_at=?, output_json=?
                WHERE job_id=? AND worker_id=? AND status='running'
                """,
                (timestamp, json.dumps(output, sort_keys=True), job_id, worker_id),
            )

    def fail(
        self,
        job_id: str,
        worker_id: str,
        error_message: str,
        *,
        retryable: bool,
        base_delay_seconds: int = 30,
    ) -> str:
        with self.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise KeyError(job_id)

            timestamp = now()
            attempts = int(row["attempt_count"])
            max_attempts = int(row["max_attempts"])

            if retryable and attempts < max_attempts:
                delay = base_delay_seconds * (2 ** max(0, attempts - 1))
                available_at = (now_dt() + timedelta(seconds=delay)).isoformat()
                status = "retry"
                conn.execute(
                    """
                    UPDATE jobs
                    SET status=?, available_at=?, leased_until=NULL,
                        worker_id=NULL, last_error=?, updated_at=?
                    WHERE job_id=?
                    """,
                    (status, available_at, error_message, timestamp, job_id),
                )
            else:
                status = "dead_letter"
                conn.execute(
                    """
                    UPDATE jobs
                    SET status=?, leased_until=NULL, last_error=?, updated_at=?
                    WHERE job_id=?
                    """,
                    (status, error_message, timestamp, job_id),
                )
                conn.execute(
                    """
                    INSERT INTO dead_letter_jobs(
                        dead_letter_id, original_job_id, queue_name, job_type,
                        payload_json, trace_id, failure_count, last_error, moved_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()), row["job_id"], row["queue_name"],
                        row["job_type"], row["payload_json"], row["trace_id"],
                        attempts, error_message, timestamp
                    ),
                )

            conn.execute(
                """
                UPDATE job_attempts
                SET status='failed', finished_at=?, error_message=?
                WHERE job_id=? AND worker_id=? AND status='running'
                """,
                (timestamp, error_message, job_id, worker_id),
            )
            return status

    def extend_lease(
        self,
        job_id: str,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> None:
        leased_until = (now_dt() + timedelta(seconds=lease_seconds)).isoformat()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET leased_until=?, updated_at=?
                WHERE job_id=? AND worker_id=? AND status='running'
                """,
                (leased_until, now(), job_id, worker_id),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("Lease extension failed.")

    def recover_expired_leases(self) -> int:
        timestamp = now()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET status='retry', worker_id=NULL, leased_until=NULL,
                    available_at=?, last_error='Worker lease expired',
                    updated_at=?
                WHERE status='running' AND leased_until < ?
                """,
                (timestamp, timestamp, timestamp),
            )
            return cursor.rowcount

    @staticmethod
    def _to_job(row) -> Job:
        return Job(
            job_id=row["job_id"],
            queue_name=row["queue_name"],
            job_type=row["job_type"],
            payload=json.loads(row["payload_json"]),
            status=row["status"],
            priority=row["priority"],
            attempt_count=row["attempt_count"],
            max_attempts=row["max_attempts"],
            available_at=row["available_at"],
            leased_until=row["leased_until"],
            worker_id=row["worker_id"],
            dedupe_key=row["dedupe_key"],
            parent_job_id=row["parent_job_id"],
            trace_id=row["trace_id"],
            last_error=row["last_error"],
        )


class WorkerRepository:
    def __init__(self, db: QueueDatabase) -> None:
        self.db = db

    def register(self, worker: WorkerRegistration) -> None:
        timestamp = now()
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO workers(
                    worker_id, worker_type, queue_name, status, hostname,
                    process_id, started_at, heartbeat_at, metadata_json
                )
                VALUES (?, ?, ?, 'online', ?, ?, ?, ?, ?)
                ON CONFLICT(worker_id) DO UPDATE SET
                    status='online',
                    heartbeat_at=excluded.heartbeat_at,
                    metadata_json=excluded.metadata_json
                """,
                (
                    worker.worker_id, worker.worker_type, worker.queue_name,
                    worker.hostname, worker.process_id, timestamp, timestamp,
                    json.dumps(worker.metadata or {}, sort_keys=True)
                ),
            )

    def heartbeat(self, worker_id: str) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE workers
                SET heartbeat_at=?, status='online'
                WHERE worker_id=?
                """,
                (now(), worker_id),
            )

    def mark_stale(self, stale_after_seconds: int = 120) -> int:
        cutoff = (now_dt() - timedelta(seconds=stale_after_seconds)).isoformat()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE workers
                SET status='stale'
                WHERE heartbeat_at < ? AND status='online'
                """,
                (cutoff,),
            )
            return cursor.rowcount
