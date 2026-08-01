"""Refresh Phase 10 integrity evidence and freeze hashes after implementation correction."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pead.config.console import ResearchConsole
from pead.phase10.audit import _console_inventory
from pead.phase10.execution import RUN_ID, _freeze_candidate, _integrity_audits, _power_report, _preflight, _write_json, capture_phase9a_snapshot, environment_report


def main() -> None:
    console = ResearchConsole("10")
    summary_path = REPO_ROOT / f"results/reports/{RUN_ID}/phase10_summary.json"
    public_path = REPO_ROOT / f"results/processed/{RUN_ID}/public_validation_metrics.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    public_report = json.loads(public_path.read_text(encoding="utf-8"))
    public = {**summary["public_validation"], "reports": public_report["methods"]}
    # STEP LOG P10-REFRESH-001: Re-run the five-family leakage adversary, duplicate, budget, parity, non-triviality, and abstention audits after correction.
    console.log("P10-REFRESH-001", "Refreshing corrected Phase 10 integrity audits.")
    audits = _integrity_audits(REPO_ROOT, summary["method_outcomes"], public)
    power = _power_report(REPO_ROOT)
    environment = environment_report(REPO_ROOT)
    _write_json(REPO_ROOT / f"results/audits/{RUN_ID}/integrity_audits.json", audits)
    _write_json(REPO_ROOT / f"results/reports/{RUN_ID}/power_effect_size.json", power)
    _write_json(REPO_ROOT / f"results/audits/{RUN_ID}/environment.json", environment)
    _write_json(REPO_ROOT / f"results/audits/{RUN_ID}/console_inventory.json", _console_inventory(REPO_ROOT))
    summary["integrity_audits"] = audits
    summary["power_effect_size"] = power
    summary["environment"] = environment
    summary["status"] = "pass" if audits["status"] == power["status"] == environment["status"] == "pass" else "fail"
    _write_json(summary_path, summary)
    # STEP LOG P10-REFRESH-002: Rebuild the freeze candidate over every claim-relevant source, config, test, bank, checkpoint, trace, audit, and report hash.
    console.log("P10-REFRESH-002", "Refreshing Phase 10 freeze-candidate hash closure.")
    freeze = _freeze_candidate(REPO_ROOT, RUN_ID, summary["method_outcomes"], public, audits, power, capture_phase9a_snapshot(REPO_ROOT), _preflight(REPO_ROOT))
    freeze["operational_gap_corrections"] = ["results/audits/phase10-dev-v3/gap_correction_001.json"]
    _write_json(REPO_ROOT / "manifests/freeze_candidate_v1.json", freeze)
    # STEP LOG P10-REFRESH-003: Close refresh only after all expanded integrity adversaries and freeze hash inputs pass.
    console.log("P10-REFRESH-003", "Corrected Phase 10 audit refresh completed.", status=summary["status"], details={"adversaries": len(audits["leakage"]["adversary_accuracy"]), "claim_relevant_files": freeze["claim_relevant_file_count"]})
    if summary["status"] != "pass":
        raise SystemExit("Phase 10 refresh failed")


if __name__ == "__main__":
    main()
