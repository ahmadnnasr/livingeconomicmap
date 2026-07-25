from __future__ import annotations
from datetime import datetime, timezone

from .models import DeliveryAttempt, DeliveryHealth


class DeliveryHealthEngine:
    def evaluate(
        self,
        attempts: list[DeliveryAttempt],
        pending_created_at: list[str] | None = None,
    ) -> DeliveryHealth:
        pending_created_at = pending_created_at or []
        successful = sum(item.status == "delivered" for item in attempts)
        failed = sum(item.status == "failed" for item in attempts)
        pending = sum(item.status == "retry" for item in attempts) + len(pending_created_at)
        total = len(attempts) + len(pending_created_at)
        success_rate = successful / len(attempts) if attempts else 1.0

        oldest = 0.0
        now = datetime.now(timezone.utc)
        if pending_created_at:
            oldest = max(
                (now - datetime.fromisoformat(item)).total_seconds() / 60.0
                for item in pending_created_at
            )

        alerts = []
        if success_rate < 0.95:
            alerts.append("Delivery success rate fell below 95%.")
        if failed > 0:
            alerts.append("One or more deliveries permanently failed.")
        if oldest > 15:
            alerts.append("A pending delivery is older than 15 minutes.")

        return DeliveryHealth(
            total_attempts=total,
            successful=successful,
            failed=failed,
            pending=pending,
            success_rate=success_rate,
            oldest_pending_minutes=oldest,
            alerts=alerts,
        )
