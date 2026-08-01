"""Regenerate Phase 10 open banks after the Oracle-only interface repair."""

from __future__ import annotations

import argparse
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase10.repair import repair_oracle_representation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[1])
    repair_oracle_representation(parser.parse_args().repo_root.resolve(), ResearchConsole("10"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
