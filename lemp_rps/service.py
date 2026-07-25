from __future__ import annotations

from .models import Publication
from .renderers import MarkdownRenderer, HtmlRenderer, JsonRenderer
from .recipients import RecipientRegistry
from .archive import PublicationArchive
from .delivery import EmailDeliveryService


class ResearchPublicationService:
    def __init__(
        self,
        archive: PublicationArchive,
        recipients: RecipientRegistry,
        email_delivery: EmailDeliveryService,
        publish_event,
    ) -> None:
        self.archive = archive
        self.recipients = recipients
        self.email_delivery = email_delivery
        self.publish_event = publish_event
        self.markdown_renderer = MarkdownRenderer()
        self.html_renderer = HtmlRenderer()
        self.json_renderer = JsonRenderer()

    def publish(self, publication: Publication) -> dict:
        markdown = self.markdown_renderer.render(publication)
        html = self.html_renderer.render(publication)
        json_render = self.json_renderer.render(publication)

        archive_path = self.archive.save(
            publication,
            [markdown, html, json_render],
        )

        recipients = self.recipients.eligible(publication)
        attempts = [
            self.email_delivery.deliver(
                publication,
                recipient,
                html,
                markdown,
            )
            for recipient in recipients
        ]

        publication.status = (
            "published"
            if all(item.status == "delivered" for item in attempts)
            else "delivery_incomplete"
        )
        self.publish_event(
            "publication.published",
            {
                "publication_id": publication.publication_id,
                "publication_type": publication.publication_type,
                "archive_path": str(archive_path),
                "recipient_count": len(recipients),
                "delivery_statuses": [item.status for item in attempts],
                "trace_id": publication.trace_id,
            },
        )
        return {
            "archive_path": str(archive_path),
            "attempts": attempts,
            "recipient_count": len(recipients),
            "status": publication.status,
        }
