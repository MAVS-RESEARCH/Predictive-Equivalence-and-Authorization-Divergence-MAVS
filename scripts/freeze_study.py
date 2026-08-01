"""Sign the complete Phase 11 method freeze after Phase 10 reconciliation."""

from __future__ import annotations

import argparse
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase11.freeze import build_freeze


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--custody-operator", type=Path, required=True)
    args = parser.parse_args()
    console = ResearchConsole("11")
    # STEP LOG P11-FREEZE-SCRIPT-001: Resolve the registered study and isolated signing authority before freezing.
    console.log("P11-FREEZE-SCRIPT-001", "Resolving registered study and external freeze authority.")
    if not args.study.is_file():
        raise FileNotFoundError(args.study)
    build_freeze(args.repo_root.resolve(), args.authority_root.resolve(), args.custody_operator.resolve(), console)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
