"""Core schemas for Deviatrix Genesis.

These dataclasses are the *only* authoritative contracts between layers.
The LLM may not emit freeform sigma claims; it must emit a
:class:`MathClaim`. The verifier must consume a :class:`MathProofPacket`,
not LLM prose.

Schema hierarchy
================

MathClaim          (LLM generator → SymPy MCP)
   └─ SymbolProof   (SymPy MCP → numerical executor)
        └─ EmpiricalProof  (numerical executor → verifier)
             └─ DeviationProof  (statistical evaluator → verifier)
                  └─ AdversarialProof  (verifier → routing)
                       └─ MathProofPacket  (sealed by verifier)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


# ────────────────────────────────────────────────────────────────────
# Enums
# ────────────────────────────────────────────────────────────────────


class DiamondKind(str, Enum):
    OPPORTUNITY = "opportunity"
    INVENTION = "invention"
    PROOF = "proof"


class ExpeditionKind(str, Enum):
    POSITIVE_TAIL = "positive_tail"
    NEGATIVE_TAIL = "negative_tail"
    REPAIRED_TAIL = "repaired_tail"


class GateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    MUTATE = "MUTATE"
    ESCALATE = "ESCALATE"


class Direction(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    REPAIRED = "repaired"


class FailureClass(str, Enum):
    SYMBOLIC_ERROR = "symbolic_error"
    UNSTABLE_SIGMA = "unstable_sigma"
    LOW_DEVIATION = "low_deviation"
    DECORATIVE_DEVIATION = "decorative_deviation"
    INCOHERENT_OUTLIER = "incoherent_outlier"
    CORPUS_ARTIFACT = "corpus_artifact"
    IMPOSSIBLE_CLAIM = "impossible_claim"
    THRESHOLD_EXCEEDED = "threshold_exceeded"


# ────────────────────────────────────────────────────────────────────
# MathClaim: generator → SymPy MCP
# ────────────────────────────────────────────────────────────────────


@dataclass
class MathClaim:
    """An executable claim an LLM generator emits.

    The generator MUST NOT emit freeform ``"this is 31σ from the median"``
    strings. It must emit one of these, with an explicit reference
    population and an explicit falsifier.
    """

    expression: str  # SymPy-parseable formula
    symbols: list[str] = field(default_factory=list)
    assumptions: dict[str, Any] = field(default_factory=dict)
    reference_population: list[float] = field(default_factory=list)
    estimator: str = "robust_madz"  # default robust estimator
    expected_result: float | None = None
    falsifier: str = ""  # what would refute this claim

    # provenance
    candidate_hash: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_hash:
            self.candidate_hash = self._hash()

    def _hash(self) -> str:
        body = json.dumps(
            {
                "expression": self.expression,
                "symbols": self.symbols,
                "assumptions": self.assumptions,
                "estimator": self.estimator,
                "expected_result": self.expected_result,
                "falsifier": self.falsifier,
            },
            sort_keys=True,
        )
        return hashlib.sha256(body.encode()).hexdigest()[:16]


# ────────────────────────────────────────────────────────────────────
# SymbolicProof: SymPy MCP → numerical executor
# ────────────────────────────────────────────────────────────────────


@dataclass
class SymbolicProof:
    parse_status: str = "ERROR"  # OK | ERROR
    dimensional_consistency: bool = False
    simplified_expression: str = ""
    assumptions_used: dict[str, Any] = field(default_factory=dict)
    domain_restrictions: list[str] = field(default_factory=list)
    singularities: list[str] = field(default_factory=list)
    derivative_checks: dict[str, Any] = field(default_factory=dict)
    inequality_solution: str = ""
    counterexample: dict[str, Any] | None = None
    status: str = "FAIL"  # PASS | FAIL | WARN

    # error reporting
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ────────────────────────────────────────────────────────────────────
# EmpiricalProof: numerical executor → statistical evaluator
# ────────────────────────────────────────────────────────────────────


@dataclass
class EmpiricalProof:
    metric: str = ""
    candidate_value: float = 0.0
    reference_population_hash: str = ""
    reference_count: int = 0
    median: float = 0.0
    mad: float = 0.0
    qn: float = 0.0
    robust_madz: float = 0.0
    qn_z: float = 0.0
    bootstrap_interval: tuple[float, float] = (0.0, 0.0)
    alternate_corpus_z: float = 0.0
    certified_z: float = 0.0  # conservative_minimum of the above

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # tuple serialisation
        d["bootstrap_interval"] = list(self.bootstrap_interval)
        return d


# ────────────────────────────────────────────────────────────────────
# DeviationProof: structural vs behavioral split
# ────────────────────────────────────────────────────────────────────


@dataclass
class DeviationProof:
    direction: Direction = Direction.POSITIVE
    structural_distance: float = 0.0
    behavioral_distance: float = 0.0
    composite_distance: float = 0.0  # 0.3 * structural + 0.7 * behavioral
    target_band: str = ""  # e.g. "+20σ"
    ceiling_breach: bool = False
    deep_review_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "direction": self.direction.value}


# ────────────────────────────────────────────────────────────────────
# AdversarialProof: Pass C
# ────────────────────────────────────────────────────────────────────


@dataclass
class AdversarialProof:
    perturbations_run: list[str] = field(default_factory=list)
    estimator_sensitivity: dict[str, float] = field(default_factory=dict)
    corpus_sensitivity: dict[str, float] = field(default_factory=dict)
    weight_sensitivity: dict[str, float] = field(default_factory=dict)
    nearest_neighbors: list[str] = field(default_factory=list)
    deduplication_result: str = ""
    falsification_result: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ────────────────────────────────────────────────────────────────────
# Routing & Verifier
# ────────────────────────────────────────────────────────────────────


@dataclass
class RoutingDecision:
    gate_status: GateStatus = GateStatus.FAIL
    failure_class: FailureClass | None = None
    engine_fired: str = ""
    successor_candidate_hash: str = ""
    band: str = ""  # sigma band, e.g. "+20σ"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "gate_status": self.gate_status.value,
            "failure_class": self.failure_class.value if self.failure_class else None,
        }


@dataclass
class VerifierDecision:
    verifier_id: str = ""
    decision: GateStatus = GateStatus.FAIL
    reason: str = ""
    signature: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "decision": self.decision.value,
        }


# ────────────────────────────────────────────────────────────────────
# MathProofPacket: the sealed artifact
# ────────────────────────────────────────────────────────────────────


@dataclass
class MathProofPacket:
    run_id: str
    diamond: DiamondKind
    expedition: ExpeditionKind
    iqrsqpi_cycle: int = 0
    candidate_hash: str = ""

    symbolic: SymbolicProof = field(default_factory=SymbolicProof)
    empirical: EmpiricalProof = field(default_factory=EmpiricalProof)
    deviation: DeviationProof = field(default_factory=DeviationProof)
    adversarial: AdversarialProof = field(default_factory=AdversarialProof)
    routing: RoutingDecision = field(default_factory=RoutingDecision)
    verifier: VerifierDecision = field(default_factory=VerifierDecision)

    sealed_hash: str = ""

    def seal(self) -> str:
        """Compute the sealed hash. Called by the verifier at the end."""
        body = json.dumps(
            {
                "run_id": self.run_id,
                "diamond": self.diamond.value,
                "expedition": self.expedition.value,
                "iqrsqpi_cycle": self.iqrsqpi_cycle,
                "candidate_hash": self.candidate_hash,
                "symbolic": self.symbolic.to_dict(),
                "empirical": self.empirical.to_dict(),
                "deviation": self.deviation.to_dict(),
                "adversarial": self.adversarial.to_dict(),
                "routing": self.routing.to_dict(),
            },
            sort_keys=True,
        )
        self.sealed_hash = hashlib.sha256(body.encode()).hexdigest()[:32]
        return self.sealed_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "diamond": self.diamond.value,
            "expedition": self.expedition.value,
            "iqrsqpi_cycle": self.iqrsqpi_cycle,
            "candidate_hash": self.candidate_hash,
            "symbolic": self.symbolic.to_dict(),
            "empirical": self.empirical.to_dict(),
            "deviation": self.deviation.to_dict(),
            "adversarial": self.adversarial.to_dict(),
            "routing": self.routing.to_dict(),
            "verifier": self.verifier.to_dict(),
            "sealed_hash": self.sealed_hash,
        }


# ────────────────────────────────────────────────────────────────────
# Diamond harness tuple (H, E, T, C, S, L, V)
# ────────────────────────────────────────────────────────────────────


@dataclass
class DiamondHarness:
    """Holds the per-diamond environment, trace, context, skills, loop, verifier."""

    H_environment: dict[str, Any] = field(default_factory=dict)
    T_trace: list[dict[str, Any]] = field(default_factory=list)
    C_context: dict[str, Any] = field(default_factory=dict)
    S_skills: list[str] = field(default_factory=list)
    L_loop: dict[str, Any] = field(default_factory=dict)
    V_verifier: dict[str, Any] = field(default_factory=dict)

    def trace(self, entry: dict[str, Any]) -> None:
        self.T_trace.append(entry)


# ────────────────────────────────────────────────────────────────────
# IQRSQPI stage tracking
# ────────────────────────────────────────────────────────────────────


class IQRSQPIStage(str, Enum):
    INTENT = "intent"
    QUESTION = "question"
    RESEARCH = "research"
    SOLUTION = "solution"
    QUALITY = "quality"
    PROOF = "proof"
    INTEGRATE = "integrate"


@dataclass
class StageRecord:
    stage: IQRSQPIStage
    cycle: int
    passed: bool = False
    energy: float = 1.0
    theta: float = 0.2
    open_questions: int = 0
    notes: str = ""

    def advance_eligible(self) -> bool:
        # The gate is purely energy + open_questions; ``passed`` is the
        # *output* of the gate, not an input. We must not include it in
        # the predicate or we get a chicken-and-egg bug.
        return self.energy <= self.theta and self.open_questions == 0
