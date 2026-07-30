"""Unit tests for every registered predictive-state distance family."""

from __future__ import annotations

import unittest
from pathlib import Path

from pead.tracks.distances import load_distance_registry, predictive_distance
from pead.tracks.exact import base_predictive_parents
from pead.world.schema import predictive_state_from_parents


REPO_ROOT = Path(__file__).resolve().parents[2]


class Phase3DistanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load_distance_registry(
            REPO_ROOT / "configs/tracks/near_distance_registry.yaml"
        )

    def test_registry_covers_all_frozen_typed_metrics(self) -> None:
        observed = {
            config["type"] for config in self.registry["fields"].values()
        }
        self.assertEqual(
            observed,
            {
                "scalar",
                "calibrated_probability",
                "vector",
                "categorical",
                "set",
                "graph",
                "text",
            },
        )

    def test_identical_states_have_zero_distance(self) -> None:
        state = predictive_state_from_parents(base_predictive_parents())
        result = predictive_distance(state, state, self.registry)
        self.assertEqual(result.aggregate, 0.0)
        self.assertTrue(all(value == 0.0 for _, value in result.field_distances))

    def test_scalar_epsilon_is_the_weighted_maximum(self) -> None:
        left = base_predictive_parents()
        right = base_predictive_parents()
        right["uncertainty"] += 0.05
        result = predictive_distance(
            predictive_state_from_parents(left),
            predictive_state_from_parents(right),
            self.registry,
        )
        self.assertAlmostEqual(result.aggregate, 0.05)
        self.assertEqual(
            dict(result.field_distances)["uncertainty"],
            result.aggregate,
        )


if __name__ == "__main__":
    unittest.main()
