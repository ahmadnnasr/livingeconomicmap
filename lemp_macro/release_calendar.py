from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Iterable

from .models import ReleaseEvent


class ReleaseCalendar:
    def __init__(self, events: Iterable[ReleaseEvent] = ()) -> None:
        self.events = {event.release_key: event for event in events}

    def upsert(self, event: ReleaseEvent) -> None:
        self.events[event.release_key] = event

    def due_between(
        self,
        start: str,
        end: str,
    ) -> list[ReleaseEvent]:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(end)
        result = []
        for event in self.events.values():
            event_dt = datetime.fromisoformat(event.scheduled_at)
            if start_dt <= event_dt <= end_dt:
                result.append(event)
        return sorted(result, key=lambda item: item.scheduled_at)

    def ingestion_jobs(self, event: ReleaseEvent) -> list[dict]:
        return [
            {
                "queue_name": "ingestion",
                "job_type": "macro.release.ingest",
                "payload": {
                    "release_key": event.release_key,
                    "source_id": event.source_id,
                    "series_id": series_id,
                    "scheduled_at": event.scheduled_at,
                },
                "dedupe_key": (
                    f"{event.release_key}:{event.scheduled_at}:{series_id}"
                ),
            }
            for series_id in event.expected_series
        ]
