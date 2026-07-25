from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Protocol, Optional
import uuid

from .models import Publication, Recipient, DeliveryAttempt, RenderedPublication


class EmailProvider(Protocol):
    def send(
        self,
        recipient: Recipient,
        subject: str,
        html_body: str,
        text_body: str,
        idempotency_key: str,
    ) -> str:
        ...


@dataclass
class DeliveryPolicy:
    max_attempts: int = 5
    base_retry_seconds: int = 30
    maximum_retry_seconds: int = 3600


class EmailDeliveryService:
    def __init__(
        self,
        provider: EmailProvider,
        persist_attempt,
        policy: DeliveryPolicy | None = None,
    ) -> None:
        self.provider = provider
        self.persist_attempt = persist_attempt
        self.policy = policy or DeliveryPolicy()

    def deliver(
        self,
        publication: Publication,
        recipient: Recipient,
        html: RenderedPublication,
        markdown: RenderedPublication,
        attempt_number: int = 1,
    ) -> DeliveryAttempt:
        delivery_id = str(uuid.uuid4())
        attempted_at = datetime.now(timezone.utc).isoformat()
        idempotency_key = (
            f"{publication.publication_id}:{recipient.recipient_id}:email"
        )

        try:
            provider_message_id = self.provider.send(
                recipient=recipient,
                subject=publication.subject,
                html_body=html.content,
                text_body=markdown.content,
                idempotency_key=idempotency_key,
            )
            attempt = DeliveryAttempt(
                delivery_id=delivery_id,
                publication_id=publication.publication_id,
                recipient_id=recipient.recipient_id,
                channel="email",
                status="delivered",
                attempt_number=attempt_number,
                attempted_at=attempted_at,
                provider_message_id=provider_message_id,
            )
        except Exception as exc:
            status = (
                "failed"
                if attempt_number >= self.policy.max_attempts
                else "retry"
            )
            attempt = DeliveryAttempt(
                delivery_id=delivery_id,
                publication_id=publication.publication_id,
                recipient_id=recipient.recipient_id,
                channel="email",
                status=status,
                attempt_number=attempt_number,
                attempted_at=attempted_at,
                error_message=str(exc),
            )

        self.persist_attempt(attempt)
        return attempt

    def retry_delay_seconds(self, attempt_number: int) -> int:
        return min(
            self.policy.maximum_retry_seconds,
            self.policy.base_retry_seconds * (2 ** max(0, attempt_number - 1)),
        )
