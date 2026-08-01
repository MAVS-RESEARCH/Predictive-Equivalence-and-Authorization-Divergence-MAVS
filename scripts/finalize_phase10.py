"""Finalize complete Phase 10 artifacts after an audit-only interruption."""

from __future__ import annotations

import argparse
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase10.finalize import finalize_existing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[1])
    report = finalize_existing(parser.parse_args().repo_root.resolve(), ResearchConsole("10"))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
