"""Live text-based telemetry dashboard.

Subscribes to :class:`EventBus` events and renders progress bars,
ASCII sparklines, and quality metrics.
"""

from __future__ import annotations

from typing import Any

from .telemetry import EventBus, TelemetryEvent

__all__ = ["Dashboard"]

# Sparkline characters for z-score visualisation.
_SPARK = "▁▂▃▄▅▆▇█"


def _sparkline(values: list[float]) -> str:
    """Render *values* as an ASCII sparkline."""
    if not values:
        return ""
    lo, hi = min(values), max(values)
    span = hi - lo if hi != lo else 1.0
    return "".join(
        _SPARK[min(int((v - lo) / span * 7), 7)]
        for v in values
    )


class Dashboard:
    """Text-based telemetry dashboard."""

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._sub_id: int | None = None
        self._rounds: list[dict[str, Any]] = []
        self._current_round: int = 0
        self._expedition_count: int = 0
        self._total_expeditions: int = 0
        self._memory_writes: int = 0
        self._memory_errors: int = 0
        self._hybrids: int = 0
        self._last_expeditions: list[dict[str, Any]] = []

    def start(self, total_expeditions: int = 0) -> None:
        self._total_expeditions = total_expeditions
        self._sub_id = self.bus.subscribe(self._on_event)

    def stop(self) -> None:
        if self._sub_id is not None:
            self.bus.unsubscribe(self._sub_id)
            self._sub_id = None

    def _on_event(self, evt: TelemetryEvent) -> None:
        if evt.event_type == "round_start":
            self._current_round = evt.payload.get("round", self._current_round + 1)
            self._expedition_count = 0
        elif evt.event_type == "round_end":
            self._rounds.append({
                "round": evt.payload.get("round", self._current_round),
                "survivors": evt.payload.get("survivors_count", 0),
                "median_z": evt.payload.get("median_z", 0.0),
                "max_z": evt.payload.get("max_z", 0.0),
                "wall_ms": evt.payload.get("wall_ms", 0.0),
            })
        elif evt.event_type == "expedition_complete":
            self._expedition_count += 1
            z = evt.payload.get("z", 0.0)
            band = evt.payload.get("band", "")
            kind = evt.payload.get("kind", "")
            diamond = evt.payload.get("diamond", "")
            self._last_expeditions.append({
                "diamond": diamond, "kind": kind, "z": z, "band": band,
            })
            # Keep only last 9
            if len(self._last_expeditions) > 9:
                self._last_expeditions = self._last_expeditions[-9:]
        elif evt.event_type == "memory_write":
            self._memory_writes += 1
        elif evt.event_type == "memory_error":
            self._memory_errors += 1
        elif evt.event_type == "fusion_hybrid":
            self._hybrids += 1

    def render(self) -> str:
        """Return the current dashboard state as formatted text."""
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("  DEVIATRIX GENESIS v5 — LIVE TELEMETRY")
        lines.append("=" * 60)

        # Progress bar
        if self._total_expeditions > 0:
            pct = self._expedition_count / self._total_expeditions
            filled = int(pct * 30)
            bar = "█" * filled + "░" * (30 - filled)
            lines.append(f"  [{bar}] {self._expedition_count}/{self._total_expeditions} expeditions")
        else:
            lines.append(f"  Round {self._current_round} | {self._expedition_count} expeditions this round")

        # Convergence sparkline
        if self._rounds:
            z_values = [r["median_z"] for r in self._rounds]
            lines.append(f"  Z-trend:  {_sparkline(z_values)}  (median σ per round)")
            latest = self._rounds[-1]
            lines.append(
                f"  Latest:   round={latest['round']}  survivors={latest['survivors']}  "
                f"median_z={latest['median_z']:.2f}  max_z={latest['max_z']:.2f}"
            )

        # Quality
        if self._rounds:
            best = max(r["max_z"] for r in self._rounds)
            lines.append(f"  Best σ across all rounds: {best:.2f}")

        # Memory OS
        lines.append(f"  Memory OS: {self._memory_writes} writes, {self._memory_errors} errors")

        # Fusion
        if self._hybrids:
            lines.append(f"  Cross-brief hybrids: {self._hybrids}")

        # Last expeditions
        if self._last_expeditions:
            lines.append("  Last expeditions:")
            for ep in self._last_expeditions:
                z_str = f"{ep['z']:+.2f}σ"
                lines.append(f"    {ep['diamond']:>12} {ep['kind']:<10} z={z_str:>10}  {ep['band']}")

        lines.append("=" * 60)
        return "\n".join(lines)
