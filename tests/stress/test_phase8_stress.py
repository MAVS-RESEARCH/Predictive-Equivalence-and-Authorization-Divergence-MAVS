"""Independent high-volume Phase 8 stress gates."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase8.review import execute_phase8_review

ROOT = Path(__file__).parents[2]


class Phase8StressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = execute_phase8_review(ROOT, ResearchConsole("8-stress-test", stream=io.StringIO()))

    def test_exhaustive_veto_denominators_and_zero_violations(self) -> None:
        rules = self.report["rule_fidelity"]
        self.assertEqual(rules["vectors"], 279_936)
        self.assertEqual(rules["active_veto_combinations"], 27_216)
        self.assertEqual(rules["veto_violations"], 0)
        self.assertEqual(rules["raw_correlation_only_vetoes"], 0)

    def test_all_ablation_stress_traces_and_equal_information(self) -> None:
        ablations = self.report["ablations"]
        self.assertEqual(ablations["decisions"], 4096)
        self.assertEqual(ablations["complete_traces"], 4096)
        self.assertEqual(ablations["raw_g_projection_mismatches"], 0)

    def test_semantic_scope_scalar_and_dependency_gates(self) -> None:
        self.assertEqual(self.report["semantic_registry"]["semantic_changes"], 0)
        self.assertEqual(self.report["monotonicity"]["violations"], 0)
        self.assertEqual(self.report["scalar_compression"]["collision_count"], 2)
        self.assertEqual(self.report["dependencies"]["violations"], [])


if __name__ == "__main__":
    unittest.main()
