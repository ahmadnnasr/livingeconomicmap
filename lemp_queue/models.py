from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class Job:
    job_id: str
    queue_name: str
    job_type: str
    payload: dict[str, Any]
    status: str
    priority: int
    attempt_count: int
    max_attempts: int
    available_at: str
    leased_until: Optional[str]
    worker_id: Optional[str]
    dedupe_key: Optional[str]
    parent_job_id: Optional[str]
    trace_id: str
    last_error: Optional[str]


@dataclass
class JobResult:
    status: str
    output: dict
    retryable: bool = False
    error_message: Optional[str] = None


@dataclass
class WorkerRegistration:
    worker_id: str
    worker_type: str
    queue_name: str
    hostname: Optional[str] = None
    process_id: Optional[int] = None
    metadata: Optional[dict] = None
