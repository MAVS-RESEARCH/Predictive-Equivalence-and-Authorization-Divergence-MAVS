from __future__ import annotations

import unittest

from pead.core.ids import (
    ContentId,
    artifact_id,
    derive_content_id,
    pair_id,
    run_id,
    sequence_id,
    world_id,
)


class ContentIdTests(unittest.TestCase):
    def test_all_required_id_kinds_are_full_content_digests(self) -> None:
        payload = {"study": "pead", "value": 1}
        identifiers = {
            "world": world_id(payload),
            "pair": pair_id(payload),
            "sequence": sequence_id(payload),
            "run": run_id(payload),
            "artifact": artifact_id(payload),
        }
        for kind, identifier in identifiers.items():
            parsed = ContentId.parse(identifier, expected_kind=kind)
            self.assertEqual(len(parsed.digest), 64)

    def test_identifier_is_order_invariant_and_content_sensitive(self) -> None:
        self.assertEqual(
            derive_content_id("world", {"b": 2, "a": 1}),
            derive_content_id("world", {"a": 1, "b": 2}),
        )
        self.assertNotEqual(
            derive_content_id("world", {"a": 1}),
            derive_content_id("world", {"a": 2}),
        )

    def test_malformed_or_wrong_kind_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ContentId.parse("world_short")
        with self.assertRaises(ValueError):
            ContentId.parse(world_id({"a": 1}), expected_kind="pair")


if __name__ == "__main__":
    unittest.main()
