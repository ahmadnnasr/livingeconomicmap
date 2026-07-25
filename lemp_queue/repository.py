from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from app.db import connection


@dataclass
class Job:
    id: str
    job_type: str
    status: str
    payload: dict[str, Any]
    worker: Optional[str]
    error: Optional[str]


class JobRepository:
    """Repository for interacting with the persistent PostgreSQL job queue."""

    def enqueue_job(
        self,
        queue: str,
        job_type: str,
        payload: dict[str, Any] | None = None,
    ) -> str:
        payload = payload or {}

        with connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO jobs (
                    queue,
                    job_type,
                    payload
                )
                VALUES (%s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    queue,
                    job_type,
                    json.dumps(payload),
                ),
            )

            job_id = cur.fetchone()[0]
            conn.commit()

        return str(job_id)

    def list_queued(
        self,
        queue: str | None = None,
    ) -> list[Job]:
        with connection() as conn:
            cur = conn.cursor()

            if queue is None:
                cur.execute(
                    """
                    SELECT
                        id,
                        job_type,
                        status,
                        payload,
                        worker,
                        error
                    FROM jobs
                    WHERE status = 'QUEUED'
                    ORDER BY created_at
                    """
                )
            else:
                cur.execute(
                    """
                    SELECT
                        id,
                        job_type,
                        status,
                        payload,
                        worker,
                        error
                    FROM jobs
                    WHERE status = 'QUEUED'
                      AND queue = %s
                    ORDER BY created_at
                    """,
                    (queue,),
                )

            rows = cur.fetchall()

        return [self._to_job(row) for row in rows]

    def claim_next_job(
        self,
        queue: str,
        worker: str,
    ) -> Job | None:
        """
        Atomically claim the oldest queued job.

        SKIP LOCKED prevents multiple workers from claiming the same job.
        """
        with connection() as conn:
            cur = conn.cursor()

            cur.execute(
                """
                WITH next_job AS (
                    SELECT id
                    FROM jobs
                    WHERE status = 'QUEUED'
                      AND queue = %s
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE jobs
                SET
                    status = 'RUNNING',
                    worker = %s,
                    started_at = NOW(),
                    finished_at = NULL,
                    error = NULL
                WHERE id = (
                    SELECT id
                    FROM next_job
                )
                RETURNING
                    id,
                    job_type,
                    status,
                    payload,
                    worker,
                    error
                """,
                (
                    queue,
                    worker,
                ),
            )

            row = cur.fetchone()
            conn.commit()

        if row is None:
            return None

        return self._to_job(row)

    def mark_completed(
        self,
        job_id: str,
    ) -> None:
        with connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE jobs
                SET
                    status = 'COMPLETED',
                    finished_at = NOW(),
                    error = NULL
                WHERE id = %s
                  AND status = 'RUNNING'
                """,
                (job_id,),
            )
            conn.commit()

    def mark_failed(
        self,
        job_id: str,
        error: str,
    ) -> None:
        with connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE jobs
                SET
                    status = 'FAILED',
                    finished_at = NOW(),
                    error = %s
                WHERE id = %s
                  AND status = 'RUNNING'
                """,
                (
                    error[:5000],
                    job_id,
                ),
            )
            conn.commit()

    @staticmethod
    def _to_job(row: tuple[Any, ...]) -> Job:
        payload = row[3]

        if isinstance(payload, str):
            payload = json.loads(payload)

        return Job(
            id=str(row[0]),
            job_type=row[1],
            status=row[2],
            payload=payload or {},
            worker=row[4],
            error=row[5],
        )
