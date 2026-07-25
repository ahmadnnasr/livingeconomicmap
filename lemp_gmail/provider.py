from __future__ import annotations
from typing import Protocol

from .models import GmailMessage, GmailDraftResult, GmailSendResult


class GmailClient(Protocol):
    def create_draft(self, message: GmailMessage) -> GmailDraftResult:
        ...

    def send_message(self, message: GmailMessage) -> GmailSendResult:
        ...

    def send_draft(self, draft_id: str) -> GmailSendResult:
        ...


class GmailConnectorClient:
    """
    Production adapter boundary for the connected Gmail actions.

    The runtime implementation should map:
      create_draft -> Gmail.create_draft
      send_message -> Gmail.send_email
      send_draft -> Gmail.send_draft

    This package intentionally does not embed OAuth tokens or Gmail credentials.
    Authentication is delegated to the connected Gmail account.
    """

    def create_draft(self, message: GmailMessage) -> GmailDraftResult:
        raise NotImplementedError(
            "Bind this method to the connected Gmail create_draft action."
        )

    def send_message(self, message: GmailMessage) -> GmailSendResult:
        raise NotImplementedError(
            "Bind this method to the connected Gmail send_email action."
        )

    def send_draft(self, draft_id: str) -> GmailSendResult:
        raise NotImplementedError(
            "Bind this method to the connected Gmail send_draft action."
        )
