from __future__ import annotations

import json
import unittest
from pathlib import Path

from pead.holdouts.commitment_verifier import verify_signed_mapping
from pead.holdouts.interface import HoldoutContractError

ROOT = Path(__file__).parents[2]


class Phase9AStressTests(unittest.TestCase):
    def test_1000_signature_mutations_fail_closed(self):
        base = json.loads((ROOT / "manifests/allocations/final_claim_bank_v1.json").read_text(encoding="utf-8"))
        for index in range(1000):
            changed = dict(base); changed["allocation_id"] = f"mutation-{index}"
            with self.assertRaises(HoldoutContractError): verify_signed_mapping(changed)

    def test_all_design_hashes_unique_and_complete(self):
        commitment = json.loads((ROOT / "manifests/custody/holdout_design_commitment.json").read_text(encoding="utf-8"))
        rows = commitment["design_artifacts"]
        self.assertEqual(len(rows), 15)
        self.assertEqual(len({row["artifact_id"] for row in rows}), 15)
        self.assertEqual(len({row["sha256"] for row in rows}), 15)
