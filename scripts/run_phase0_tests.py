"""Repository entry point for retained Phase 0 test evidence."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pead.phase0.test_runner import main


if __name__ == "__main__":
    raise SystemExit(main())
