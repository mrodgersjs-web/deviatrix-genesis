"""Structured telemetry event bus.

Every stage emits a typed event.  Subscribers can filter by event type
or source.  Built-in :class:`ConvergenceMetrics` per round.
"""

from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Callable

__all__ = ["TelemetryEvent", "EventBus", "ConvergenceMetrics", "TelemetryCollector", "get_bus"]


# ────────────────────────────────────────────────────────────────────
# Event
# ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TelemetryEvent:
    timestamp: float          # time.monotonic()
    event_type: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────
# Convergence snapshot
# ────────────────────────────────────────────────────────────────────


@dataclass
class ConvergenceMetrics:
    round_number: int
    survivors_count: int
    median_z: float
    max_z: float
    z_improvement_vs_prev: float
    wall_clock_ms: float


# ────────────────────────────────────────────────────────────────────
# EventBus
# ────────────────────────────────────────────────────────────────────

_SubscriberFn = Callable[[TelemetryEvent], None]
_Counter = 0  # module-level counter for unique ids


class EventBus:
    """Thread-safe (asyncio-safe) publish/subscribe event bus."""

    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []
        self._subscribers: dict[int, _SubscriberFn] = {}
        self._next_id: int = 0
        self._lock = asyncio.Lock()

    def emit(self, event_type: str, source: str, **payload: Any) -> TelemetryEvent:
        evt = TelemetryEvent(
            timestamp=time.monotonic(), event_type=event_type,
            source=source, payload=payload,
        )
        self._events.append(evt)
        for cb in list(self._subscribers.values()):
            try:
                cb(evt)
            except Exception:
                pass  # never let a subscriber crash the emitter
        return evt

    def subscribe(self, callback: _SubscriberFn) -> int:
        sid = self._next_id
        self._next_id += 1
        self._subscribers[sid] = callback
        return sid

    def unsubscribe(self, subscription_id: int) -> None:
        self._subscribers.pop(subscription_id, None)

    def get_events(
        self,
        event_type: str | None = None,
        source: str | None = None,
        since: float | None = None,
    ) -> list[TelemetryEvent]:
        out = self._events
        if event_type is not None:
            out = [e for e in out if e.event_type == event_type]
        if source is not None:
            out = [e for e in out if e.source == source]
        if since is not None:
            out = [e for e in out if e.timestamp >= since]
        return out

    def clear(self) -> None:
        self._events.clear()


# ────────────────────────────────────────────────────────────────────
# Collector
# ────────────────────────────────────────────────────────────────────


class TelemetryCollector:
    """Subscribes to the bus and computes per-round convergence metrics."""

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self.rounds: list[ConvergenceMetrics] = []
        self._sub_id: int | None = None
        self._prev_median_z: float = 0.0
        self._round_start: float = 0.0
        # Quality metrics
        self.total_expeditions: int = 0
        self.total_passed: int = 0
        self.total_wall_breaches: int = 0
        self.diamond_timings: list[float] = []
        self.expedition_z_scores: list[float] = []

    def start(self) -> None:
        self._sub_id = self.bus.subscribe(self._on_event)

    def stop(self) -> None:
        if self._sub_id is not None:
            self.bus.unsubscribe(self._sub_id)
            self._sub_id = None

    def _on_event(self, evt: TelemetryEvent) -> None:
        if evt.event_type == "round_start":
            self._round_start = evt.timestamp
        elif evt.event_type == "round_end":
            elapsed = (evt.timestamp - self._round_start) * 1000
            median_z = evt.payload.get("median_z", 0.0)
            improvement = median_z - self._prev_median_z
            self.rounds.append(ConvergenceMetrics(
                round_number=evt.payload.get("round", len(self.rounds) + 1),
                survivors_count=evt.payload.get("survivors_count", 0),
                median_z=median_z,
                max_z=evt.payload.get("max_z", 0.0),
                z_improvement_vs_prev=improvement,
                wall_clock_ms=elapsed,
            ))
            self._prev_median_z = median_z
        elif evt.event_type == "expedition_complete":
            self.total_expeditions += 1
            z = evt.payload.get("z", 0.0)
            self.expedition_z_scores.append(z)
            if abs(z) < 30.0:
                self.total_passed += 1
            else:
                self.total_wall_breaches += 1
        elif evt.event_type == "diamond_complete":
            wall_ms = evt.payload.get("wall_ms", 0.0)
            self.diamond_timings.append(wall_ms)

    def quality_summary(self) -> dict[str, Any]:
        """Return aggregate quality metrics."""
        pass_rate = (self.total_passed / self.total_expeditions * 100) if self.total_expeditions else 0.0
        avg_diamond_ms = (sum(self.diamond_timings) / len(self.diamond_timings)) if self.diamond_timings else 0.0
        z_scores = self.expedition_z_scores
        return {
            "total_expeditions": self.total_expeditions,
            "pass_rate_pct": round(pass_rate, 1),
            "wall_breaches": self.total_wall_breaches,
            "avg_diamond_ms": round(avg_diamond_ms, 1),
            "z_mean": round(statistics.mean(z_scores), 2) if z_scores else 0.0,
            "z_median": round(statistics.median(z_scores), 2) if z_scores else 0.0,
            "z_stdev": round(statistics.stdev(z_scores), 2) if len(z_scores) > 1 else 0.0,
            "z_min": round(min(z_scores), 2) if z_scores else 0.0,
            "z_max": round(max(z_scores), 2) if z_scores else 0.0,
        }


# ────────────────────────────────────────────────────────────────────
# Module-level singleton
# ────────────────────────────────────────────────────────────────────

_bus: EventBus | None = None


def get_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus
