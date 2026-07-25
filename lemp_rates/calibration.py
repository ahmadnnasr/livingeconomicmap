from __future__ import annotations
from dataclasses import dataclass
from statistics import mean
from typing import Iterable

from .models import RatesLiquiditySnapshot


@dataclass
class CalibrationPoint:
    as_of_date: str
    predicted_probability: float
    realized_outcome: int


@dataclass
class CalibrationReport:
    brier_score: float
    mean_prediction: float
    realized_rate: float
    sample_size: int


class ProbabilityCalibrator:
    @staticmethod
    def evaluate(points: Iterable[CalibrationPoint]) -> CalibrationReport:
        points = list(points)
        if not points:
            raise ValueError("At least one calibration point is required.")
        brier = mean(
            (point.predicted_probability - point.realized_outcome) ** 2
            for point in points
        )
        return CalibrationReport(
            brier_score=brier,
            mean_prediction=mean(point.predicted_probability for point in points),
            realized_rate=mean(point.realized_outcome for point in points),
            sample_size=len(points),
        )
