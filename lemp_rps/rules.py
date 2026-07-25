from __future__ import annotations


class PublicationRules:
    @staticmethod
    def should_publish_release_bulletin(
        belief_change: float,
        regime_change: float,
        calibration_change: float | None = None,
    ) -> bool:
        return (
            abs(belief_change) >= 0.10
            or abs(regime_change) >= 0.15
            or (
                calibration_change is not None
                and abs(calibration_change) >= 0.10
            )
        )

    @staticmethod
    def should_publish_governance_package(candidate_exists: bool) -> bool:
        return candidate_exists

    @staticmethod
    def should_publish_daily_brief() -> bool:
        return True

    @staticmethod
    def confidence_label(
        macro_coverage: float,
        critical_stage_failed: bool,
    ) -> str:
        if critical_stage_failed:
            return "do_not_publish"
        if macro_coverage < 0.85:
            return "partial"
        return "full"
