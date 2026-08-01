from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from pead.config.console import ResearchConsole
from pead.custody.rehearsal import run_synthetic_rehearsal


class CustodyMutationV3StressTests(unittest.TestCase):
    def test_all_registered_mutations_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_synthetic_rehearsal(Path(directory) / "mutation-evidence.json", ResearchConsole("stress"))
        self.assertGreaterEqual(result["mutation_denominator"], 80)
        self.assertEqual(result["accepted_invalid_mutations"], 0)
        self.assertTrue(all(item["status"] == "pass" for item in result["mutations"]))

    def test_rehearsal_is_byte_identically_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "determinism.json"
            first = run_synthetic_rehearsal(output, ResearchConsole("stress"))
            first_bytes = output.read_bytes()
            second = run_synthetic_rehearsal(output, ResearchConsole("stress"))
            self.assertEqual(first, second)
            self.assertEqual(output.read_bytes(), first_bytes)
