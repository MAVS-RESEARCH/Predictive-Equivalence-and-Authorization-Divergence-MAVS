"""Run the complete repository regression and retain Phase 11 test evidence."""

from __future__ import annotations

import json
import time
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole


def run_tests(root: Path, console: ResearchConsole) -> dict[str, object]:
    # STEP LOG P11-TEST-001: Discover the complete repository unit, integration, property, and stress suite.
    console.log("P11-TEST-001", "Discovering complete repository test suite.")
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py", top_level_dir=str(root))
    candidate_path = root / "manifests/freeze_candidate_v1.json"
    historical_candidate = candidate_path.read_bytes()
    started = time.perf_counter()
    try:
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    finally:
        candidate_path.write_bytes(historical_candidate)
    report = {
        "schema_version": "1.0",
        "phase": 11,
        "status": "pass" if result.wasSuccessful() else "fail",
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "duration_seconds": round(time.perf_counter() - started, 3),
        "scientific_materialization_executed": False,
    }
    target = root / "results/audits/phase11-prefreeze-tests.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P11-TEST-002: Retain the exact full-suite verdict without treating contract tests as a successful blind-bank release.
    console.log("P11-TEST-002", "Complete Phase 11 regression program finished.", status=report["status"], details={"tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors)})
    return report
