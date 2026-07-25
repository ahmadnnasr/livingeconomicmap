from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DailySchedule:
    schedule_key: str
    name: str
    timezone: str
    run_time: str
    job_type: str
    queue_name: str
    enabled: bool = True
    business_days_only: bool = True


@dataclass
class DailyRun:
    run_id: str
    as_of_date: str
    status: str
    started_at: str
    completed_at: Optional[str]
    stages: list[str]
    trace_id: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class StageResult:
    stage_key: str
    status: str
    started_at: str
    completed_at: Optional[str]
    output: dict
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class HealthSignal:
    key: str
    status: str
    observed_value: float
    threshold: float
    message: str


@dataclass
class Alert:
    alert_key: str
    severity: str
    category: str
    message: str
    as_of_date: str
    dedupe_key: str
    requires_human_action: bool


@dataclass
class ApprovalPackage:
    candidate_model_id: str
    production_model_id: str
    generated_at: str
    executive_summary: str
    coefficient_changes: list[dict]
    performance_comparison: dict
    stability_summary: dict
    risks: list[str]
    recommendation: str
    approval_status: str = "pending"


@dataclass
class DailyBrief:
    as_of_date: str
    headline: str
    regime_summary: str
    belief_changes: list[str]
    market_transmission: list[str]
    ranking_changes: list[str]
    alerts: list[str]
    model_governance: list[str]
