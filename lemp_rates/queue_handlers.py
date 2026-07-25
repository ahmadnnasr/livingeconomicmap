from __future__ import annotations
from dataclasses import asdict
from .engine import RatesLiquidityEngine
from .models import SeriesSignal


class RatesLiquidityReasoningHandler:
    def __init__(
        self,
        load_signals,
        persist_snapshot,
        publish_event,
        load_priors=None,
    ) -> None:
        self.load_signals = load_signals
        self.persist_snapshot = persist_snapshot
        self.publish_event = publish_event
        self.load_priors = load_priors or (lambda as_of_date: {})

    def __call__(self, job) -> dict:
        as_of_date = job.payload["as_of_date"]
        raw_signals = self.load_signals(as_of_date)
        signals = [
            item if isinstance(item, SeriesSignal) else SeriesSignal(**item)
            for item in raw_signals
        ]
        priors = self.load_priors(as_of_date)
        snapshot = RatesLiquidityEngine().run(
            signals,
            as_of_date,
            priors=priors,
        )
        snapshot_id = self.persist_snapshot(snapshot)
        self.publish_event(
            "rates_liquidity.snapshot.created",
            {
                "snapshot_id": snapshot_id,
                "as_of_date": as_of_date,
                "coverage_ratio": snapshot.coverage_ratio,
                "trace_id": job.trace_id,
            },
        )
        return {
            "snapshot_id": snapshot_id,
            "coverage_ratio": snapshot.coverage_ratio,
            "top_regime": snapshot.regimes[0].regime_key,
        }
