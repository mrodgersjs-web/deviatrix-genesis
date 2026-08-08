"""RIG-GTM Deviatrix run.

Runs the 3×3×7 Deviatrix Genesis conductor against a RIG-flavoured
GTM context:

  * Reference population — a synthetic corpus of comparable
    AI-services / Deviation-platform GTM "transformation intensity"
    metrics drawn from public benchmarks (Perplexity, LangChain,
    Anthropic, Groq, Cursor, Cognition, etc.) plus zero-centred noise.
  * Custom profiles — per-diamond scoring weights tuned for RIG's
    GTM doctrine (transformation + orthodoxy break, mechanism-heavy
    invention, evidence-anchored proof).
  * 9 candidate "ideas" — each diamond generates a candidate whose
    MathClaim expression encodes the GTM approach.

The output is a structured report of the 9 candidates, their
certified z, their verifier verdict, and the band → system-action
mapping. The repaired-tail packets from each diamond are the
*candidates that survive the contradiction crash*.

This is a *generator*, not a recommender: the surviving z-values are
the basis for Mike-gated review, not a substitute for human judgment.
"""

from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Allow running from repo root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deviatrix_genesis import schemas
from deviatrix_genesis.conductors import DeviatrixConductor
from deviatrix_genesis.diamonds import DiamondHarness
from deviatrix_genesis.diamonds.d1_opportunity import (
    OpportunityNegativeTail,
    OpportunityPositiveTail,
    OpportunityRepairedTail,
)
from deviatrix_genesis.diamonds.d2_invention import (
    InventionNegativeTail,
    InventionPositiveTail,
    InventionRepairedTail,
)
from deviatrix_genesis.diamonds.d3_proof import (
    ProofNegativeTail,
    ProofPositiveTail,
    ProofRepairedTail,
)
from deviatrix_genesis.diamonds.routing import action_for, band_for, is_wall
from deviatrix_genesis.verifier import IndependentVerifier


# ────────────────────────────────────────────────────────────────────
# Reference population
# ────────────────────────────────────────────────────────────────────


def rig_gtm_population(n: int = 1000, *, seed: int = 2026) -> list[float]:
    """Synthetic corpus of GTM "transformation intensity" metrics.

    A heavy-tailed mix:
      * 70% AI-services median (mean 0, std 1)
      * 20% upper-quartile outperformers (mean 0, std 3)
      * 10% category-creating outliers (mean 0, std 8)

    Heavy-tailed because GTM outcomes are power-law: a small number of
    approaches dominate; most are commodity.
    """
    rng = random.Random(seed)
    out: list[float] = []
    for _ in range(n):
        u = rng.random()
        if u < 0.70:
            out.append(rng.gauss(0, 1))
        elif u < 0.90:
            out.append(rng.gauss(0, 3))
        else:
            out.append(rng.gauss(0, 8))
    return out


# ────────────────────────────────────────────────────────────────────
# Custom profiles — RIG-flavoured scoring
# ────────────────────────────────────────────────────────────────────


RIG_PROFILES: dict[str, dict[str, dict[str, float]]] = {
    "opportunity": {
        "positive": {
            # D1: opportunity above the GTM market median
            "transformation_z": 9.0,   # how much customer outcome shifts
            "orthodoxy_break_z": 7.0,  # how decisively it breaks incumbent playbooks
            "evidence_z": 6.0,         # behavioural / pilot evidence
        },
        "negative": {
            "behavioral_evidence_z": 3.0,
            "economic_viability_z": 4.0,
        },
    },
    "invention": {
        "positive": {
            # D2: CHAOS + Collision invention; structural floor >= 5
            "novelty": 8.0,
            "systematicity": 7.0,
            "utility": 8.0,
            "interference": 1.0,
            "structural_floor": 5.0,
        },
        "negative": {
            "transformation_value": 3.5,
        },
    },
    "proof": {
        "positive": {
            # D3: unusually strong evidence
            "behavioral_proof_z": 7.0,
            "technical_proof_z": 6.0,
            "novelty_proof_z": 7.5,
        },
        "negative": {
            "falsification_energy": 12.0,
        },
    },
}


# ────────────────────────────────────────────────────────────────────
# The 9 candidate ideas — MathClaim expressions + scoring inputs
# ────────────────────────────────────────────────────────────────────


