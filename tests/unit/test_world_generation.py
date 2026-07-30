"""Unit tests for Phase 3 world schemas and independent generators."""

from __future__ import annotations

import dataclasses
import unittest
from pathlib import Path

from pead.audits.leakage import audit_generator_sources
from pead.tracks.exact import build_exact_pair, load_exact_allocations
from pead.world.mechanisms import MECHANISMS


REPO_ROOT = Path(__file__).resolve().parents[2]


class WorldGenerationTests(unittest.TestCase):
    def test_mechanism_registry_is_exactly_M01_through_M12(self) -> None:
        self.assertEqual(
            tuple(item.mechanism_id for item in MECHANISMS),
            tuple(f"M{index:02d}" for index in range(1, 13)),
        )
        self.assertEqual(MECHANISMS[10].permitted_subbanks, ("I-N",))

    def test_generated_world_schema_has_no_authorization_label(self) -> None:
        pair = build_exact_pair(load_exact_allocations(REPO_ROOT)[0], REPO_ROOT)
        names = {field.name for field in dataclasses.fields(pair.left)}
        self.assertFalse(
            names & {"label", "authorization_label", "target", "outcome"}
        )

    def test_generator_sources_are_label_free_and_independent(self) -> None:
        report = audit_generator_sources(REPO_ROOT)
        self.assertEqual(report["status"], "pass")
        self.assertTrue(report["separate_primary_reference_sources"])


if __name__ == "__main__":
    unittest.main()
