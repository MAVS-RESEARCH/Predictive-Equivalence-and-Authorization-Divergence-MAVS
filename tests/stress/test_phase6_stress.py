"""Mutation and scale stress tests for Phase 6 projections."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash
from pead.projections import graph, sequence, tabular
from pead.projections.oracle import project_oracle, reconstruct_oracle_projection
from pead.projections.raw_governance import project_raw_governance
from pead.tracks.exact import build_exact_pair, load_exact_allocations

REPO_ROOT = Path(__file__).parents[2]


class Phase6StressTests(unittest.TestCase):
    def test_cross_representation_and_oracle_round_trip_on_192_worlds(self) -> None:
        allocations = load_exact_allocations(REPO_ROOT)
        selected = []
        counts = {f"D{index}": 0 for index in range(1, 7)}
        for allocation in allocations:
            if allocation.domain_id in counts and counts[allocation.domain_id] < 16:
                selected.append(allocation)
                counts[allocation.domain_id] += 1
            if all(count == 16 for count in counts.values()):
                break
        self.assertEqual(len(selected), 96)
        console = ResearchConsole("6", stream=io.StringIO())
        raw_semantics = 0
        oracle_round_trips = 0
        for allocation in selected:
            pair = build_exact_pair(allocation, REPO_ROOT)
            for world in (pair.left.world_state, pair.right.world_state):
                semantic_hashes = set()
                for representation in (
                    tabular.REPRESENTATION_ID,
                    sequence.REPRESENTATION_ID,
                    graph.REPRESENTATION_ID,
                ):
                    raw, trace = project_raw_governance(
                        world,
                        representation_id=representation,
                        console=console,
                    )
                    oracle, _ = project_oracle(
                        world,
                        representation_id=representation,
                        console=console,
                    )
                    semantic_hashes.add(trace.semantic_fact_hash)
                    self.assertEqual(
                        canonical_hash(
                            tuple(
                                sorted(
                                    reconstruct_oracle_projection(oracle).items()
                                )
                            )
                        ),
                        oracle.semantic_fact_hash,
                    )
                    self.assertFalse(any(trace.truncation.values()))
                    raw_semantics += 1
                    oracle_round_trips += 1
                self.assertEqual(len(semantic_hashes), 1)
        self.assertEqual(raw_semantics, 576)
        self.assertEqual(oracle_round_trips, 576)


if __name__ == "__main__":
    unittest.main()
