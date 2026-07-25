from __future__ import annotations
from datetime import datetime, timezone
from .models import ApprovalPackage


class ApprovalPackageBuilder:
    def build(
        self,
        candidate: dict,
        production: dict,
        performance: dict,
        stability: dict,
    ) -> ApprovalPackage:
        changes = []
        all_keys = sorted(
            set(candidate["coefficients"]) | set(production["coefficients"])
        )
        for key in all_keys:
            old = production["coefficients"].get(key, 0.0)
            new = candidate["coefficients"].get(key, 0.0)
            relative = None if old == 0 else (new - old) / abs(old)
            changes.append(
                {
                    "feature": key,
                    "production_weight": old,
                    "candidate_weight": new,
                    "absolute_change": new - old,
                    "relative_change": relative,
                    "economic_interpretation": self._interpret(key, old, new),
                }
            )

        risks = []
        if performance.get("improvement_ratio", 0) < 0.05:
            risks.append("Performance improvement is below the 5% promotion threshold.")
        if stability.get("unstable_features"):
            risks.append(
                "Unstable coefficients: "
                + ", ".join(stability["unstable_features"])
            )

        recommendation = (
            "Approve candidate for production."
            if not risks and candidate.get("promotion_approved")
            else "Do not approve without additional review."
        )

        return ApprovalPackage(
            candidate_model_id=candidate["model_id"],
            production_model_id=production["model_id"],
            generated_at=datetime.now(timezone.utc).isoformat(),
            executive_summary=(
                f"Candidate {candidate['model_id']} is compared with "
                f"production {production['model_id']}."
            ),
            coefficient_changes=changes,
            performance_comparison=performance,
            stability_summary=stability,
            risks=risks,
            recommendation=recommendation,
        )

    @staticmethod
    def _interpret(feature: str, old: float, new: float) -> str:
        direction = "stronger" if abs(new) > abs(old) else "weaker"
        return f"{feature} has a {direction} influence in the candidate model."
