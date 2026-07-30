"""Generate and audit the complete Phase 4 validation banks in memory."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pead.config.console import ResearchConsole
from pead.phase4.generation import generate_phase4_banks


if __name__ == "__main__":
    generate_phase4_banks(REPO_ROOT, ResearchConsole("4"))
