from __future__ import annotations


class PublicationJobHandler:
    def __init__(
        self,
        load_publication,
        publication_service,
    ) -> None:
        self.load_publication = load_publication
        self.publication_service = publication_service

    def __call__(self, job) -> dict:
        publication = self.load_publication(job.payload["publication_id"])
        result = self.publication_service.publish(publication)
        return {
            "publication_id": publication.publication_id,
            "status": result["status"],
            "recipient_count": result["recipient_count"],
            "archive_path": result["archive_path"],
        }
