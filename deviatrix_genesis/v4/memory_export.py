"""Export a sealed v4 run into RIG Memory OS.

The exporter records the import as an immutable Memory OS episode, then proposes
one *candidate* procedural memory per evaluated idea. A candidate with a failed
independent verifier is explicitly marked ``promotion_blocked``; this exporter
never promotes generated content to active memory.

Writes go through ``rig-memory-os call``. SQLite is read only to preserve
idempotency across reruns of the same sealed source packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..v3.memory_os import DEFAULT_DB_PATH, DEFAULT_TENANT

APP_DIR = Path("~/.rig/rig-memory-os/app").expanduser()
CREDENTIAL_PATH = Path(
    "~/.rig/rig-memory-os/credentials/coding-fleet.token"
).expanduser()
PROJECT_SCOPE = "deviatrix-genesis"
OPERATOR = "deviatrix-genesis"
EXPORT_VERSION = "v4-memory-export-1"


@dataclass(frozen=True)
class ExportReceipt:
    """Outcome of an idempotent export attempt."""

    source_hash: str
    run_id: str
    proposed: int
    already_present: int
    event_count: int
    memory_ids: tuple[str, ...]


def canonical_json(value: Any) -> str:
    """Serialize a deterministic JSON value for hashes and tool inputs."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def source_hash(path: Path) -> str:
    """Return the SHA-256 hash of an on-disk proof packet."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_id_for(packet_hash: str) -> str:
    """Derive a stable Memory OS run ID from the sealed packet hash."""
    return f"deviatrix-v4-import-{packet_hash[:16]}"


def memory_id_for(packet_hash: str, name: str) -> str:
    """Derive a deterministic UUID for one source packet / candidate pair."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"rig://deviatrix/v4/{packet_hash}/{name}"))


def memory_os_call(
    tool: str,
    payload: dict[str, Any],
    *,
    db_path: Path,
    dry_run: bool,
) -> dict[str, Any]:
    """Invoke the governed Memory OS CLI or return the validated dry-run input."""
    if dry_run:
        return {"dry_run": True, "tool": tool, "payload": payload}

    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONPATH": str(APP_DIR / "src"),
            "RIG_MEMORY_DB": str(db_path),
            "RIG_MEMORY_CREDENTIAL": str(CREDENTIAL_PATH),
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "rig_memory_os",
            "call",
            tool,
            "--input",
            canonical_json(payload),
        ],
        cwd=APP_DIR,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        output = (completed.stdout + completed.stderr).strip()
        raise RuntimeError(f"{tool} failed (exit {completed.returncode}): {output[:500]}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{tool} returned non-JSON output: {completed.stdout[:500]}") from error


def existing_memory_ids(db_path: Path, packet_hash: str, tenant_id: str) -> set[str]:
    """Read existing import IDs without changing the Memory OS database."""
    if not db_path.exists():
        return set()
    source_ref = f"deviatrix-genesis-v4://proof/{packet_hash}"
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT memory_id FROM memories "
            "WHERE tenant_scope=? AND content_json LIKE ?",
            (tenant_id, f"%{source_ref}%"),
        ).fetchall()
    return {str(row[0]) for row in rows}


def has_event_run(db_path: Path, run_id: str, tenant_id: str) -> bool:
    """Return whether the immutable episode for this source packet exists."""
    if not db_path.exists():
        return False
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT 1 FROM episode_events WHERE tenant_id=? AND run_id=? LIMIT 1",
            (tenant_id, run_id),
        ).fetchone()
    return row is not None


