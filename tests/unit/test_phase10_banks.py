from __future__ import annotations

import unittest

import numpy as np

from pead.phase10.banks import _bank_arrays


class Phase10BankTests(unittest.TestCase):
    def test_exact_pairs_preserve_predictive_equivalence_and_group_atomicity(self):
        value = _bank_arrays("development_fit", 1, "exact", 100)
        self.assertEqual(len(value["label"]), 200)
        controls = 0
        for index in range(0, 200, 2):
            np.testing.assert_equal(value["features"][index, :8], value["features"][index + 1, :8])
            self.assertEqual(value["atomic_group_id"][index], value["atomic_group_id"][index + 1])
            controls += int(value["label"][index] == value["label"][index + 1])
        self.assertEqual(controls, 20)

    def test_roles_and_domains_have_disjoint_identities(self):
        values = [_bank_arrays(role, domain, "near", 20) for role in ("development_fit", "calibration_fit", "public_validation") for domain in (1, 6)]
        identities = [set(item["case_id"].tolist()) for item in values]
        for left in range(len(identities)):
            for right in range(left + 1, len(identities)): self.assertFalse(identities[left] & identities[right])

    def test_public_shift_does_not_change_registered_shape(self):
        development = _bank_arrays("development_fit", 2, "scope", 50)
        public = _bank_arrays("public_validation", 2, "scope", 50)
        self.assertEqual(development["features"].shape, public["features"].shape)
        self.assertFalse(np.array_equal(np.nan_to_num(development["features"]), np.nan_to_num(public["features"])))

    def test_oracle_projection_reconstructs_every_authorization_label(self):
        for track in ("exact", "near", "reversal", "scope", "evidence"):
            value = _bank_arrays("public_validation", 3, track, 100)
            self.assertTrue(np.array_equal(value["features"][:, 23].astype(np.uint8), value["label"]))
