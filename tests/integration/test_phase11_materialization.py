"""Integration tests for the immutable Phase 11 bank contract."""

from __future__ import annotations

import gzip
import json
import unittest
from pathlib import Path

from pead.custody.contract import sha256_file


class Phase11MaterializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.path = cls.root / "manifests/blind_bank_manifest.json"
        if not cls.path.is_file():
            raise unittest.SkipTest("blind bank is created only after the signed freeze")
        cls.manifest = json.loads(cls.path.read_text(encoding="utf-8"))

    def test_exact_counts_hashes_and_lineage(self) -> None:
        self.assertEqual(self.manifest["study_version"], "pead-study-v3")
        self.assertEqual(self.manifest["preseal_id"], "phase9a-preseal-v3")
        self.assertEqual(self.manifest["bank_counts"]["total_records"], 106400)
        self.assertEqual(sum(self.manifest["bank_counts"]["per_bank"].values()), 106400)
        for bank in self.manifest["banks"].values():
            for value in bank["projections"].values():
                path = self.root / value["path"]
                self.assertEqual(sha256_file(path), value["sha256"])

    def test_registered_projection_fields_and_no_labels(self) -> None:
        forbidden = {"label", "decision", "ambiguity_certificate", "world_truth", "seed", "seed_identity"}
        for bank in self.manifest["banks"].values():
            for profile, value in bank["projections"].items():
                with gzip.open(self.root / value["path"], "rt", encoding="utf-8") as stream:
                    row = json.loads(next(stream))
                self.assertEqual(row["access_profile"], profile)
                self.assertFalse(forbidden.intersection(row))
                self.assertIn("predictive_state", row)
                self.assertEqual("governance_state" in row, profile in {"Raw-G", "Oracle-G"})

    def test_labels_are_separately_encrypted_and_one_shot(self) -> None:
        self.assertEqual(self.manifest["labels"]["state"], "separately-encrypted-evaluator-only")
        self.assertTrue(self.manifest["labels"]["evaluator_only"])
        self.assertEqual(self.manifest["materialization_count"], 1)
        self.assertTrue(self.manifest["one_shot_state_consumed"])


if __name__ == "__main__":
    unittest.main()

