"""Provenance chain — SHA-256 hash chain from brief to memory.

Every step in the pipeline produces a hash that includes the previous
step's hash, creating an immutable audit trail.

Brief hash → Formula hash → Packet hash → Survivor hash → Memory hash

Usage::

    from deviatrix_genesis.v5.provenance import ProvenanceChain

    chain = ProvenanceChain()
    chain.add_step("brief", {"text": "GTM strategy"})
    chain.add_step("formula", {"expression": "x**2 + 3*x"})
    print(chain.verify())  # True
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ProvenanceChain", "ProvenanceStep"]


@dataclass
class ProvenanceStep:
    """One step in the provenance chain."""
    step_type: str  # brief, formula, packet, survivor, memory
    data_hash: str
    prev_hash: str
    chain_hash: str
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ProvenanceChain:
    """SHA-256 hash chain for pipeline provenance."""

    def __init__(self) -> None:
        self._steps: list[ProvenanceStep] = []
        self._prev_hash = "0" * 64  # genesis hash

    def add_step(
        self,
        step_type: str,
        data: dict[str, Any],
        timestamp: float = 0.0,
    ) -> str:
        """Add a step and return the chain hash."""
        data_str = json.dumps(data, sort_keys=True, default=str)
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()

        chain_input = f"{self._prev_hash}:{data_hash}"
        chain_hash = hashlib.sha256(chain_input.encode()).hexdigest()

        step = ProvenanceStep(
            step_type=step_type,
            data_hash=data_hash,
            prev_hash=self._prev_hash,
            chain_hash=chain_hash,
            timestamp=timestamp,
            metadata=data,
        )
        self._steps.append(step)
        self._prev_hash = chain_hash
        return chain_hash

    def verify(self) -> bool:
        """Verify the entire chain is intact."""
        prev = "0" * 64
        for step in self._steps:
            if step.prev_hash != prev:
                return False
            chain_input = f"{prev}:{step.data_hash}"
            expected = hashlib.sha256(chain_input.encode()).hexdigest()
            if step.chain_hash != expected:
                return False
            prev = step.chain_hash
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [
                {
                    "type": s.step_type,
                    "data_hash": s.data_hash[:16],
                    "chain_hash": s.chain_hash[:16],
                    "prev_hash": s.prev_hash[:16],
                }
                for s in self._steps
            ],
            "length": len(self._steps),
            "valid": self.verify(),
            "tip": self._prev_hash[:16] if self._prev_hash else "",
        }

    @property
    def tip(self) -> str:
        return self._prev_hash

    @property
    def length(self) -> int:
        return len(self._steps)
