"""Sealed last-known-good snapshots per pipeline stage.

Every stage (formula emission, scoring, expedition, verification)
produces a sealed snapshot on success. If a later stage fails,
the pipeline can roll back to the last known-good state for that
stage only — never escalating past the stage boundary.

Usage::

    from deviatrix_genesis.v5.snapshots import StageSnapshotManager

    mgr = StageSnapshotManager()
    mgr.seal("formula_emission", {"formulas": [...]})
    mgr.seal("scoring", {"scores": {...}})

    # On failure, roll back to last good state
    state = mgr.rollback_to("scoring")
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["StageSnapshotManager", "StageSnapshot"]


@dataclass
class StageSnapshot:
    """A sealed snapshot of one pipeline stage."""
    stage_name: str
    data_hash: str
    timestamp: float
    data: dict[str, Any]
    prev_hash: str = ""
    chain_hash: str = ""

    def verify(self, prev_hash: str) -> bool:
        """Verify the snapshot chain integrity."""
        return self.prev_hash == prev_hash


class StageSnapshotManager:
    """Manage sealed snapshots per pipeline stage."""

    def __init__(self, snapshot_dir: str | Path | None = None) -> None:
        self._snapshots: dict[str, list[StageSnapshot]] = {}
        self._latest_hashes: dict[str, str] = {}
        self._snapshot_dir = Path(snapshot_dir) if snapshot_dir else None

    def seal(self, stage_name: str, data: dict[str, Any]) -> StageSnapshot:
        """Seal a snapshot for a stage. Returns the sealed snapshot."""
        data_str = json.dumps(data, sort_keys=True, default=str)
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()[:16]

        prev_hash = self._latest_hashes.get(stage_name, "0" * 16)
        chain_input = f"{prev_hash}:{data_hash}"
        chain_hash = hashlib.sha256(chain_input.encode()).hexdigest()[:16]

        snapshot = StageSnapshot(
            stage_name=stage_name,
            data_hash=data_hash,
            timestamp=time.monotonic(),
            data=data,
            prev_hash=prev_hash,
            chain_hash=chain_hash,
        )

        if stage_name not in self._snapshots:
            self._snapshots[stage_name] = []
        self._snapshots[stage_name].append(snapshot)
        self._latest_hashes[stage_name] = chain_hash

        # Persist if configured
        if self._snapshot_dir:
            self._persist(snapshot)

        return snapshot

    def rollback_to(self, stage_name: str) -> dict[str, Any] | None:
        """Roll back to the last known-good state for a stage."""
        snapshots = self._snapshots.get(stage_name, [])
        if not snapshots:
            return None
        return snapshots[-1].data

    def get_latest(self, stage_name: str) -> StageSnapshot | None:
        """Get the latest snapshot for a stage."""
        snapshots = self._snapshots.get(stage_name, [])
        return snapshots[-1] if snapshots else None

    def verify_chain(self, stage_name: str) -> bool:
        """Verify the entire snapshot chain for a stage."""
        snapshots = self._snapshots.get(stage_name, [])
        if not snapshots:
            return True

        prev = "0" * 16
        for snap in snapshots:
            if not snap.verify(prev):
                return False
            prev = snap.chain_hash
        return True

    def get_all_stages(self) -> list[str]:
        """Return all stage names with snapshots."""
        return list(self._snapshots.keys())

    def summary(self) -> dict[str, Any]:
        """Return a summary of all snapshots."""
        return {
            stage: {
                "count": len(snaps),
                "latest_hash": snaps[-1].chain_hash if snaps else "",
                "chain_valid": self.verify_chain(stage),
            }
            for stage, snaps in self._snapshots.items()
        }

    def _persist(self, snapshot: StageSnapshot) -> None:
        """Persist a snapshot to disk."""
        if not self._snapshot_dir:
            return
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = self._snapshot_dir / f"{snapshot.stage_name}_{snapshot.data_hash[:8]}.json"
        path.write_text(json.dumps({
            "stage": snapshot.stage_name,
            "data_hash": snapshot.data_hash,
            "timestamp": snapshot.timestamp,
            "prev_hash": snapshot.prev_hash,
            "chain_hash": snapshot.chain_hash,
            "data": snapshot.data,
        }, indent=2, default=str))
