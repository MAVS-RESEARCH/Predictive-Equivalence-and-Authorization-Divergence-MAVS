"""Run complete regression plus Phase 9A public/custody compliance."""

from __future__ import annotations

import argparse
import io
import json
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase9a.audit import PRESEAL_ID, run_audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    parser.add_argument("--report", type=Path, default=Path(f"results/audits/{PRESEAL_ID}/phase9a_tests.json"))
    args = parser.parse_args(); root = args.repo_root.resolve(); console = ResearchConsole("9A")
    # STEP LOG P9A-TEST-001: Discover every repository regression and Phase 9A mutation test.
    console.log("P9A-TEST-001", "Discovering complete repository test suite.")
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py", top_level_dir=str(root))
    stream = io.StringIO(); result = unittest.TextTestRunner(stream=stream, verbosity=2, buffer=True).run(suite)
    # STEP LOG P9A-TEST-002: Replay the complete Phase 9A zero-gap audit after all regression tests.
    console.log("P9A-TEST-002", "Replaying Phase 9A compliance after complete regression.", details={"tests": result.testsRun})
    try: compliance = run_audit(root, console)
    except Exception as exc: compliance = {"status": "fail", "error": str(exc)}
    report = {"schema_version": "1.0", "phase": "9A", "status": "pass" if result.wasSuccessful() and compliance["status"] == "pass" else "fail", "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped), "runner_output": stream.getvalue(), "compliance_status": compliance["status"]}
    path = args.report if args.report.is_absolute() else root / args.report; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P9A-TEST-003: Retain exact complete-suite and compliance verdicts without exposing custody content.
    console.log("P9A-TEST-003", "Complete Phase 9A test program finished.", status=report["status"], details={"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors)})
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__": raise SystemExit(main())
