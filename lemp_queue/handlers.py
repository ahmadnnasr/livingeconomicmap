from __future__ import annotations
from .models import Job, JobResult


def pass_through_handler(stage: str):
    def handler(job: Job) -> JobResult:
        return JobResult(
            status="completed",
            output={
                "last_completed_stage": stage,
                "trace_id": job.trace_id,
            },
        )
    return handler


def transient_failure_handler(job: Job) -> JobResult:
    return JobResult(
        status="failed",
        output={},
        retryable=True,
        error_message="Simulated transient provider failure.",
    )


def permanent_failure_handler(job: Job) -> JobResult:
    return JobResult(
        status="failed",
        output={},
        retryable=False,
        error_message="Simulated invalid payload.",
    )
