from __future__ import annotations
from datetime import datetime, timezone
import uuid

from .models import Publication, PublicationSection
from .templates import PUBLICATION_TYPES, validate_sections


class PublicationBuilder:
    def build(
        self,
        publication_type: str,
        as_of_date: str,
        executive_summary: str,
        sections: list[PublicationSection],
        snapshot_id: str,
        model_version: str,
        trace_id: str,
        subject: str | None = None,
        metadata: dict | None = None,
    ) -> Publication:
        if publication_type not in PUBLICATION_TYPES:
            raise ValueError(f"Unsupported publication type: {publication_type}")

        missing = validate_sections(publication_type, sections)
        if missing:
            raise ValueError(
                "Missing required publication sections: " + ", ".join(missing)
            )

        return Publication(
            publication_id=str(uuid.uuid4()),
            publication_type=publication_type,
            as_of_date=as_of_date,
            subject=subject or PUBLICATION_TYPES[publication_type]["default_subject"],
            executive_summary=executive_summary,
            sections=sections,
            snapshot_id=snapshot_id,
            model_version=model_version,
            trace_id=trace_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            status="ready",
            metadata=metadata or {},
        )
