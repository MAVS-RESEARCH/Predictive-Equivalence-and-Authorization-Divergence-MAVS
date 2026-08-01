"""Run complete repository regression and replay Phase 10 compliance."""

from __future__ import annotations

import argparse
import io
import json
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase10.audit import run_audit
from pead.phase10.training import RUN_ID


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3]); args = parser.parse_args(); root = args.repo_root.resolve(); console = ResearchConsole("10")
    # STEP LOG P10-TEST-001: Discover the complete repository regression and Phase 10 stress suite.
    console.log("P10-TEST-001", "Discovering complete repository test suite.")
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py", top_level_dir=str(root)); stream = io.StringIO(); result = unittest.TextTestRunner(stream=stream, verbosity=2, buffer=True).run(suite)
    # STEP LOG P10-TEST-002: Replay Phase 10 integrity and freeze-candidate gates after all regression tests.
    console.log("P10-TEST-002", "Replaying Phase 10 compliance after regression.", details={"tests": result.testsRun})
    try: compliance = run_audit(root, console)
    except Exception as exc: compliance = {"status": "fail", "error": str(exc)}
    report = {"schema_version": "1.0", "phase": 10, "run_id": RUN_ID, "status": "pass" if result.wasSuccessful() and compliance["status"] == "pass" else "fail", "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped), "runner_output": stream.getvalue(), "compliance_status": compliance["status"]}
    path = root / f"results/audits/{RUN_ID}/phase10_tests.json"; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P10-TEST-003: Retain exact regression denominators and the final compliance verdict.
    console.log("P10-TEST-003", "Complete Phase 10 test program finished.", status=report["status"], details={"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors)})
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__": raise SystemExit(main())
