from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence

from .models import TrainingRow, WeightConstraint, FitConfig, FittedModel
from .math_utils import mean


class ConstrainedRidgeFitter:
    """
    Projected-gradient ridge regression.

    After every gradient step, coefficients are projected back into their
    economically allowed intervals.
    """

    def fit(
        self,
        rows: list[TrainingRow],
        constraints: list[WeightConstraint],
        config: FitConfig,
        target_key: str,
    ) -> FittedModel:
        if not rows:
            raise ValueError("Training rows are required.")

        feature_names = [item.feature_name for item in constraints]
        weights = {name: 0.0 for name in feature_names}
        intercept = mean([row.target for row in rows]) if config.intercept else 0.0

        converged = False
        prior_objective = float("inf")

        for iteration in range(1, config.max_iterations + 1):
            gradients = {name: 0.0 for name in feature_names}
            intercept_gradient = 0.0

            for row in rows:
                prediction = intercept + sum(
                    weights[name] * row.features[name]
                    for name in feature_names
                )
                error = prediction - row.target
                for name in feature_names:
                    gradients[name] += 2.0 * error * row.features[name]
                intercept_gradient += 2.0 * error

            n = len(rows)
            for name in feature_names:
                gradients[name] = (
                    gradients[name] / n
                    + 2.0 * config.ridge_lambda * weights[name]
                )
            intercept_gradient /= n

            old_weights = dict(weights)
            old_intercept = intercept

            for constraint in constraints:
                candidate = (
                    weights[constraint.feature_name]
                    - config.learning_rate * gradients[constraint.feature_name]
                )
                weights[constraint.feature_name] = min(
                    constraint.upper_bound,
                    max(constraint.lower_bound, candidate),
                )

            if config.intercept:
                intercept -= config.learning_rate * intercept_gradient

            objective = self.objective(
                rows, feature_names, weights, intercept, config.ridge_lambda
            )
            movement = max(
                [abs(weights[name] - old_weights[name]) for name in feature_names]
                + [abs(intercept - old_intercept)]
            )

            if abs(prior_objective - objective) < config.tolerance and movement < config.tolerance:
                converged = True
                break
            prior_objective = objective

        return FittedModel(
            target_key=target_key,
            coefficients=weights,
            intercept=intercept,
            ridge_lambda=config.ridge_lambda,
            training_rows=len(rows),
            converged=converged,
            iterations=iteration,
            objective_value=objective,
        )

    @staticmethod
    def objective(
        rows: list[TrainingRow],
        feature_names: list[str],
        weights: dict[str, float],
        intercept: float,
        ridge_lambda: float,
    ) -> float:
        residual = 0.0
        for row in rows:
            prediction = intercept + sum(
                weights[name] * row.features[name]
                for name in feature_names
            )
            residual += (prediction - row.target) ** 2
        residual /= len(rows)
        penalty = ridge_lambda * sum(value * value for value in weights.values())
        return residual + penalty
