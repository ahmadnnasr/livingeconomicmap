from __future__ import annotations
from dataclasses import asdict
from typing import Callable

from .models import (
    GmailMessage,
    GmailDraftResult,
    GmailSendResult,
    GmailDeliveryRecord,
)
from .provider import GmailClient


class GmailRPSAdapter:
    """
    Adapts RPS rendered publications to Gmail delivery.

    Modes:
      - draft_first: create a Gmail draft for human review
      - send_now: send immediately
      - send_existing_draft: send a previously reviewed draft
    """

    def __init__(
        self,
        client: GmailClient,
        persist_record: Callable[[GmailDeliveryRecord], None],
    ) -> None:
        self.client = client
        self.persist_record = persist_record

    @staticmethod
    def idempotency_key(
        publication_id: str,
        recipient_email: str,
        mode: str,
    ) -> str:
        return f"{publication_id}:{recipient_email.lower()}:{mode}"

    def create_review_draft(
        self,
        publication_id: str,
        recipient_email: str,
        subject: str,
        text_body: str,
        html_body: str,
        *,
        cc: str = "",
        bcc: str = "",
        reply_message_id: str | None = None,
        attachment_files: list[str] | None = None,
    ) -> GmailDeliveryRecord:
        key = self.idempotency_key(
            publication_id,
            recipient_email,
            "draft_first",
        )
        message = GmailMessage(
            to=recipient_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            cc=cc,
            bcc=bcc,
            reply_message_id=reply_message_id,
            attachment_files=attachment_files or [],
        )
        try:
            result = self.client.create_draft(message)
            record = GmailDeliveryRecord(
                publication_id=publication_id,
                recipient_email=recipient_email,
                delivery_mode="draft_first",
                idempotency_key=key,
                status="draft_created",
                draft_id=result.draft_id,
                message_id=result.message_id,
                thread_id=result.thread_id,
            )
        except Exception as exc:
            record = GmailDeliveryRecord(
                publication_id=publication_id,
                recipient_email=recipient_email,
                delivery_mode="draft_first",
                idempotency_key=key,
                status="failed",
                error_message=str(exc),
            )
        self.persist_record(record)
        return record

    def send_now(
        self,
        publication_id: str,
        recipient_email: str,
        subject: str,
        text_body: str,
        html_body: str,
        *,
        cc: str = "",
        bcc: str = "",
        reply_message_id: str | None = None,
        attachment_files: list[str] | None = None,
    ) -> GmailDeliveryRecord:
        key = self.idempotency_key(
            publication_id,
            recipient_email,
            "send_now",
        )
        message = GmailMessage(
            to=recipient_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
            cc=cc,
            bcc=bcc,
            reply_message_id=reply_message_id,
            attachment_files=attachment_files or [],
        )
        try:
            result = self.client.send_message(message)
            record = GmailDeliveryRecord(
                publication_id=publication_id,
                recipient_email=recipient_email,
                delivery_mode="send_now",
                idempotency_key=key,
                status="sent",
                message_id=result.message_id,
                thread_id=result.thread_id,
            )
        except Exception as exc:
            record = GmailDeliveryRecord(
                publication_id=publication_id,
                recipient_email=recipient_email,
                delivery_mode="send_now",
                idempotency_key=key,
                status="failed",
                error_message=str(exc),
            )
        self.persist_record(record)
        return record

    def send_reviewed_draft(
        self,
        publication_id: str,
        recipient_email: str,
        draft_id: str,
    ) -> GmailDeliveryRecord:
        key = self.idempotency_key(
            publication_id,
            recipient_email,
            "send_existing_draft",
        )
        try:
            result = self.client.send_draft(draft_id)
            record = GmailDeliveryRecord(
                publication_id=publication_id,
                recipient_email=recipient_email,
                delivery_mode="send_existing_draft",
                idempotency_key=key,
                status="sent",
                draft_id=draft_id,
                message_id=result.message_id,
                thread_id=result.thread_id,
            )
        except Exception as exc:
            record = GmailDeliveryRecord(
                publication_id=publication_id,
                recipient_email=recipient_email,
                delivery_mode="send_existing_draft",
                idempotency_key=key,
                status="failed",
                draft_id=draft_id,
                error_message=str(exc),
            )
        self.persist_record(record)
        return record
