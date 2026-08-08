"""Contract tests for v4 proof-packet export to RIG Memory OS."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from deviatrix_genesis.v4.memory_export import (
    candidate_payload,
    export_proof_packet,
    memory_id_for,
    run_id_for,
    source_hash,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PACKET_PATH = PROJECT_ROOT / "v4_proofs" / "data.json"


class TestMemoryExport(unittest.TestCase):
    """Keep the export candidate-only, provenance-bound, and idempotent by design."""

    def setUp(self) -> None:
        self.packet_hash = source_hash(PACKET_PATH)
        self.packet = json.loads(PACKET_PATH.read_text())
        self.survivor = self.packet["survivors"][0]

    def test_memory_id_is_deterministic_per_source_and_candidate(self) -> None:
        name = self.survivor["name"]
        self.assertEqual(
            memory_id_for(self.packet_hash, name),
            memory_id_for(self.packet_hash, name),
        )
        self.assertNotEqual(
            memory_id_for(self.packet_hash, name),
            memory_id_for(self.packet_hash, "different candidate"),
        )

    def test_candidate_is_blocked_when_any_verifier_failed(self) -> None:
        payload = candidate_payload(
            self.survivor,
            packet_hash=self.packet_hash,
            run_id=run_id_for(self.packet_hash),
            imported_at="2026-08-07T00:00:00+00:00",
            tenant_id="rig-default",
        )
        self.assertEqual(payload["status"], "candidate")
        self.assertEqual(payload["source_type"], "model_synthesized")
        self.assertTrue(payload["content"]["promotion_blocked"])
        self.assertFalse(payload["content"]["independent_verifier_passed"])
        self.assertEqual(
            payload["content"]["source_packet_sha256"], self.packet_hash
        )

    def test_dry_run_exports_every_packet_candidate_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            receipt = export_proof_packet(
                PACKET_PATH,
                db_path=Path(directory) / "memory.db",
                dry_run=True,
            )
        self.assertEqual(receipt.proposed, len(self.packet["survivors"]))
        self.assertEqual(receipt.event_count, 1)
        self.assertEqual(receipt.already_present, 0)
        self.assertEqual(len(receipt.memory_ids), len(self.packet["survivors"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
