"""Run the Phase 12 pre-label frozen-contract audit without blind execution."""

from __future__ import annotations

import argparse
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase12.preflight import run_preflight


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--custody-root", type=Path, required=True)
    parser.add_argument("--executed-at", required=True)
    args = parser.parse_args()
    console = ResearchConsole("12")
    # STEP LOG P12-SCRIPT-PREFLIGHT-001: Enter the Phase 12 preflight with an explicit custody root and execution timestamp.
    console.log("P12-SCRIPT-PREFLIGHT-001", "Starting Phase 12 pre-label compliance preflight.")
    result = run_preflight(args.repo_root, args.custody_root, args.executed_at, console)
    # STEP LOG P12-SCRIPT-PREFLIGHT-BLOCK: Return a nonzero blocked status after preserving all evidence and without crossing the hidden-label boundary.
    console.log("P12-SCRIPT-PREFLIGHT-BLOCK", "Phase 12 preflight retained a release-blocking verdict.", status="blocked", details={"compliance_gaps": result["compliance"]["gap_count"]})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
