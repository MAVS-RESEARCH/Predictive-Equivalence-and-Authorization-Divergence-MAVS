"""Fail-closed Phase 11 orchestration with freeze-before-unlock ordering."""

from __future__ import annotations

import argparse
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase11.audit import run_audit
from pead.phase11.freeze import build_freeze
from pead.phase11.materialize import materialize_once
from pead.phase11.test_runner import run_tests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--custody-root", type=Path, required=True)
    args = parser.parse_args()
    console = ResearchConsole("11")
    # STEP LOG P11-ORCH-001: Run all tests before the signed freeze so later code repair cannot occur silently.
    console.log("P11-ORCH-001", "Running the pre-freeze complete regression suite.")
    run_tests(args.repo_root, console, "prefreeze")
    # STEP LOG P11-ORCH-002: Sign the final method/report freeze before any key access, decryption, or materialization.
    console.log("P11-ORCH-002", "Constructing the final signed freeze before custody unlock.")
    build_freeze(args.repo_root, args.custody_root, console)
    # STEP LOG P11-ORCH-003: Execute exactly one custody unlock and materialization from the precommitted design.
    console.log("P11-ORCH-003", "Executing the single authorized custody materialization.")
    materialize_once(args.repo_root, args.custody_root, console)
    # STEP LOG P11-ORCH-004: Re-run the complete regression suite against the immutable materialization.
    console.log("P11-ORCH-004", "Running the post-materialization complete regression suite.")
    run_tests(args.repo_root, console, "postmaterialization")
    # STEP LOG P11-ORCH-005: Run the final WorkPlan compliance audit before Phase 12 authorization.
    console.log("P11-ORCH-005", "Executing the final Phase 11 WorkPlan compliance audit.")
    run_audit(args.repo_root, console)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