def outcome_summary(survivor: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract verifier facts from every diamond without inventing a formula."""
    outcomes = survivor.get("outcomes", {})
    return {
        diamond: {
            "positive_z": outcome.get("positive_z"),
            "negative_z": outcome.get("negative_z"),
            "repaired_z": outcome.get("repaired_z"),
            "band": outcome.get("band"),
            "verifier": outcome.get("verifier"),
        }
        for diamond, outcome in outcomes.items()
        if isinstance(outcome, dict)
    }


def candidate_payload(
    survivor: dict[str, Any],
    *,
    packet_hash: str,
    run_id: str,
    imported_at: str,
    tenant_id: str,
) -> dict[str, Any]:
    """Build a candidate memory envelope from an observed v4 result.

    The existing proof packet shows every diamond verifier failed. That is stored
    as evidence, not hidden: no exported candidate is safe to promote without a
    new independent verification pass.
    """
    name = str(survivor["name"])
    outcomes = outcome_summary(survivor)
    verifier_passed = all(
        outcome["verifier"] == "PASS" for outcome in outcomes.values()
    )
    source_ref = f"deviatrix-genesis-v4://proof/{packet_hash}"
    content = {
        "kind": "deviatrix_candidate",
        "name": name,
        "owner_dept": survivor.get("owner_dept"),
        "composite_z": survivor.get("composite_z"),
        "diamond_outcomes": outcomes,
        "sealed_hashes": survivor.get("sealed_hashes", {}),
        "independent_verifier_passed": verifier_passed,
        "promotion_blocked": not verifier_passed,
        "promotion_block_reason": (
            None
            if verifier_passed
            else "v4 proof packet records a non-PASS verifier decision"
        ),
        "source_packet_sha256": packet_hash,
        "source_ref": source_ref,
        "export_version": EXPORT_VERSION,
    }
    return {
        "id": memory_id_for(packet_hash, name),
        "memory_type": "procedural",
        "content": content,
        "tenant_scope": tenant_id,
        "operator_scope": OPERATOR,
        "project_scope": PROJECT_SCOPE,
        "agent_scope": OPERATOR,
        "source_type": "model_synthesized",
        "sensitivity": "internal",
        "status": "candidate",
        "confidence": min(1.0, max(0.0, abs(float(survivor["composite_z"])) / 30.0)),
        "observed_at": imported_at,
        "valid_from": imported_at,
        "learned_at": imported_at,
        "source_refs": [source_ref],
        "provenance": [
            "agent:deviatrix-genesis-v4",
            f"run_id:{run_id}",
            f"proof_sha256:{packet_hash}",
        ],
        "writer": OPERATOR,
        "retention_policy": "deviatrix-genesis-candidate-90d",
        "supersedes": [],
        "contradicts": [],
        "supports": [],
    }


def event_payload(
    *,
    run_id: str,
    packet_hash: str,
    imported_at: str,
    survivor_count: int,
    tenant_id: str,
) -> dict[str, Any]:
    """Build one immutable episode event for this import."""
    return {
        "tenant_id": tenant_id,
        "run_id": run_id,
        "actor": OPERATOR,
        "operator_scope": OPERATOR,
        "sensitivity": "internal",
        "event_type": "deviatrix_v4_candidates_imported",
        "occurred_at": imported_at,
        "sequence": 1,
        "idempotency_key": f"{run_id}:1",
        "payload": {
            "proof_packet_sha256": packet_hash,
            "survivor_count": survivor_count,
            "export_version": EXPORT_VERSION,
            "all_imports_candidate_only": True,
        },
    }


def export_proof_packet(
    packet_path: Path,
    *,
    db_path: Path = Path(DEFAULT_DB_PATH).expanduser(),
    tenant_id: str = DEFAULT_TENANT,
    dry_run: bool = False,
) -> ExportReceipt:
    """Export one v4 proof packet into Memory OS through governed tool calls."""
    packet_hash = source_hash(packet_path)
    run_id = run_id_for(packet_hash)
    packet = json.loads(packet_path.read_text())
    survivors = packet.get("survivors", [])
    if not isinstance(survivors, list) or not survivors:
        raise ValueError("proof packet has no survivors to export")

    imported_at = datetime.now(timezone.utc).isoformat()
    existing_ids = existing_memory_ids(db_path, packet_hash, tenant_id)
    event_exists = has_event_run(db_path, run_id, tenant_id)

    event_count = 0
    if not event_exists:
        memory_os_call(
            "memory.record_event",
            event_payload(
                run_id=run_id,
                packet_hash=packet_hash,
                imported_at=imported_at,
                survivor_count=len(survivors),
                tenant_id=tenant_id,
            ),
            db_path=db_path,
            dry_run=dry_run,
        )
        event_count = 1

    proposed = 0
    present = 0
    memory_ids: list[str] = []
    for survivor in survivors:
        candidate_id = memory_id_for(packet_hash, str(survivor["name"]))
        memory_ids.append(candidate_id)
        if candidate_id in existing_ids:
            present += 1
            continue
        memory_os_call(
            "memory.propose_memory",
            candidate_payload(
                survivor,
                packet_hash=packet_hash,
                run_id=run_id,
                imported_at=imported_at,
                tenant_id=tenant_id,
            ),
            db_path=db_path,
            dry_run=dry_run,
        )
        proposed += 1

    return ExportReceipt(
        source_hash=packet_hash,
        run_id=run_id,
        proposed=proposed,
        already_present=present,
        event_count=event_count,
        memory_ids=tuple(memory_ids),
    )


def main() -> int:
    """Export a v4 proof artifact from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packet",
        type=Path,
        default=Path("v4_proofs/data.json"),
        help="Path to v4 proof packet JSON.",
    )
    parser.add_argument("--db", type=Path, default=Path(DEFAULT_DB_PATH).expanduser())
    parser.add_argument("--tenant", default=DEFAULT_TENANT)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()

    receipt = export_proof_packet(
        arguments.packet,
        db_path=arguments.db.expanduser(),
        tenant_id=arguments.tenant,
        dry_run=arguments.dry_run,
    )
    print(json.dumps(receipt.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
