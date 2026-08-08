"""Integration checks for the fail-closed Phase 12 preflight record."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class Phase12PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[2]
        cls.audit_root = cls.root / "results/audits/phase12-blind-v3-attempt-001"
        cls.manifest_path = cls.root / "results/manifests/phase12-blind-v3-attempt-001/run_manifest.json"
        if not cls.manifest_path.is_file():
            raise unittest.SkipTest("Phase 12 preflight has not been executed")
        cls.manifest = json.loads(cls.manifest_path.read_text(encoding="utf-8"))
        cls.compliance = json.loads((cls.audit_root / "phase12_compliance.json").read_text(encoding="utf-8"))

    def test_attempt_stopped_before_scientific_or_label_activity(self) -> None:
        self.assertEqual(self.manifest["status"], "blocked-before-blind-execution")
        self.assertFalse(self.manifest["scientific_run_started"])
        self.assertEqual(self.manifest["method_executions"], 0)
        self.assertEqual(self.manifest["decisions_committed"], 0)
        self.assertEqual(self.manifest["labels_revealed"], 0)
        self.assertEqual(self.manifest["unlock_calls"], 0)
        self.assertEqual(self.manifest["decryption_calls"], 0)
        self.assertEqual(self.manifest["rematerialization_calls"], 0)

    def test_all_five_release_blocking_gaps_are_retained(self) -> None:
        self.assertEqual(self.compliance["status"], "blocked")
        self.assertFalse(self.compliance["phase_finished"])
        self.assertEqual({row["gap_id"] for row in self.compliance["compliance_gaps"]}, {"P12-GAP-001", "P12-GAP-002", "P12-GAP-003", "P12-GAP-004", "P12-GAP-005"})
        self.assertFalse(self.compliance["phase13_authorized"])

    def test_mutation_stress_and_console_inventory_pass(self) -> None:
        stress = json.loads((self.audit_root / "stress_test.json").read_text(encoding="utf-8"))
        console = json.loads((self.audit_root / "console_inventory.json").read_text(encoding="utf-8"))
        self.assertEqual(stress["status"], "pass")
        self.assertEqual(stress["mutations_attempted"], 6000)
        self.assertEqual(stress["mutations_rejected"], 6000)
        self.assertEqual(console["status"], "pass")
        self.assertGreaterEqual(len(console["call_sites"]), 18)

    def test_required_outcomes_are_explicitly_not_estimable(self) -> None:
        outcomes = json.loads((self.root / "results/processed/phase12-blind-v3-attempt-001/scientific_outcomes.json").read_text(encoding="utf-8"))
        self.assertEqual(outcomes["status"], "not-estimable-preblind-contract-block")
        self.assertEqual(len(outcomes["scientific_outcomes"]), 12)
        self.assertEqual(set(outcomes["scientific_outcomes"].values()), {"not_estimable_no_valid_blind_run"})
        self.assertEqual(outcomes["negative_outcomes_suppressed"], 0)


if __name__ == "__main__":
    unittest.main()
