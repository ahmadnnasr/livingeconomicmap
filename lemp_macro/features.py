from __future__ import annotations
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Sequence

from .models import FeatureValue


class FeatureCalculator:
    methodology_version = "macro_features_v1"

    @staticmethod
    def change(values: Sequence[float], periods: int = 1) -> float:
        if len(values) <= periods:
            raise ValueError("Insufficient observations.")
        return values[-1] - values[-1 - periods]

    @staticmethod
    def percent_change(values: Sequence[float], periods: int = 1) -> float:
        if len(values) <= periods:
            raise ValueError("Insufficient observations.")
        prior = values[-1 - periods]
        if prior == 0:
            raise ZeroDivisionError("Prior value is zero.")
        return values[-1] / prior - 1.0

    @staticmethod
    def z_score(values: Sequence[float], window: int) -> float:
        if len(values) < window:
            raise ValueError("Insufficient observations.")
        sample = list(values[-window:])
        sigma = pstdev(sample)
        if sigma == 0:
            return 0.0
        return (sample[-1] - mean(sample)) / sigma

    @staticmethod
    def percentile_rank(values: Sequence[float], window: int) -> float:
        if len(values) < window:
            raise ValueError("Insufficient observations.")
        sample = list(values[-window:])
        current = sample[-1]
        less_or_equal = sum(item <= current for item in sample)
        return less_or_equal / len(sample)

    @staticmethod
    def acceleration(values: Sequence[float]) -> float:
        if len(values) < 3:
            raise ValueError("Insufficient observations.")
        recent_change = values[-1] - values[-2]
        prior_change = values[-2] - values[-3]
        return recent_change - prior_change
