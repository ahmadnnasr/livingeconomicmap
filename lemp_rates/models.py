from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SeriesSignal:
    series_id: str
    as_of_date: str
    level: float
    change_1: Optional[float] = None
    change_4: Optional[float] = None
    z_score: Optional[float] = None
    percentile: Optional[float] = None
    acceleration: Optional[float] = None
    units: str = "unknown"
    freshness_days: int = 0
    source_reliability: float = 1.0


@dataclass
class EvidenceItem:
    evidence_id: str
    belief_key: str
    series_id: str
    direction: float
    magnitude: float
    confidence: float
    reliability: float
    contribution: float
    as_of_date: str
    explanation: str
    correlation_group: str


@dataclass
class BeliefState:
    belief_key: str
    prior_probability: float
    posterior_probability: float
    confidence: float
    evidence: list[EvidenceItem]
    as_of_date: str
    explanation: str


@dataclass
class RegimeState:
    regime_key: str
    probability: float
    as_of_date: str
    supporting_beliefs: dict[str, float]
    explanation: str


@dataclass
class PropagationResult:
    node_key: str
    prior_probability: float
    posterior_probability: float
    active_edges: list[str]
    blocked_edges: list[str]
    explanation: str


@dataclass
class RatesLiquiditySnapshot:
    as_of_date: str
    component_beliefs: dict[str, BeliefState]
    composite_liquidity: BeliefState
    rate_beliefs: dict[str, BeliefState]
    regimes: list[RegimeState]
    propagation: list[PropagationResult]
    coverage_ratio: float
    missing_series: list[str]
