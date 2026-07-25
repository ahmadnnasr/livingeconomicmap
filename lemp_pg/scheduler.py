from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import json

from .db import PostgresDatabase
from .repository import PostgresJobRepository
from . import sql


@dataclass
class DueSchedule:
    schedule_id: str
    queue_name: str
    job_type: str
    payload: dict
    cron_expression: str
    dedupe_template: str | None
    next_run_at: str


class PostgresScheduler:
    """
    Reference scheduler supporting interval:N expressions.

    PostgreSQL advisory locks or SKIP LOCKED allow multiple scheduler instances
    without duplicate execution.
    """

    def __init__(
        self,
        db: PostgresDatabase,
        jobs: PostgresJobRepository,
    ) -> None:
        self.db = db
        self.jobs = jobs

    def tick(self, limit: int = 100) -> int:
        with self.db.transaction() as conn:
            rows = conn.execute(
                sql.CLAIM_DUE_SCHEDULE_SQL,
                {"limit": limit},
            ).fetchall()

            schedules = [
                DueSchedule(
                    schedule_id=str(row["schedule_id"]),
                    queue_name=row["queue_name"],
                    job_type=row["job_type"],
                    payload=row["payload_json"],
                    cron_expression=row["cron_expression"],
                    dedupe_template=row["dedupe_template"],
                    next_run_at=row["next_run_at"].isoformat(),
                )
                for row in rows
            ]

            for item in schedules:
                interval_minutes = self._interval_minutes(item.cron_expression)
                dedupe = (
                    item.dedupe_template.format(
                        scheduled_at=item.next_run_at
                    )
                    if item.dedupe_template
                    else f"{item.schedule_id}:{item.next_run_at}"
                )
                self.jobs.enqueue(
                    item.queue_name,
                    item.job_type,
                    item.payload,
                    dedupe_key=dedupe,
                )
                conn.execute(
                    """
                    UPDATE schedules
                    SET last_enqueued_at=next_run_at,
                        next_run_at=next_run_at + (%s || ' minutes')::interval
                    WHERE schedule_id=%s::uuid
                    """,
                    (interval_minutes, item.schedule_id),
                )
            return len(schedules)

    @staticmethod
    def _interval_minutes(expression: str) -> int:
        if not expression.startswith("interval:"):
            raise ValueError("Only interval:N expressions are supported.")
        value = int(expression.split(":", 1)[1])
        if value <= 0:
            raise ValueError("Interval must be positive.")
        return value
