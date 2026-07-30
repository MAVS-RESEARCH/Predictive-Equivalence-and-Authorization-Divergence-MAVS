"""Run the complete test suite and retain Phase 1 evidence."""

from __future__ import annotations

import argparse
import io
import json
import time
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole


class RecordingResult(unittest.TextTestResult):
    """Record every successful test and duration for audit denominators."""

    def startTest(self, test: unittest.TestCase) -> None:
        self._started_at = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test: unittest.TestCase) -> None:
        duration = time.perf_counter() - self._started_at
        if not isinstance(getattr(self, "durations", None), dict):
            self.durations: dict[str, float] = {}
        self.durations[test.id()] = duration
        super().stopTest(test)

    def addSuccess(self, test: unittest.TestCase) -> None:
        if not isinstance(getattr(self, "successes", None), list):
            self.successes: list[str] = []
        self.successes.append(test.id())
        super().addSuccess(test)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("results/audits/phase1/phase1_tests.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    console = ResearchConsole("1")
    # STEP LOG P1-TEST-RUN-001: Discover the complete regression and Phase 1 test suite.
    console.log("P1-TEST-RUN-001", "Discovering complete test suite.")
    suite = unittest.defaultTestLoader.discover(
        str(repo_root / "tests"),
        pattern="test_*.py",
        top_level_dir=str(repo_root),
    )
    test_count = suite.countTestCases()
    # STEP LOG P1-TEST-RUN-002: Report the exact discovered-test denominator.
    console.log(
        "P1-TEST-RUN-002",
        "Complete test suite discovered.",
        details={"tests": test_count},
    )
    details_stream = io.StringIO()
    runner = unittest.TextTestRunner(
        stream=details_stream,
        verbosity=2,
        failfast=False,
        buffer=True,
        resultclass=RecordingResult,
    )
    result = runner.run(suite)
    durations = getattr(result, "durations", {})
    successes = getattr(result, "successes", [])
    report = {
        "phase": 1,
        "status": "pass" if result.wasSuccessful() else "fail",
        "tests_run": result.testsRun,
        "successful_tests": sorted(successes),
        "durations_seconds": {
            key: round(value, 6) for key, value in sorted(durations.items())
        },
        "failures": [
            {"test": test.id(), "detail": detail} for test, detail in result.failures
        ],
        "errors": [
            {"test": test.id(), "detail": detail} for test, detail in result.errors
        ],
        "skipped": [
            {"test": test.id(), "reason": reason} for test, reason in result.skipped
        ],
        "stress_gates": {
            "id_collision_trials": 100_000,
            "trace_records": 10_000,
            "canonical_random_reorderings": 2_000,
            "canonical_exhaustive_key_permutations": 120,
        },
    }
    report_path = args.report
    if not report_path.is_absolute():
        report_path = repo_root / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # STEP LOG P1-TEST-RUN-003: Retain the full test and stress verdict with denominators.
    console.log(
        "P1-TEST-RUN-003",
        "Complete test suite finished.",
        status=report["status"],
        details={
            "errors": len(result.errors),
            "failures": len(result.failures),
            "report": report_path.relative_to(repo_root).as_posix(),
            "tests_run": result.testsRun,
        },
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
