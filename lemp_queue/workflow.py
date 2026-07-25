from __future__ import annotations
from datetime import datetime, timezone
import json
import uuid

from .db import QueueDatabase
from .repository import JobRepository


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkflowOrchestrator:
    """
    Implements a durable fan-out pipeline:

    ingest -> validate -> features -> reasoning -> ranking -> report
    """

    STEPS = [
        ("ingest", "ingestion", "ingest.source"),
        ("validate", "validation", "validate.batch"),
        ("features", "features", "features.compute"),
        ("reasoning", "reasoning", "reasoning.update"),
        ("ranking", "ranking", "ranking.compute"),
        ("report", "reporting", "report.generate"),
    ]

    def __init__(self, db: QueueDatabase, jobs: JobRepository) -> None:
        self.db = db
        self.jobs = jobs

    def start(self, workflow_name: str, input_payload: dict) -> str:
        workflow_run_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        timestamp = now()

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO workflow_runs(
                    workflow_run_id, workflow_name, trace_id, status,
                    input_json, started_at
                )
                VALUES (?, ?, ?, 'running', ?, ?)
                """,
                (
                    workflow_run_id, workflow_name, trace_id,
                    json.dumps(input_payload, sort_keys=True), timestamp
                ),
            )

        first_step, queue_name, job_type = self.STEPS[0]
        job_id = self.jobs.enqueue(
            queue_name,
            job_type,
            {
                **input_payload,
                "workflow_run_id": workflow_run_id,
                "workflow_step": first_step,
            },
            trace_id=trace_id,
            dedupe_key=f"{workflow_run_id}:{first_step}",
        )
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO workflow_steps(
                    workflow_step_id, workflow_run_id, step_name,
                    job_id, status
                )
                VALUES (?, ?, ?, ?, 'queued')
                """,
                (str(uuid.uuid4()), workflow_run_id, first_step, job_id),
            )
        return workflow_run_id

    def advance(
        self,
        workflow_run_id: str,
        completed_step: str,
        output: dict,
    ) -> str:
        with self.db.transaction() as conn:
            run = conn.execute(
                """
                SELECT * FROM workflow_runs
                WHERE workflow_run_id=?
                """,
                (workflow_run_id,),
            ).fetchone()
            if run is None:
                raise KeyError(workflow_run_id)

            conn.execute(
                """
                UPDATE workflow_steps
                SET status='completed', completed_at=?, output_json=?
                WHERE workflow_run_id=? AND step_name=?
                """,
                (
                    now(), json.dumps(output, sort_keys=True),
                    workflow_run_id, completed_step
                ),
            )

            index = [step[0] for step in self.STEPS].index(completed_step)
            if index == len(self.STEPS) - 1:
                conn.execute(
                    """
                    UPDATE workflow_runs
                    SET status='completed', completed_at=?
                    WHERE workflow_run_id=?
                    """,
                    (now(), workflow_run_id),
                )
                return "completed"

            next_step, queue_name, job_type = self.STEPS[index + 1]
            payload = {
                **json.loads(run["input_json"]),
                **output,
                "workflow_run_id": workflow_run_id,
                "workflow_step": next_step,
            }

        job_id = self.jobs.enqueue(
            queue_name,
            job_type,
            payload,
            trace_id=run["trace_id"],
            dedupe_key=f"{workflow_run_id}:{next_step}",
        )

        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO workflow_steps(
                    workflow_step_id, workflow_run_id, step_name,
                    job_id, status
                )
                VALUES (?, ?, ?, ?, 'queued')
                """,
                (str(uuid.uuid4()), workflow_run_id, next_step, job_id),
            )
        return next_step
