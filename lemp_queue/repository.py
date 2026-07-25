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
    """
    Repository for interacting with the persistent jobs queue.
    """

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

    def list_queued(self) -> list[Job]:

        with connection() as conn:
            cur = conn.cursor()

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
                WHERE status='QUEUED'
                ORDER BY created_at
                """
            )

            rows = cur.fetchall()

        jobs = []

        for row in rows:

            jobs.append(
                Job(
                    id=str(row[0]),
                    job_type=row[1],
                    status=row[2],
                    payload=row[3] or {},
                    worker=row[4],
                    error=row[5],
                )
            )

        return jobs
