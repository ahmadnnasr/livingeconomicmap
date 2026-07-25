from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TrainingRow:
    as_of_date: str
    features: dict[str, float]
    target: float
    target_key: str


@dataclass
class WeightConstraint:
    feature_name: str
    lower_bound: float
    upper_bound: float
    expected_sign: int


@dataclass
class FitConfig:
    ridge_lambda: float = 1.0
    learning_rate: float = 0.05
    max_iterations: int = 5000
    tolerance: float = 1e-8
    intercept: bool = True


@dataclass
class FittedModel:
    target_key: str
    coefficients: dict[str, float]
    intercept: float
    ridge_lambda: float
    training_rows: int
    converged: bool
    iterations: int
    objective_value: float


@dataclass
class FoldResult:
    fold_id: int
    train_size: int
    test_size: int
    mean_squared_error: float
    directional_accuracy: float
    coefficients: dict[str, float]


@dataclass
class StabilityResult:
    feature_name: str
    mean_weight: float
    standard_deviation: float
    sign_consistency: float
    range_width: float


@dataclass
class BaselineComparison:
    model_mse: float
    baseline_mse: float
    improvement_ratio: float
    model_directional_accuracy: float
    baseline_directional_accuracy: float


@dataclass
class PromotionDecision:
    approved: bool
    reasons: list[str]
    warnings: list[str]
    recommended_coefficients: dict[str, float]
    model_version: str


@dataclass
class FittingReport:
    model: FittedModel
    folds: list[FoldResult]
    stability: list[StabilityResult]
    baseline: BaselineComparison
    promotion: PromotionDecision
    methodology_version: str = "constrained_fit_v1"
