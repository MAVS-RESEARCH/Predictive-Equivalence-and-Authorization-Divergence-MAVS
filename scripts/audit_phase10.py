"""Run the release-blocking corrected study-v3 Phase 10 compliance audit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pead.config.console import ResearchConsole
from pead.phase10.audit import audit_phase10


if __name__ == "__main__":
    audit_root = REPO_ROOT / "results/audits/phase10-dev-v3"
    tests = json.loads((audit_root / "phase10_tests.json").read_text(encoding="utf-8"))
    stress = json.loads((audit_root / "phase10_stress.json").read_text(encoding="utf-8"))
    # STEP LOG P10-AUDIT-SCRIPT-001: Execute the complete Phase 10 WorkPlan audit from retained test and stress evidence.
    ResearchConsole("10").log("P10-AUDIT-SCRIPT-001", "Invoking complete Phase 10 compliance audit.")
    result = audit_phase10(REPO_ROOT, ResearchConsole("10"), tests, stress)
    (audit_root / "phase10_compliance.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
