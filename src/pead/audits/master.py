"""Fail-closed aggregation of all thirteen registered Phase 9 audit families."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pead.config.console import ResearchConsole

AUDIT_IDS = (
    "equivalence", "authorization", "leakage", "access", "holdouts", "budget",
    "traces", "abstention", "manifest", "reproduction", "claims",
    "failure_retention", "non_triviality",
)


def execute_master_audit(reports: Mapping[str, Mapping[str, Any]], *, console: ResearchConsole) -> dict[str, Any]:
    # STEP LOG P9-MASTER-001: Admit exactly the thirteen registered release and claim audit families.
    console.log("P9-MASTER-001", "Validating exact master-audit inventory.")
    if set(reports) != set(AUDIT_IDS):
        raise ValueError("master audit inventory is not exact")
    # STEP LOG P9-MASTER-002: Reject every failed, missing, malformed, or evidence-free audit report.
    console.log("P9-MASTER-002", "Evaluating all release-blocking audit verdicts.")
    failed = sorted(name for name, report in reports.items() if report.get("status") != "pass" or len(report) <= 1)
    if failed:
        raise ValueError(f"master audit release blockers: {failed}")
    # STEP LOG P9-MASTER-003: Emit a release-eligible machine-audit verdict only after all thirteen families pass.
    console.log("P9-MASTER-003", "Master machine-audit suite passed.", status="pass", details={"audits": len(reports)})
    return {"status": "pass", "audits": list(AUDIT_IDS), "release_blockers": []}
