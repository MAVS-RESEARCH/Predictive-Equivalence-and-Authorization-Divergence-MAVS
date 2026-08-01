"""Independent high-volume Phase 7 contract, determinism, and leakage stress tests."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.core.training import TrainingContractError, TrainingRow, audit_role_isolation
from pead.phase7.suite import execute_contract_suite

ROOT = Path(__file__).parents[2]


class Phase7StressTests(unittest.TestCase):
    def test_2300_cross_family_contract_decisions_are_deterministic(self) -> None:
        first = execute_contract_suite(ROOT, ResearchConsole("7-stress", stream=io.StringIO()), repetitions=100)
        second = execute_contract_suite(ROOT, ResearchConsole("7-stress", stream=io.StringIO()), repetitions=100)
        self.assertEqual(first["decisions"], 2300)
        self.assertEqual(first["decision_hash"], second["decision_hash"])
        self.assertEqual(first["scientific_results"], 0)

    def test_5000_group_cross_role_attacks_are_rejected(self) -> None:
        for index in range(5000):
            rows = (
                TrainingRow(f"fit-{index}", f"wf-{index}", f"g-{index}", "development_fit", f"pf-{index}", (), "Accept"),
                TrainingRow(f"select-{index}", f"ws-{index}", f"g-{index}", "development_selection", f"ps-{index}", (), "Reject"),
            )
            with self.assertRaises(TrainingContractError):
                audit_role_isolation(rows)


if __name__ == "__main__":
    unittest.main()
