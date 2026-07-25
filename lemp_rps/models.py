from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, Any


@dataclass
class PublicationSection:
    key: str
    title: str
    summary: str
    items: list[str] = field(default_factory=list)
    severity: str = "info"


@dataclass
class Publication:
    publication_id: str
    publication_type: str
    as_of_date: str
    subject: str
    executive_summary: str
    sections: list[PublicationSection]
    snapshot_id: str
    model_version: str
    trace_id: str
    generated_at: str
    status: str = "draft"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Recipient:
    recipient_id: str
    email: str
    display_name: Optional[str] = None
    is_active: bool = True


@dataclass
class DeliveryPreference:
    recipient_id: str
    publication_type: str
    enabled: bool = True
    minimum_severity: str = "info"
    delivery_channel: str = "email"


@dataclass
class DeliveryAttempt:
    delivery_id: str
    publication_id: str
    recipient_id: str
    channel: str
    status: str
    attempt_number: int
    attempted_at: str
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class RenderedPublication:
    publication_id: str
    format: str
    content: str
    content_hash: str


@dataclass
class DeliveryHealth:
    total_attempts: int
    successful: int
    failed: int
    pending: int
    success_rate: float
    oldest_pending_minutes: float
    alerts: list[str]
