"""Repository entry point for the complete Phase 2 test suite."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pead.phase2.test_runner import main


if __name__ == "__main__":
    raise SystemExit(main())
