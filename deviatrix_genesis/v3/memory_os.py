"""RIG Memory OS adapter — bridge Deviatrix ↔ RIG Memory OS.

RIG Memory OS is the *substrate* for everything RIG records:
memories, predictions, intentions, events. Deviatrix v3 emits
verified ideas; this adapter writes them as ``memory.propose_memory``
candidates and reads prior memories back to seed the corpus.

The adapter is *read-write*:
  * read: pull prior memories and use them as known-archetype
    candidates in the corpus_loader.
  * write: after a v3 run, propose each verified idea as a new
    memory with ``memory_type="idea_proposal"`` so Mike can review
    and promote.

Auth: the adapter uses the existing ``coding-fleet`` token. All
writes go through the existing ``memory.propose_memory`` tool; no
new auth surface is introduced.

The Memory OS database lives at ``~/.rig/rig-memory-os/memory.db``
(override with ``RIG_MEMORY_DB``).
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["MemoryOSAdapter", "read_prior_memories", "write_idea_as_memory"]


# ────────────────────────────────────────────────────────────────────
# Direct SQLite (faster than shelling out for every read)
# ────────────────────────────────────────────────────────────────────


DEFAULT_DB_PATH = "~/.rig/rig-memory-os/memory.db"
DEFAULT_TENANT = "rig-default"


@dataclass
class PriorMemory:
    """A memory read back from RIG Memory OS."""

    memory_id: str
    memory_type: str
    content: dict[str, Any]
    status: str
    recorded_at: str = ""


@dataclass
class WriteReceipt:
    """The result of writing an idea as a memory candidate."""

    idea_name: str
    accepted: bool
    memory_id: str | None
    error: str | None
    raw: dict[str, Any] = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────
# Read
# ────────────────────────────────────────────────────────────────────


def read_prior_memories(
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    tenant_id: str = DEFAULT_TENANT,
    memory_types: tuple[str, ...] | None = None,
    limit: int = 200,
) -> list[PriorMemory]:
    """Read prior memories from RIG Memory OS as substrate for the corpus.

    The ``memory_types`` filter (when provided) restricts to idea /
    customer_signal / doctrine memories. When ``None``, returns
    every active/candidate memory.
    """
    db = Path(db_path).expanduser()
    if not db.exists():
        return []

    sql = (
        "SELECT memory_id, memory_type, content_json, initial_status FROM memories "
        "WHERE tenant_scope=? AND initial_status IN ('active','candidate') "
    )
    params: list[Any] = [tenant_id]
    if memory_types:
        placeholders = ",".join("?" for _ in memory_types)
        sql += f"AND memory_type IN ({placeholders}) "
        params.extend(memory_types)
    sql += "ORDER BY rowid DESC LIMIT ?"
    params.append(limit)

    out: list[PriorMemory] = []
    try:
        conn = sqlite3.connect(str(db))
    except sqlite3.Error:
        return []
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        conn.close()

    for mid, mtype, content_json, status in rows:
        try:
            content = json.loads(content_json) if isinstance(content_json, str) else (content_json or {})
        except json.JSONDecodeError:
            content = {}
        out.append(
            PriorMemory(
                memory_id=mid,
                memory_type=mtype,
                content=content,
                status=status,
                recorded_at=str(content.get("recorded_at", "")),
            )
        )
    return out


# ────────────────────────────────────────────────────────────────────
# Write
# ────────────────────────────────────────────────────────────────────


def _build_memory_payload(
    idea_name: str,
    formula: str,
    falsifier: str,
    composite_z: float,
    archetype_z: float,
    is_respin: bool,
    mechanism_family: str,
    parent_names: list[str] | None,
    action_90d: str,
    run_id: str,
) -> dict[str, Any]:
    """Construct the JSON body for memory.propose_memory.

    Conforms to RIG Memory OS ``validate_memory`` schema:
    memory_type ∈ {working, episodic, semantic, entity, procedural,
    hierarchical, cached, prospective}; source_type must be set;
    sensitivity, status, confidence, observed_at, valid_from,
    source_refs, provenance must all be present.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    confidence = min(1.0, max(0.0, abs(composite_z) / 30.0))
    return {
        "memory_type": "procedural",  # an idea is a procedure/protocol
        "source_type": "model_synthesized",
        "sensitivity": "internal",
        "status": "candidate",
        "confidence": confidence,
        "observed_at": now,
        "valid_from": now,
        "learned_at": now,
        "source_refs": [
            f"deviatrix-genesis-v3://run/{run_id}",
        ],
        "provenance": [
            "agent:deviatrix-genesis-v3",
            f"run_id:{run_id}",
        ],
        "tenant_scope": DEFAULT_TENANT,
        "operator_scope": "deviatrix-genesis",
        "retention_policy": "deviatrix-genesis-90d",
        "content": {
            "name": idea_name,
            "formula": formula,
            "falsifier": falsifier,
            "composite_z": composite_z,
            "archetype_z": archetype_z,
            "is_respin_of_known": is_respin,
            "mechanism_family": mechanism_family,
            "parent_names": parent_names or [],
            "action_90d": action_90d,
            "run_id": run_id,
        },
    }


