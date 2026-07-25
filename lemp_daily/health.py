from __future__ import annotations
from .models import HealthSignal, Alert


class HealthCheckEngine:
    def evaluate(self, metrics: dict[str, float], as_of_date: str) -> tuple[list[HealthSignal], list[Alert]]:
        signals = []
        alerts = []

        rules = [
            ("queue_oldest_seconds", 900, "warning", "Queue backlog is too old."),
            ("stale_worker_count", 0, "critical", "One or more workers are stale."),
            ("dead_letter_count_24h", 0, "warning", "Dead-letter jobs were created."),
            ("macro_coverage_ratio", 0.85, "critical", "Macro coverage fell below 85%."),
            ("daily_run_duration_seconds", 3600, "warning", "Daily run exceeded one hour."),
        ]

        for key, threshold, severity, message in rules:
            value = metrics.get(key, 0.0)
            if key == "macro_coverage_ratio":
                failed = value < threshold
            else:
                failed = value > threshold

            status = "fail" if failed else "pass"
            signals.append(
                HealthSignal(
                    key=key,
                    status=status,
                    observed_value=value,
                    threshold=threshold,
                    message=message if failed else "Within threshold.",
                )
            )
            if failed:
                alerts.append(
                    Alert(
                        alert_key=f"health:{key}",
                        severity=severity,
                        category="platform_health",
                        message=message,
                        as_of_date=as_of_date,
                        dedupe_key=f"{as_of_date}:health:{key}",
                        requires_human_action=severity == "critical",
                    )
                )
        return signals, alerts
