from __future__ import annotations
from .engine import ConstrainedFittingEngine
from .models import TrainingRow, FitConfig


class ConstrainedFitHandler:
    def __init__(
        self,
        load_training_rows,
        persist_report,
        persist_candidate_weights,
        publish_event,
    ) -> None:
        self.load_training_rows = load_training_rows
        self.persist_report = persist_report
        self.persist_candidate_weights = persist_candidate_weights
        self.publish_event = publish_event

    def __call__(self, job) -> dict:
        target_key = job.payload["target_key"]
        rows = [
            item if isinstance(item, TrainingRow) else TrainingRow(**item)
            for item in self.load_training_rows(target_key)
        ]
        config = FitConfig(**job.payload.get("fit_config", {}))
        report = ConstrainedFittingEngine().run(
            rows,
            target_key,
            config=config,
            model_version=job.payload.get(
                "model_version",
                "rates_market_fit_v1",
            ),
        )
        report_id = self.persist_report(report)
        candidate_id = self.persist_candidate_weights(
            report.model.coefficients,
            report.promotion,
        )
        self.publish_event(
            "constrained_fit.completed",
            {
                "report_id": report_id,
                "candidate_id": candidate_id,
                "approved": report.promotion.approved,
                "trace_id": job.trace_id,
            },
        )
        return {
            "report_id": report_id,
            "candidate_id": candidate_id,
            "approved": report.promotion.approved,
            "improvement_ratio": report.baseline.improvement_ratio,
        }
