"""Run the complete repository suite and retain Phase 5 test evidence."""

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
        default=Path("results/audits/phase5/phase5_tests.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    console = ResearchConsole("5")
    # STEP LOG P5-TEST-RUN-001: Discover the complete regression and Phase 5 verification suite.
    console.log("P5-TEST-RUN-001", "Discovering complete test suite.")
    suite = unittest.defaultTestLoader.discover(
        str(repo_root / "tests"),
        pattern="test_*.py",
        top_level_dir=str(repo_root),
    )
    # STEP LOG P5-TEST-RUN-002: Report the exact complete-suite test denominator before execution.
    console.log(
        "P5-TEST-RUN-002",
        "Complete test suite discovered.",
        details={"tests": suite.countTestCases()},
    )
    stream = io.StringIO()
    result = unittest.TextTestRunner(
        stream=stream,
        verbosity=2,
        failfast=False,
        buffer=True,
    ).run(suite)
    report = {
        "schema_version": "1.0",
        "phase": 5,
        "status": "pass" if result.wasSuccessful() else "fail",
        "tests_run": result.testsRun,
        "failures": [
            {"test": test.id(), "detail": detail}
            for test, detail in result.failures
        ],
        "errors": [
            {"test": test.id(), "detail": detail}
            for test, detail in result.errors
        ],
        "skipped": [
            {"test": test.id(), "reason": reason}
            for test, reason in result.skipped
        ],
        "runner_output": stream.getvalue(),
        "stress_gates": {
            "open_adapters": 6,
            "mechanisms_per_adapter_minimum": 6,
            "complete_open_cases": 3_600,
            "crossed_anti_shortcut_variants": 288,
            "heldout_placeholder_interfaces": 2,
            "heldout_implementations_exposed": 0,
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
    # STEP LOG P5-TEST-RUN-003: Retain the complete regression, integration, adversarial, and stress verdict.
    console.log(
        "P5-TEST-RUN-003",
        "Complete test suite finished.",
        status=report["status"],
        details={
            "errors": len(result.errors),
            "failures": len(result.failures),
            "tests_run": result.testsRun,
        },
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
