"""Finalize an already executed Phase 10 run after an audit-only interruption."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pead.config.console import ResearchConsole
from pead.phase10.audit import run_audit
from pead.phase10.training import RUN_ID


def finalize_existing(root: Path, console: ResearchConsole) -> dict[str, Any]:
    # STEP LOG P10-FINALIZE-001: Load only the complete v2 bank, training, and validation receipts without executing or selecting a method again.
    console.log("P10-FINALIZE-001", "Loading completed Phase 10 v2 receipts without retraining.")
    banks = json.loads((root / "results/manifests/phase10/open_bank_manifest.json").read_text(encoding="utf-8"))
    training = json.loads((root / f"results/raw/{RUN_ID}/training_trace.json").read_text(encoding="utf-8"))
    validation = json.loads((root / f"results/processed/{RUN_ID}/public_validation.json").read_text(encoding="utf-8"))
    # STEP LOG P10-FINALIZE-002: Re-execute the strengthened audit after the audit-scanner correction and before writing the run summary.
    console.log("P10-FINALIZE-002", "Re-executing corrected Phase 10 audit.")
    audit = run_audit(root, console)
    report = {"schema_version": "1.0", "phase": 10, "run_id": RUN_ID, "status": audit["status"], "bank_files": len(banks["files"]), "inventory_methods": training["inventory_method_count"], "public_methods": len(validation["methods"]), "compliance_gaps": audit["compliance_gaps"], "retraining_performed": False, "finalization_reason": "audit-only false-positive correction"}
    path = root / f"results/reports/{RUN_ID}/phase10_summary.json"; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P10-FINALIZE-003: Retain the final zero-gap verdict and stop before Phase 11.
    console.log("P10-FINALIZE-003", "Phase 10 v2 finalization finished.", status=report["status"], details={"methods": report["inventory_methods"], "bank_files": report["bank_files"], "compliance_gaps": len(report["compliance_gaps"])})
    return report
