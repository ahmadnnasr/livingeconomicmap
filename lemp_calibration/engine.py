from __future__ import annotations
from dataclasses import asdict
from datetime import date, timedelta
from typing import Iterable
import math

from .models import (
    BeliefObservation, MarketObservation, CalibrationPoint,
    MetricResult, LagResult, AttributionResult,
    WalkForwardFold, CalibrationReport,
)
from .targets import MARKET_TARGETS
from .math_utils import (
    pearson, spearman, mae, rmse, directional_accuracy, slope, mean
)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class MarketCalibrationEngine:
    """
    Calibrates the rates-and-liquidity beliefs against faster-moving market outcomes.
    """

    def build_prediction(self, belief: BeliefObservation) -> float:
        liquidity = belief.composite_liquidity - 0.5
        easing = belief.financial_conditions_easing - 0.5
        growth = belief.growth_valuation_support - 0.5
        real_drag = belief.real_yield_pressure - 0.5
        long_drag = belief.long_rate_pressure - 0.5
        return (
            liquidity * 0.30
            + easing * 0.30
            + growth * 0.20
            - real_drag * 0.15
            - long_drag * 0.05
        ) * 2.0

    def build_points(
        self,
        beliefs: list[BeliefObservation],
        markets: list[MarketObservation],
    ) -> list[CalibrationPoint]:
        belief_lookup = {item.as_of_date: item for item in beliefs}
        market_lookup = {item.as_of_date: item for item in markets}
        dates = sorted(set(belief_lookup) & set(market_lookup))
        points = []

        for target in MARKET_TARGETS:
            for current_date in dates:
                future_date = (
                    date.fromisoformat(current_date)
                    + timedelta(days=target.horizon_days)
                ).isoformat()
                if future_date not in market_lookup:
                    continue

                current_market = market_lookup[current_date]
                future_market = market_lookup[future_date]
                current_value = getattr(current_market, target.source_field)
                future_value = getattr(future_market, target.source_field)
                if current_value is None or future_value is None:
                    continue

                if target.transform == "change":
                    realized = future_value - current_value
                elif target.transform == "forward_return":
                    realized = future_value
                else:
                    raise ValueError(target.transform)

                realized *= target.expected_direction
                prediction = self.build_prediction(belief_lookup[current_date])

                points.append(
                    CalibrationPoint(
                        as_of_date=current_date,
                        prediction=prediction,
                        realized=realized,
                        target_key=target.key,
                        horizon_days=target.horizon_days,
                    )
                )
        return points

    def evaluate(
        self,
        beliefs: list[BeliefObservation],
        markets: list[MarketObservation],
        as_of_date: str,
    ) -> CalibrationReport:
        points = self.build_points(beliefs, markets)
        warnings = []
        metrics = []
        lag_results = []
        attributions = []

        for target in MARKET_TARGETS:
            subset = [p for p in points if p.target_key == target.key]
            predicted = [p.prediction for p in subset]
            realized = [p.realized for p in subset]

            corr = pearson(predicted, realized)
            rank_corr = spearman(predicted, realized)
            direction = directional_accuracy(predicted, realized)
            metric = MetricResult(
                target_key=target.key,
                sample_size=len(subset),
                correlation=corr,
                rank_correlation=rank_corr,
                directional_accuracy=direction,
                mean_absolute_error=mae(predicted, realized),
                root_mean_squared_error=rmse(predicted, realized),
                calibration_slope=slope(predicted, realized),
                stability_score=self._stability(predicted, realized),
            )
            metrics.append(metric)

            if len(subset) < 20:
                warnings.append(
                    f"{target.key} has only {len(subset)} observations."
                )

            lag_results.extend(
                self._lag_test(target.key, beliefs, markets, [5, 10, 20, 40, 60])
            )
            attributions.append(self._attribution(target.key, beliefs, markets))

        folds = self._walk_forward(points)
        composite = self._composite_score(metrics)

        return CalibrationReport(
            as_of_date=as_of_date,
            metrics=metrics,
            lag_results=lag_results,
            attributions=attributions,
            walk_forward_folds=folds,
            composite_score=composite,
            warnings=warnings,
        )

    def _lag_test(
        self,
        target_key: str,
        beliefs: list[BeliefObservation],
        markets: list[MarketObservation],
        lags: list[int],
    ) -> list[LagResult]:
        target = next(item for item in MARKET_TARGETS if item.key == target_key)
        belief_lookup = {item.as_of_date: item for item in beliefs}
        market_lookup = {item.as_of_date: item for item in markets}
        common_dates = sorted(set(belief_lookup) & set(market_lookup))
        output = []

        for lag in lags:
            predicted = []
            realized = []
            for current_date in common_dates:
                future_date = (
                    date.fromisoformat(current_date) + timedelta(days=lag)
                ).isoformat()
                if future_date not in market_lookup:
                    continue
                current_value = getattr(market_lookup[current_date], target.source_field)
                future_value = getattr(market_lookup[future_date], target.source_field)
                if current_value is None or future_value is None:
                    continue
                value = (
                    future_value - current_value
                    if target.transform == "change"
                    else future_value
                ) * target.expected_direction
                predicted.append(self.build_prediction(belief_lookup[current_date]))
                realized.append(value)
            output.append(
                LagResult(
                    target_key=target_key,
                    lag_days=lag,
                    correlation=pearson(predicted, realized),
                    directional_accuracy=directional_accuracy(predicted, realized),
                    sample_size=len(predicted),
                )
            )
        return output

    def _attribution(
        self,
        target_key: str,
        beliefs: list[BeliefObservation],
        markets: list[MarketObservation],
    ) -> AttributionResult:
        target = next(item for item in MARKET_TARGETS if item.key == target_key)
        market_lookup = {item.as_of_date: item for item in markets}
        components = {
            "composite_liquidity": [],
            "financial_conditions_easing": [],
            "growth_valuation_support": [],
            "real_yield_pressure": [],
            "long_rate_pressure": [],
        }
        realized = []

        for belief in beliefs:
            future_date = (
                date.fromisoformat(belief.as_of_date)
                + timedelta(days=target.horizon_days)
            ).isoformat()
            if belief.as_of_date not in market_lookup or future_date not in market_lookup:
                continue
            current = getattr(market_lookup[belief.as_of_date], target.source_field)
            future = getattr(market_lookup[future_date], target.source_field)
            if current is None or future is None:
                continue
            outcome = (
                future - current if target.transform == "change" else future
            ) * target.expected_direction
            realized.append(outcome)
            components["composite_liquidity"].append(belief.composite_liquidity)
            components["financial_conditions_easing"].append(belief.financial_conditions_easing)
            components["growth_valuation_support"].append(belief.growth_valuation_support)
            components["real_yield_pressure"].append(-belief.real_yield_pressure)
            components["long_rate_pressure"].append(-belief.long_rate_pressure)

        contributions = {
            key: (pearson(values, realized) or 0.0)
            for key, values in components.items()
        }
        dominant = (
            max(contributions, key=lambda key: abs(contributions[key]))
            if contributions else None
        )
        return AttributionResult(
            target_key=target_key,
            contributions=contributions,
            dominant_driver=dominant,
        )

    def _walk_forward(
        self,
        points: list[CalibrationPoint],
        minimum_train: int = 30,
        test_size: int = 10,
    ) -> list[WalkForwardFold]:
        ordered = sorted(points, key=lambda item: (item.as_of_date, item.target_key))
        folds = []
        fold_id = 1
        for start in range(minimum_train, len(ordered), test_size):
            train = ordered[:start]
            test = ordered[start:start + test_size]
            if len(test) < 3:
                continue
            predicted = [item.prediction for item in test]
            realized = [item.realized for item in test]
            folds.append(
                WalkForwardFold(
                    fold_id=fold_id,
                    train_start=train[0].as_of_date,
                    train_end=train[-1].as_of_date,
                    test_start=test[0].as_of_date,
                    test_end=test[-1].as_of_date,
                    sample_size=len(test),
                    correlation=pearson(predicted, realized),
                    directional_accuracy=directional_accuracy(predicted, realized),
                )
            )
            fold_id += 1
        return folds

    def _stability(self, predicted, realized) -> float | None:
        if len(predicted) < 12:
            return None
        midpoint = len(predicted) // 2
        first = pearson(predicted[:midpoint], realized[:midpoint])
        second = pearson(predicted[midpoint:], realized[midpoint:])
        if first is None or second is None:
            return None
        return clamp(1.0 - abs(first - second) / 2.0)

    def _composite_score(self, metrics: list[MetricResult]) -> float:
        weighted = 0.0
        total = 0.0
        target_lookup = {item.key: item for item in MARKET_TARGETS}
        for metric in metrics:
            target = target_lookup[metric.target_key]
            if metric.correlation is None or metric.directional_accuracy is None:
                continue
            quality = (
                clamp((metric.correlation + 1) / 2) * 0.55
                + metric.directional_accuracy * 0.35
                + (metric.stability_score or 0.5) * 0.10
            )
            weighted += quality * target.weight
            total += target.weight
        return weighted / total if total else 0.0
