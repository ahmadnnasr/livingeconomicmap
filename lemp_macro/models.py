from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class CanonicalObservation:
    series_id: str
    source_id: str
    external_id: str
    observation_date: str
    value: float
    vintage_date: str
    units: str
    frequency: str
    seasonal_adjustment: Optional[str] = None
    release_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorRequest:
    endpoint: str
    parameters: dict[str, Any]
    credential_reference: Optional[str] = None


@dataclass
class ConnectorResponse:
    source_id: str
    request: ConnectorRequest
    payload: Any
    retrieved_at: str
    content_hash: str


@dataclass
class ReleaseEvent:
    release_key: str
    source_id: str
    release_name: str
    scheduled_at: str
    timezone: str
    expected_series: list[str]
    status: str = "scheduled"


@dataclass
class FeatureValue:
    series_id: str
    feature_name: str
    as_of_date: str
    value: float
    methodology_version: str
    inputs: list[str]
