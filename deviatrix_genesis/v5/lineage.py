"""Formula lineage graph — track parent-child relationships across rounds.

Every formula that enters the pipeline gets a lineage record. When
survivors are fused into hybrids, the lineage graph captures the
full ancestry.

Usage::

    from deviatrix_genesis.v5.lineage import LineageTracker

    tracker = LineageTracker()
    tracker.register("idea_1", formula="x**2", parents=[])
    tracker.register("hybrid_1", formula="x**2 + sin(x)", parents=["idea_1", "idea_2"])
    graph = tracker.to_graph()
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["LineageNode", "LineageTracker"]


@dataclass
class LineageNode:
    """A single node in the lineage graph."""
    name: str
    formula: str
    parents: list[str] = field(default_factory=list)
    round_number: int = 0
    composite_z: float = 0.0
    mechanism_family: str = ""
    status: str = "active"  # active | dropped | hybrid


class LineageTracker:
    """Track formula lineage across pipeline rounds."""

    def __init__(self) -> None:
        self._nodes: dict[str, LineageNode] = {}

    def register(
        self,
        name: str,
        formula: str,
        parents: list[str] | None = None,
        round_number: int = 0,
        composite_z: float = 0.0,
        mechanism_family: str = "",
        status: str = "active",
    ) -> None:
        """Register a formula with its lineage."""
        self._nodes[name] = LineageNode(
            name=name, formula=formula, parents=parents or [],
            round_number=round_number, composite_z=composite_z,
            mechanism_family=mechanism_family, status=status,
        )

    def mark_dropped(self, name: str) -> None:
        if name in self._nodes:
            self._nodes[name].status = "dropped"

    def get_ancestors(self, name: str, max_depth: int = 10) -> list[str]:
        """Get all ancestors of a formula up to max_depth."""
        visited: set[str] = set()
        frontier = [name]
        for _ in range(max_depth):
            next_frontier: list[str] = []
            for n in frontier:
                if n in visited:
                    continue
                visited.add(n)
                node = self._nodes.get(n)
                if node:
                    next_frontier.extend(node.parents)
            if not next_frontier:
                break
            frontier = next_frontier
        return sorted(visited - {name})

    def get_descendants(self, name: str) -> list[str]:
        """Get all descendants of a formula."""
        descendants: list[str] = []
        for node in self._nodes.values():
            if name in node.parents:
                descendants.append(node.name)
                descendants.extend(self.get_descendants(node.name))
        return sorted(set(descendants))

    def to_graph(self) -> dict[str, Any]:
        """Export the lineage graph as a serializable dict."""
        return {
            "nodes": [
                {
                    "name": n.name, "formula": n.formula, "parents": n.parents,
                    "round": n.round_number, "z": n.composite_z,
                    "family": n.mechanism_family, "status": n.status,
                }
                for n in self._nodes.values()
            ],
            "edges": [
                {"from": parent, "to": n.name}
                for n in self._nodes.values()
                for parent in n.parents
            ],
            "stats": {
                "total": len(self._nodes),
                "active": sum(1 for n in self._nodes.values() if n.status == "active"),
                "dropped": sum(1 for n in self._nodes.values() if n.status == "dropped"),
                "hybrid": sum(1 for n in self._nodes.values() if n.status == "hybrid"),
                "max_depth": self._max_depth(),
            },
        }

    def to_mermaid(self) -> str:
        """Export as Mermaid diagram."""
        lines = ["graph TD"]
        for n in self._nodes.values():
            label = f"{n.name}<br/>z={n.composite_z:.1f}"
            style = ""
            if n.status == "dropped":
                style = ":::dropped"
            elif n.status == "hybrid":
                style = ":::hybrid"
            lines.append(f"  {n.name}[\"{label}\"]{style}")
            for parent in n.parents:
                lines.append(f"  {parent} --> {n.name}")
        lines.append("  classDef dropped fill:#330000,stroke:#ff4444")
        lines.append("  classDef hybrid fill:#003333,stroke:#00ffff")
        return "\n".join(lines)

    def save(self, path: str | Path) -> None:
        """Save lineage graph to JSON."""
        Path(path).write_text(json.dumps(self.to_graph(), indent=2))

    def _max_depth(self) -> int:
        """Compute the maximum depth of the lineage graph."""
        max_d = 0
        for node in self._nodes.values():
            depth = 0
            current = node.name
            visited: set[str] = set()
            while current in self._nodes and current not in visited:
                visited.add(current)
                parents = self._nodes[current].parents
                if not parents:
                    break
                current = parents[0]
                depth += 1
            max_d = max(max_d, depth)
        return max_d
