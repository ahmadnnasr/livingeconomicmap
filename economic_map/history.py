from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional
import json
from .models import RankingSnapshot


@dataclass
class RankChange:
    ticker: str
    prior_rank: Optional[int]
    current_rank: Optional[int]
    rank_change: Optional[int]
    prior_score: Optional[float]
    current_score: Optional[float]
    score_change: Optional[float]
    module_changes: Dict[str, Optional[float]]
    explanation: str


class SnapshotComparator:
    @staticmethod
    def compare(prior: RankingSnapshot, current: RankingSnapshot) -> List[RankChange]:
        prior_lookup = {item.ticker: item for item in prior.rankings}
        changes: List[RankChange] = []

        for item in current.rankings:
            old = prior_lookup.get(item.ticker)
            if old is None:
                changes.append(
                    RankChange(
                        ticker=item.ticker,
                        prior_rank=None,
                        current_rank=item.rank,
                        rank_change=None,
                        prior_score=None,
                        current_score=item.total_score,
                        score_change=None,
                        module_changes={},
                        explanation="New company entered the ranked universe.",
                    )
                )
                continue

            module_changes = {}
            for name, module in item.modules.items():
                old_module = old.modules.get(name)
                if module.score is None or old_module is None or old_module.score is None:
                    module_changes[name] = None
                else:
                    module_changes[name] = module.score - old_module.score

            rank_change = None
            if old.rank is not None and item.rank is not None:
                rank_change = old.rank - item.rank

            score_change = None
            if old.total_score is not None and item.total_score is not None:
                score_change = item.total_score - old.total_score

            material = sorted(
                [
                    (name, delta)
                    for name, delta in module_changes.items()
                    if delta is not None
                ],
                key=lambda pair: abs(pair[1]),
                reverse=True,
            )
            explanation = "No material module change."
            if material:
                name, delta = material[0]
                direction = "improved" if delta > 0 else "weakened"
                explanation = f"{name.capitalize()} {direction} by {abs(delta):.3f}."

            changes.append(
                RankChange(
                    ticker=item.ticker,
                    prior_rank=old.rank,
                    current_rank=item.rank,
                    rank_change=rank_change,
                    prior_score=old.total_score,
                    current_score=item.total_score,
                    score_change=score_change,
                    module_changes=module_changes,
                    explanation=explanation,
                )
            )
        return changes


def snapshot_from_dict(payload: dict) -> RankingSnapshot:
    from .models import RankedCompany, QualityGateResult, ModuleScore
    rankings = []
    for item in payload["rankings"]:
        modules = {
            name: ModuleScore(**module)
            for name, module in item["modules"].items()
        }
        rankings.append(
            RankedCompany(
                ticker=item["ticker"],
                name=item["name"],
                sector=item["sector"],
                industry=item["industry"],
                total_score=item["total_score"],
                rank=item["rank"],
                gate=QualityGateResult(**item["gate"]),
                modules=modules,
                positive_drivers=item["positive_drivers"],
                risks=item["risks"],
                generated_at=item["generated_at"],
            )
        )
    return RankingSnapshot(
        snapshot_id=payload["snapshot_id"],
        generated_at=payload["generated_at"],
        universe=payload["universe"],
        rankings=rankings,
        methodology_version=payload["methodology_version"],
    )
