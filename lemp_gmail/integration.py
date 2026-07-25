from __future__ import annotations

from .adapter import GmailRPSAdapter
from .policy import GmailDeliveryPolicy
from .threading import ThreadingPolicy


class GmailPublicationDispatcher:
    def __init__(
        self,
        adapter: GmailRPSAdapter,
        load_thread_state,
    ) -> None:
        self.adapter = adapter
        self.load_thread_state = load_thread_state

    def dispatch(
        self,
        publication,
        recipient,
        html_render,
        markdown_render,
    ):
        mode = GmailDeliveryPolicy.mode_for(publication.publication_type)
        state = self.load_thread_state(
            publication.publication_type,
            recipient.recipient_id,
        )
        reply_message_id = ThreadingPolicy.reply_message_id(
            publication.publication_type,
            state,
        )

        kwargs = dict(
            publication_id=publication.publication_id,
            recipient_email=recipient.email,
            subject=publication.subject,
            text_body=markdown_render.content,
            html_body=html_render.content,
            reply_message_id=reply_message_id,
        )

        if mode == "draft_first":
            return self.adapter.create_review_draft(**kwargs)
        if mode == "send_now":
            return self.adapter.send_now(**kwargs)
        raise ValueError(mode)
