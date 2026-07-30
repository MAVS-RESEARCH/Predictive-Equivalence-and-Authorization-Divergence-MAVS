from __future__ import annotations

import unittest

from pead.core.seeds import SEED_NAMESPACES, derive_seed


class SeedLineageTests(unittest.TestCase):
    def test_derivation_is_deterministic_and_in_namespace(self) -> None:
        first = derive_seed(
            namespace="development", root_seed=11, component="world", index=4
        )
        second = derive_seed(
            namespace="development", root_seed=11, component="world", index=4
        )
        self.assertEqual(first, second)
        lower, upper = SEED_NAMESPACES["development"]
        self.assertLessEqual(lower, first.derived_seed)
        self.assertLessEqual(first.derived_seed, upper)

    def test_namespaces_are_pairwise_disjoint(self) -> None:
        ranges = list(SEED_NAMESPACES.values())
        for index, left in enumerate(ranges):
            for right in ranges[index + 1 :]:
                self.assertTrue(left[1] < right[0] or right[1] < left[0])

    def test_component_and_index_change_lineage(self) -> None:
        base = derive_seed(
            namespace="calibration", root_seed=7, component="case", index=0
        )
        changed = derive_seed(
            namespace="calibration", root_seed=7, component="case", index=1
        )
        self.assertNotEqual(base.derivation_digest, changed.derivation_digest)

    def test_invalid_namespace_or_index_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            derive_seed(namespace="unknown", root_seed=1, component="case")
        with self.assertRaises(ValueError):
            derive_seed(
                namespace="development", root_seed=1, component="case", index=-1
            )


if __name__ == "__main__":
    unittest.main()
