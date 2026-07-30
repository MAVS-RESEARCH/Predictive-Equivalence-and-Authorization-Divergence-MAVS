"""Properties for atomic grouping and lineage-safe splits."""

from __future__ import annotations

import unittest
from collections import defaultdict
from pathlib import Path

from pead.tracks.exact import load_exact_allocations
from pead.tracks.near import load_near_allocations


REPO_ROOT = Path(__file__).resolve().parents[2]


class GroupSplitTests(unittest.TestCase):
    def test_all_pair_and_lineage_groups_are_indivisible(self) -> None:
        allocations = (
            *load_exact_allocations(REPO_ROOT),
            *load_near_allocations(REPO_ROOT),
        )
        self.assertEqual(
            len({item.atomic_group_id for item in allocations}),
            len(allocations),
        )
        lineage_splits = defaultdict(set)
        for item in allocations:
            for kind, lineage in (
                ("template", item.template_family_id),
                ("latent", item.latent_family_id),
                ("sequence", item.sequence_lineage_id),
                ("intervention", item.intervention_lineage_id),
                ("provenance", item.provenance_lineage_id),
            ):
                lineage_splits[(kind, lineage)].add(item.split_id)
        self.assertFalse(
            {
                lineage: splits
                for lineage, splits in lineage_splits.items()
                if len(splits) != 1
            }
        )


if __name__ == "__main__":
    unittest.main()
