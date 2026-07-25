from __future__ import annotations
from dataclasses import asdict
from typing import Callable

from .models import CanonicalObservation


class MacroIngestionHandler:
    """
    Adapter between provider connectors and the PostgreSQL-native queue.

    Dependencies are injected so the handler can be tested without network or
    database access.
    """

    def __init__(
        self,
        connector_lookup: dict[str, object],
        fetcher: Callable,
        persist_raw: Callable,
        persist_observations: Callable,
        publish_event: Callable,
        credential_resolver: Callable,
    ) -> None:
        self.connector_lookup = connector_lookup
        self.fetcher = fetcher
        self.persist_raw = persist_raw
        self.persist_observations = persist_observations
        self.publish_event = publish_event
        self.credential_resolver = credential_resolver

    def __call__(self, job) -> dict:
        payload = job.payload
        connector = self.connector_lookup[payload["connector_name"]]
        request = connector.build_request(**payload["request_arguments"])

        secret = None
        if request.credential_reference:
            secret = self.credential_resolver(request.credential_reference)

        response = self.fetcher(connector.source_id, request, secret)
        raw_id = self.persist_raw(response)
        observations = connector.normalize(
            response.payload,
            vintage_date=payload["vintage_date"],
            **payload["normalization_arguments"],
        )
        persisted = self.persist_observations(raw_id, observations)

        self.publish_event(
            "macro.observations.created",
            {
                "source_id": connector.source_id,
                "observation_ids": persisted,
                "trace_id": job.trace_id,
            },
        )
        return {
            "raw_payload_id": raw_id,
            "observation_count": len(persisted),
            "source_id": connector.source_id,
        }
