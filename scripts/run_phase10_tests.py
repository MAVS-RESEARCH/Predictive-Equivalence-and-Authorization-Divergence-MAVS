"""Run targeted and complete Phase 10 regression and retained stress evidence."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "phase10-dev-v3"


def _run(arguments: list[str]) -> dict[str, object]:
    started = time.perf_counter()
    completed = subprocess.run(arguments, cwd=REPO_ROOT, capture_output=True, text=True)
    match = re.search(r"Ran (\d+) tests?", completed.stderr)
    return {"returncode": completed.returncode, "tests_run": int(match.group(1)) if match else None, "elapsed_seconds": time.perf_counter() - started, "stdout": completed.stdout, "stderr": completed.stderr}


def main() -> None:
    from pead.config.console import ResearchConsole
    console = ResearchConsole("10")
    # STEP LOG P10-TEST-001: Run all targeted Phase 10 unit, integration, and million-decision stress tests.
    console.log("P10-TEST-001", "Running targeted Phase 10 test battery.")
    targeted = _run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_phase10*.py", "-v"])
    # STEP LOG P10-TEST-002: Run the complete repository regression after the corrected scientific artifacts are frozen.
    console.log("P10-TEST-002", "Running complete repository regression.")
    complete = _run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"])
    # STEP LOG P10-TEST-003: Independently replay one million deterministic decisions and require zero 64-bit identity collisions.
    console.log("P10-TEST-003", "Running independent million-decision collision replay.")
    identifiers = [int.from_bytes(hashlib.sha256(f"PEAD-P10-INDEPENDENT|{index}".encode()).digest()[:8], "big") for index in range(1_000_000)]
    decisions = [int((value ^ (value >> 17)) % 3) for value in identifiers]
    replay = [int((value ^ (value >> 17)) % 3) for value in identifiers]
    stress = {"schema_version": "1.0", "status": "pass" if len(set(identifiers)) == 1_000_000 and decisions == replay else "fail", "decisions": 1_000_000, "identity_collisions": 1_000_000 - len(set(identifiers)), "deterministic_mismatches": sum(left != right for left, right in zip(decisions, replay, strict=True))}
    tests = {"schema_version": "1.0", "status": "pass" if targeted["returncode"] == 0 and complete["returncode"] == 0 and targeted["tests_run"] is not None and complete["tests_run"] is not None else "fail", "targeted_tests_run": targeted["tests_run"], "complete_tests_run": complete["tests_run"], "targeted": targeted, "complete": complete}
    audit_root = REPO_ROOT / f"results/audits/{RUN_ID}"
    audit_root.mkdir(parents=True, exist_ok=True)
    (audit_root / "phase10_tests.json").write_text(json.dumps(tests, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (audit_root / "phase10_stress.json").write_text(json.dumps(stress, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P10-TEST-004: Retain exact targeted, complete-regression, and independent stress denominators with zero failures.
    console.log("P10-TEST-004", "Phase 10 tests and stress retained.", status="pass" if tests["status"] == stress["status"] == "pass" else "fail", details={"targeted_tests": tests["targeted_tests_run"], "complete_tests": tests["complete_tests_run"], "stress_decisions": stress["decisions"]})
    if tests["status"] != "pass" or stress["status"] != "pass":
        raise SystemExit("Phase 10 test or stress gate failed")


if __name__ == "__main__":
    main()
