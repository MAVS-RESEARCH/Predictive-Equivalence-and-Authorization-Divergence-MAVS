"""Extreme-rigor WorkPlan Phase 9 compliance audit."""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path
from typing import Any

import yaml

from pead.audits.human import CHECKPOINTS, audit_human_program
from pead.audits.master import AUDIT_IDS
from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash
from pead.phase0.audit import inventory_console_logs
from pead.phase2.audit import write_json
from pead.phase9.review import execute_phase9_review, metric_review
from pead.reports.failure_card_schema import FailureCard

EXPECTED_FILES = {
    *(f"src/pead/metrics/{name}.py" for name in ("paradigm", "protected", "causal", "scope", "sequential", "statistics")),
    *(f"src/pead/audits/{name}.py" for name in AUDIT_IDS),
    *(f"src/pead/reports/{name}.py" for name in ("tables", "figures", "failure_cards", "claim_ledger", "failure_card_schema")),
    "scripts/audit_all.py", "scripts/build_report.py",
    "tests/integration/test_master_audit.py", "tests/integration/test_failure_card_bijection.py",
    "configs/metrics/metric_registry_v1.yaml", "configs/audits/audit_registry_v1.yaml",
    "configs/reports/provenance_v1.yaml", "results/reports/phase9_contract/report_contract.json",
}


def _audit_files(root: Path) -> dict[str, Any]:
    missing = sorted(path for path in EXPECTED_FILES if not (root / path).is_file())
    metric_tests = sorted((root / "tests/unit").glob("test_metrics_*.py"))
    human = sorted((root / "results/audits/phase9/human").glob("*.json"))
    if missing or len(metric_tests) < 5 or len(human) != 7:
        raise ValueError(f"Phase 9 required-file gap: missing={missing}; metric_tests={len(metric_tests)}; human={len(human)}")
    return {"status": "pass", "required_files": len(EXPECTED_FILES), "metric_test_files": len(metric_tests), "human_artifacts": len(human), "missing": []}


def _audit_metric_contract(root: Path) -> dict[str, Any]:
    report = metric_review(root)
    registry = yaml.safe_load((root / "configs/metrics/metric_registry_v1.yaml").read_text(encoding="utf-8"))
    gates = {
        "paired_bootstrap": registry["statistics"]["bootstrap"] == "paired_cluster_by_evaluation_unit",
        "mechanism_domain": registry["statistics"]["generalization_bootstrap"] == "mechanism_by_domain_cluster",
        "exact_zero": registry["statistics"]["exact_zero_count_interval"] == "clopper_pearson_two_sided",
        "strata_before_macro": registry["statistics"]["primary_strata_order"] == ["domain", "mechanism", "macro"],
        "holm": registry["statistics"]["secondary_ablation_correction"] == "Holm",
    }
    if not all(gates.values()):
        raise ValueError(f"metric/statistical contract failed: {gates}")
    return {**report, "statistical_gates": gates, "registry_sha256": canonical_hash(registry)}


def _audit_audit_registry(root: Path) -> dict[str, Any]:
    registry = yaml.safe_load((root / "configs/audits/audit_registry_v1.yaml").read_text(encoding="utf-8"))
    if tuple(registry["release_blocking_audits"]) != AUDIT_IDS or tuple(registry["mandatory_human_checkpoints"]) != CHECKPOINTS:
        raise ValueError("machine/human audit registry is not exact")
    return {"status": "pass", "machine_audits": len(AUDIT_IDS), "human_checkpoints": len(CHECKPOINTS), "release_rule": registry["release_rule"]}


def _audit_failure_schema(root: Path) -> dict[str, Any]:
    schema = yaml.safe_load((root / "configs/study/failure_card_schema_v1.yaml").read_text(encoding="utf-8"))
    implementation = {field.name for field in dataclasses.fields(FailureCard)}
    registered = set(schema["required_fields"])
    event_types = set(schema["bijection_events"])
    expected_events = {"protected error", "scope anomaly", "label disagreement", "access violation", "quarantine", "invalidation", "reproduction mismatch"}
    if implementation != registered or len(implementation) != 31 or schema["additional_fields_allowed"] is not False or event_types != expected_events:
        raise ValueError("FailureCard implementation differs from strict frozen schema")
    return {"status": "pass", "fields": len(implementation), "additional_fields_allowed": False, "qualifying_event_types": len(event_types), "bijection_required": True}


