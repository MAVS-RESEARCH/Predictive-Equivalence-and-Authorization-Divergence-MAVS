"""Run Phase 0 tests and retain a machine-readable summary."""

from __future__ import annotations

import argparse
import io
import json
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("results/audits/phase0/phase0_tests.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    console = ResearchConsole("0")
    # STEP LOG P0-TEST-RUN-001: Discover the independent Phase 0 test suite.
    console.log("P0-TEST-RUN-001", "Discovering Phase 0 tests.")
    suite = unittest.defaultTestLoader.discover(
        str(repo_root / "tests"),
        pattern="test_*.py",
        top_level_dir=str(repo_root),
    )
    test_count = suite.countTestCases()
    # STEP LOG P0-TEST-RUN-002: Report the exact discovered-test denominator.
    console.log(
        "P0-TEST-RUN-002",
        "Phase 0 tests discovered.",
        details={"tests": test_count},
    )
    details_stream = io.StringIO()
    result = unittest.TextTestRunner(
        stream=details_stream,
        verbosity=2,
        failfast=False,
        buffer=True,
    ).run(suite)
    report = {
        "phase": 0,
        "status": "pass" if result.wasSuccessful() else "fail",
        "tests_run": result.testsRun,
        "failures": [
            {"test": str(test), "detail": detail} for test, detail in result.failures
        ],
        "errors": [
            {"test": str(test), "detail": detail} for test, detail in result.errors
        ],
        "skipped": [
            {"test": str(test), "reason": reason} for test, reason in result.skipped
        ],
        "unexpected_successes": [str(test) for test in result.unexpectedSuccesses],
    }
    report_path = args.report
    if not report_path.is_absolute():
        report_path = repo_root / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # STEP LOG P0-TEST-RUN-003: Retain the independent test verdict and denominators.
    console.log(
        "P0-TEST-RUN-003",
        "Phase 0 tests completed.",
        status=report["status"],
        details={
            "errors": len(result.errors),
            "failures": len(result.failures),
            "report": str(report_path),
            "skipped": len(result.skipped),
            "tests_run": result.testsRun,
        },
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

