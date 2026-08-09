"""Provenance anomaly detection — detect fabricated or corrupted provenance.

After the competitor frame revealed that Memory OS could be flooded
with fabricated provenance chains, this module detects anomalies in
provenance data:

  * Chain breakage: hash chain doesn't verify
  * Timestamp anomalies: entries out of order or from the future
  * Content anomalies: entries that don't match their claimed source
  * Volume anomalies: sudden spike in entries from one source
  * Duplication: identical content with different hashes

Usage::

    from deviatrix_genesis.v5.provenance_audit import ProvenanceAuditor

    auditor = ProvenanceAuditor()
    report = auditor.audit(run_history_entries)
    print(report.anomalies)
"""

from __future__ import annotations

import hashlib
import json
import statistics
import time
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ProvenanceAuditor", "AuditReport", "Anomaly"]


@dataclass
class Anomaly:
    """A detected provenance anomaly."""
    kind: str  # chain_break, timestamp, content, volume, duplication
    severity: str  # low, medium, high
    description: str
    entry_id: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditReport:
    """Result of a provenance audit."""
    entries_audited: int
    anomalies: list[Anomaly]
    chain_valid: bool = True
    volume_z_score: float = 0.0

    @property
    def has_anomalies(self) -> bool:
        return len(self.anomalies) > 0

    @property
    def high_severity(self) -> list[Anomaly]:
        return [a for a in self.anomalies if a.severity == "high"]

    def summary(self) -> str:
        lines = [f"Provenance Audit: {self.entries_audited} entries"]
        lines.append(f"  Chain valid: {self.chain_valid}")
        lines.append(f"  Anomalies: {len(self.anomalies)}")
        for a in self.anomalies:
            lines.append(f"    [{a.severity}] {a.kind}: {a.description}")
        return "\n".join(lines)


class ProvenanceAuditor:
    """Audit provenance data for anomalies."""

    def audit(self, entries: list[dict[str, Any]]) -> AuditReport:
        """Audit a list of provenance entries."""
        anomalies: list[Anomaly] = []

        if not entries:
            return AuditReport(entries_audited=0, anomalies=[])

        # Chain verification
        chain_anomalies = self._check_chain(entries)
        anomalies.extend(chain_anomalies)

        # Timestamp anomalies
        ts_anomalies = self._check_timestamps(entries)
        anomalies.extend(ts_anomalies)

        # Volume anomalies
        vol_anomalies, vol_z = self._check_volume(entries)
        anomalies.extend(vol_anomalies)

        # Duplication anomalies
        dup_anomalies = self._check_duplicates(entries)
        anomalies.extend(dup_anomalies)

        return AuditReport(
            entries_audited=len(entries),
            anomalies=anomalies,
            chain_valid=len(chain_anomalies) == 0,
            volume_z_score=vol_z,
        )

    def _check_chain(self, entries: list[dict[str, Any]]) -> list[Anomaly]:
        """Verify hash chain integrity."""
        anomalies: list[Anomaly] = []
        prev_hash = "0" * 64

        for i, entry in enumerate(entries):
            entry_hash = entry.get("chain_hash", entry.get("hash", ""))
            expected_prev = entry.get("prev_hash", "")

            if expected_prev and expected_prev != prev_hash:
                anomalies.append(Anomaly(
                    kind="chain_break",
                    severity="high",
                    description=f"Chain break at entry {i}: expected prev={prev_hash[:16]}, got={expected_prev[:16]}",
                    entry_id=entry.get("entry_id", f"entry_{i}"),
                ))

            prev_hash = entry_hash or prev_hash

        return anomalies

    def _check_timestamps(self, entries: list[dict[str, Any]]) -> list[Anomaly]:
        """Check for timestamp anomalies."""
        anomalies: list[Anomaly] = []
        now = time.time()

        timestamps = [e.get("timestamp", 0) for e in entries]

        # Check for future timestamps
        for i, ts in enumerate(timestamps):
            if ts > now + 3600:  # more than 1 hour in the future
                anomalies.append(Anomaly(
                    kind="timestamp",
                    severity="medium",
                    description=f"Entry {i} has future timestamp: {ts}",
                    entry_id=entries[i].get("entry_id", f"entry_{i}"),
                ))

        # Check for out-of-order timestamps
        for i in range(1, len(timestamps)):
            if timestamps[i] < timestamps[i - 1] and timestamps[i] > 0:
                anomalies.append(Anomaly(
                    kind="timestamp",
                    severity="low",
                    description=f"Entry {i} timestamp ({timestamps[i]}) < entry {i-1} ({timestamps[i-1]})",
                    entry_id=entries[i].get("entry_id", f"entry_{i}"),
                ))

        return anomalies

    def _check_volume(self, entries: list[dict[str, Any]]) -> tuple[list[Anomaly], float]:
        """Check for volume anomalies (sudden spikes)."""
        anomalies: list[Anomaly] = []

        # Group by source
        sources: dict[str, int] = {}
        for entry in entries:
            source = entry.get("source", entry.get("operator", "unknown"))
            sources[source] = sources.get(source, 0) + 1

        if len(sources) < 2:
            return anomalies, 0.0

        counts = list(sources.values())
        if len(counts) < 2:
            return anomalies, 0.0

        mean_count = statistics.mean(counts)
        stdev = statistics.stdev(counts) if len(counts) > 1 else 1.0

        # Check for z-score > 2 (unusual volume)
        for source, count in sources.items():
            if stdev > 0:
                z = (count - mean_count) / stdev
                if z > 2.0:
                    anomalies.append(Anomaly(
                        kind="volume",
                        severity="medium",
                        description=f"Source '{source}' has {count} entries (z={z:.1f} vs mean={mean_count:.1f})",
                        details={"source": source, "count": count, "z": z},
                    ))

        # Overall volume z-score
        vol_z = max((count - mean_count) / stdev for count in counts) if stdev > 0 else 0.0

        return anomalies, vol_z

    def _check_duplicates(self, entries: list[dict[str, Any]]) -> list[Anomaly]:
        """Check for content duplication with different hashes."""
        anomalies: list[Anomaly] = []

        # Group by content hash
        content_hashes: dict[str, list[int]] = {}
        for i, entry in enumerate(entries):
            content = json.dumps(entry.get("content", entry.get("data", {})), sort_keys=True)
            chash = hashlib.sha256(content.encode()).hexdigest()[:16]
            if chash not in content_hashes:
                content_hashes[chash] = []
            content_hashes[chash].append(i)

        # Find duplicates with different entry hashes
        for chash, indices in content_hashes.items():
            if len(indices) > 1:
                entry_hashes = set()
                for idx in indices:
                    eh = entries[idx].get("chain_hash", entries[idx].get("hash", ""))
                    entry_hashes.add(eh)

                if len(entry_hashes) > 1:
                    anomalies.append(Anomaly(
                        kind="duplication",
                        severity="high",
                        description=f"Same content at entries {indices} but different hashes: {entry_hashes}",
                        details={"content_hash": chash, "entry_indices": indices},
                    ))

        return anomalies
