"""Execute the complete Phase 10 open-development program."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase10.audit import run_audit
from pead.phase10.banks import generate_open_banks
from pead.phase10.preflight import retain_resource_failure_evidence
from pead.phase10.repair import repair_oracle_representation
from pead.phase10.training import RUN_ID, execute_training
from pead.phase10.validation import execute_validation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3]); args = parser.parse_args(); root = args.repo_root.resolve(); console = ResearchConsole("10")
    # STEP LOG P10-RUN-001: Generate all five exact-volume open roles before any training attempt.
    console.log("P10-RUN-001", "Starting exact open-bank generation.")
    banks = generate_open_banks(root, console)
    # STEP LOG P10-RUN-001A: Prove the corrected Oracle representation leaves P-only and Raw-G identities, labels, and features unchanged under regeneration.
    console.log("P10-RUN-001A", "Starting Oracle representation isolation proof.")
    repair_oracle_representation(root, console)
    # STEP LOG P10-RUN-001B: Record exact backend and compute availability before any registered method attempt.
    console.log("P10-RUN-001B", "Starting registered environment preflight.")
    retain_resource_failure_evidence(root, console)
    # STEP LOG P10-RUN-002: Execute registered training/fixed readiness and retain every success or failure.
    console.log("P10-RUN-002", "Starting registered method development.")
    training = execute_training(root, console)
    # STEP LOG P10-RUN-003: Freeze calibration-policy choices and execute inspection-only public validation.
    console.log("P10-RUN-003", "Starting calibration-policy and public-validation execution.")
    validation = execute_validation(root, console)
    # STEP LOG P10-RUN-004: Run the complete zero-gap audit and create the method-freeze candidate.
    console.log("P10-RUN-004", "Starting final Phase 10 compliance audit.")
    audit = run_audit(root, console)
    report = {"schema_version": "1.0", "phase": 10, "run_id": RUN_ID, "status": audit["status"], "bank_files": len(banks["files"]), "inventory_methods": training["inventory_method_count"], "public_methods": len(validation["methods"]), "compliance_gaps": audit["compliance_gaps"]}
    path = root / f"results/reports/{RUN_ID}/phase10_summary.json"; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P10-RUN-005: Retain the complete Phase 10 outcome and stop before Phase 11.
    console.log("P10-RUN-005", "Phase 10 execution finished.", status=report["status"], details={"methods": report["inventory_methods"], "bank_files": report["bank_files"], "compliance_gaps": len(report["compliance_gaps"])})
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__": raise SystemExit(main())
