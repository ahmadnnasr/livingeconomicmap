from __future__ import annotations
from .orchestrator import DailyOperatingSystem


class DailyRunHandler:
    def __init__(self, operating_system: DailyOperatingSystem) -> None:
        self.operating_system = operating_system

    def __call__(self, job) -> dict:
        run = self.operating_system.run(job.payload["as_of_date"])
        return {
            "run_id": run.run_id,
            "status": run.status,
            "warning_count": len(run.warnings),
            "trace_id": run.trace_id,
        }
