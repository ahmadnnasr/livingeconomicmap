from __future__ import annotations
from typing import List, Optional
from .models import RankingSnapshot
from .history import RankChange


class BriefingGenerator:
    def generate(
        self,
        snapshot: RankingSnapshot,
        changes: Optional[List[RankChange]] = None,
        top_n: int = 5,
    ) -> str:
        eligible = [
            item for item in snapshot.rankings
            if item.rank is not None
        ]
        failed = [
            item for item in snapshot.rankings
            if item.rank is None
        ]

        lines = [
            "WHAT CHANGES NEXT",
            f"Methodology: {snapshot.methodology_version}",
            "",
            "Highest-ranked opportunities:",
        ]

        for item in eligible[:top_n]:
            drivers = "; ".join(item.positive_drivers) or "No module exceeded the support threshold."
            lines.append(
                f"{item.rank}. {item.ticker} — {item.total_score:.3f}. {drivers}"
            )

        if changes:
            lines.extend(["", "Largest changes since the prior snapshot:"])
            material = sorted(
                [
                    change for change in changes
                    if change.score_change is not None
                ],
                key=lambda item: abs(item.score_change),
                reverse=True,
            )[:top_n]
            for item in material:
                rank_text = (
                    f"rank change {item.rank_change:+d}"
                    if item.rank_change is not None
                    else "rank unavailable"
                )
                lines.append(
                    f"- {item.ticker}: score {item.score_change:+.3f}; "
                    f"{rank_text}. {item.explanation}"
                )

        if failed:
            lines.extend(["", "Excluded by data-quality gates:"])
            for item in failed:
                lines.append(
                    f"- {item.ticker}: " + "; ".join(item.gate.failures)
                )

        lines.extend([
            "",
            "Research interpretation:",
            "- Scores prioritize evidence completeness and freshness before ranking.",
            "- A high score identifies a research candidate, not an automatic trade.",
            "- Position sizing, entry conditions, catalysts, and downside scenarios remain separate decisions.",
        ])
        return "\n".join(lines)
