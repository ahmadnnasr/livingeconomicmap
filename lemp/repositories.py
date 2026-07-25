from __future__ import annotations
from datetime import datetime, timezone
from typing import Iterable, Optional
import hashlib
import json
import uuid

from .db import Database
from .models import Source, SeriesDefinition, Observation, ValidationResult


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class SourceRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(self, source: Source) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO sources(
                    source_id, name, provider_type, base_url,
                    license_class, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    name=excluded.name,
                    provider_type=excluded.provider_type,
                    base_url=excluded.base_url,
                    license_class=excluded.license_class
                """,
                (
                    source.source_id,
                    source.name,
                    source.provider_type,
                    source.base_url,
                    source.license_class,
                    now(),
                ),
            )


class SeriesRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert(self, series: SeriesDefinition) -> None:
        timestamp = now()
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO series_registry(
                    series_id, source_id, external_id, name, category,
                    frequency, units, seasonal_adjustment,
                    transformation_policy, revision_policy,
                    metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(series_id) DO UPDATE SET
                    name=excluded.name,
                    category=excluded.category,
                    frequency=excluded.frequency,
                    units=excluded.units,
                    seasonal_adjustment=excluded.seasonal_adjustment,
                    transformation_policy=excluded.transformation_policy,
                    revision_policy=excluded.revision_policy,
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (
                    series.series_id,
                    series.source_id,
                    series.external_id,
                    series.name,
                    series.category,
                    series.frequency,
                    series.units,
                    series.seasonal_adjustment,
                    series.transformation_policy,
                    series.revision_policy,
                    json.dumps(series.metadata, sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )


class IngestionRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def start_run(
        self,
        source_id: str,
        connector_name: str,
        request: dict,
    ) -> str:
        run_id = str(uuid.uuid4())
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO ingestion_runs(
                    run_id, source_id, connector_name, started_at,
                    status, request_fingerprint, request_json
                )
                VALUES (?, ?, ?, ?, 'running', ?, ?)
                """,
                (
                    run_id,
                    source_id,
                    connector_name,
                    now(),
                    stable_hash(request),
                    json.dumps(request, sort_keys=True),
                ),
            )
        return run_id

    def store_payload(
        self,
        run_id: str,
        source_id: str,
        observed_at: str,
        payload: dict,
        content_type: str = "application/json",
    ) -> str:
        payload_id = str(uuid.uuid4())
        payload_hash = stable_hash(payload)
        with self.db.transaction() as connection:
            existing = connection.execute(
                """
                SELECT payload_id FROM raw_payloads
                WHERE source_id=? AND content_hash=?
                """,
                (source_id, payload_hash),
            ).fetchone()
            if existing:
                return existing["payload_id"]

            connection.execute(
                """
                INSERT INTO raw_payloads(
                    payload_id, run_id, source_id, observed_at, retrieved_at,
                    content_type, content_hash, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload_id,
                    run_id,
                    source_id,
                    observed_at,
                    now(),
                    content_type,
                    payload_hash,
                    json.dumps(payload, sort_keys=True),
                ),
            )
        return payload_id

    def finish_run(
        self,
        run_id: str,
        status: str,
        response_hash: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                """
                UPDATE ingestion_runs
                SET completed_at=?, status=?, response_hash=?, error_message=?
                WHERE run_id=?
                """,
                (now(), status, response_hash, error_message, run_id),
            )


class ObservationRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def append(self, observation: Observation) -> str:
        with self.db.transaction() as connection:
            prior = connection.execute(
                """
                SELECT revision_number, value
                FROM observations
                WHERE series_id=? AND observation_date=?
                ORDER BY revision_number DESC
                LIMIT 1
                """,
                (observation.series_id, observation.observation_date),
            ).fetchone()

            revision_number = 0
            if prior is not None:
                if float(prior["value"]) == float(observation.value):
                    existing = connection.execute(
                        """
                        SELECT observation_id FROM observations
                        WHERE series_id=? AND observation_date=? AND vintage_date=?
                        """,
                        (
                            observation.series_id,
                            observation.observation_date,
                            observation.vintage_date,
                        ),
                    ).fetchone()
                    if existing:
                        return existing["observation_id"]
                revision_number = int(prior["revision_number"]) + 1

            observation_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO observations(
                    observation_id, series_id, observation_date, value,
                    vintage_date, revision_number, release_id, payload_id,
                    quality_status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation_id,
                    observation.series_id,
                    observation.observation_date,
                    observation.value,
                    observation.vintage_date,
                    revision_number,
                    observation.release_id,
                    observation.payload_id,
                    observation.quality_status,
                    now(),
                ),
            )
            return observation_id

    def latest_vintage(
        self,
        series_id: str,
        observation_date: Optional[str] = None,
    ):
        query = """
            SELECT * FROM observations
            WHERE series_id=?
        """
        params = [series_id]
        if observation_date is not None:
            query += " AND observation_date=?"
            params.append(observation_date)
        query += " ORDER BY observation_date DESC, revision_number DESC LIMIT 1"

        with self.db.connect() as connection:
            return connection.execute(query, params).fetchone()


class ValidationRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def record(
        self,
        object_type: str,
        object_id: str,
        result: ValidationResult,
    ) -> str:
        validation_id = str(uuid.uuid4())
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO validation_results(
                    validation_id, object_type, object_id, rule_name,
                    status, severity, message, details_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    validation_id,
                    object_type,
                    object_id,
                    result.rule_name,
                    result.status,
                    result.severity,
                    result.message,
                    json.dumps(result.details, sort_keys=True),
                    now(),
                ),
            )
        return validation_id


class EventRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def publish(
        self,
        event_type: str,
        subject_type: str,
        subject_id: Optional[str],
        occurred_at: str,
        payload: dict,
        dedupe_key: str,
    ) -> str:
        event_id = str(uuid.uuid4())
        with self.db.transaction() as connection:
            existing = connection.execute(
                "SELECT event_id FROM events WHERE dedupe_key=?",
                (dedupe_key,),
            ).fetchone()
            if existing:
                return existing["event_id"]

            connection.execute(
                """
                INSERT INTO events(
                    event_id, event_type, subject_type, subject_id,
                    occurred_at, recorded_at, payload_json, dedupe_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    event_type,
                    subject_type,
                    subject_id,
                    occurred_at,
                    now(),
                    json.dumps(payload, sort_keys=True),
                    dedupe_key,
                ),
            )
        return event_id

    def pending(self, limit: int = 100):
        with self.db.connect() as connection:
            return connection.execute(
                """
                SELECT * FROM events
                WHERE status='pending'
                ORDER BY occurred_at
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
