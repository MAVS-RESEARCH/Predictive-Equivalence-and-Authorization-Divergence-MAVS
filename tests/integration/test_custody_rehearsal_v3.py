from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from pead.config.console import ResearchConsole
from pead.custody.rehearsal import run_synthetic_rehearsal


class CustodyRehearsalV3IntegrationTests(unittest.TestCase):
    def test_actual_producer_consumer_and_one_shot_materializer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_synthetic_rehearsal(Path(directory) / "rehearsal.json", ResearchConsole("test"))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["missing_commitments"], [])
        self.assertEqual(result["consumer_invented_values"], [])
        self.assertEqual(result["valid_materializations_accepted"], 1)
        self.assertEqual(result["repeat_materializations_accepted"], 0)
        self.assertEqual(result["custody_events"]["unsigned_events"], 0)
        self.assertIs(result["real_bank_touched"], False)
