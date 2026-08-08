"""Formula emitter — generates SymPy-parseable formulas from a brief.

v3's proposer used a fixed template library: 9 hand-written
formulas. v4's emitter builds formulas *from the brief* by
combining:

  * **primitive tokens** — atoms from a curated vocabulary
    (`outcome`, `verifier`, `escrow`, `auction`, `reputation`,
    `signed_receipt`, `smart_contract`, `doctrine`, `bond`,
    `attribution`, `negative_pick`, `counterfactual`, `baseline`)
  * **operators** — `*` (product / conjunction), `+` (sum /
    union), `-` (subtraction / exclusion), `^` (composition),
    `(...)` (grouping)
  * **scoring** — the corpus-derived newness scores, applied
    to the emitted formula

The output is a tuple of (formula_str, name, falsifier,
newness_dict). The formula_str is SymPy-parseable (verified by
the existing sympy_mcp.parse tool) so the conductor can consume
it without changes.

This is the *LLM-style* path: no LLM is called, but the output
*shape* is what an LLM would produce (a candidate formula with
named mechanisms), and the corpus-derived scores replace the
hand-tuned scalars.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any

from ..v3.corpus_loader import KNOWN_MECHANISM_PATTERNS

__all__ = ["EmittedFormula", "emit_formulas", "PRIMITIVE_VOCAB", "OPERATOR_VOCAB"]


# ────────────────────────────────────────────────────────────────────
# Vocabularies
# ────────────────────────────────────────────────────────────────────


# Each primitive has: name, formula_atom, falsifier_template,
# default_action, mechanism_family, dept.
PRIMITIVE_VOCAB: list[dict[str, str]] = [
    {
        "name": "escrow",
        "atom": "verifiable_outcome(x) * escrow_release(x)",
        "falsifier": "An incumbent copy-cat launches a comparable outcome-escrow marketplace within 90 days OR < 5 customer-paid escrows.",
        "family": "independent_verification",
        "dept": "gtm",
        "action": "Design the outcome-escrow protocol (state-machine + verifier network), publish the spec, recruit 2 independent-verification partners, on-board 3 customers willing to escrow $10K+ each.",
    },
    {
        "name": "verifier",
        "atom": "third_party_verifier(x) * adversarial_quality_proof(x)",
        "falsifier": "Lead quality regresses to the prior mean within 90 days OR the verification mechanism is reverse-engineered OR < 100 qualified leads delivered.",
        "family": "independent_verification",
        "dept": "sales",
        "action": "Design the adversarial-quality protocol (third-party audit of the lead-source method), publish the spec, recruit 2 buyers willing to pay per-verified-lead (not per-lead), run a 90-day cohort.",
    },
    {
        "name": "counterfactual",
        "atom": "counterfactual_baseline(x) * saved_outcome_delta(x) * independent_reconstruction(x)",
        "falsifier": "No independent re-constructor agrees to the protocol OR < $50K saved-outcome payments in 90 days OR the baseline is challenged.",
        "family": "independent_verification",
        "dept": "strategy",
        "action": "Design the counterfactual-receipt protocol (independent baseline reconstruction + delta measurement + payment-on-delta), publish the spec, recruit 2 re-constructor partners, run a 90-day pilot.",
    },
    {
        "name": "smart_contract",
        "atom": "executable_doctrine(x) * automatic_payment(x) * verifiability_guarantee(x)",
        "falsifier": "No operator accepts the executable doctrine OR < 5 operators auto-paid OR the verification guarantee is reverse-engineered.",
        "family": "financial_primitive",
        "dept": "engineering",
        "action": "Write the doctrine as a smart contract (Solidity or equivalent), publish the code + verification guarantees, deploy on testnet, audit the contract, recruit 5 operators to test auto-payment.",
    },
    {
        "name": "bond",
        "atom": "doctrine_yield(x) * default_recovery(x) * covenant_enforcement(x)",
        "falsifier": "No investor willing to fund under the doctrine-yield curve OR the yield curve is falsified by an operator OR < $100K deployed.",
        "family": "yield_curve",
        "dept": "finance",
        "action": "Design the doctrine-yield curve (operator-output × verification-rate × duration), publish the spec, recruit 1 friendly investor, file the regulatory posture, deploy $50K-$250K as the first cohort.",
    },
    {
        "name": "reputation",
        "atom": "portable_reputation(x) * signed_receipt_chain(x) * cross_platform_inheritance(x)",
        "falsifier": "Operators refuse the primitive OR < 100 operators sign up OR no platform adopts the receipt format within 90 days.",
        "family": "portable_reputation",
        "dept": "strategy",
        "action": "Design the reputation object schema (JSON-LD or signed CBOR), publish the spec, recruit 3 platforms willing to honour the receipt, run a 90-day pilot with 50 operators.",
    },
    {
        "name": "negative_pick",
        "atom": "negative_pick_payment(x) * optional_disclosure(x) * competitor_research_artefact(x)",
        "falsifier": "Operators refuse the disclosure option OR no customer activates a negative-pick OR the disclosure itself damages trust.",
        "family": "portable_reputation",
        "dept": "strategy",
        "action": "Design the negative-pick contract (payment-for-non-recommendation + optional disclosure), publish the spec, recruit 3 operators willing to test, run a 90-day pilot with 10 customers.",
    },
    {
        "name": "auction",
        "atom": "auction_revenue(x) * problem_clarity(x) * winner_take_all_proof(x)",
        "falsifier": "Operators refuse to underbid OR < 50 problems posted OR < 10 paid resolutions OR the underbid price floor collapses.",
        "family": "inverted_market",
        "dept": "gtm",
        "action": "Design the reverse-auction protocol (problem-post + underbid window + escrow release), publish the spec, seed 10 problem posts from friendly customers, run a 90-day auction.",
    },
    {
        "name": "attribution",
        "atom": "public_attribution(x) * downstream_revenue_share(x) * visibility_premium(x)",
        "falsifier": "Operators refuse the visibility-premium OR < $50K downstream revenue is generated in 90 days OR no measurable attribution delta between tagged and untagged outputs.",
        "family": "inverted_market",
        "dept": "content",
        "action": "Design the attribution protocol (signed receipts + downstream conversion telemetry), publish the spec, instrument 3 public operators to test the visibility-premium, run a 90-day attribution measurement.",
    },
    {
        "name": "covenantee",
        "atom": "covenant_enforcement(x) * dispute_resolution(x) * third_party_audit(x)",
        "falsifier": "Any party refuses the covenant OR no third-party auditor agrees OR < 5 covenants active in 90 days.",
        "family": "independent_verification",
        "dept": "legal",
        "action": "Design the covenant template (state-machine + dispute-resolution + third-party-audit hooks), publish the spec, recruit 2 friendly law firms, run a 90-day pilot.",
    },
    {
        "name": "oracle",
        "atom": "external_oracle(x) * timestamp_proof(x) * signed_assertion(x)",
        "falsifier": "The oracle is gamed within 90 days OR no operator accepts the oracle's outputs OR the timestamp proof is broken.",
        "family": "independent_verification",
        "dept": "engineering",
        "action": "Stand up an external oracle (timestamped signed assertions from 3 independent data sources), publish the protocol, recruit 5 operators willing to consume oracle outputs.",
    },
    {
        "name": "license",
        "atom": "doctrine_license(x) * attribution_chain(x) * per_use_payment(x)",
        "falsifier": "< 10 licensees in 90 days OR < $25K revenue OR < 1 active per-use payment stream.",
        "family": "financial_primitive",
        "dept": "finance",
        "action": "Design the doctrine-license agreement (attribution chain + per-use payment), publish the spec, recruit 5 anchor licensees, run a 90-day pilot.",
    },
]


OPERATOR_VOCAB: list[str] = ["*", "+", "-", "^"]


# ────────────────────────────────────────────────────────────────────
# Emitted formula
# ────────────────────────────────────────────────────────────────────


@dataclass
class EmittedFormula:
    """A formula emitted by the formula emitter."""

    name: str
    formula: str  # SymPy-parseable
    falsifier: str
    action_90d: str
    owner_dept: str
    mechanism_family: str
    anti_orthodoxy_new: float
    mechanism_originality_new: float
    prior_art_distance_new: float
    primitives: list[str] = field(default_factory=list)  # for lineage


# ────────────────────────────────────────────────────────────────────
# Brief-driven emission
# ────────────────────────────────────────────────────────────────────


def _brief_tokens(brief: str) -> set[str]:
    return {t.lower() for t in re.findall(r"\b\w+\b", brief) if len(t) > 3}


def _primitive_score(prim: dict[str, str], brief_tokens: set[str]) -> float:
    """Score a primitive against the brief by name-overlap."""
    name = prim["name"]
    name_tokens = set(name.split("_"))
    if not name_tokens:
        return 0.0
    return len(name_tokens & brief_tokens) / len(name_tokens)


def emit_formulas(
    brief: str,
    *,
    n: int = 9,
    corpus_newness: dict[str, tuple[float, float, float]] | None = None,
    seed: int = 2026,
) -> list[EmittedFormula]:
    """Emit ``n`` candidate formulas from ``brief``.

    Each emitted formula is built by combining 1-3 primitives from
    PRIMITIVE_VOCAB whose names overlap with the brief. The
    combination operator is chosen at random; the formula is
    SymPy-parseable.

    ``corpus_newness`` is an optional mapping from primitive name
    to (anti_orthodoxy, mechanism_originality, prior_art_distance)
    derived from the corpus. When provided, the emitter uses these
    real scores; otherwise it falls back to a hand-tuned default.
    """
    rng = random.Random(seed)
    brief_tokens = _brief_tokens(brief)

    # Rank primitives by brief-fit
    ranked = sorted(
        PRIMITIVE_VOCAB,
        key=lambda p: -_primitive_score(p, brief_tokens),
    )

    out: list[EmittedFormula] = []
    seen_combinations: set[str] = set()

    for prim in ranked:
        if len(out) >= n:
            break
        # Decide composition depth
        depth = rng.choice([1, 2, 3])
        chosen = [prim]
        # Pick 0-2 additional primitives from different families
        others = [p for p in ranked if p["name"] != prim["name"] and p["family"] != prim["family"]]
        rng.shuffle(others)
        chosen.extend(others[: depth - 1])

        formula_atom = chosen[0]["atom"]
        if len(chosen) > 1:
            op = rng.choice(["*", "+"])
            for extra in chosen[1:]:
                formula_atom = f"({formula_atom}) {op} ({extra['atom']})"

        combination_key = "|".join(sorted(c["name"] for c in chosen))
        if combination_key in seen_combinations:
            continue
        seen_combinations.add(combination_key)

        family = chosen[0]["family"]

        # Use corpus-derived scores if provided, else fall back.
        if corpus_newness:
            prim_name = chosen[0]["name"]
            ao, mo, pa = corpus_newness.get(
                prim_name,
                (4.5, 4.5, 4.5),  # default
            )
            # Add a small bonus for combining (depth-1)
            bonus = 0.2 * (depth - 1)
            ao = min(8.0, ao + bonus)
            mo = min(8.0, mo + bonus * 0.5)
            pa = min(8.0, pa + bonus * 0.5)
        else:
            ao = mo = pa = 4.5 + 0.2 * (depth - 1)

        name_parts = [c["name"].replace("_", "-") for c in chosen]
        name = f"{' + '.join(name_parts)} ({family})"

        out.append(
            EmittedFormula(
                name=name,
                formula=formula_atom,
                falsifier=chosen[0]["falsifier"],
                action_90d=chosen[0]["action"],
                owner_dept=chosen[0]["dept"],
                mechanism_family=family,
                anti_orthodoxy_new=ao,
                mechanism_originality_new=mo,
                prior_art_distance_new=pa,
                primitives=[c["name"] for c in chosen],
            )
        )

    return out
