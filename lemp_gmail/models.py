from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass
class GmailMessage:
    to: str
    subject: str
    text_body: str
    html_body: str
    cc: str = ""
    bcc: str = ""
    reply_message_id: Optional[str] = None
    attachment_files: list[str] | None = None


@dataclass
class GmailDraftResult:
    draft_id: str
    message_id: Optional[str] = None
    thread_id: Optional[str] = None


@dataclass
class GmailSendResult:
    message_id: str
    thread_id: Optional[str] = None
    provider: str = "gmail"


@dataclass
class GmailDeliveryRecord:
    publication_id: str
    recipient_email: str
    delivery_mode: str
    idempotency_key: str
    status: str
    draft_id: Optional[str] = None
    message_id: Optional[str] = None
    thread_id: Optional[str] = None
    error_message: Optional[str] = None
