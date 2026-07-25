from __future__ import annotations
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Callable
import uuid

from .models import DailyRun, StageResult


class DailyOperatingSystem:
    STAGES = [
        "release_calendar_refresh",
        "macro_ingestion",
        "data_validation",
        "feature_calculation",
        "rates_liquidity_reasoning",
        "market_calibration",
        "company_ranking",
        "model_governance",
        "daily_brief",
        "health_checks",
    ]

    def __init__(
        self,
        handlers: dict[str, Callable[[dict], dict]],
        persist_run: Callable[[DailyRun], None],
        persist_stage: Callable[[str, StageResult], None],
        publish_event: Callable[[str, dict], None],
    ) -> None:
        self.handlers = handlers
        self.persist_run = persist_run
        self.persist_stage = persist_stage
        self.publish_event = publish_event

    def run(self, as_of_date: str) -> DailyRun:
        run_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()
        run = DailyRun(
            run_id=run_id,
            as_of_date=as_of_date,
            status="running",
            started_at=started_at,
            completed_at=None,
            stages=[],
            trace_id=trace_id,
        )
        self.persist_run(run)
        context = {
            "run_id": run_id,
            "trace_id": trace_id,
            "as_of_date": as_of_date,
        }

        try:
            for stage in self.STAGES:
                stage_started = datetime.now(timezone.utc).isoformat()
                handler = self.handlers.get(stage)
                if handler is None:
                    result = StageResult(
                        stage_key=stage,
                        status="skipped",
                        started_at=stage_started,
                        completed_at=datetime.now(timezone.utc).isoformat(),
                        output={},
                        warnings=["No handler registered."],
                    )
                else:
                    try:
                        output = handler(dict(context))
                        result = StageResult(
                            stage_key=stage,
                            status="completed",
                            started_at=stage_started,
                            completed_at=datetime.now(timezone.utc).isoformat(),
                            output=output or {},
                            warnings=list((output or {}).get("warnings", [])),
                        )
                        context.update(output or {})
                    except Exception as exc:
                        result = StageResult(
                            stage_key=stage,
                            status="failed",
                            started_at=stage_started,
                            completed_at=datetime.now(timezone.utc).isoformat(),
                            output={},
                            error=str(exc),
                        )
                        self.persist_stage(run_id, result)
                        run.status = "failed"
                        run.completed_at = datetime.now(timezone.utc).isoformat()
                        run.warnings.append(f"{stage} failed: {exc}")
                        self.persist_run(run)
                        self.publish_event(
                            "daily_run.failed",
                            {
                                "run_id": run_id,
                                "stage": stage,
                                "error": str(exc),
                                "trace_id": trace_id,
                            },
                        )
                        return run

                self.persist_stage(run_id, result)
                run.stages.append(stage)
                run.warnings.extend(result.warnings)

            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc).isoformat()
            self.persist_run(run)
            self.publish_event(
                "daily_run.completed",
                {
                    "run_id": run_id,
                    "as_of_date": as_of_date,
                    "trace_id": trace_id,
                    "warning_count": len(run.warnings),
                },
            )
            return run
        except Exception as exc:
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc).isoformat()
            run.warnings.append(str(exc))
            self.persist_run(run)
            raise
