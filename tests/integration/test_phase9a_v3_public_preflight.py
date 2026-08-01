from __future__ import annotations

import json
import unittest
from pathlib import Path

from pead.custody.contract import COMMITMENT_FIELDS, PACKAGE_FIELDS, validate_commitment, verify_public_precommit, verify_signature
from pead.custody.events import read_event_log, verify_event_log


class Phase9AV3PublicPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).parents[2]
        cls.commitment_path = cls.root / "manifests/custody/holdout_design_commitment.json"
        cls.index_path = cls.root / "manifests/custody/encrypted_blind_package.index.json"
        cls.commitment = json.loads(cls.commitment_path.read_text(encoding="utf-8"))

    def test_real_public_precommit_requires_every_exact_field(self) -> None:
        result = validate_commitment(self.commitment, expected_study="pead-study-v3", expected_preseal="phase9a-preseal-v3")
        self.assertEqual(set(self.commitment), COMMITMENT_FIELDS)
        self.assertEqual(set(result["packages"]), {"content", "labels", "seeds"})
        self.assertTrue(all(set(package) == PACKAGE_FIELDS for package in self.commitment["packages"]))

    def test_real_ciphertexts_and_signed_index_pass_public_consumer(self) -> None:
        result = verify_public_precommit(
            self.root,
            self.commitment_path,
            self.index_path,
            expected_study="pead-study-v3",
            expected_preseal="phase9a-preseal-v3",
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["missing_commitments"], [])
        self.assertEqual(result["consumer_invented_values"], [])

    def test_real_custody_log_is_fully_signed_from_event_one(self) -> None:
        events = read_event_log(self.root / "manifests/custody/phase9a-preseal-v3.custody-events.jsonl")
        receipt = verify_event_log(
            events,
            study_version="pead-study-v3",
            preseal_id="phase9a-preseal-v3",
            expected_signer_identity=self.commitment["custody_public_key_identity"],
        )
        self.assertEqual(receipt["event_count"], 309)
        self.assertEqual(receipt["unsigned_events"], 0)
        self.assertEqual(receipt["head_sha256"], self.commitment["custody_log_head_sha256"])

    def test_signed_design_inventory_matches_frozen_semantic_reference(self) -> None:
        inventory = json.loads((self.root / "manifests/custody/holdout_design_inventory.json").read_text(encoding="utf-8"))
        verify_signature(inventory, expected_signer=self.commitment["custody_public_key_identity"])
        observed = {row["artifact_id"]: row["sha256"] for row in inventory["design_artifacts"]}
        invariance = json.loads((self.root / "manifests/scientific_invariance_v3.json").read_text(encoding="utf-8"))
        expected = invariance["must_remain_semantically_identical"]["reference_artifacts"]
        self.assertEqual({path: observed[path] for path in expected}, expected)
