from __future__ import annotations


class GmailDeliveryJobHandler:
    def __init__(
        self,
        load_publication_bundle,
        dispatcher,
    ) -> None:
        self.load_publication_bundle = load_publication_bundle
        self.dispatcher = dispatcher

    def __call__(self, job) -> dict:
        bundle = self.load_publication_bundle(
            job.payload["publication_id"],
            job.payload["recipient_id"],
        )
        record = self.dispatcher.dispatch(
            bundle["publication"],
            bundle["recipient"],
            bundle["html_render"],
            bundle["markdown_render"],
        )
        return {
            "publication_id": record.publication_id,
            "recipient_email": record.recipient_email,
            "delivery_mode": record.delivery_mode,
            "status": record.status,
            "draft_id": record.draft_id,
            "message_id": record.message_id,
            "thread_id": record.thread_id,
        }
