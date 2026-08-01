from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from pead.phase10.validation import _apply_policy, _policy_candidates
from pead.phase10.training import RUN_ID

ROOT = Path(__file__).parents[2]


class Phase10StressTests(unittest.TestCase):
    def test_10000_policy_rows_are_selected_only_by_lexicographic_constraint(self):
        rng = np.random.default_rng(101); probabilities = rng.dirichlet((1.0, 1.0, 1.0), size=10000); labels = rng.integers(0, 3, size=10000)
        sweep, selected = _policy_candidates(probabilities, labels, 1.0)
        self.assertEqual(len(sweep), 36); self.assertEqual(selected["partition"], "calibration_policy")
        self.assertEqual(len(_apply_policy(probabilities, selected)), 10000)

    def test_all_method_failures_are_retained_without_substitution(self):
        trace = json.loads((ROOT / f"results/raw/{RUN_ID}/training_trace.json").read_text(encoding="utf-8"))
        serialized = json.dumps(trace)
        self.assertIn("failed_retained", serialized); self.assertNotIn('"substitution_used": true', serialized); self.assertNotIn('"budget_expanded": true', serialized)

    def test_freeze_candidate_contains_all_claim_relevant_hashes(self):
        candidate = json.loads((ROOT / "manifests/freeze_candidate_v1.json").read_text(encoding="utf-8"))
        self.assertGreater(len(candidate["claim_relevant_files"]), 100)
        self.assertTrue(candidate["minimum_effect_sizes_frozen"])
        self.assertEqual(candidate["status"], "candidate_not_final_freeze")
