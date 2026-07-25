from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, Optional
import socket
import os

from .db import PostgresDatabase
from .repository import PostgresJobRepository, ClaimedJob


@dataclass
class HandlerResult:
    completed: bool
    output: dict
    retryable: bool = False
    error_message: Optional[str] = None


Handler = Callable[[ClaimedJob], HandlerResult]


class PostgresWorker:
    def __init__(
        self,
        db: PostgresDatabase,
        jobs: PostgresJobRepository,
        worker_id: str,
        worker_type: str,
        queue_name: str,
        handlers: Dict[str, Handler],
        lease_seconds: int = 120,
    ) -> None:
        self.db = db
        self.jobs = jobs
        self.worker_id = worker_id
        self.worker_type = worker_type
        self.queue_name = queue_name
        self.handlers = handlers
        self.lease_seconds = lease_seconds

    def register(self) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO workers(
                    worker_id, worker_type, queue_name, status,
                    hostname, process_id, metadata_json
                )
                VALUES (%s, %s, %s, 'online', %s, %s, '{}'::jsonb)
                ON CONFLICT(worker_id) DO UPDATE SET
                    worker_type=EXCLUDED.worker_type,
                    queue_name=EXCLUDED.queue_name,
                    status='online',
                    hostname=EXCLUDED.hostname,
                    process_id=EXCLUDED.process_id,
                    heartbeat_at=NOW()
                """,
                (
                    self.worker_id,
                    self.worker_type,
                    self.queue_name,
                    socket.gethostname(),
                    os.getpid(),
                ),
            )

    def heartbeat(self) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE workers
                SET heartbeat_at=NOW(), status='online'
                WHERE worker_id=%s
                """,
                (self.worker_id,),
            )

    def run_once(self) -> bool:
        self.heartbeat()
        job = self.jobs.claim(
            self.queue_name,
            self.worker_id,
            self.lease_seconds,
        )
        if job is None:
            return False

        handler = self.handlers.get(job.job_type)
        if handler is None:
            self.jobs.fail(
                job,
                self.worker_id,
                f"No handler registered for {job.job_type}",
                retryable=False,
            )
            return True

        try:
            result = handler(job)
            if result.completed:
                self.jobs.complete(job.job_id, self.worker_id, result.output)
            else:
                self.jobs.fail(
                    job,
                    self.worker_id,
                    result.error_message or "Job failed.",
                    retryable=result.retryable,
                )
        except Exception as exc:
            self.jobs.fail(
                job,
                self.worker_id,
                str(exc),
                retryable=True,
            )
        return True
