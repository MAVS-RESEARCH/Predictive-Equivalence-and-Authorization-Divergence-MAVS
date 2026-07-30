from __future__ import annotations

import unittest

from pead.core.hashing import (
    CanonicalizationError,
    canonical_bytes,
    canonical_hash,
    field_hashes,
    normalize_candidate_action,
)
from tests.phase1_fixtures import predictive_state


class CanonicalHashingTests(unittest.TestCase):
    def test_mapping_order_and_unicode_composition_are_invariant(self) -> None:
        left = {"b": 2, "a": "cafe\u0301"}
        right = {"a": "café", "b": 2}
        self.assertEqual(canonical_bytes(left), canonical_bytes(right))
        self.assertEqual(canonical_hash(left), canonical_hash(right))

    def test_float_quantization_is_half_even_decimal12(self) -> None:
        self.assertEqual(
            canonical_hash({"value": 0.1234567890124}),
            canonical_hash({"value": 0.12345678901249}),
        )
        self.assertNotEqual(
            canonical_hash({"value": 0.1234567890124}),
            canonical_hash({"value": 0.1234567890136}),
        )

    def test_nonfinite_floats_are_rejected(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(CanonicalizationError):
                    canonical_bytes(value)

    def test_set_and_graph_order_are_stable(self) -> None:
        graph_a = {
            "nodes": [{"id": "b", "x": 2}, {"id": "a", "x": 1}],
            "edges": [
                {"source": "b", "target": "a", "type": "x"},
                {"source": "a", "target": "b", "type": "y"},
            ],
            "tags": {"beta", "alpha"},
        }
        graph_b = {
            "tags": {"alpha", "beta"},
            "edges": list(reversed(graph_a["edges"])),
            "nodes": list(reversed(graph_a["nodes"])),
        }
        self.assertEqual(canonical_bytes(graph_a), canonical_bytes(graph_b))

    def test_graph_without_stable_identifiers_is_rejected(self) -> None:
        with self.assertRaises(CanonicalizationError):
            canonical_bytes({"nodes": [{"name": "unstable"}], "edges": []})

    def test_candidate_action_rejects_governance_annotations(self) -> None:
        with self.assertRaises(CanonicalizationError):
            normalize_candidate_action({"action_type": "classify", "policy": "p1"})
        with self.assertRaises(CanonicalizationError):
            normalize_candidate_action(
                {"action_type": "classify", "parameters": {"authority": "admin"}}
            )

    def test_candidate_action_float_remains_canonicalizable(self) -> None:
        action = normalize_candidate_action(
            {"action_type": "score", "parameters": {"threshold": 0.1234567890124}}
        )
        self.assertEqual(
            canonical_hash(action),
            canonical_hash(
                {"parameters": {"threshold": 0.12345678901249}, "action_type": "score"}
            ),
        )

    def test_field_hashes_cover_every_record_field(self) -> None:
        state = predictive_state()
        hashes = field_hashes(state)
        self.assertEqual(len(hashes), 10)
        self.assertTrue(all(len(value) == 64 for value in hashes.values()))


if __name__ == "__main__":
    unittest.main()
