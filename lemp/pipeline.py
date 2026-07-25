from __future__ import annotations
from dataclasses import dataclass
from typing import List

from .models import Observation
from .repositories import (
    IngestionRepository,
    ObservationRepository,
    ValidationRepository,
    EventRepository,
    stable_hash,
)
from .validation import ObservationValidator, SeriesValidationPolicy


@dataclass
class IngestionOutcome:
    run_id: str
    payload_id: str
    observation_ids: List[str]
    event_ids: List[str]
    accepted: int
    rejected: int


class IngestionPipeline:
    def __init__(
        self,
        ingestion_repository: IngestionRepository,
        observation_repository: ObservationRepository,
        validation_repository: ValidationRepository,
        event_repository: EventRepository,
        validator: ObservationValidator | None = None,
    ) -> None:
        self.ingestion_repository = ingestion_repository
        self.observation_repository = observation_repository
        self.validation_repository = validation_repository
        self.event_repository = event_repository
        self.validator = validator or ObservationValidator()

    def run(
        self,
        source_id: str,
        connector_name: str,
        request: dict,
        raw_payload: dict,
        observed_at: str,
        observations: List[Observation],
        policies: dict[str, SeriesValidationPolicy],
    ) -> IngestionOutcome:
        run_id = self.ingestion_repository.start_run(
            source_id,
            connector_name,
            request,
        )
        payload_id = self.ingestion_repository.store_payload(
            run_id,
            source_id,
            observed_at,
            raw_payload,
        )

        accepted = 0
        rejected = 0
        observation_ids: List[str] = []
        event_ids: List[str] = []

        try:
            for observation in observations:
                observation.payload_id = payload_id
                prior = self.observation_repository.latest_vintage(
                    observation.series_id,
                    observation.observation_date,
                )
                prior_value = float(prior["value"]) if prior else None
                policy = policies.get(
                    observation.series_id,
                    SeriesValidationPolicy(),
                )
                results = self.validator.validate(
                    observation,
                    policy,
                    prior_value,
                )

                if not self.validator.is_acceptable(results):
                    rejected += 1
                    for result in results:
                        self.validation_repository.record(
                            "candidate_observation",
                            f"{observation.series_id}:{observation.observation_date}",
                            result,
                        )
                    continue

                observation_id = self.observation_repository.append(observation)
                observation_ids.append(observation_id)
                accepted += 1

                for result in results:
                    self.validation_repository.record(
                        "observation",
                        observation_id,
                        result,
                    )

                event_id = self.event_repository.publish(
                    event_type="observation.created",
                    subject_type="series",
                    subject_id=observation.series_id,
                    occurred_at=observed_at,
                    payload={
                        "observation_id": observation_id,
                        "observation_date": observation.observation_date,
                        "vintage_date": observation.vintage_date,
                    },
                    dedupe_key=stable_hash({
                        "type": "observation.created",
                        "observation_id": observation_id,
                    }),
                )
                event_ids.append(event_id)

            self.ingestion_repository.finish_run(
                run_id,
                "succeeded",
                response_hash=stable_hash(raw_payload),
            )
        except Exception as exc:
            self.ingestion_repository.finish_run(
                run_id,
                "failed",
                error_message=str(exc),
            )
            raise

        return IngestionOutcome(
            run_id=run_id,
            payload_id=payload_id,
            observation_ids=observation_ids,
            event_ids=event_ids,
            accepted=accepted,
            rejected=rejected,
        )