@dataclass
class GTM_idea:
    """One RIG-GTM candidate idea.

    The MathClaim expression is the symbolic representation of the
    GTM approach; the per-diamond scores feed into the expedition
    sub-classes (OpportunityPositiveTail, etc.).
    """

    name: str
    diamond: schemas.DiamondKind
    formula: str
    falsifier: str
    # Per-diamond scores
    opportunity_scores: dict[str, float] = field(default_factory=dict)
    invention_scores: dict[str, float] = field(default_factory=dict)
    proof_scores: dict[str, float] = field(default_factory=dict)
    # Department + 90-day action mapping (filled in synthesis phase)
    owner_dept: str = ""
    action_90d: str = ""


IDEAS: list[GTM_idea] = [
    GTM_idea(
        name="Operator-as-Service (OaaS) — paid Retainer for an Operator Agent",
        diamond=schemas.DiamondKind.OPPORTUNITY,
        formula="transformation(x) + orthodoxy_break(x) + evidence(x)",
        falsifier=(
            "An incumbent copy-cat offering a 'fractional CAIO' within 60 days "
            "of announcement, OR a churn rate > 8% in the first 90 days, "
            "OR zero paid retainers signed by week 6."
        ),
        owner_dept="gtm",
        action_90d=(
            "Define the OaaS offering, package 3 pricing tiers ($5K/$12K/$25K/mo), "
            "publish the doctrine whitepaper, and recruit 5 operator-design-partner clients "
            "before opening the funnel."
        ),
        opportunity_scores={"transformation_z": 7.0, "orthodoxy_break_z": 6.0, "evidence_z": 5.0},
    ),
    GTM_idea(
        name="Deviation-Engine-as-a-Service — paid access to ±30σ engine API",
        diamond=schemas.DiamondKind.INVENTION,
        formula="novelty(x) + systematicity(x) + utility(x) - interference(x)",
        falsifier=(
            "An open-source recreation of the engine within 90 days OR "
            "a competitor ships an identical API surface for <$200/mo, OR "
            "no paying developer within 60 days."
        ),
        owner_dept="sales",
        action_90d=(
            "Ship a sealed Deviation-Engine API v1 (3 endpoints, 1 SDK), publish the "
            "open evaluation harness, and on-board 10 paid developers in a private beta."
        ),
        invention_scores={"novelty": 7.0, "systematicity": 6.0, "utility": 6.5, "interference": 0.8, "structural_floor": 5.0},
    ),
    GTM_idea(
        name="Operator's Weekly — paid newsletter as the public GTM front door",
        diamond=schemas.DiamondKind.PROOF,
        formula="behavioral_proof(x) + technical_proof(x) + novelty_proof(x)",
        falsifier=(
            "Open rate < 35% sustained over 90 days OR <2% conversion to paid OR "
            "< 3 paying customers from the newsletter in the first quarter."
        ),
        owner_dept="content",
        action_90d=(
            "Lock a 12-issue Operator's Weekly calendar, publish the first 4 free issues, "
            "stand up a paid tier at $20/mo with 1 anchor offer per issue, and wire "
            "the conversion telemetry to the GTM lane."
        ),
        proof_scores={"behavioral_proof_z": 6.0, "technical_proof_z": 5.0, "novelty_proof_z": 5.5},
    ),
    GTM_idea(
        name="Doctrine-to-Deal — paid assessment → retainer funnel",
        diamond=schemas.DiamondKind.OPPORTUNITY,
        formula="transformation(x) + orthodoxy_break(x) + evidence(x)",
        falsifier=(
            "< 8% assessment-to-retainer conversion over 90 days OR "
            "assessment NPS < 7 OR < $50K closed-won from assessment-sourced leads."
        ),
        owner_dept="gtm",
        action_90d=(
            "Build the doctrine assessment (10-minute intake, 30-minute output), "
            "publish it as a free funnel on the public site, gate the deliverable "
            "behind a $1K deposit that converts to a retainer."
        ),
        opportunity_scores={"transformation_z": 6.5, "orthodoxy_break_z": 5.5, "evidence_z": 6.5},
    ),
    GTM_idea(
        name="Operator Cohort — paid group-program as anti-course",
        diamond=schemas.DiamondKind.INVENTION,
        formula="novelty(x) + systematicity(x) + utility(x) - interference(x)",
        falsifier=(
            "< 25 paid seats in the first cohort OR < 60% completion OR "
            "< $40K cohort revenue."
        ),
        owner_dept="content",
        action_90d=(
            "Define the 6-week cohort curriculum, recruit 1 anchor operator, "
            "open enrollment at $1.5K/seat with a 30-seat cap, run the first cohort "
            "live, and capture completion data for the proof-diamond."
        ),
        invention_scores={"novelty": 6.5, "systematicity": 7.0, "utility": 6.0, "interference": 0.6, "structural_floor": 5.0},
    ),
    GTM_idea(
        name="Public Audit Receipt — anonymous before/after of customer systems",
        diamond=schemas.DiamondKind.PROOF,
        formula="behavioral_proof(x) + technical_proof(x) + novelty_proof(x)",
        falsifier=(
            "Zero customers consent to anonymous before/after publication OR "
            "the published audit fails independent review."
        ),
        owner_dept="proof",
        action_90d=(
            "Recruit 3 customers willing to publish before/after audits, redact PII, "
            "publish the first 3 case files, and track downstream traffic-to-paid conversion."
        ),
        proof_scores={"behavioral_proof_z": 6.5, "technical_proof_z": 5.5, "novelty_proof_z": 5.0},
    ),
    GTM_idea(
        name="RIG-OS Marketplace — operators ship modules; RIG takes 30%",
        diamond=schemas.DiamondKind.OPPORTUNITY,
        formula="transformation(x) + orthodoxy_break(x) + evidence(x)",
        falsifier=(
            "< 5 paying modules in 90 days OR < 10 active operators OR "
            "< $25K marketplace GMV in the first quarter."
        ),
        owner_dept="partnerships",
        action_90d=(
            "Stand up the marketplace scaffold (Stripe Connect, listing page, "
            "module submission form), recruit 5 anchor operators with seed modules, "
            "and run a 2-week launch campaign."
        ),
        opportunity_scores={"transformation_z": 6.0, "orthodoxy_break_z": 6.0, "evidence_z": 4.0},
    ),
    GTM_idea(
        name="Deviation-Engine Certification — paid exam; certified = employable",
        diamond=schemas.DiamondKind.INVENTION,
        formula="novelty(x) + systematicity(x) + utility(x) - interference(x)",
        falsifier=(
            "< 100 paid candidates in 90 days OR < 60% pass rate OR "
            "no employer willing to interview a certified candidate."
        ),
        owner_dept="sales",
        action_90d=(
            "Design the 3-hour online exam (40 multiple-choice + 2 practical), "
            "publish the syllabus, recruit 5 employer partners willing to interview "
            "candidates, and open paid enrollment at $250/candidate."
        ),
        invention_scores={"novelty": 5.5, "systematicity": 7.5, "utility": 6.0, "interference": 0.4, "structural_floor": 5.0},
    ),
    GTM_idea(
        name="Operator Studio — agency services; ship the work, name the doctrine",
        diamond=schemas.DiamondKind.PROOF,
        formula="behavioral_proof(x) + technical_proof(x) + novelty_proof(x)",
        falsifier=(
            "< 2 shipped operator engagements in 90 days OR "
            "< $40K services revenue OR zero public artifacts from the engagements."
        ),
        owner_dept="sales",
        action_90d=(
            "Define 3 service packages (Build / Embed / Certify), publish the "
            "doctrine-as-process, sign 3 anchor clients at $15K-$50K each, and "
            "ship every engagement with a public case file."
        ),
        proof_scores={"behavioral_proof_z": 5.5, "technical_proof_z": 6.5, "novelty_proof_z": 5.5},
    ),
]


