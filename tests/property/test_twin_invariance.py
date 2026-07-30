"""Property tests for exact predictive-equivalence twins."""

from __future__ import annotations

import unittest
from pathlib import Path

from pead.tracks.exact import build_exact_pair, load_exact_allocations


REPO_ROOT = Path(__file__).resolve().parents[2]


class TwinInvarianceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.allocations = load_exact_allocations(REPO_ROOT)

    def test_exact_twins_preserve_predictive_state(self) -> None:
        sample_indices = [
            domain * 2_000 + offset
            for domain in range(8)
            for offset in (0, 799, 800, 1_200, 1_600, 1_999)
        ]
        for index in sample_indices:
            with self.subTest(index=index):
                pair = build_exact_pair(self.allocations[index], REPO_ROOT)
                self.assertEqual(pair.predictive_equivalence_index, 1)
                self.assertTrue(pair.predictive_field_equal)
                self.assertTrue(pair.predictive_byte_equal)
                self.assertTrue(pair.primary_reference_generation_agreement)

    def test_divergent_and_same_label_controls_have_required_adi(self) -> None:
        for offset, expected_adi in (
            (0, 1),
            (800, 1),
            (1_200, 1),
            (1_600, 0),
        ):
            pair = build_exact_pair(self.allocations[offset], REPO_ROOT)
            self.assertEqual(pair.authorization_divergence_index, expected_adi)

    def test_interventions_freeze_predictive_parents(self) -> None:
        for index in range(0, 2_000, 137):
            pair = build_exact_pair(self.allocations[index], REPO_ROOT)
            self.assertTrue(
                pair.intervention_proof.predictive_parents_byte_equal
            )
            self.assertEqual(
                pair.intervention_proof.unchanged_predictive_parent_hash_before,
                pair.intervention_proof.unchanged_predictive_parent_hash_after,
            )


if __name__ == "__main__":
    unittest.main()
