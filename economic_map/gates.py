from __future__ import annotations
from datetime import date
from typing import Dict, List, Optional
from .models import CompanyInput, QualityGateResult


class DataQualityGate:
    REQUIRED_MODULES = ("macro", "fundamental", "valuation", "technical", "revisions")
    MODULE_WEIGHTS = {
        "macro": 0.25,
        "fundamental": 0.25,
        "valuation": 0.15,
        "technical": 0.20,
        "revisions": 0.15,
    }

    def __init__(
        self,
        minimum_coverage: float = 0.75,
        maximum_age_days: Optional[Dict[str, int]] = None,
    ) -> None:
        self.minimum_coverage = minimum_coverage
        self.maximum_age_days = maximum_age_days or {
            "macro": 14,
            "fundamental": 120,
            "valuation": 3,
            "technical": 3,
            "revisions": 14,
        }

    def evaluate(self, company: CompanyInput, as_of: str) -> QualityGateResult:
        values = {
            "macro": company.macro_score,
            "fundamental": company.fundamental_score,
            "valuation": company.valuation_score,
            "technical": company.technical_score,
            "revisions": company.revision_score,
        }
        failures: List[str] = []
        warnings: List[str] = []

        coverage = sum(
            self.MODULE_WEIGHTS[name]
            for name, value in values.items()
            if value is not None
        )

        if coverage < self.minimum_coverage:
            failures.append(
                f"Coverage {coverage:.0%} is below the {self.minimum_coverage:.0%} requirement."
            )

        for name, value in values.items():
            if value is None:
                warnings.append(f"{name} module is missing.")
                continue
            if not 0 <= value <= 1:
                failures.append(f"{name} score {value} is outside [0, 1].")

            observed = company.module_dates.get(name)
            if not observed:
                warnings.append(f"{name} module has no observation date.")
                continue

            age = (date.fromisoformat(as_of) - date.fromisoformat(observed)).days
            limit = self.maximum_age_days[name]
            if age > limit:
                failures.append(
                    f"{name} data is {age} days old; maximum is {limit}."
                )
            elif age > max(1, int(limit * 0.75)):
                warnings.append(f"{name} data is approaching its age limit.")

        status = "PASS"
        if failures:
            status = "FAIL"
        elif warnings:
            status = "PASS_WITH_WARNINGS"

        return QualityGateResult(
            passed=not failures,
            status=status,
            failures=failures,
            warnings=warnings,
            effective_coverage=coverage,
        )
