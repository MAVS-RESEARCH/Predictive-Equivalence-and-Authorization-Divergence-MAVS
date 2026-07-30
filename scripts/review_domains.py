"""Execute the complete independent Phase 5 domain-validity review."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pead.config.console import ResearchConsole
from pead.phase5.review import execute_domain_review


if __name__ == "__main__":
    execute_domain_review(REPO_ROOT, ResearchConsole("5"))
