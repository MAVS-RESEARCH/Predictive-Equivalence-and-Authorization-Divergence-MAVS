"""Generate and validate the complete Phase 3 bank without releasing unsigned rows."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pead.config.console import ResearchConsole
from pead.phase2.audit import write_json
from pead.phase3.generation import generate_validation_bank


def main() -> int:
    console = ResearchConsole("3")
    # STEP LOG P3-BANK-001: Execute complete in-memory Phase 3 bank generation.
    console.log("P3-BANK-001", "Starting validation-only bank generation.")
    equivalence, authorization, _, summary = generate_validation_bank(
        REPO_ROOT,
        console,
    )
    evidence_root = REPO_ROOT / "results/audits/phase3"
    write_json(evidence_root / "equivalence_report.json", equivalence)
    write_json(evidence_root / "authorization_report.json", authorization)
    write_json(evidence_root / "generation_summary.json", summary)
    # STEP LOG P3-BANK-002: Retain generation evidence while preserving the Phase 9A release boundary.
    console.log(
        "P3-BANK-002",
        "Validation-only bank evidence retained.",
        status="pass",
        details={"released_rows": 0},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
