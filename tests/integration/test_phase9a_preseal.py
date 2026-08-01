from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.holdouts.commitment_verifier import verify_preseal
from pead.phase9a.audit import run_audit

ROOT = Path(__file__).parents[2]


class Phase9APresealTests(unittest.TestCase):
    def test_zero_gap_audit(self):
        report = run_audit(ROOT, ResearchConsole("9A"))
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["compliance_gaps"], [])

    def test_ciphertext_mutation_is_blocked(self):
        index = json.loads((ROOT / "manifests/custody/encrypted_blind_package.index.json").read_text(encoding="utf-8"))
        target = ROOT / index["packages"][0]["path"]
        original = target.read_bytes()
        try:
            target.write_bytes(original + b"mutation")
            with self.assertRaises(Exception): verify_preseal(ROOT)
        finally:
            target.write_bytes(original)

    def test_phase10_artifacts_absent(self):
        self.assertFalse((ROOT / "banks/development").exists())
        self.assertFalse((ROOT / "manifests/freeze_candidate_v1.json").exists())
