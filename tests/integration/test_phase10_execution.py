"""Integration tests for corrected Phase 10 chronology and freeze evidence."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from pead.custody.contract import sha256_file

ROOT = Path(__file__).parents[2]
RUN = "phase10-dev-v3"


class Phase10ExecutionTests(unittest.TestCase):
    def test_phase10_public_validation_is_inspection_only(self) -> None:
        report = json.loads((ROOT / f"results/processed/{RUN}/public_validation_metrics.json").read_text(encoding="utf-8"))
        self.assertFalse(report["selection_from_public_validation"])
        self.assertTrue(all(row.get("public_used_for_selection") is not True for row in report["methods"].values()))
        self.assertEqual(len(report["methods"]), 42)

    def test_phase10_conformal_roles_and_causality_are_explicit(self) -> None:
        static = json.loads((ROOT / f"results/raw/{RUN}/P05-CONF-STATIC.training.json").read_text(encoding="utf-8"))
        adaptive = json.loads((ROOT / f"results/raw/{RUN}/P06-CONF-ADAPT.training.json").read_text(encoding="utf-8"))
        self.assertEqual(static["quantile_partition"], "calibration_fit")
        self.assertEqual(static["terminal_policy_partition"], "calibration_policy")
        self.assertFalse(adaptive["selected"]["current_label_used_before_decision"])
        self.assertFalse(adaptive["public_validation_used_for_selection"])

    def test_phase10_freeze_candidate_hashes_close(self) -> None:
        freeze = json.loads((ROOT / "manifests/freeze_candidate_v1.json").read_text(encoding="utf-8"))
        self.assertFalse(freeze["phase11_started"])
        self.assertFalse(freeze["unlock_attempted"])
        self.assertNotIn(f"results/audits/{RUN}/phase10_compliance.json", freeze["claim_relevant_files"])
        self.assertTrue(all((ROOT / path).is_file() and sha256_file(ROOT / path) == digest for path, digest in freeze["claim_relevant_files"].items()))

    def test_phase10_retains_exact_method_failures(self) -> None:
        summary = json.loads((ROOT / f"results/reports/{RUN}/phase10_summary.json").read_text(encoding="utf-8"))
        failures = [row for row in summary["method_outcomes"].values() if row["status"] == "method_failure"]
        self.assertEqual(len(failures), 13)
        self.assertTrue(all(row["substitution_attempted"] is False and row["budget_expanded"] is False for row in failures))
