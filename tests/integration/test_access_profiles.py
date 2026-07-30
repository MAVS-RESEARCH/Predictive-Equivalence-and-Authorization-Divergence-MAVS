"""Integration tests for Phase 6 visibility profiles and renderings."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from pead.audits.access import (
    assert_no_hidden_back_reference,
    validate_access_configs,
)
from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash
from pead.projections import graph, sequence, tabular
from pead.projections.oracle import (
    oracle_facts,
    project_oracle,
    reconstruct_oracle_projection,
)
from pead.projections.predictive import predictive_facts, project_predictive
from pead.projections.raw_governance import (
    project_raw_governance,
    raw_governance_facts,
)
from pead.tracks.exact import build_exact_pair, load_exact_allocations

REPO_ROOT = Path(__file__).parents[2]


class AccessProfileIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        allocation = load_exact_allocations(REPO_ROOT)[0]
        cls.pair = build_exact_pair(allocation, REPO_ROOT)
        cls.world = cls.pair.left.world_state

    def setUp(self) -> None:
        self.console = ResearchConsole("6", stream=io.StringIO())

    def test_access_configs_match_exact_frozen_field_masks(self) -> None:
        report = validate_access_configs(REPO_ROOT)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["frozen_predictive_fields"], 9)
        self.assertEqual(report["frozen_governance_fields"], 9)
        self.assertEqual(report["declared_oracle_fields"], 2)

    def test_profiles_are_nested_without_hidden_back_references(self) -> None:
        p_only, p_trace = project_predictive(
            self.world,
            representation_id=tabular.REPRESENTATION_ID,
            console=self.console,
        )
        raw_g, raw_trace = project_raw_governance(
            self.world,
            representation_id=tabular.REPRESENTATION_ID,
            console=self.console,
        )
        oracle_g, oracle_trace = project_oracle(
            self.world,
            representation_id=tabular.REPRESENTATION_ID,
            console=self.console,
        )
        self.assertEqual(len(p_only.field_ids), 9)
        self.assertEqual(len(raw_g.field_ids), 18)
        self.assertEqual(len(oracle_g.field_ids), 20)
        self.assertEqual(
            set(p_only.field_ids),
            {field_id for field_id in raw_g.field_ids if field_id.startswith("P-")},
        )
        self.assertEqual(
            set(raw_g.field_ids),
            {
                field_id
                for field_id in oracle_g.field_ids
                if not field_id.startswith("O-")
            },
        )
        self.assertEqual(
            {p_trace.world_id, raw_trace.world_id, oracle_trace.world_id},
            {self.world.world_id},
        )
        for sealed in (p_only, raw_g, oracle_g):
            assert_no_hidden_back_reference(sealed)

    def test_all_renderings_are_lossless_and_semantically_equal(self) -> None:
        source = raw_governance_facts(self.world)
        hashes = set()
        reconstructors = {
            tabular.REPRESENTATION_ID: tabular.reconstruct,
            sequence.REPRESENTATION_ID: sequence.reconstruct,
            graph.REPRESENTATION_ID: graph.reconstruct,
        }
        for representation, reconstruct in reconstructors.items():
            sealed, trace = project_raw_governance(
                self.world,
                representation_id=representation,
                console=self.console,
            )
            self.assertEqual(canonical_hash(reconstruct(sealed.payload)), canonical_hash(source))
            self.assertFalse(trace.lossy)
            self.assertFalse(any(trace.truncation.values()))
            hashes.add(trace.semantic_fact_hash)
        self.assertEqual(hashes, {canonical_hash(tuple(sorted(source.items())))})

    def test_oracle_serialization_reconstructs_every_visible_fact(self) -> None:
        expected = canonical_hash(oracle_facts(self.world))
        for representation in (
            tabular.REPRESENTATION_ID,
            sequence.REPRESENTATION_ID,
            graph.REPRESENTATION_ID,
        ):
            sealed, _ = project_oracle(
                self.world,
                representation_id=representation,
                console=self.console,
            )
            self.assertEqual(
                canonical_hash(reconstruct_oracle_projection(sealed)),
                expected,
            )

    def test_predictive_projection_contains_no_governance_ids(self) -> None:
        sealed, trace = project_predictive(
            self.world,
            representation_id=tabular.REPRESENTATION_ID,
            console=self.console,
        )
        self.assertEqual(set(sealed.payload), set(predictive_facts(self.world)))
        self.assertTrue(all(field_id.startswith("P-") for field_id in trace.field_mask))
        self.assertFalse(any(field_id.startswith(("G-", "O-")) for field_id in trace.field_mask))


if __name__ == "__main__":
    unittest.main()
