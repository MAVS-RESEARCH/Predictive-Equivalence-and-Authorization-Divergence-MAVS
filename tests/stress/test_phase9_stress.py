"""High-volume Phase 9 metrics, audit mutation, and report stress gates."""

import io
import unittest
from functools import lru_cache
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase9.review import execute_phase9_review

ROOT = Path(__file__).parents[2]


@lru_cache(maxsize=1)
def review() -> dict[str, object]:
    return execute_phase9_review(ROOT, ResearchConsole("9-stress", stream=io.StringIO()))


class Phase9StressTests(unittest.TestCase):
    def test_statistical_denominators_and_reproducibility(self) -> None:
        report = review()["statistics"]
        self.assertEqual(report["paired_units"], 10_000)
        self.assertEqual(report["bootstrap_repetitions"], 2_000)
        self.assertEqual(report["deterministic_replays"], 2)

    def test_all_machine_and_human_release_gates(self) -> None:
        report = review()
        self.assertEqual(report["master_audit"]["release_blocking_mutations"], 13)
        self.assertEqual(report["human_program"]["checkpoints"], 7)

    def test_failure_cards_reports_and_claim_boundary(self) -> None:
        report = review()["reporting"]
        self.assertEqual(report["failure_card_bijection"]["events"], 7)
        self.assertEqual(report["table"]["complete"], 39)
        self.assertEqual(report["claim_ledger"]["claims"], [])


if __name__ == "__main__":
    unittest.main()
