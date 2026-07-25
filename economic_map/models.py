from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class ModuleScore:
    name: str
    score: Optional[float]
    weight: float
    coverage: float
    as_of: Optional[str]
    evidence: List[dict] = field(default_factory=list)
    missing_reason: Optional[str] = None


@dataclass
class CompanyInput:
    ticker: str
    name: str
    sector: str
    industry: str
    macro_score: Optional[float]
    fundamental_score: Optional[float]
    valuation_score: Optional[float]
    technical_score: Optional[float]
    revision_score: Optional[float]
    module_dates: Dict[str, Optional[str]]
    module_evidence: Dict[str, List[dict]] = field(default_factory=dict)


@dataclass
class QualityGateResult:
    passed: bool
    status: str
    failures: List[str]
    warnings: List[str]
    effective_coverage: float


@dataclass
class RankedCompany:
    ticker: str
    name: str
    sector: str
    industry: str
    total_score: Optional[float]
    rank: Optional[int]
    gate: QualityGateResult
    modules: Dict[str, ModuleScore]
    positive_drivers: List[str]
    risks: List[str]
    generated_at: str


@dataclass
class RankingSnapshot:
    snapshot_id: str
    generated_at: str
    universe: List[str]
    rankings: List[RankedCompany]
    methodology_version: str

    def to_dict(self) -> dict:
        return asdict(self)
