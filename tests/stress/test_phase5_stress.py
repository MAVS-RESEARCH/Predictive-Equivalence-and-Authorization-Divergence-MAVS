"""Complete Phase 5 open-domain denominator and mutation stress gates."""

from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from pead.core.hashing import canonical_hash
from pead.phase5.review import load_open_adapters


REPO_ROOT = Path(__file__).resolve().parents[2]


class Phase5StressTests(unittest.TestCase):
    def test_all_3600_open_cases_validate_with_exact_mechanism_balance(self) -> None:
        adapters = load_open_adapters(REPO_ROOT)
        total = 0
        identities = set()
        for adapter in adapters:
            definition = adapter.definition
            count = len(definition.mechanisms) * definition.cases_per_mechanism
            cases = tuple(adapter.build_case(index) for index in range(count))
            total += len(cases)
            identities.update(case.case_id for case in cases)
            self.assertEqual(
                Counter(case.mechanism.mechanism_id for case in cases),
                Counter(
                    {
                        mechanism.mechanism_id: definition.cases_per_mechanism
                        for mechanism in definition.mechanisms
                    }
                ),
            )
        self.assertEqual(total, 3_600)
        self.assertEqual(len(identities), 3_600)

    def test_all_288_crossed_anti_shortcut_variants_are_invariant(self) -> None:
        adapters = load_open_adapters(REPO_ROOT)
        variants = tuple(
            variant
            for adapter in adapters
            for mechanism_index in range(len(adapter.definition.mechanisms))
            for variant in adapter.anti_shortcut_variants(mechanism_index)
        )
        self.assertEqual(len(variants), 288)
        groups: dict[tuple[str, str], list] = {}
        for variant in variants:
            groups.setdefault(
                (variant.domain_id, variant.mechanism.mechanism_id),
                [],
            ).append(variant)
        self.assertEqual(len(groups), 36)
        for group in groups.values():
            self.assertEqual(len({item.latent_meaning_hash for item in group}), 1)
            self.assertEqual(
                len({canonical_hash(item.projection) for item in group}),
                1,
            )
            self.assertEqual(len({item.surface_hash for item in group}), 8)
