"""Stress tests for Phase 11 bank completeness and mutation rejection."""

from __future__ import annotations

import copy
import gzip
import json
import unittest
from collections import Counter
from pathlib import Path

from pead.phase11.contracts import Phase11ContractError, verify_signed_mapping


class Phase11StressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.freeze_path = cls.root / "manifests/freeze_manifest.json"
        cls.bank_path = cls.root / "manifests/blind_bank_manifest.json"

    def test_1200_signed_freeze_mutations_rejected(self) -> None:
        if not self.freeze_path.is_file():
            self.skipTest("authoritative freeze follows the pre-freeze test stage")
        freeze = json.loads(self.freeze_path.read_text(encoding="utf-8"))
        rejected = 0
        for index in range(1200):
            value = copy.deepcopy(freeze)
            if index % 3 == 0:
                value["freeze_id"] += "x"
            elif index % 3 == 1:
                value["phase9a_commitment_sha256"] = "0" * 64
            else:
                value["signature"]["signature_b64"] = value["signature"]["signature_b64"][:-2] + "AA"
            try:
                verify_signed_mapping(value)
            except (Phase11ContractError, ValueError):
                rejected += 1
        self.assertEqual(rejected, 1200)

    def test_complete_projection_denominator_and_identity_uniqueness(self) -> None:
        if not self.bank_path.is_file():
            self.skipTest("sealed banks follow the signed freeze")
        manifest = json.loads(self.bank_path.read_text(encoding="utf-8"))
        totals: Counter[str] = Counter()
        for bank, bank_value in manifest["banks"].items():
            profile_ids: dict[str, set[str]] = {}
            for profile, value in bank_value["projections"].items():
                identities: set[str] = set()
                with gzip.open(self.root / value["path"], "rt", encoding="utf-8") as stream:
                    for line in stream:
                        row = json.loads(line)
                        identities.add(row["case_id"])
                        totals[profile] += 1
                self.assertEqual(len(identities), value["records"])
                profile_ids[profile] = identities
            self.assertEqual(profile_ids["P-only"], profile_ids["Raw-G"])
            self.assertEqual(profile_ids["P-only"], profile_ids["Oracle-G"])
        self.assertEqual(totals, Counter({"P-only": 106400, "Raw-G": 106400, "Oracle-G": 106400}))


if __name__ == "__main__":
    unittest.main()

