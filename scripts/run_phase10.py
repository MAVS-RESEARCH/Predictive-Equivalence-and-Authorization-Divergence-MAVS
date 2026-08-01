"""Execute the corrected study-v3 Phase 10 development lineage exactly once."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pead.config.console import ResearchConsole
from pead.phase10.execution import execute_phase10


if __name__ == "__main__":
    # STEP LOG P10-SCRIPT-001: Enter the one-shot Phase 10 orchestrator without permitting Phase 11 unlock behavior.
    ResearchConsole("10").log("P10-SCRIPT-001", "Invoking one-shot Phase 10 execution.")
    execute_phase10(REPO_ROOT, ResearchConsole("10"))
