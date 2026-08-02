"""CLI for the single Phase 11 custody materialization."""

from __future__ import annotations

import argparse
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase11.materialize import materialize_once


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--custody-root", type=Path, required=True)
    args = parser.parse_args()
    console = ResearchConsole("11")
    # STEP LOG P11-SCRIPT-MATERIALIZE-001: Enter the only authorized pead-study-v3 scientific materialization command.
    console.log("P11-SCRIPT-MATERIALIZE-001", "Starting the one-shot Phase 11 custody materialization.")
    materialize_once(args.repo_root, args.custody_root, console)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

