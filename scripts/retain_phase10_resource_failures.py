"""Retain Phase 10 resource-preflight evidence for failed registered methods."""

from __future__ import annotations

import argparse
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase10.preflight import retain_resource_failure_evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[1])
    retain_resource_failure_evidence(parser.parse_args().repo_root.resolve(), ResearchConsole("10"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