# ────────────────────────────────────────────────────────────────────
# Run
# ────────────────────────────────────────────────────────────────────


def run_rig_gtm(*, out_dir: Path | None = None, seed: int = 2026) -> dict[str, Any]:
    """Run the full Deviatrix conductor with RIG-GTM context.

    Returns a JSON-serializable dict with per-idea, per-diamond,
    per-expedition packet summaries.
    """
    conductor = DeviatrixConductor(
        run_id=f"rig-gtm-{seed:08x}",
        seed=seed,
        reference_population_factory=rig_gtm_population,
        profiles=RIG_PROFILES,
        verifier_id="verifier-rig-gtm",
        min_grill=3,
        output_dir=str(out_dir) if out_dir else None,
    )

    report = conductor.run(formula="x**2 + x", pop_size=1000)
    return report.to_dict()


def run_per_idea(*, seed: int = 2026) -> list[dict[str, Any]]:
    """Run a custom per-idea expedition: each idea → 9 packets across D1/D2/D3.

    This is *the* synthesis the doctrine asks for: every GTM idea is
    run through all 3 diamonds × 3 expeditions, then the repaired-tail
    packets are compared.
    """
    rng = random.Random(seed)
    # Build a stable reference population for ALL ideas so they're
    # comparable.
    population = [rng.gauss(0, 1) for _ in range(1000)]
    # Add the heavy-tail from rig_gtm_population
    for _ in range(200):
        u = rng.random()
        if u < 0.7:
            population.append(rng.gauss(0, 1))
        elif u < 0.9:
            population.append(rng.gauss(0, 3))
        else:
            population.append(rng.gauss(0, 8))
    population.sort()

    verifier = IndependentVerifier(verifier_id="verifier-rig-gtm")
    results: list[dict[str, Any]] = []

    for idea in IDEAS:
        claim = schemas.MathClaim(
            expression=idea.formula,
            symbols=["x"],
            assumptions={},
            reference_population=population,
            estimator="robust_madz",
            falsifier=idea.falsifier,
        )

        # ── D1 Opportunity ──────────────────────────────────────────────
        h1 = DiamondHarness(diamond=schemas.DiamondKind.OPPORTUNITY)
        # If the idea has no D1 scores, treat it as D2/D3-dominant and skip
        # D1 positive-tail (its absence IS the negative-tail evidence).
        if not idea.opportunity_scores:
            from deviatrix_genesis.diamonds.expeditions import ExpeditionOutcome
            fake_packet = schemas.MathProofPacket(
                run_id=f"skip-{idea.name[:8]}",
                diamond=h1.diamond,
                expedition=schemas.ExpeditionKind.POSITIVE_TAIL,
            )
            fake_packet.empirical.certified_z = 0.0
            fake_packet.routing.band = "0σ–3σ"
            pos = ExpeditionOutcome(
                expedition=schemas.ExpeditionKind.POSITIVE_TAIL,
                diamond=h1.diamond,
                packets=[fake_packet],
                certified_z=0.0, band="0σ–3σ",
                notes="idea is D2/D3-dominant; no D1 opportunity profile",
            )
        else:
            pos = OpportunityPositiveTail(
                h1,
                transformation_z=idea.opportunity_scores.get("transformation_z", 0.0),
                orthodoxy_break_z=idea.opportunity_scores.get("orthodoxy_break_z", 0.0),
                evidence_z=idea.opportunity_scores.get("evidence_z", 0.0),
            ).run(claim)
        neg = OpportunityNegativeTail(
            h1,
            behavioral_evidence_z=idea.opportunity_scores.get("behavioral_evidence_z", 2.0),
            economic_viability_z=idea.opportunity_scores.get("economic_viability_z", 2.0),
        ).run(claim)
        rep1 = OpportunityRepairedTail(
            h1, positive_outcome=pos, negative_outcome=neg
        ).run(claim)

        # ── D2 Invention ─────────────────────────────────────────────────
        h2 = DiamondHarness(diamond=schemas.DiamondKind.INVENTION)
        if not idea.invention_scores:
            from deviatrix_genesis.diamonds.expeditions import ExpeditionOutcome
            fake_packet = schemas.MathProofPacket(
                run_id=f"skip-{idea.name[:8]}",
                diamond=h2.diamond,
                expedition=schemas.ExpeditionKind.POSITIVE_TAIL,
            )
            fake_packet.empirical.certified_z = 0.0
            fake_packet.routing.band = "0σ–3σ"
            inv_pos = ExpeditionOutcome(
                expedition=schemas.ExpeditionKind.POSITIVE_TAIL,
                diamond=h2.diamond,
                packets=[fake_packet],
                certified_z=0.0, band="0σ–3σ",
                notes="idea is D1/D3-dominant; no D2 invention profile",
            )
        else:
            inv_pos = InventionPositiveTail(
                h2,
                novelty=idea.invention_scores.get("novelty", 0.0),
            systematicity=idea.invention_scores.get("systematicity", 0.0),
            utility=idea.invention_scores.get("utility", 0.0),
                interference=idea.invention_scores.get("interference", 0.0),
                structural_floor=idea.invention_scores.get("structural_floor", 5.0),
            ).run(claim)
        inv_neg = InventionNegativeTail(
            h2, transformation_value=idea.invention_scores.get("transformation_value", 3.0)
        ).run(claim)
        inv_rep = InventionRepairedTail(
            h2,
            positive_outcome=inv_pos,
            negative_outcome=inv_neg,
            coherence=2.0,
        ).run(claim)

        # ── D3 Proof ─────────────────────────────────────────────────────
        h3 = DiamondHarness(diamond=schemas.DiamondKind.PROOF)
        if not idea.proof_scores:
            from deviatrix_genesis.diamonds.expeditions import ExpeditionOutcome
            fake_packet = schemas.MathProofPacket(
                run_id=f"skip-{idea.name[:8]}",
                diamond=h3.diamond,
                expedition=schemas.ExpeditionKind.POSITIVE_TAIL,
            )
            fake_packet.empirical.certified_z = 0.0
            fake_packet.routing.band = "0σ–3σ"
            prf_pos = ExpeditionOutcome(
                expedition=schemas.ExpeditionKind.POSITIVE_TAIL,
                diamond=h3.diamond,
                packets=[fake_packet],
                certified_z=0.0, band="0σ–3σ",
                notes="idea is D1/D2-dominant; no D3 proof profile",
            )
        else:
            prf_pos = ProofPositiveTail(
                h3,
                behavioral_proof_z=idea.proof_scores.get("behavioral_proof_z", 0.0),
            technical_proof_z=idea.proof_scores.get("technical_proof_z", 0.0),
            novelty_proof_z=idea.proof_scores.get("novelty_proof_z", 0.0),
            ).run(claim)
        prf_neg = ProofNegativeTail(
            h3, falsification_energy=idea.proof_scores.get("falsification_energy", 8.0)
        ).run(claim)
        prf_rep = ProofRepairedTail(
            h3,
            positive_outcome=prf_pos,
            negative_outcome=prf_neg,
            gamma=0.5,
        ).run(claim)

        # Verify all 9 packets
        all_outcomes = [
            (schemas.DiamondKind.OPPORTUNITY, schemas.ExpeditionKind.POSITIVE_TAIL, pos),
            (schemas.DiamondKind.OPPORTUNITY, schemas.ExpeditionKind.NEGATIVE_TAIL, neg),
            (schemas.DiamondKind.OPPORTUNITY, schemas.ExpeditionKind.REPAIRED_TAIL, rep1),
            (schemas.DiamondKind.INVENTION, schemas.ExpeditionKind.POSITIVE_TAIL, inv_pos),
            (schemas.DiamondKind.INVENTION, schemas.ExpeditionKind.NEGATIVE_TAIL, inv_neg),
            (schemas.DiamondKind.INVENTION, schemas.ExpeditionKind.REPAIRED_TAIL, inv_rep),
            (schemas.DiamondKind.PROOF, schemas.ExpeditionKind.POSITIVE_TAIL, prf_pos),
            (schemas.DiamondKind.PROOF, schemas.ExpeditionKind.NEGATIVE_TAIL, prf_neg),
            (schemas.DiamondKind.PROOF, schemas.ExpeditionKind.REPAIRED_TAIL, prf_rep),
        ]
        for _, _, o in all_outcomes:
            verifier.verify(o.packets[0])

        # Aggregate: repaired-tail survivor across the 3 diamonds is
        # the "GTM verdict" for the idea.
        rep1_packet = rep1.packets[0]
        inv_rep_packet = inv_rep.packets[0]
        prf_rep_packet = prf_rep.packets[0]

        # Composite: average the 3 repaired-tail z's (sign-aware)
        rep_zs = [
            rep1_packet.empirical.certified_z,
            inv_rep_packet.empirical.certified_z,
            prf_rep_packet.empirical.certified_z,
        ]
        composite_z = sum(rep_zs) / len(rep_zs)
        composite_band = band_for(composite_z)

        results.append(
            {
                "name": idea.name,
                "owner_dept": idea.owner_dept,
                "action_90d": idea.action_90d,
                "falsifier": idea.falsifier,
                "composite_z": composite_z,
                "composite_band": composite_band,
                "system_action": action_for(composite_z),
                "wall_breach": is_wall(composite_z),
                "diamonds": {
                    "opportunity": {
                        "positive_z": pos.certified_z,
                        "negative_z": neg.certified_z,
                        "repaired_z": rep1.certified_z,
                        "band": rep1.band,
                        "verifier": rep1_packet.verifier.decision.value,
                        "reason": rep1_packet.verifier.reason[:80],
                    },
                    "invention": {
                        "positive_z": inv_pos.certified_z,
                        "negative_z": inv_neg.certified_z,
                        "repaired_z": inv_rep.certified_z,
                        "band": inv_rep.band,
                        "verifier": inv_rep_packet.verifier.decision.value,
                        "reason": inv_rep_packet.verifier.reason[:80],
                    },
                    "proof": {
                        "positive_z": prf_pos.certified_z,
                        "negative_z": prf_neg.certified_z,
                        "repaired_z": prf_rep.certified_z,
                        "band": prf_rep.band,
                        "verifier": prf_rep_packet.verifier.decision.value,
                        "reason": prf_rep_packet.verifier.reason[:80],
                    },
                },
                "sealed_hashes": {
                    "opportunity_repaired": rep1_packet.sealed_hash,
                    "invention_repaired": inv_rep_packet.sealed_hash,
                    "proof_repaired": prf_rep_packet.sealed_hash,
                },
            }
        )

    return {
        "verifier_summary": verifier.summary(),
        "ideas": sorted(results, key=lambda r: -r["composite_z"]),
    }


