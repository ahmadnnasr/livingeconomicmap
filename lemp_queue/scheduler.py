from __future__ import annotations
from datetime import datetime, timezone, timedelta
import json
import uuid

from .db import QueueDatabase
from .repository import JobRepository, now


class SchedulerRepository:
    def __init__(self, db: QueueDatabase) -> None:
        self.db = db

    def add_interval_schedule(
        self,
        name: str,
        queue_name: str,
        job_type: str,
        payload: dict,
        interval_minutes: int,
        timezone_name: str = "UTC",
        dedupe_template: str | None = None,
    ) -> str:
        schedule_id = str(uuid.uuid4())
        current = datetime.now(timezone.utc)
        next_run = current + timedelta(minutes=interval_minutes)
        expression = f"interval:{interval_minutes}"
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO schedules(
                    schedule_id, name, queue_name, job_type, payload_json,
                    cron_expression, timezone, is_enabled, dedupe_template,
                    next_run_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """,
                (
                    schedule_id, name, queue_name, job_type,
                    json.dumps(payload, sort_keys=True), expression,
                    timezone_name, dedupe_template, next_run.isoformat(),
                    current.isoformat(), current.isoformat()
                ),
            )
        return schedule_id

    def due(self):
        with self.db.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM schedules
                WHERE is_enabled=1 AND next_run_at <= ?
                ORDER BY next_run_at
                """,
                (now(),),
            ).fetchall()

    def advance(self, schedule_id: str, interval_minutes: int) -> None:
        current = datetime.now(timezone.utc)
        next_run = current + timedelta(minutes=interval_minutes)
        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE schedules
                SET last_enqueued_at=?, next_run_at=?, updated_at=?
                WHERE schedule_id=?
                """,
                (
                    current.isoformat(),
                    next_run.isoformat(),
                    current.isoformat(),
                    schedule_id
                ),
            )


class Scheduler:
    def __init__(
        self,
        schedules: SchedulerRepository,
        jobs: JobRepository,
    ) -> None:
        self.schedules = schedules
        self.jobs = jobs

    def tick(self) -> int:
        count = 0
        for row in self.schedules.due():
            expression = row["cron_expression"]
            if not expression.startswith("interval:"):
                continue
            interval_minutes = int(expression.split(":", 1)[1])
            payload = json.loads(row["payload_json"])
            dedupe_key = None
            if row["dedupe_template"]:
                dedupe_key = row["dedupe_template"].format(
                    scheduled_at=row["next_run_at"]
                )
            self.jobs.enqueue(
                row["queue_name"],
                row["job_type"],
                payload,
                dedupe_key=dedupe_key,
            )
            self.schedules.advance(row["schedule_id"], interval_minutes)
            count += 1
        return count
