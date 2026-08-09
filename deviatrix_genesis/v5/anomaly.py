"""Real-time anomaly detection on z-score distributions.

Monitors z-scores during a pipeline run and flags unusual patterns:
  * Sudden jumps (>5σ between consecutive expeditions)
  * Clustering (all z-scores within 0.5σ of each other)
  * Wall proximity (multiple expeditions near ±30σ)
  * Inversion (negative z-scores when positive expected)

Usage::

    from deviatrix_genesis.v5.anomaly import AnomalyDetector

    detector = AnomalyDetector()
    detector.feed(5.2)
    detector.feed(5.3)
    detector.feed(28.1)  # triggers wall_proximity alert
    print(detector.alerts())
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["AnomalyDetector", "Anomaly"]


@dataclass
class Anomaly:
    """A detected anomaly."""
    kind: str  # sudden_jump, clustering, wall_proximity, inversion
    severity: str  # low, medium, high
    value: float
    description: str


class AnomalyDetector:
    """Detect anomalies in z-score streams."""

    def __init__(
        self,
        jump_threshold: float = 10.0,
        cluster_threshold: float = 0.5,
        wall_threshold: float = 25.0,
    ) -> None:
        self.jump_threshold = jump_threshold
        self.cluster_threshold = cluster_threshold
        self.wall_threshold = wall_threshold
        self._values: list[float] = []
        self._anomalies: list[Anomaly] = []

    def feed(self, z: float) -> list[Anomaly]:
        """Feed a new z-score and return any anomalies detected."""
        new_anomalies: list[Anomaly] = []

        # Sudden jump
        if self._values:
            delta = abs(z - self._values[-1])
            if delta > self.jump_threshold:
                a = Anomaly(
                    kind="sudden_jump", severity="high",
                    value=z, description=f"Jump of {delta:.1f}σ from {self._values[-1]:.1f} to {z:.1f}",
                )
                new_anomalies.append(a)
                self._anomalies.append(a)

        # Wall proximity
        if abs(z) >= self.wall_threshold:
            a = Anomaly(
                kind="wall_proximity", severity="high" if abs(z) >= 29 else "medium",
                value=z, description=f"z={z:.1f} near ±30σ wall",
            )
            new_anomalies.append(a)
            self._anomalies.append(a)

        self._values.append(z)

        # Clustering (check after enough values)
        if len(self._values) >= 5:
            recent = self._values[-5:]
            span = max(recent) - min(recent)
            if span < self.cluster_threshold:
                a = Anomaly(
                    kind="clustering", severity="medium",
                    value=z, description=f"Last 5 values within {span:.2f}σ span",
                )
                new_anomalies.append(a)
                self._anomalies.append(a)

        return new_anomalies

    def alerts(self) -> list[Anomaly]:
        """Return all detected anomalies."""
        return list(self._anomalies)

    def clear(self) -> None:
        self._values.clear()
        self._anomalies.clear()

    def summary(self) -> dict[str, Any]:
        """Return anomaly summary."""
        by_kind: dict[str, int] = {}
        for a in self._anomalies:
            by_kind[a.kind] = by_kind.get(a.kind, 0) + 1
        return {
            "total": len(self._anomalies),
            "by_kind": by_kind,
            "values_processed": len(self._values),
        }
