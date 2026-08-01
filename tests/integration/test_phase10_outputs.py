from __future__ import annotations

import json
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase10.audit import run_audit
from pead.phase10.training import RUN_ID

ROOT = Path(__file__).parents[2]


class Phase10OutputTests(unittest.TestCase):
    def test_complete_phase10_audit(self):
        report = run_audit(ROOT, ResearchConsole("10"))
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["compliance_gaps"], [])

    def test_public_validation_is_never_a_selection_role(self):
        report = json.loads((ROOT / f"results/processed/{RUN_ID}/public_validation.json").read_text(encoding="utf-8"))
        self.assertFalse(report["public_validation_selected_anything"])
        self.assertTrue(all(item.get("public_validation_selection_use", False) is False for item in report["methods"].values()))

    def test_phase9a_commitment_remains_identical(self):
        compliance = json.loads((ROOT / f"results/audits/{RUN_ID}/phase10_compliance.json").read_text(encoding="utf-8"))
        self.assertTrue(compliance["phase9a_commitment_unchanged"])
        self.assertEqual(compliance["sealed_bank_accesses"], 0)
