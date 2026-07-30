"""Authorization and proof properties across all registered mechanisms."""

from __future__ import annotations

import unittest
from pathlib import Path

from pead.labels.ambiguity import CompatibleWorld, verify_certificate
from pead.tracks.exact import build_exact_pair, load_exact_allocations


REPO_ROOT = Path(__file__).resolve().parents[2]


class Phase3AuthorizationTests(unittest.TestCase):
    def test_all_mechanisms_generate_expected_dual_engine_labels(self) -> None:
        allocations = load_exact_allocations(REPO_ROOT)
        selected = {}
        for allocation in allocations:
            selected.setdefault(allocation.mechanism_id, allocation)
            if len(selected) == 12:
                break
        self.assertEqual(len(selected), 12)
        for mechanism, allocation in selected.items():
            with self.subTest(mechanism=mechanism):
                pair = build_exact_pair(allocation, REPO_ROOT)
                self.assertIs(
                    pair.left_evaluation.label,
                    allocation.left_expected,
                )
                self.assertIs(
                    pair.right_evaluation.label,
                    allocation.right_expected,
                )

    def test_escalation_certificates_verify_independently(self) -> None:
        allocations = load_exact_allocations(REPO_ROOT)
        pair = build_exact_pair(allocations[800], REPO_ROOT)
        self.assertTrue(pair.ambiguity_certificates)
        for certificate in pair.ambiguity_certificates:
            worlds = tuple(
                CompatibleWorld(
                    witness.world_id,
                    witness.facts_hash,
                    witness.authorization,
                )
                for witness in certificate.witnesses
            )
            self.assertTrue(verify_certificate(certificate, worlds))


if __name__ == "__main__":
    unittest.main()
