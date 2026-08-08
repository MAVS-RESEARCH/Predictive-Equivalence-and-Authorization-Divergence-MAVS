"""Run the complete repository regression after the Phase 12 preflight audit."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase11.contracts import atomic_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--report", type=Path, default=Path("results/audits/phase12-blind-v3-attempt-001/regression.json"))
    args = parser.parse_args()
    root = args.repo_root.resolve()
    report = args.report if args.report.is_absolute() else root / args.report
    console = ResearchConsole("12")
    # STEP LOG P12-SCRIPT-TEST-001: Execute the complete test suite in a bytecode-free subprocess after the pre-label audit.
    console.log("P12-SCRIPT-TEST-001", "Starting complete Phase 12 regression verification.")
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--disable-warnings"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    summary = {
        "schema_version": "1.0",
        "phase": 12,
        "attempt_id": "phase12-blind-v3-attempt-001",
        "status": "pass" if completed.returncode == 0 else "fail",
        "returncode": completed.returncode,
        "command": [sys.executable, "-m", "pytest", "-q", "--disable-warnings"],
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "hidden_label_access": False,
    }
    atomic_json(report, summary)
    # STEP LOG P12-SCRIPT-TEST-002: Retain the exact regression result without interpreting it as a blind scientific execution.
    console.log("P12-SCRIPT-TEST-002", "Complete Phase 12 regression verification retained.", status=summary["status"], details={"returncode": completed.returncode})
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