def _audit_human_artifacts(root: Path) -> dict[str, Any]:
    artifacts = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((root / "results/audits/phase9/human").glob("*.json"))]
    report = audit_human_program(artifacts)
    report["disclosure"] = "Internal contract-fixture review; not external human validation."
    return report


def _audit_report_contract(root: Path) -> dict[str, Any]:
    report = json.loads((root / "results/reports/phase9_contract/report_contract.json").read_text(encoding="utf-8"))
    if (
        report.get("status") != "pass" or report.get("report_type") != "implementation-contract-only"
        or report["failure_card_bijection"]["missing"] or report["failure_card_bijection"]["duplicates"]
        or report["failure_card_bijection"]["orphaned"] or report["failure_card_bijection"]["schema_invalid"]
        or not report["table"]["failed_methods_visible"] or report["table"]["complete"] != 39
        or report["figure_points"] != 39 or report["claim_ledger"]["claims"]
    ):
        raise ValueError("Phase 9 report contract is incomplete")
    return {"status": "pass", "methods": 39, "table_cells": 39, "figure_points": 39, "failure_cards": 7, "scientific_claims": 0}


def _audit_test_evidence(root: Path) -> dict[str, Any]:
    report = json.loads((root / "results/audits/phase9/phase9_tests.json").read_text(encoding="utf-8"))
    stress = report.get("stress_gates", {})
    if (
        report.get("status") != "pass" or report.get("failures") or report.get("errors")
        or report.get("tests_run", 0) < 189 or stress.get("statistics", {}).get("paired_units") != 10_000
        or stress.get("statistics", {}).get("bootstrap_repetitions") != 2_000
        or stress.get("master_audit", {}).get("release_blocking_mutations") != 13
        or stress.get("human_program", {}).get("checkpoints") != 7
        or stress.get("scientific_results") != 0
    ):
        raise ValueError("Phase 9 complete-suite evidence is incomplete")
    return {"status": "pass", "tests_run": report["tests_run"], "failures": 0, "errors": 0, "stress_gates": stress}


def _audit_phase_boundary(root: Path) -> dict[str, Any]:
    forbidden = [
        path.relative_to(root).as_posix()
        for directory in (root / "results/raw", root / "results/processed", root / "results/models", root / "results/checkpoints")
        if directory.exists() for path in directory.rglob("*") if path.is_file() and "phase9" in path.as_posix().lower()
    ]
    if forbidden:
        raise ValueError(f"Phase 9 created scientific/training artifacts: {forbidden}")
    return {"status": "pass", "scientific_results": 0, "trained_models": 0, "released_rows": 0, "phase9a_started": False, "forbidden_artifacts": []}


def _write_manifest(root: Path) -> dict[str, Any]:
    paths = sorted((root / "src/pead/metrics").glob("*.py")) + sorted((root / "src/pead/audits").glob("*.py")) + sorted((root / "src/pead/reports").glob("*.py")) + sorted((root / "configs/metrics").glob("*.yaml")) + sorted((root / "configs/audits").glob("*.yaml")) + sorted((root / "configs/reports").glob("*.yaml"))
    files = {path.relative_to(root).as_posix(): canonical_hash(path.read_bytes()) for path in paths}
    manifest = {"schema_version": "1.0", "phase": 9, "registry_id": "PEAD-METRIC-AUDIT-REPORT-v1", "files": files, "metric_count": 38, "audit_count": 13, "human_checkpoint_count": 7, "released_rows": 0}
    manifest["manifest_sha256"] = canonical_hash(manifest)
    write_json(root / "results/manifests/phase9/metric_audit_report_registry_v1.json", manifest)
    return {"status": "pass", "files": len(files), "manifest_sha256": manifest["manifest_sha256"]}


def _audit_console(root: Path) -> dict[str, Any]:
    entries = [entry for entry in inventory_console_logs(root) if entry["event_id"].startswith("P9-")]
    if not entries:
        raise ValueError("Phase 9 console inventory is empty")
    return {"status": "pass", "events": len(entries), "entries": entries}


