"""Run all comparator contracts through the common baseline runner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase7.suite import execute_contract_suite


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--contract-probe", action="store_true")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--report", type=Path, default=Path("results/audits/phase7/common_runner.json"))
    args = parser.parse_args()
    if not args.contract_probe:
        raise SystemExit("Phase 7 permits only --contract-probe; scientific execution begins in Phase 10")
    console = ResearchConsole("7")
    # STEP LOG P7-RUN-SCRIPT-001: Start the explicitly non-scientific common-runner contract probe.
    console.log("P7-RUN-SCRIPT-001", "Starting common-runner contract probe.")
    report = execute_contract_suite(args.repo_root.resolve(), console, repetitions=args.repetitions)
    path = args.report if args.report.is_absolute() else args.repo_root.resolve() / args.report
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P7-RUN-SCRIPT-002: Retain the common-runner proof with zero scientific-result status.
    console.log("P7-RUN-SCRIPT-002", "Common-runner contract probe retained.", status="pass", details={"decisions": report["decisions"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
