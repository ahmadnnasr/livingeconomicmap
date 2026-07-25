from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import hashlib
import json
from .models import RankingSnapshot
from .history import snapshot_from_dict


class SnapshotStore:
    """
    Append-only JSON snapshot store with content hashes.

    This is intentionally file-backed so the research engine remains portable.
    A database becomes necessary only when multiple users, concurrent writes,
    or large historical datasets are introduced.
    """

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _digest(payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def save(self, snapshot: RankingSnapshot) -> Path:
        payload = snapshot.to_dict()
        envelope = {
            "sha256": self._digest(payload),
            "snapshot": payload,
        }
        path = self.directory / f"{snapshot.snapshot_id}.json"
        if path.exists():
            existing = json.loads(path.read_text())
            if existing["sha256"] != envelope["sha256"]:
                raise ValueError("Snapshot ID collision with different content.")
            return path
        path.write_text(json.dumps(envelope, indent=2) + "\n")
        return path

    def load(self, snapshot_id: str) -> RankingSnapshot:
        path = self.directory / f"{snapshot_id}.json"
        envelope = json.loads(path.read_text())
        actual = self._digest(envelope["snapshot"])
        if actual != envelope["sha256"]:
            raise ValueError("Snapshot integrity check failed.")
        return snapshot_from_dict(envelope["snapshot"])

    def list_ids(self) -> List[str]:
        return sorted(path.stem for path in self.directory.glob("*.json"))

    def latest(self) -> Optional[RankingSnapshot]:
        ids = self.list_ids()
        return self.load(ids[-1]) if ids else None
