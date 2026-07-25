from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import math

from .models import Observation, ValidationResult


@dataclass
class SeriesValidationPolicy:
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    maximum_absolute_change: Optional[float] = None
    allow_negative: bool = True


class ObservationValidator:
    def validate(
        self,
        observation: Observation,
        policy: SeriesValidationPolicy,
        prior_value: Optional[float] = None,
    ) -> List[ValidationResult]:
        results: List[ValidationResult] = []

        if not math.isfinite(observation.value):
            results.append(
                ValidationResult(
                    "finite_numeric",
                    "fail",
                    "error",
                    "Observation value is not finite.",
                )
            )
            return results
        results.append(
            ValidationResult(
                "finite_numeric",
                "pass",
                "info",
                "Observation value is finite.",
            )
        )

        if not policy.allow_negative and observation.value < 0:
            results.append(
                ValidationResult(
                    "negative_value",
                    "fail",
                    "error",
                    "Negative values are not allowed.",
                )
            )

        if policy.minimum is not None and observation.value < policy.minimum:
            results.append(
                ValidationResult(
                    "minimum_bound",
                    "fail",
                    "error",
                    f"Value is below minimum {policy.minimum}.",
                )
            )

        if policy.maximum is not None and observation.value > policy.maximum:
            results.append(
                ValidationResult(
                    "maximum_bound",
                    "fail",
                    "error",
                    f"Value is above maximum {policy.maximum}.",
                )
            )

        if (
            prior_value is not None
            and policy.maximum_absolute_change is not None
            and abs(observation.value - prior_value)
            > policy.maximum_absolute_change
        ):
            results.append(
                ValidationResult(
                    "maximum_absolute_change",
                    "warn",
                    "warning",
                    "Observation changed more than the configured threshold.",
                    {
                        "prior_value": prior_value,
                        "current_value": observation.value,
                        "threshold": policy.maximum_absolute_change,
                    },
                )
            )

        return results

    @staticmethod
    def is_acceptable(results: List[ValidationResult]) -> bool:
        return not any(
            result.status == "fail" and result.severity == "error"
            for result in results
        )
