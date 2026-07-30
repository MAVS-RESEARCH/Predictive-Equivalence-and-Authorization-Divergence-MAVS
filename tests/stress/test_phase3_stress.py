"""Stress gates for the complete Phase 3 allocation and sampled generation space."""

from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from pead.tracks.exact import allocation_counts, load_exact_allocations
from pead.tracks.near import (
    build_near_pair,
    load_near_allocations,
    near_allocation_counts,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class Phase3StressTests(unittest.TestCase):
    def test_complete_allocation_denominators_and_quotas(self) -> None:
        exact = load_exact_allocations(REPO_ROOT)
        near = load_near_allocations(REPO_ROOT)
        exact_counts = allocation_counts(exact)
        near_counts = near_allocation_counts(near)
        self.assertEqual(exact_counts["pairs"], 16_000)
        self.assertEqual(near_counts["pairs"], 8_000)
        self.assertEqual(exact_counts["atomic_groups"], 16_000)
        self.assertEqual(near_counts["atomic_groups"], 8_000)
        self.assertEqual(
            exact_counts["subbanks"],
            Counter({"I-A": 6_400, "I-B": 3_200, "I-C": 3_200, "I-N": 3_200}),
        )
        self.assertEqual(
            exact_counts["world_labels"],
            Counter({"Escalate": 10_668, "Accept": 10_666, "Reject": 10_666}),
        )
        self.assertEqual(
            near_counts["world_labels"],
            Counter({"Accept": 5_334, "Reject": 5_334, "Escalate": 5_332}),
        )
        self.assertEqual(exact_counts["three_or_more_facts"], 6_400)

    def test_all_64_near_epsilon_cells_generate_with_frozen_distance(self) -> None:
        allocations = load_near_allocations(REPO_ROOT)
        for domain_index in range(8):
            for epsilon_index in range(8):
                index = domain_index * 1_000 + epsilon_index * 125
                pair = build_near_pair(allocations[index], REPO_ROOT)
                self.assertLessEqual(
                    abs(pair.distance.aggregate - pair.allocation.epsilon),
                    1e-12,
                )
                self.assertFalse(
                    pair.governance_intervention_visible_in_predictive
                )


if __name__ == "__main__":
    unittest.main()
