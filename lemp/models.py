from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Source:
    source_id: str
    name: str
    provider_type: str
    base_url: Optional[str] = None
    license_class: str = "public"


@dataclass
class SeriesDefinition:
    series_id: str
    source_id: str
    external_id: str
    name: str
    category: str
    frequency: str
    units: str
    seasonal_adjustment: Optional[str] = None
    transformation_policy: Optional[str] = None
    revision_policy: str = "append_revision"
    metadata: dict = field(default_factory=dict)


@dataclass
class Observation:
    series_id: str
    observation_date: str
    value: float
    vintage_date: str
    payload_id: str
    release_id: Optional[str] = None
    quality_status: str = "validated"


@dataclass
class ValidationResult:
    rule_name: str
    status: str
    severity: str
    message: str
    details: dict = field(default_factory=dict)
