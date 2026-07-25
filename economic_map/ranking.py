from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List
from .models import CompanyInput, ModuleScore, RankedCompany, RankingSnapshot
from .gates import DataQualityGate


class UnifiedRankingEngine:
    WEIGHTS = {
        "macro": 0.25,
        "fundamental": 0.25,
        "valuation": 0.15,
        "technical": 0.20,
        "revisions": 0.15,
    }

    def __init__(self, gate: DataQualityGate | None = None) -> None:
        self.gate = gate or DataQualityGate()

    def _modules(self, company: CompanyInput) -> Dict[str, ModuleScore]:
        values = {
            "macro": company.macro_score,
            "fundamental": company.fundamental_score,
            "valuation": company.valuation_score,
            "technical": company.technical_score,
            "revisions": company.revision_score,
        }
        return {
            name: ModuleScore(
                name=name,
                score=value,
                weight=self.WEIGHTS[name],
                coverage=1.0 if value is not None else 0.0,
                as_of=company.module_dates.get(name),
                evidence=company.module_evidence.get(name, []),
                missing_reason=None if value is not None else "No verified source value.",
            )
            for name, value in values.items()
        }

    def _score(self, modules: Dict[str, ModuleScore]) -> float:
        available = [module for module in modules.values() if module.score is not None]
        weight = sum(module.weight for module in available)
        if weight == 0:
            return 0.0
        return sum(module.score * module.weight for module in available) / weight

    def _explain(self, modules: Dict[str, ModuleScore]) -> tuple[List[str], List[str]]:
        scored = [module for module in modules.values() if module.score is not None]
        strongest = sorted(scored, key=lambda item: item.score, reverse=True)[:2]
        weakest = sorted(scored, key=lambda item: item.score)[:2]

        positive = [
            f"{item.name.capitalize()} is supportive at {item.score:.3f}."
            for item in strongest if item.score >= 0.55
        ]
        risks = [
            f"{item.name.capitalize()} is a constraint at {item.score:.3f}."
            for item in weakest if item.score < 0.45
        ]
        missing = [
            item.name for item in modules.values() if item.score is None
        ]
        if missing:
            risks.append("Missing modules: " + ", ".join(missing) + ".")
        return positive, risks

    def rank(
        self,
        companies: List[CompanyInput],
        as_of: str,
        methodology_version: str = "1.4",
    ) -> RankingSnapshot:
        generated_at = datetime.now(timezone.utc).isoformat()
        ranked: List[RankedCompany] = []

        for company in companies:
            modules = self._modules(company)
            gate = self.gate.evaluate(company, as_of)
            score = self._score(modules) if gate.passed else None
            positive, risks = self._explain(modules)
            ranked.append(
                RankedCompany(
                    ticker=company.ticker,
                    name=company.name,
                    sector=company.sector,
                    industry=company.industry,
                    total_score=score,
                    rank=None,
                    gate=gate,
                    modules=modules,
                    positive_drivers=positive,
                    risks=risks,
                    generated_at=generated_at,
                )
            )

        eligible = sorted(
            [item for item in ranked if item.total_score is not None],
            key=lambda item: item.total_score,
            reverse=True,
        )
        for index, item in enumerate(eligible, start=1):
            item.rank = index

        failed = [item for item in ranked if item.total_score is None]
        ordered = eligible + failed
        snapshot_id = f"{as_of}-{methodology_version}-" + "-".join(
            item.ticker for item in ordered
        )
        return RankingSnapshot(
            snapshot_id=snapshot_id,
            generated_at=generated_at,
            universe=[item.ticker for item in ordered],
            rankings=ordered,
            methodology_version=methodology_version,
        )
