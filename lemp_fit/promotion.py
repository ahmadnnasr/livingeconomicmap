from __future__ import annotations
from .models import (
    FittedModel, StabilityResult, BaselineComparison, PromotionDecision
)


class PromotionGate:
    def decide(
        self,
        model: FittedModel,
        stability: list[StabilityResult],
        baseline: BaselineComparison,
        model_version: str,
    ) -> PromotionDecision:
        reasons = []
        warnings = []

        if not model.converged:
            reasons.append("Optimizer did not converge.")

        if baseline.improvement_ratio < 0.05:
            reasons.append(
                f"MSE improvement {baseline.improvement_ratio:.1%} is below 5%."
            )

        if (
            baseline.model_directional_accuracy
            < baseline.baseline_directional_accuracy
        ):
            reasons.append("Directional accuracy is worse than the baseline.")

        for item in stability:
            if item.sign_consistency < 0.80:
                reasons.append(
                    f"{item.feature_name} sign consistency is below 80%."
                )
            if item.standard_deviation > 0.20:
                warnings.append(
                    f"{item.feature_name} weight is unstable across folds."
                )

        approved = not reasons
        return PromotionDecision(
            approved=approved,
            reasons=reasons,
            warnings=warnings,
            recommended_coefficients=dict(model.coefficients),
            model_version=model_version,
        )
