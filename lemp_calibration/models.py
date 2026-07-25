from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BeliefObservation:
    as_of_date: str
    composite_liquidity: float
    real_yield_pressure: float
    long_rate_pressure: float
    financial_conditions_easing: float
    growth_valuation_support: float


@dataclass
class MarketObservation:
    as_of_date: str
    financial_conditions_index: Optional[float] = None
    high_yield_spread: Optional[float] = None
    investment_grade_spread: Optional[float] = None
    dollar_index: Optional[float] = None
    rate_volatility: Optional[float] = None
    growth_relative_return: Optional[float] = None
    equity_multiple_change: Optional[float] = None


@dataclass
class CalibrationTarget:
    key: str
    source_field: str
    expected_direction: int
    transform: str
    horizon_days: int
    weight: float
    description: str


@dataclass
class CalibrationPoint:
    as_of_date: str
    prediction: float
    realized: float
    target_key: str
    horizon_days: int


@dataclass
class MetricResult:
    target_key: str
    sample_size: int
    correlation: Optional[float]
    rank_correlation: Optional[float]
    directional_accuracy: Optional[float]
    mean_absolute_error: Optional[float]
    root_mean_squared_error: Optional[float]
    calibration_slope: Optional[float]
    stability_score: Optional[float]


@dataclass
class LagResult:
    target_key: str
    lag_days: int
    correlation: Optional[float]
    directional_accuracy: Optional[float]
    sample_size: int


@dataclass
class AttributionResult:
    target_key: str
    contributions: dict[str, float]
    dominant_driver: Optional[str]


@dataclass
class WalkForwardFold:
    fold_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    sample_size: int
    correlation: Optional[float]
    directional_accuracy: Optional[float]


@dataclass
class CalibrationReport:
    as_of_date: str
    metrics: list[MetricResult]
    lag_results: list[LagResult]
    attributions: list[AttributionResult]
    walk_forward_folds: list[WalkForwardFold]
    composite_score: float
    warnings: list[str]
    methodology_version: str = "market_calibration_v1"
