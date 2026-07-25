from __future__ import annotations
from .models import Alert


class AlertEngine:
    def build_research_alerts(
        self,
        as_of_date: str,
        belief_changes: dict[str, float],
        regime_changes: dict[str, float],
        ranking_changes: dict[str, int],
        calibration_score: float | None,
    ) -> list[Alert]:
        alerts = []

        for key, delta in belief_changes.items():
            if abs(delta) >= 0.10:
                alerts.append(
                    Alert(
                        alert_key=f"belief:{key}",
                        severity="warning",
                        category="belief_change",
                        message=f"{key} changed by {delta:+.1%}.",
                        as_of_date=as_of_date,
                        dedupe_key=f"{as_of_date}:belief:{key}",
                        requires_human_action=False,
                    )
                )

        for key, delta in regime_changes.items():
            if abs(delta) >= 0.15:
                alerts.append(
                    Alert(
                        alert_key=f"regime:{key}",
                        severity="warning",
                        category="regime_change",
                        message=f"{key} regime probability changed by {delta:+.1%}.",
                        as_of_date=as_of_date,
                        dedupe_key=f"{as_of_date}:regime:{key}",
                        requires_human_action=False,
                    )
                )

        for ticker, rank_change in ranking_changes.items():
            if abs(rank_change) >= 3:
                alerts.append(
                    Alert(
                        alert_key=f"ranking:{ticker}",
                        severity="info",
                        category="ranking_change",
                        message=f"{ticker} moved {rank_change:+d} ranking positions.",
                        as_of_date=as_of_date,
                        dedupe_key=f"{as_of_date}:ranking:{ticker}",
                        requires_human_action=False,
                    )
                )

        if calibration_score is not None and calibration_score < 0.50:
            alerts.append(
                Alert(
                    alert_key="calibration:weak",
                    severity="critical",
                    category="model_performance",
                    message="Market calibration score fell below 0.50.",
                    as_of_date=as_of_date,
                    dedupe_key=f"{as_of_date}:calibration:weak",
                    requires_human_action=True,
                )
            )
        return alerts
