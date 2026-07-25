from __future__ import annotations
from collections import defaultdict
from typing import Callable

from .models import (
    TrainingRow, WeightConstraint, FitConfig, FittedModel,
    FoldResult, StabilityResult, BaselineComparison,
)
from .optimizer import ConstrainedRidgeFitter
from .math_utils import mse, directional_accuracy, mean, standard_deviation
from .constraints import BASELINE_WEIGHTS


class ModelEvaluator:
    def predict(self, model: FittedModel, rows: list[TrainingRow]) -> list[float]:
        return [
            model.intercept + sum(
                model.coefficients[name] * row.features[name]
                for name in model.coefficients
            )
            for row in rows
        ]

    def expanding_window_cv(
        self,
        rows: list[TrainingRow],
        constraints: list[WeightConstraint],
        config: FitConfig,
        target_key: str,
        minimum_train: int = 60,
        test_size: int = 20,
    ) -> list[FoldResult]:
        folds = []
        fitter = ConstrainedRidgeFitter()
        fold_id = 1

        for start in range(minimum_train, len(rows), test_size):
            train = rows[:start]
            test = rows[start:start+test_size]
            if len(test) < 5:
                continue
            model = fitter.fit(train, constraints, config, target_key)
            predicted = self.predict(model, test)
            actual = [row.target for row in test]
            folds.append(
                FoldResult(
                    fold_id=fold_id,
                    train_size=len(train),
                    test_size=len(test),
                    mean_squared_error=mse(predicted, actual),
                    directional_accuracy=directional_accuracy(predicted, actual),
                    coefficients=dict(model.coefficients),
                )
            )
            fold_id += 1
        return folds

    def stability(self, folds: list[FoldResult]) -> list[StabilityResult]:
        if not folds:
            return []
        values = defaultdict(list)
        for fold in folds:
            for name, weight in fold.coefficients.items():
                values[name].append(weight)

        output = []
        for name, weights in values.items():
            nonzero = [w for w in weights if abs(w) > 1e-12]
            sign_consistency = 1.0
            if nonzero:
                positive = sum(w > 0 for w in nonzero)
                negative = sum(w < 0 for w in nonzero)
                sign_consistency = max(positive, negative) / len(nonzero)
            output.append(
                StabilityResult(
                    feature_name=name,
                    mean_weight=mean(weights),
                    standard_deviation=standard_deviation(weights),
                    sign_consistency=sign_consistency,
                    range_width=max(weights) - min(weights),
                )
            )
        return output

    def compare_to_baseline(
        self,
        model: FittedModel,
        rows: list[TrainingRow],
    ) -> BaselineComparison:
        model_predictions = self.predict(model, rows)
        baseline_predictions = [
            sum(BASELINE_WEIGHTS[name] * row.features[name] for name in BASELINE_WEIGHTS)
            for row in rows
        ]
        actual = [row.target for row in rows]
        model_mse = mse(model_predictions, actual)
        baseline_mse = mse(baseline_predictions, actual)
        improvement = (
            (baseline_mse - model_mse) / baseline_mse
            if baseline_mse > 0 else 0.0
        )
        return BaselineComparison(
            model_mse=model_mse,
            baseline_mse=baseline_mse,
            improvement_ratio=improvement,
            model_directional_accuracy=directional_accuracy(model_predictions, actual),
            baseline_directional_accuracy=directional_accuracy(baseline_predictions, actual),
        )
