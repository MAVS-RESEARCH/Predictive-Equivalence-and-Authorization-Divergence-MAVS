from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from pead.holdouts.commitment_verifier import verify_preseal, verify_signed_mapping
from pead.holdouts.interface import HoldoutContractError, HoldoutPackageIndex

ROOT = Path(__file__).parents[2]


class HoldoutCommitmentTests(unittest.TestCase):
    def test_complete_preseal_verifies(self):
        receipt = verify_preseal(ROOT)
        self.assertEqual(receipt.status, "pass")
        self.assertEqual(len(receipt.verified_ciphertexts), 3)

    def test_signature_mutation_is_blocked(self):
        value = json.loads((ROOT / "manifests/custody/holdout_design_commitment.json").read_text(encoding="utf-8"))
        changed = copy.deepcopy(value); changed["study_version"] = "tampered"
        with self.assertRaises(HoldoutContractError): verify_signed_mapping(changed)

    def test_package_roles_must_be_separate(self):
        value = json.loads((ROOT / "manifests/custody/encrypted_blind_package.index.json").read_text(encoding="utf-8"))
        value["packages"][2]["role"] = "content"
        with self.assertRaises(HoldoutContractError): HoldoutPackageIndex.from_mapping(value)