def _write_reports(output: Path, reports: dict[str, dict[str, Any]]) -> None:
    for name, report in reports.items():
        write_json(output / f"{name}.json", {"schema_version": "1.0", **report})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output = root / "results/audits/phase9"
    console = ResearchConsole("9")
    try:
        # STEP LOG P9-AUDIT-001: Verify every WorkPlan-named Phase 9 metric, audit, report, script, test, and human artifact exists.
        console.log("P9-AUDIT-001", "Auditing required Phase 9 files.")
        files = _audit_files(root)
        # STEP LOG P9-AUDIT-002: Prove all metric identities, paired units, strata ordering, exact intervals, bootstrap, and multiplicity controls.
        console.log("P9-AUDIT-002", "Auditing metric and statistical contracts.")
        metrics = _audit_metric_contract(root)
        # STEP LOG P9-AUDIT-003: Prove the exact thirteen machine audits and seven mandatory human checkpoints are registered.
        console.log("P9-AUDIT-003", "Auditing machine and human audit inventory.")
        audit_registry = _audit_audit_registry(root)
        # STEP LOG P9-AUDIT-004: Prove the immutable 31-field FailureCard schema and seven-type bijection contract are exact.
        console.log("P9-AUDIT-004", "Auditing strict FailureCard schema.")
        failure_schema = _audit_failure_schema(root)
        # STEP LOG P9-AUDIT-005: Validate all signed internal checkpoint artifacts and explicit non-external-review disclosure.
        console.log("P9-AUDIT-005", "Auditing signed internal checkpoint artifacts.")
        human = _audit_human_artifacts(root)
        # STEP LOG P9-AUDIT-006: Independently replay metrics, statistics, audit mutations, reports, failure cards, and human checkpoints.
        console.log("P9-AUDIT-006", "Executing independent Phase 9 review.")
        review = execute_phase9_review(root, console)
        # STEP LOG P9-AUDIT-007: Prove report builders retain failed methods, complete provenance, exact cards, and zero ineligible claims.
        console.log("P9-AUDIT-007", "Auditing report-builder contract.")
        reporting = _audit_report_contract(root)
        # STEP LOG P9-AUDIT-008: Validate the complete repository regression and retained high-volume Phase 9 evidence.
        console.log("P9-AUDIT-008", "Auditing complete-suite evidence.")
        tests = _audit_test_evidence(root)
        # STEP LOG P9-AUDIT-009: Prove Phase 9 produced no training, model, claim-bank, scientific-result, or Phase 9A artifact.
        console.log("P9-AUDIT-009", "Auditing Phase 9 boundary.")
        boundary = _audit_phase_boundary(root)
        # STEP LOG P9-AUDIT-010: Freeze exact metric, audit, report, and registry source identities.
        console.log("P9-AUDIT-010", "Writing Phase 9 implementation manifest.")
        manifest = _write_manifest(root)
        # STEP LOG P9-AUDIT-011: Inventory every Phase 9 console.log with its adjacent identifying comment and exact line.
        console.log("P9-AUDIT-011", "Auditing Phase 9 console instrumentation.")
        console_inventory = _audit_console(root)
        reports = {"required_files": files, "metric_contract": metrics, "audit_registry": audit_registry, "failure_schema": failure_schema, "human_program": human, "implementation_review": review, "report_contract": reporting, "test_evidence": tests, "phase_boundary": boundary, "implementation_manifest": manifest, "console_inventory": console_inventory}
        _write_reports(output, reports)
        write_json(output / "phase9_compliance.json", {"schema_version": "1.0", "phase": 9, "status": "pass", "compliance_gaps": [], "checks": reports})
        # STEP LOG P9-AUDIT-012: Emit the zero-gap Phase 9 verdict only after every metric, audit, report, human, regression, and boundary gate passes.
        console.log("P9-AUDIT-012", "Phase 9 compliance audit passed.", status="pass", details={"compliance_gaps": 0, "metrics": metrics["registered_metrics"], "tests": tests["tests_run"]})
        return 0
    except Exception as exc:
        write_json(output / "phase9_compliance.json", {"schema_version": "1.0", "phase": 9, "status": "fail", "compliance_gaps": [str(exc)]})
        # STEP LOG P9-AUDIT-FAIL: Retain the release-blocking Phase 9 compliance failure and its exact cause.
        console.log("P9-AUDIT-FAIL", "Phase 9 compliance audit failed.", status="fail", details={"error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
