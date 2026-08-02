"""CLI for the signed Phase 11 freeze."""

from __future__ import annotations

import argparse
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase11.freeze import build_freeze


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--custody-root", type=Path, required=True)
    args = parser.parse_args()
    console = ResearchConsole("11")
    # STEP LOG P11-SCRIPT-FREEZE-001: Enter the authoritative Phase 11 freeze command with an explicit external custody root.
    console.log("P11-SCRIPT-FREEZE-001", "Starting the authoritative Phase 11 freeze command.")
    build_freeze(args.repo_root, args.custody_root, console)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

