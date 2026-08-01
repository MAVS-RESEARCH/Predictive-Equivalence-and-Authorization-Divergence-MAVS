"""Run the complete repository suite and retain Phase 9 evidence."""

from __future__ import annotations

import argparse
import io
import json
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase9.review import execute_phase9_review


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    parser.add_argument("--report", type=Path, default=Path("results/audits/phase9/phase9_tests.json"))
    args = parser.parse_args()
    root = args.repo_root.resolve()
    console = ResearchConsole("9")
    # STEP LOG P9-TEST-RUN-001: Discover the complete repository metric, audit, reporting, regression, and stress suite.
    console.log("P9-TEST-RUN-001", "Discovering complete repository test suite.")
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py", top_level_dir=str(root))
    # STEP LOG P9-TEST-RUN-002: Retain the exact complete-suite denominator before any test executes.
    console.log("P9-TEST-RUN-002", "Complete test suite discovered.", details={"tests": suite.countTestCases()})
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2, failfast=False, buffer=True).run(suite)
    # STEP LOG P9-TEST-RUN-003: Independently replay all high-volume Phase 9 metric, mutation, report, and human-checkpoint gates.
    console.log("P9-TEST-RUN-003", "Executing independent Phase 9 stress review.")
    stress = execute_phase9_review(root, console)
    report = {
        "schema_version": "1.0", "phase": 9,
        "status": "pass" if result.wasSuccessful() and stress["status"] == "pass" else "fail",
        "tests_run": result.testsRun,
        "failures": [{"test": test.id(), "detail": detail} for test, detail in result.failures],
        "errors": [{"test": test.id(), "detail": detail} for test, detail in result.errors],
        "skipped": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
        "runner_output": stream.getvalue(), "stress_gates": stress,
    }
    report_path = args.report if args.report.is_absolute() else root / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P9-TEST-RUN-004: Retain the complete regression and independent Phase 9 verdict with exact denominators.
    console.log("P9-TEST-RUN-004", "Complete Phase 9 test program finished.", status=report["status"], details={"errors": len(result.errors), "failures": len(result.failures), "tests_run": result.testsRun})
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
