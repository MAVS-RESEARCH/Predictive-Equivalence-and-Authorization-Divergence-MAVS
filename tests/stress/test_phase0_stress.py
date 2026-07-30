"""Mutation and determinism stress tests for Phase 0."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pead.config.validator import Phase0Validator
from pead.phase0.audit import run_mutation_stress


class Phase0StressTests(unittest.TestCase):
    def test_one_thousand_invalid_mutations_are_rejected(self) -> None:
        report = run_mutation_stress(REPO_ROOT, 1000)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["rejected_invalid_mutations"], 1000)
        self.assertEqual(report["unexpected_acceptances"], 0)

    def test_repeated_full_validation_is_deterministic(self) -> None:
        baseline = Phase0Validator(REPO_ROOT).validate()
        for _ in range(25):
            self.assertEqual(Phase0Validator(REPO_ROOT).validate(), baseline)


if __name__ == "__main__":
    unittest.main()
