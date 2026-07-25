from __future__ import annotations
from dataclasses import dataclass
from .models import CalibrationReport


@dataclass
class DiagnosticSummary:
    strongest_target: str | None
    weakest_target: str | None
    unstable_targets: list[str]
    insufficient_targets: list[str]
    recommendation: str


class CalibrationDiagnostics:
    def summarize(self, report: CalibrationReport) -> DiagnosticSummary:
        scored = [
            item for item in report.metrics
            if item.correlation is not None
        ]
        strongest = (
            max(scored, key=lambda item: item.correlation).target_key
            if scored else None
        )
        weakest = (
            min(scored, key=lambda item: item.correlation).target_key
            if scored else None
        )
        unstable = [
            item.target_key
            for item in report.metrics
            if item.stability_score is not None and item.stability_score < 0.60
        ]
        insufficient = [
            item.target_key
            for item in report.metrics
            if item.sample_size < 20
        ]

        if report.composite_score >= 0.70:
            recommendation = "Proceed with cautious production weighting."
        elif report.composite_score >= 0.55:
            recommendation = "Retain the model but continue calibration before production use."
        else:
            recommendation = "Do not rely on market transmission weights without redesign."

        return DiagnosticSummary(
            strongest_target=strongest,
            weakest_target=weakest,
            unstable_targets=unstable,
            insufficient_targets=insufficient,
            recommendation=recommendation,
        )
