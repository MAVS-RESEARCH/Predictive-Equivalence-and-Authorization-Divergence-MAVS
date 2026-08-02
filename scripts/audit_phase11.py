"""CLI for the complete Phase 11 compliance audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase11.audit import run_audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    console = ResearchConsole("11")
    # STEP LOG P11-SCRIPT-AUDIT-001: Enter the Phase 11 audit without invoking any blind method or label consumer.
    console.log("P11-SCRIPT-AUDIT-001", "Starting the complete Phase 11 compliance audit.")
    run_audit(args.repo_root, console)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

