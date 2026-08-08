"""Deviatrix Genesis v3 — 1000x better.

The v1/v2 engine is a *correct* implementation of the doctrine, but
the user-facing loop was:

  1. Hand-tune newness scores until D1/D2/D3 land in target bands.
  2. Re-run, eyeball the output.
  3. Repeat for hours.

v3 replaces that loop with five independent improvements:

  * **Real corpus loader** (`corpus_loader.py`) — reads JakeStudio,
    the GTM substrate, and prior Deviatrix runs to build a *real*
    reference population. No more synthetic noise.

  * **Formula proposer** (`proposer.py`) — converts a 1-paragraph brief
    into 9 MathClaim candidates. The proposer is deterministic
    (template-driven) so it works without an LLM, but it accepts an
    optional LLM-emitted ``extra_candidates`` list.

  * **Collision Engine** (`collision.py`) — fuses the top survivors
    into 2-3 hybrid ideas, with each hybrid carrying explicit
    lineage back to its parents. The hybrids re-enter the
    3×3×7 conductor for a second pass.

  * **Self-calibration loop** (`calibration.py`) — reads prior run
    results, computes the empirical "score-to-z" mapping, and
    re-proposes scores for the next brief so the loop converges
    without hand-tuning.

  * **Multi-seed ensemble** (`ensemble.py`) — runs the conductor with
    N seeds, takes the *median* z across seeds, and reports the
    inter-seed variance. Variance > 1σ triggers a verifier flag.

The verifier and the doctrine machinery are unchanged; v3 is a
*thicker* substrate + a smarter orchestrator.

The Memory-OS adapter (`memory_os.py`) writes verified ideas as
``memory.propose_memory`` candidates into RIG Memory OS, and reads
back the prior corpus to seed the reference population.
"""

from __future__ import annotations

__all__ = ["corpus_loader", "proposer", "collision", "calibration", "ensemble", "memory_os", "pipeline"]
