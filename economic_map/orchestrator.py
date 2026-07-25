from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from .models import CompanyInput, RankingSnapshot
from .ranking import UnifiedRankingEngine
from .history import SnapshotComparator, RankChange
from .store import SnapshotStore
from .briefing import BriefingGenerator


@dataclass
class CycleOutput:
    snapshot: RankingSnapshot
    snapshot_path: Path
    changes: List[RankChange]
    briefing: str


class ResearchCycle:
    def __init__(
        self,
        store: SnapshotStore,
        ranker: UnifiedRankingEngine | None = None,
        briefing_generator: BriefingGenerator | None = None,
    ) -> None:
        self.store = store
        self.ranker = ranker or UnifiedRankingEngine()
        self.briefing_generator = briefing_generator or BriefingGenerator()

    def run(
        self,
        companies: List[CompanyInput],
        as_of: str,
        methodology_version: str = "1.7",
    ) -> CycleOutput:
        prior = self.store.latest()
        snapshot = self.ranker.rank(
            companies,
            as_of=as_of,
            methodology_version=methodology_version,
        )
        changes = (
            SnapshotComparator.compare(prior, snapshot)
            if prior is not None
            else []
        )
        path = self.store.save(snapshot)
        briefing = self.briefing_generator.generate(snapshot, changes)
        return CycleOutput(
            snapshot=snapshot,
            snapshot_path=path,
            changes=changes,
            briefing=briefing,
        )
