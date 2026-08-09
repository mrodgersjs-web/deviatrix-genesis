"""Multi-objective Pareto optimization — find the Pareto frontier of survivors.

Instead of ranking by a single composite_z, find the set of survivors
that are non-dominated across multiple objectives:
  * composite_z (deviation magnitude)
  * mechanism_diversity (how different from other survivors)
  * novelty (distance from known archetypes)

Usage::

    from deviatrix_genesis.v5.pareto import pareto_frontier

    frontier = pareto_frontier(survivors)
"""

from __future__ import annotations

from typing import Any

__all__ = ["pareto_frontier", "is_dominated", "ParetoPoint"]


class ParetoPoint:
    """A survivor with multi-objective scores."""

    def __init__(self, name: str, objectives: dict[str, float], data: dict[str, Any]) -> None:
        self.name = name
        self.objectives = objectives
        self.data = data

    def dominates(self, other: "ParetoPoint") -> bool:
        """True if self dominates other (better in all objectives, strictly better in one)."""
        better_in_any = False
        for key in self.objectives:
            if self.objectives[key] < other.objectives[key]:
                return False
            if self.objectives[key] > other.objectives[key]:
                better_in_any = True
        return better_in_any


def is_dominated(point: ParetoPoint, others: list[ParetoPoint]) -> bool:
    """Check if point is dominated by any other point."""
    for other in others:
        if other is not point and other.dominates(point):
            return True
    return False


def pareto_frontier(
    survivors: list[dict[str, Any]],
    objectives: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Find the Pareto-optimal frontier among survivors.

    Default objectives: composite_z, mechanism_diversity, novelty.
    """
    if objectives is None:
        objectives = ["composite_z", "mechanism_diversity", "novelty"]

    if not survivors:
        return []

    # Build ParetoPoint objects
    points: list[ParetoPoint] = []
    for s in survivors:
        obj: dict[str, float] = {}
        for o in objectives:
            if o == "composite_z":
                obj[o] = s.get("composite_z", s.get("composite_z_median", 0.0))
            elif o == "mechanism_diversity":
                # Count unique mechanism families among survivors
                obj[o] = 1.0 if s.get("mechanism_family") else 0.0
            elif o == "novelty":
                obj[o] = s.get("anti_orthodoxy_new", s.get("composite_z", 0.0))
            else:
                obj[o] = s.get(o, 0.0)
        points.append(ParetoPoint(name=s.get("name", ""), objectives=obj, data=s))

    # Find Pareto frontier
    frontier: list[ParetoPoint] = []
    for p in points:
        dominated_by = [other for other in points if other is not p and other.dominates(p)]
        if not dominated_by:
            frontier.append(p)

    # Return as dicts with pareto_rank added
    result: list[dict[str, Any]] = []
    for p in frontier:
        entry = dict(p.data)
        entry["pareto_rank"] = 0
        entry["pareto_objectives"] = p.objectives
        result.append(entry)

    return sorted(result, key=lambda x: -x.get("composite_z", 0))
