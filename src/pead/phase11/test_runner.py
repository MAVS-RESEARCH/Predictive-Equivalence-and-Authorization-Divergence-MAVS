"""Execute and retain the complete Phase 11 regression verdict."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from pead.config.console import ResearchConsole
from pead.phase11.contracts import atomic_json


def run_tests(root: Path, console: ResearchConsole, stage: str) -> dict[str, Any]:
    # STEP LOG P11-TEST-001: Discover and execute the complete repository test suite in an isolated bytecode-free process.
    console.log("P11-TEST-001", "Executing the complete repository regression suite.", details={"stage": stage})
    started = time.perf_counter()
    environment = dict(__import__("os").environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-p", "test_*.py", "-q"],
        cwd=root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    match = __import__("re").search(r"Ran (\d+) tests", completed.stderr)
    report = {
        "schema_version": "1.0",
        "phase": 11,
        "study_version": "pead-study-v3",
        "preseal_id": "phase9a-preseal-v3",
        "stage": stage,
        "status": "pass" if completed.returncode == 0 else "fail",
        "tests": int(match.group(1)) if match else None,
        "returncode": completed.returncode,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "blind_methods_executed": 0,
        "blind_labels_revealed": 0,
    }
    atomic_json(root / f"results/audits/phase11-{stage}-tests.json", report)
    # STEP LOG P11-TEST-002: Retain the exact full-suite result without treating tests as blind scientific execution.
    console.log("P11-TEST-002", "Complete repository regression suite finished.", status=report["status"], details={"stage": stage, "tests": report["tests"], "returncode": completed.returncode})
    if completed.returncode:
        raise RuntimeError("Phase 11 regression failure\n" + completed.stderr)
    return report

