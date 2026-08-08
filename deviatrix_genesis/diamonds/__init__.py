"""Diamond Harness — the H/E/T/C/S/L/V tuple.

Each diamond (Opportunity, Invention, Proof) is a sealed MathExec
subsystem. The harness holds the environment, trace, context, skills,
loop, and verifier authority. The conductor instantiates one harness
per diamond; the expeditions mutate it.

The fail_routes table maps every failure class to the recovery action.
A failure that has no mapped route is a hard stop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .. import schemas

__all__ = ["DiamondHarness", "FAIL_ROUTES", "apply_fail_route"]


# ────────────────────────────────────────────────────────────────────
# DiamondHarness (H, E, T, C, S, L, V)
# ────────────────────────────────────────────────────────────────────


@dataclass
class DiamondHarness:
    """Per-diamond harness tuple.

    The dataclass lives in ``schemas.DiamondHarness`` for the pure data
    shape; this subclass wires the methods (skill dispatch, fail-route
    routing) on top.
    """

    diamond: schemas.DiamondKind = schemas.DiamondKind.OPPORTUNITY
    H_environment: dict[str, Any] = field(default_factory=dict)
    T_trace: list[dict[str, Any]] = field(default_factory=list)
    C_context: dict[str, Any] = field(default_factory=dict)
    S_skills: list[str] = field(default_factory=list)
    L_loop: dict[str, Any] = field(default_factory=dict)
    V_verifier: dict[str, Any] = field(default_factory=dict)

    # internal counters
    n_expeditions: int = 0
    n_packets: int = 0

    def __post_init__(self) -> None:
        self.S_skills = [
            "sympy_mcp.parse",
            "sympy_mcp.simplify",
            "sympy_mcp.solve",
            "sympy_mcp.diff",
            "sympy_mcp.integrate",
            "sympy_mcp.check_assumptions",
            "mathexec.robust_madz",
            "mathexec.qn_scale",
            "mathexec.bootstrap",
            "mathexec.sensitivity",
            "mathexec.counterexample_search",
        ]
        self.V_verifier = {
            "independent": True,
            "termination_authority": "outcome_verifier_only",
            "reads": [
                "symbolic_proof_packet",
                "numerical_proof_packet",
                "adversarial_proof_packet",
            ],
            "never_accepts": [
                "narrated_sigma",
                "self_reported_novelty",
                "unexecuted_formulas",
                "hidden_retries",
            ],
        }

    # trace
    def trace(self, entry: dict[str, Any]) -> None:
        self.T_trace.append(entry)

    # context isolation (the doctrine requires the generator cannot
    # alter the reference population or select the final estimator).
    def assert_isolation(self, packet: schemas.MathProofPacket) -> bool:
        return (
            packet.candidate_hash != ""
            and packet.empirical.reference_population_hash != ""
            and packet.empirical.metric in {"robust_madz", "qn_z", "certified_z"}
        )


# ────────────────────────────────────────────────────────────────────
# Fail-routes table
# ────────────────────────────────────────────────────────────────────


FAIL_ROUTES: dict[str, str] = {
    "symbolic_error": "formula_repair",
    "unstable_sigma": "baseline_rebuild",
    "low_deviation": "deviate_engine",
    "decorative_deviation": "mechanism_furnace",
    "incoherent_outlier": "contradiction_repair",
    "corpus_artifact": "alternate_corpus",
    "impossible_claim": "physics_gate",
    "threshold_exceeded": "hard_stop",
}


def apply_fail_route(
    harness: DiamondHarness,
    failure_class: schemas.FailureClass,
    packet: schemas.MathProofPacket | None = None,
) -> dict[str, Any]:
    """Apply the doctrine-mandated recovery action.

    Returns a small report describing the route taken. The conductor
    consumes this and decides whether to retry, mutate, or escalate.
    """
    action = FAIL_ROUTES.get(failure_class.value, "hard_stop")
    harness.trace(
        {
            "kind": "fail_route",
            "diamond": harness.diamond.value,
            "failure_class": failure_class.value,
            "action": action,
            "candidate_hash": packet.candidate_hash if packet else "",
        }
    )
    return {
        "failure_class": failure_class.value,
        "action": action,
        "diamond": harness.diamond.value,
        "trace_index": len(harness.T_trace) - 1,
    }


# ────────────────────────────────────────────────────────────────────
# Skill dispatcher (the LLM calls into the harness, not into sympy_mcp
# directly — the harness is the authority on which skill is allowed)
# ────────────────────────────────────────────────────────────────────


def dispatch_skill(
    harness: DiamondHarness, skill_name: str, **kwargs: Any
) -> dict[str, Any]:
    """Invoke a registered skill on the harness.

    The harness owns the skill list; the LLM cannot call a skill that
    is not registered. This is the *capability gate*.
    """
    if skill_name not in harness.S_skills:
        raise PermissionError(
            f"skill {skill_name!r} not registered on harness "
            f"({harness.diamond.value}); refusing dispatch."
        )

    harness.trace(
        {
            "kind": "skill_dispatch",
            "skill": skill_name,
            "args_keys": sorted(kwargs.keys()),
        }
    )

    if skill_name.startswith("sympy_mcp."):
        from ..sympy_mcp import server as sympy_server

        tool_map = {
            "sympy_mcp.parse": sympy_server.tool_parse,
            "sympy_mcp.simplify": sympy_server.tool_simplify,
            "sympy_mcp.solve": sympy_server.tool_solve,
            "sympy_mcp.diff": sympy_server.tool_diff,
            "sympy_mcp.integrate": sympy_server.tool_integrate,
            "sympy_mcp.check_assumptions": sympy_server.tool_check_assumptions,
            "sympy_mcp.find_singularities": sympy_server.tool_find_singularities,
            "sympy_mcp.check_inequality": sympy_server.tool_check_inequality,
            "sympy_mcp.adversarial_substitution": sympy_server.tool_adversarial_substitution,
        }
        return tool_map[skill_name](**kwargs)

    if skill_name.startswith("mathexec."):
        from ..mathexec import (
            robust_madz,
            qn_scale,
            qn_z,
            bootstrap_lower,
            alternate_corpus_z,
            counterexample_search,
            certified_z,
            composite_deviation,
            hash_population,
        )
        fn_map = {
            "mathexec.robust_madz": robust_madz,
            "mathexec.qn_scale": qn_scale,
            "mathexec.qn_z": qn_z,
            "mathexec.bootstrap": bootstrap_lower,
            "mathexec.alternate_corpus_z": alternate_corpus_z,
            "mathexec.counterexample_search": counterexample_search,
            "mathexec.certified_z": certified_z,
            "mathexec.composite_deviation": composite_deviation,
            "mathexec.hash_population": hash_population,
        }
        return fn_map[skill_name](**kwargs)

    raise ValueError(f"unknown skill family: {skill_name}")
