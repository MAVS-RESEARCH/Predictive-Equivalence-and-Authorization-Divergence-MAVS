"""CLI for the Phase 11 complete-regression evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase11.test_runner import run_tests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--stage", choices=("prefreeze", "postmaterialization"), required=True)
    args = parser.parse_args()
    console = ResearchConsole("11")
    # STEP LOG P11-SCRIPT-TEST-001: Enter the complete Phase 11 regression runner with an explicit custody stage.
    console.log("P11-SCRIPT-TEST-001", "Starting the complete Phase 11 regression runner.", details={"stage": args.stage})
    run_tests(args.repo_root, console, args.stage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

