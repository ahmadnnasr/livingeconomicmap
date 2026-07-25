from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import json
import math
import uuid

from .db import PostgresDatabase
from . import sql


@dataclass
class ClaimedJob:
    job_id: str
    queue_name: str
    job_type: str
    payload: dict
    attempt_count: int
    max_attempts: int
    trace_id: str
    parent_job_id: Optional[str]


class PostgresJobRepository:
    def __init__(self, db: PostgresDatabase) -> None:
        self.db = db

    def enqueue(
        self,
        queue_name: str,
        job_type: str,
        payload: dict,
        *,
        priority: int = 100,
        max_attempts: int = 5,
        dedupe_key: Optional[str] = None,
        trace_id: Optional[str] = None,
        parent_job_id: Optional[str] = None,
    ) -> str:
        trace_id = trace_id or str(uuid.uuid4())
        query = """
            INSERT INTO jobs(
                queue_name, job_type, payload_json, status, priority,
                max_attempts, dedupe_key, trace_id, parent_job_id
            )
            VALUES (
                %(queue_name)s, %(job_type)s, %(payload_json)s::jsonb,
                'pending', %(priority)s, %(max_attempts)s,
                %(dedupe_key)s, %(trace_id)s::uuid, %(parent_job_id)s::uuid
            )
            ON CONFLICT (queue_name, dedupe_key)
            WHERE dedupe_key IS NOT NULL
            DO UPDATE SET dedupe_key=EXCLUDED.dedupe_key
            RETURNING job_id;
        """
        with self.db.transaction() as conn:
            row = conn.execute(
                query,
                {
                    "queue_name": queue_name,
                    "job_type": job_type,
                    "payload_json": json.dumps(payload, sort_keys=True),
                    "priority": priority,
                    "max_attempts": max_attempts,
                    "dedupe_key": dedupe_key,
                    "trace_id": trace_id,
                    "parent_job_id": parent_job_id,
                },
            ).fetchone()
            return str(row[0])

    def claim(
        self,
        queue_name: str,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> Optional[ClaimedJob]:
        with self.db.transaction() as conn:
            row = conn.execute(
                sql.CLAIM_JOB_SQL,
                {
                    "queue_name": queue_name,
                    "worker_id": worker_id,
                    "lease_seconds": lease_seconds,
                },
            ).fetchone()
            if row is None:
                return None

            conn.execute(
                sql.INSERT_ATTEMPT_SQL,
                {"job_id": row["job_id"], "worker_id": worker_id},
            )
            return ClaimedJob(
                job_id=str(row["job_id"]),
                queue_name=row["queue_name"],
                job_type=row["job_type"],
                payload=row["payload_json"],
                attempt_count=row["attempt_count"],
                max_attempts=row["max_attempts"],
                trace_id=str(row["trace_id"]),
                parent_job_id=(
                    str(row["parent_job_id"]) if row["parent_job_id"] else None
                ),
            )

    def complete(
        self,
        job_id: str,
        worker_id: str,
        output: dict,
    ) -> None:
        with self.db.transaction() as conn:
            row = conn.execute(
                sql.COMPLETE_JOB_SQL,
                {"job_id": job_id, "worker_id": worker_id},
            ).fetchone()
            if row is None:
                raise RuntimeError("Job completion rejected; lease ownership changed.")
            conn.execute(
                sql.COMPLETE_ATTEMPT_SQL,
                {
                    "job_id": job_id,
                    "worker_id": worker_id,
                    "output_json": json.dumps(output, sort_keys=True),
                },
            )

    def fail(
        self,
        job: ClaimedJob,
        worker_id: str,
        error_message: str,
        retryable: bool,
        base_delay_seconds: int = 30,
        maximum_delay_seconds: int = 3600,
    ) -> str:
        with self.db.transaction() as conn:
            if retryable and job.attempt_count < job.max_attempts:
                delay = min(
                    maximum_delay_seconds,
                    base_delay_seconds * (2 ** max(0, job.attempt_count - 1)),
                )
                conn.execute(
                    sql.RETRY_JOB_SQL,
                    {
                        "job_id": job.job_id,
                        "delay_seconds": delay,
                        "error_message": error_message,
                    },
                )
                status = "retry"
            else:
                conn.execute(
                    sql.DEAD_LETTER_JOB_SQL,
                    {
                        "job_id": job.job_id,
                        "error_message": error_message,
                    },
                )
                status = "dead_letter"

            conn.execute(
                """
                UPDATE job_attempts
                SET status='failed',
                    finished_at=NOW(),
                    error_message=%(error_message)s
                WHERE job_id=%(job_id)s::uuid
                  AND worker_id=%(worker_id)s
                  AND status='running'
                """,
                {
                    "job_id": job.job_id,
                    "worker_id": worker_id,
                    "error_message": error_message,
                },
            )
            return status

    def extend_lease(
        self,
        job_id: str,
        worker_id: str,
        lease_seconds: int,
    ) -> None:
        with self.db.transaction() as conn:
            row = conn.execute(
                """
                UPDATE jobs
                SET leased_until=NOW() + (%(seconds)s || ' seconds')::interval
                WHERE job_id=%(job_id)s::uuid
                  AND worker_id=%(worker_id)s
                  AND status='running'
                RETURNING job_id
                """,
                {
                    "seconds": lease_seconds,
                    "job_id": job_id,
                    "worker_id": worker_id,
                },
            ).fetchone()
            if row is None:
                raise RuntimeError("Cannot extend lease not owned by worker.")

    def recover_expired_leases(self) -> int:
        with self.db.transaction() as conn:
            rows = conn.execute(sql.RECOVER_EXPIRED_LEASES_SQL).fetchall()
            return len(rows)