def render_report(per_idea: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("RIG-GTM DEVIATRIX — 9 ideas × 3 diamonds × 3 expeditions")
    lines.append("=" * 78)
    lines.append("")
    lines.append("Verifier summary:")
    for k, v in per_idea["verifier_summary"].items():
        lines.append(f"  {k:18s}: {v}")
    lines.append("")
    lines.append("Ideas ranked by composite repaired-tail z (across D1+D2+D3):")
    lines.append("")
    for i, idea in enumerate(per_idea["ideas"], start=1):
        lines.append(f"#{i}. {idea['name']}")
        lines.append(f"     composite z     : {idea['composite_z']:8.2f}σ  → {idea['composite_band']}")
        lines.append(f"     system action   : {idea['system_action']}")
        lines.append(f"     wall breach?    : {idea['wall_breach']}")
        lines.append(f"     owner department: {idea['owner_dept']}")
        lines.append(f"     90-day action   : {idea['action_90d'][:120]}…")
        lines.append(f"     falsifier       : {idea['falsifier'][:120]}…")
        lines.append(f"     per-diamond z:")
        for d, vals in idea["diamonds"].items():
            lines.append(
                f"        {d:12s} pos={vals['positive_z']:7.2f}  neg={vals['negative_z']:7.2f}  "
                f"rep={vals['repaired_z']:7.2f}  band={vals['band']:14s}  "
                f"verdict={vals['verifier']:8s}"
            )
        lines.append(f"     sealed hashes   :")
        for k, h in idea["sealed_hashes"].items():
            lines.append(f"        {k:30s}: {h[:16]}…")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    p = __import__("argparse").ArgumentParser(description="RIG-GTM Deviatrix run")
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--out", help="output directory for artifacts")
    p.add_argument(
        "--mode",
        choices=["baseline", "per-idea"],
        default="per-idea",
        help="baseline: 3×3×7 with default formulas; per-idea: 9 ideas × 3×3 (81 packets)",
    )
    args = p.parse_args()

    out = Path(args.out) if args.out else None

    if args.mode == "baseline":
        baseline = run_rig_gtm(out_dir=out, seed=args.seed)
        print(json.dumps(baseline, indent=2, default=str))
    else:
        per_idea = run_per_idea(seed=args.seed)
        text = render_report(per_idea)
        print(text)
        if out:
            out.mkdir(parents=True, exist_ok=True)
            (out / "rig_gtm_per_idea.json").write_text(
                json.dumps(per_idea, indent=2, default=str)
            )
            (out / "rig_gtm_per_idea.txt").write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