def write_idea_as_memory(
    *,
    idea_name: str,
    formula: str,
    falsifier: str,
    composite_z: float,
    archetype_z: float,
    is_respin: bool,
    mechanism_family: str,
    parent_names: list[str] | None,
    action_90d: str,
    run_id: str,
    db_path: str | Path = DEFAULT_DB_PATH,
    credential_path: str | Path = "~/.rig/rig-memory-os/credentials/coding-fleet.token",
    operator: str = "deviatrix-genesis",
) -> WriteReceipt:
    """Write one verified idea as a memory candidate.

    Uses the CLI ``rig-memory-os call memory.propose_memory`` so the
    Memory OS authorization + audit path is exactly what production
    RIG agents use. Returns a WriteReceipt.
    """
    payload = _build_memory_payload(
        idea_name=idea_name,
        formula=formula,
        falsifier=falsifier,
        composite_z=composite_z,
        archetype_z=archetype_z,
        is_respin=is_respin,
        mechanism_family=mechanism_family,
        parent_names=parent_names,
        action_90d=action_90d,
        run_id=run_id,
    )
    payload_json = json.dumps(payload)

    db = Path(db_path).expanduser()
    cred = Path(credential_path).expanduser()
    app_dir = Path("~/.rig/rig-memory-os/app").expanduser()
    env = os.environ.copy()
    env["RIG_MEMORY_DB"] = str(db)
    env["RIG_MEMORY_CREDENTIAL"] = str(cred)
    env["PYTHONPATH"] = f"{app_dir}/src"

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "rig_memory_os",
                "call",
                "memory.propose_memory",
                "--input",
                payload_json,
            ],
            cwd=str(app_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return WriteReceipt(
            idea_name=idea_name,
            accepted=False,
            memory_id=None,
            error="timeout",
            raw={},
        )
    except FileNotFoundError as e:
        return WriteReceipt(
            idea_name=idea_name,
            accepted=False,
            memory_id=None,
            error=f"rig-memory-os not found: {e}",
            raw={},
        )

    raw_out = (result.stdout or "") + (result.stderr or "")
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        parsed = {}

    if result.returncode != 0:
        return WriteReceipt(
            idea_name=idea_name,
            accepted=False,
            memory_id=None,
            error=f"exit {result.returncode}: {raw_out[:200]}",
            raw=parsed,
        )

    accepted = "status" not in parsed or parsed.get("status") not in {"BLOCK", "ERROR"}
    return WriteReceipt(
        idea_name=idea_name,
        accepted=accepted,
        memory_id=parsed.get("memory_id"),
        error=None if accepted else str(parsed.get("error", "")),
        raw=parsed,
    )


# ────────────────────────────────────────────────────────────────────
# Adapter object (combines read + write + history tracking)
# ────────────────────────────────────────────────────────────────────


class MemoryOSAdapter:
    """High-level adapter for the Deviatrix → Memory OS loop."""

    def __init__(
        self,
        *,
        db_path: str | Path = DEFAULT_DB_PATH,
        credential_path: str | Path = "~/.rig/rig-memory-os/credentials/coding-fleet.token",
        tenant_id: str = DEFAULT_TENANT,
    ) -> None:
        self.db_path = db_path
        self.credential_path = credential_path
        self.tenant_id = tenant_id

    def read_corpus(self, limit: int = 200) -> list[PriorMemory]:
        return read_prior_memories(self.db_path, tenant_id=self.tenant_id, limit=limit)

    def write_idea(self, **kwargs: Any) -> WriteReceipt:
        kwargs.setdefault("db_path", self.db_path)
        kwargs.setdefault("credential_path", self.credential_path)
        return write_idea_as_memory(**kwargs)
