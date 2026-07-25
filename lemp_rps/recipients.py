from __future__ import annotations
from .models import Recipient, DeliveryPreference, Publication


SEVERITY_ORDER = {
    "info": 1,
    "warning": 2,
    "critical": 3,
}


class RecipientRegistry:
    def __init__(
        self,
        recipients: list[Recipient] | None = None,
        preferences: list[DeliveryPreference] | None = None,
    ) -> None:
        self.recipients = {
            item.recipient_id: item for item in (recipients or [])
        }
        self.preferences = list(preferences or [])

    def eligible(self, publication: Publication) -> list[Recipient]:
        publication_severity = publication.metadata.get("severity", "info")
        output = []
        for preference in self.preferences:
            if (
                preference.publication_type != publication.publication_type
                or not preference.enabled
                or preference.delivery_channel != "email"
            ):
                continue

            recipient = self.recipients.get(preference.recipient_id)
            if recipient is None or not recipient.is_active:
                continue

            if (
                SEVERITY_ORDER[publication_severity]
                < SEVERITY_ORDER[preference.minimum_severity]
            ):
                continue
            output.append(recipient)
        return output
