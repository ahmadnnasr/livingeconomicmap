from __future__ import annotations
from typing import Callable, Dict
from .models import Job, JobResult, WorkerRegistration
from .repository import JobRepository, WorkerRepository


Handler = Callable[[Job], JobResult]


class Worker:
    def __init__(
        self,
        worker_id: str,
        worker_type: str,
        queue_name: str,
        jobs: JobRepository,
        workers: WorkerRepository,
        handlers: Dict[str, Handler],
        lease_seconds: int = 60,
    ) -> None:
        self.worker_id = worker_id
        self.worker_type = worker_type
        self.queue_name = queue_name
        self.jobs = jobs
        self.workers = workers
        self.handlers = handlers
        self.lease_seconds = lease_seconds

    def register(self) -> None:
        self.workers.register(
            WorkerRegistration(
                worker_id=self.worker_id,
                worker_type=self.worker_type,
                queue_name=self.queue_name,
            )
        )

    def run_once(self) -> bool:
        self.workers.heartbeat(self.worker_id)
        job = self.jobs.claim(
            self.queue_name,
            self.worker_id,
            lease_seconds=self.lease_seconds,
        )
        if job is None:
            return False

        handler = self.handlers.get(job.job_type)
        if handler is None:
            self.jobs.fail(
                job.job_id,
                self.worker_id,
                f"No handler registered for {job.job_type}",
                retryable=False,
            )
            return True

        try:
            result = handler(job)
            if result.status == "completed":
                self.jobs.complete(job.job_id, self.worker_id, result.output)
            else:
                self.jobs.fail(
                    job.job_id,
                    self.worker_id,
                    result.error_message or "Job failed.",
                    retryable=result.retryable,
                )
        except Exception as exc:
            self.jobs.fail(
                job.job_id,
                self.worker_id,
                str(exc),
                retryable=True,
            )
        return True
