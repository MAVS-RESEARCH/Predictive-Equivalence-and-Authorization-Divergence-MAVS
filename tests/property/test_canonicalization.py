from __future__ import annotations

import itertools
import random
import unittest

from pead.core.hashing import canonical_bytes, canonical_hash
from pead.core.ids import derive_content_id


class CanonicalizationPropertyTests(unittest.TestCase):
    def test_every_key_permutation_has_one_hash_and_byte_sequence(self) -> None:
        items = [
            ("alpha", 1),
            ("beta", 2.0000000000001),
            ("gamma", {"z", "a"}),
            (
                "graph",
                {
                    "nodes": [{"id": "n2"}, {"id": "n1"}],
                    "edges": [{"source": "n1", "target": "n2", "type": "r"}],
                },
            ),
            ("text", "cafe\u0301"),
        ]
        byte_values = {
            canonical_bytes(dict(permutation))
            for permutation in itertools.permutations(items)
        }
        hash_values = {
            canonical_hash(dict(permutation))
            for permutation in itertools.permutations(items)
        }
        self.assertEqual(len(byte_values), 1)
        self.assertEqual(len(hash_values), 1)

    def test_random_nested_order_changes_preserve_identity(self) -> None:
        randomizer = random.Random(101)
        reference = {
            "outer": {"x": 1, "y": 2, "z": 3},
            "set": {"c", "a", "b"},
            "graph": {
                "nodes": [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}],
                "edges": [
                    {"source": "n1", "target": "n2", "type": "a"},
                    {"source": "n2", "target": "n3", "type": "b"},
                ],
            },
        }
        expected = derive_content_id("artifact", reference)
        for _ in range(2_000):
            outer_items = list(reference["outer"].items())
            nodes = list(reference["graph"]["nodes"])
            edges = list(reference["graph"]["edges"])
            randomizer.shuffle(outer_items)
            randomizer.shuffle(nodes)
            randomizer.shuffle(edges)
            candidate = {
                "graph": {"edges": edges, "nodes": nodes},
                "set": set(reference["set"]),
                "outer": dict(outer_items),
            }
            self.assertEqual(derive_content_id("artifact", candidate), expected)


if __name__ == "__main__":
    unittest.main()
