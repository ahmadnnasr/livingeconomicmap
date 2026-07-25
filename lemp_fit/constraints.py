from .models import WeightConstraint


DEFAULT_CONSTRAINTS = [
    WeightConstraint(
        feature_name="composite_liquidity",
        lower_bound=0.0,
        upper_bound=1.0,
        expected_sign=1,
    ),
    WeightConstraint(
        feature_name="financial_conditions_easing",
        lower_bound=0.0,
        upper_bound=1.0,
        expected_sign=1,
    ),
    WeightConstraint(
        feature_name="growth_valuation_support",
        lower_bound=0.0,
        upper_bound=1.0,
        expected_sign=1,
    ),
    WeightConstraint(
        feature_name="real_yield_pressure",
        lower_bound=-1.0,
        upper_bound=0.0,
        expected_sign=-1,
    ),
    WeightConstraint(
        feature_name="long_rate_pressure",
        lower_bound=-1.0,
        upper_bound=0.0,
        expected_sign=-1,
    ),
]

BASELINE_WEIGHTS = {
    "composite_liquidity": 0.30,
    "financial_conditions_easing": 0.30,
    "growth_valuation_support": 0.20,
    "real_yield_pressure": -0.15,
    "long_rate_pressure": -0.05,
}
