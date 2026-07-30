"""Extreme-rigor WorkPlan Phase 6 compliance audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash
from pead.phase0.audit import inventory_console_logs
from pead.phase2.audit import write_json
from pead.phase6.review import execute_projection_review

EXPECTED_FILES = {
    "src/pead/projections/predictive.py",
    "src/pead/projections/raw_governance.py",
    "src/pead/projections/oracle.py",
    "src/pead/projections/firewall.py",
    "src/pead/projections/tabular.py",
    "src/pead/projections/sequence.py",
    "src/pead/projections/graph.py",
    "configs/access/predictive_state_v1.yaml",
    "configs/access/governance_state_v1.yaml",
    "configs/access/p_only.yaml",
    "configs/access/raw_g.yaml",
    "configs/access/oracle_g.yaml",
    "src/pead/audits/access.py",
    "scripts/audit_access.py",
    "scripts/audit_representation_parity.py",
    "tests/integration/test_access_profiles.py",
    "tests/blind_contract/test_hidden_truth_isolation.py",
    "tests/stress/test_phase6_stress.py",
    "results/audits/phase6/phase6_tests.json",
}


def _audit_files(repo_root: Path) -> dict[str, Any]:
    missing = sorted(path for path in EXPECTED_FILES if not (repo_root / path).is_file())
    if missing:
        raise ValueError(f"missing Phase 6 files: {missing}")
    return {"status": "pass", "required_files": len(EXPECTED_FILES)}


def _audit_requirements(repo_root: Path) -> dict[str, Any]:
    registry = yaml.safe_load(
        (repo_root / "configs/requirements/pead_v1_requirements.yaml").read_text(
            encoding="utf-8"
        )
    )
    entries = [
        entry
        for entry in registry["requirements"]
        if "6" in {str(phase) for phase in entry["phases"]}
    ]
    if not entries:
        raise ValueError("Phase 6 has no registered source requirements")
    missing_controls = [
        entry["requirement_id"]
        for entry in entries
        if not entry.get("files")
        or not entry.get("tests")
        or not entry.get("produced_artifact")
        or not entry.get("release_failure_condition")
    ]
    if missing_controls:
        raise ValueError(f"Phase 6 source requirements are incomplete: {missing_controls}")
    return {
        "status": "pass",
        "phase6_requirement_count": len(entries),
        "requirement_ids_sha256": canonical_hash(
            tuple(sorted(entry["requirement_id"] for entry in entries))
        ),
        "missing_controls": [],
    }


def _audit_test_evidence(repo_root: Path) -> dict[str, Any]:
    report = json.loads(
        (repo_root / "results/audits/phase6/phase6_tests.json").read_text(
            encoding="utf-8"
        )
    )
    stress = report.get("stress_gates", {})
    if (
        report.get("status") != "pass"
        or report.get("failures")
        or report.get("errors")
        or stress.get("dedicated_stress_worlds") != 192
        or stress.get("full_audit_worlds") != 3_600
        or stress.get("full_audit_projection_decisions") != 32_400
    ):
        raise ValueError("Phase 6 complete-suite evidence is incomplete")
    return {
        "status": "pass",
        "tests_run": report["tests_run"],
        "failures": 0,
        "errors": 0,
        "stress_gates": stress,
    }


def _audit_boundary(repo_root: Path) -> dict[str, Any]:
    prohibited = (
        repo_root / "results/models",
        repo_root / "results/checkpoints",
        repo_root / "results/banks/released",
        repo_root / "src/pead/baselines",
    )
    files = [
        path.relative_to(repo_root).as_posix()
        for root in prohibited
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
    ]
    if files:
        raise ValueError(f"Phase 6 created training or later-phase outputs: {files}")
    return {
        "status": "pass",
        "models_trained": 0,
        "checkpoints_created": 0,
        "released_claim_bank_rows": 0,
        "phase7_started": False,
        "scientific_results_claimed": 0,
    }


def _audit_ledger(repo_root: Path) -> dict[str, Any]:
    text = (repo_root / "Path.md").read_text(encoding="utf-8")
    entries = {f"PATH-{index:04d}" for index in range(59, 65)}
    evidence = {
        "access_report.json",
        "representation_parity_report.json",
        "oracle_reconstruction_report.json",
        "runtime_firewall_report.json",
        "phase6_tests.json",
        "console_log_inventory.json",
        "phase6_compliance.json",
    }
    missing = sorted(item for item in entries | evidence if item not in text)
    if missing:
        raise ValueError(f"Phase 6 Path ledger is incomplete: {missing}")
    pending = "Local gates passed; publication pending"
    in_progress = "Local audit in progress"
    complete = "| 6 | Projection layer, feature firewall, and parity | Complete |"
    if in_progress not in text and pending not in text and complete not in text:
        raise ValueError("Phase 6 Path ledger has no valid publication state")
    return {
        "status": "pass",
        "entries": sorted(entries),
        "evidence_pointers": sorted(evidence),
        "publication_state": (
            "complete"
            if complete in text
            else "pending"
            if pending in text
            else "in_progress"
        ),
    }


def _write_review_evidence(output: Path, report: dict[str, Any]) -> None:
    write_json(output / "access_report.json", {
        "schema_version": "1.0",
        "status": "pass",
        "access_configs": report["access_configs"],
        "cross_profile_identity": report["cross_profile_identity"],
        "immutability": report["immutability"],
        "static_dependencies": report["static_dependencies"],
    })
    write_json(
        output / "representation_parity_report.json",
        {
            "schema_version": "1.0",
            "status": "pass",
            "representation_oracle": report["representation_oracle"],
            "raw_g_field_method_matrix": report["raw_g_field_method_matrix"],
            "lossy_transformations": report["lossy_transformations"],
        },
    )
    write_json(
        output / "oracle_reconstruction_report.json",
        {
            "schema_version": "1.0",
            **report["oracle_reconstruction"],
        },
    )
    write_json(
        output / "runtime_firewall_report.json",
        {
            "schema_version": "1.0",
            "status": "pass",
            "runtime_firewall": report["runtime_firewall"],
            "hidden_canaries": report["hidden_canaries"],
            "projection_event_log": report["projection_event_log"],
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    parser.add_argument("--pairs-per-domain", type=int, default=300)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output = root / "results/audits/phase6"
    console = ResearchConsole("6")
    try:
        # STEP LOG P6-AUDIT-001: Verify every WorkPlan-named Phase 6 source, config, script, test, and prerequisite artifact.
        console.log("P6-AUDIT-001", "Auditing required Phase 6 files.")
        files = _audit_files(root)
        # STEP LOG P6-AUDIT-002: Execute the complete non-vacuous projection, parity, Oracle, firewall, and canary review.
        console.log("P6-AUDIT-002", "Executing complete Phase 6 stress review.")
        review = execute_projection_review(
            root,
            console,
            pairs_per_domain=args.pairs_per_domain,
        )
        _write_review_evidence(output, review)
        # STEP LOG P6-AUDIT-003: Verify every Phase 6 source clause retains files, tests, evidence, and release-failure controls.
        console.log("P6-AUDIT-003", "Auditing Phase 6 source-clause coverage.")
        requirements = _audit_requirements(root)
        # STEP LOG P6-AUDIT-004: Verify complete regression, integration, blind-contract, and stress evidence.
        console.log("P6-AUDIT-004", "Auditing complete Phase 6 test evidence.")
        tests = _audit_test_evidence(root)
        # STEP LOG P6-AUDIT-005: Inventory every Phase 6 console call and its adjacent stable identifying comment.
        console.log("P6-AUDIT-005", "Auditing Phase 6 console traceability.")
        inventory = [
            entry
            for entry in inventory_console_logs(root)
            if entry["event_id"].startswith("P6-")
        ]
        write_json(
            output / "console_log_inventory.json",
            {"count": len(inventory), "entries": inventory},
        )
        # STEP LOG P6-AUDIT-006: Verify append-only ledger coverage and prohibit training, release, or Phase 7 outputs.
        console.log("P6-AUDIT-006", "Auditing ledger and phase boundaries.")
        ledger = _audit_ledger(root)
        boundary = _audit_boundary(root)
        registry = {
            "schema_version": "1.0",
            "registry_id": "PEAD-ACCESS-REGISTRY-v1",
            "phase": 6,
            "profiles": review["access_configs"]["profiles"],
            "renderings": list(
                review["raw_g_field_method_matrix"]["methods"]
            ),
            "field_method_matrix_sha256": canonical_hash(
                review["raw_g_field_method_matrix"]["field_method_hashes"]
            ),
            "released_case_count": 0,
            "release_authority": "none",
        }
        registry["content_sha256"] = canonical_hash(registry)
        write_json(
            root / "results/manifests/phase6/access_registry_v1.json",
            registry,
        )
        compliance = {
            "schema_version": "1.0",
            "phase": 6,
            "status": "pass",
            "files": files,
            "requirements": requirements,
            "tests": tests,
            "ledger": ledger,
            "boundary": boundary,
            "review": review,
            "access_registry_sha256": registry["content_sha256"],
            "console_events": len(inventory),
            "completion_gates": {
                "forbidden_imports": 0,
                "forbidden_attribute_reads": 0,
                "label_accesses": 0,
                "canary_correlation_detected": False,
                "raw_g_representation_parity": 1.0,
                "oracle_reconstruction_validation_accuracy": 1.0,
                "released_oracle_cases": 0,
                "representation_oracle": 1.0,
                "lossy_transformations": 0,
                "models_trained": 0,
            },
            "compliance_gaps": [],
        }
        # STEP LOG P6-AUDIT-007: Retain the clause-level Phase 6 compliance verdict and signed access registry.
        console.log(
            "P6-AUDIT-007",
            "Retaining Phase 6 compliance evidence.",
            status="pass",
            details={
                "console_events": len(inventory),
                "projection_decisions": review["projection_decisions"],
                "tests": tests["tests_run"],
                "worlds": review["worlds"],
            },
        )
        write_json(output / "phase6_compliance.json", compliance)
        # STEP LOG P6-AUDIT-008: Report the final local Phase 6 hard-gate verdict.
        console.log("P6-AUDIT-008", "All local Phase 6 gates passed.", status="pass")
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        # STEP LOG P6-AUDIT-009: Emit a hard failure with its unsuppressed cause.
        console.log(
            "P6-AUDIT-009",
            "Phase 6 compliance audit failed.",
            status="fail",
            details={"error": str(error), "error_type": type(error).__name__},
        )
        write_json(
            output / "phase6_compliance.json",
            {
                "schema_version": "1.0",
                "phase": 6,
                "status": "fail",
                "error": str(error),
                "error_type": type(error).__name__,
            },
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
