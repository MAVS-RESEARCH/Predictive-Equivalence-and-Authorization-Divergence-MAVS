"""Complete Phase 4 denominator, quota, and integrity stress gates."""

from __future__ import annotations

import unittest
from collections import Counter
from pathlib import Path

from pead.tracks.evidence_sufficiency import evidence_case_counts, iter_evidence_cases
from pead.tracks.reversal import (
    load_reversal_allocations,
    load_reversal_controls,
    reversal_allocation_counts,
)
from pead.tracks.scope import iter_scope_cases, scope_case_counts


REPO_ROOT = Path(__file__).resolve().parents[2]


class Phase4StressTests(unittest.TestCase):
    def test_bank_generators_consume_signed_manifest_not_allocation_yaml(self) -> None:
        for relative in (
            "src/pead/tracks/reversal.py",
            "src/pead/tracks/scope.py",
            "src/pead/tracks/evidence_sufficiency.py",
        ):
            source = (REPO_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("configs/tracks/", source)
            self.assertNotIn("configs/allocations/", source)
            self.assertNotIn("import yaml", source)
            self.assertIn("load_phase4_manifest", source)

    def test_complete_allocation_denominators_and_quotas(self) -> None:
        reversals = reversal_allocation_counts(
            load_reversal_allocations(REPO_ROOT),
            load_reversal_controls(REPO_ROOT),
        )
        scope = scope_case_counts(tuple(iter_scope_cases(REPO_ROOT)))
        evidence = evidence_case_counts(tuple(iter_evidence_cases(REPO_ROOT)))
        self.assertEqual(reversals["canonical_sequences"], 4_000)
        self.assertEqual(reversals["canonical_steps"], 24_000)
        self.assertEqual(reversals["additional_controls"], 800)
        self.assertEqual(
            reversals["lengths"],
            Counter({6: 2_400, 4: 800, 8: 800}),
        )
        self.assertEqual(scope["canonical_cases"], 22_400)
        self.assertEqual(scope["additional_controls"], 5_600)
        self.assertEqual(scope["atomic_groups"], 28_000)
        self.assertEqual(evidence["total_cases"], 12_000)
        self.assertEqual(evidence["verified_certificates"], 12_000)
        self.assertEqual(evidence["atomic_groups"], 12_000)

    def test_each_domain_has_exact_normative_allocations(self) -> None:
        allocations = load_reversal_allocations(REPO_ROOT)
        scope = tuple(iter_scope_cases(REPO_ROOT))
        evidence = tuple(iter_evidence_cases(REPO_ROOT))
        self.assertEqual(Counter(item.domain_id for item in allocations), Counter({f"D{i}": 500 for i in range(1, 9)}))
        self.assertEqual(Counter(item.domain_id for item in scope), Counter({f"D{i}": 3_500 for i in range(1, 9)}))
        self.assertEqual(Counter(item.domain_id for item in evidence), Counter({f"D{i}": 1_500 for i in range(1, 9)}))
