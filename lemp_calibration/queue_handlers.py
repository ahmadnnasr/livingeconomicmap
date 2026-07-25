from __future__ import annotations
from dataclasses import asdict

from .engine import MarketCalibrationEngine
from .models import BeliefObservation, MarketObservation


class MarketCalibrationHandler:
    def __init__(
        self,
        load_beliefs,
        load_markets,
        persist_report,
        publish_event,
    ) -> None:
        self.load_beliefs = load_beliefs
        self.load_markets = load_markets
        self.persist_report = persist_report
        self.publish_event = publish_event

    def __call__(self, job) -> dict:
        as_of_date = job.payload["as_of_date"]
        beliefs = [
            item if isinstance(item, BeliefObservation)
            else BeliefObservation(**item)
            for item in self.load_beliefs(as_of_date)
        ]
        markets = [
            item if isinstance(item, MarketObservation)
            else MarketObservation(**item)
            for item in self.load_markets(as_of_date)
        ]
        report = MarketCalibrationEngine().evaluate(
            beliefs,
            markets,
            as_of_date,
        )
        report_id = self.persist_report(report)
        self.publish_event(
            "market_calibration.report.created",
            {
                "report_id": report_id,
                "as_of_date": as_of_date,
                "composite_score": report.composite_score,
                "trace_id": job.trace_id,
            },
        )
        return {
            "report_id": report_id,
            "composite_score": report.composite_score,
            "warning_count": len(report.warnings),
        }
