"""Extreme-rigor compliance audit for WorkPlan Phase 3."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from pead.audits.leakage import (
    audit_generator_sources,
    empirical_leakage_audit,
)
from pead.config.console import ResearchConsole
from pead.config.models import ConfigValidationError
from pead.phase0.audit import inventory_console_logs
from pead.phase2.audit import write_json
from pead.phase3.allocation import load_validation_manifest
from pead.phase3.generation import generate_validation_bank


EXPECTED_PHASE3_FILES = {
    "Path.md",
    "src/pead/world/schema.py",
    "src/pead/world/generator_primary.py",
    "src/pead/world/generator_reference.py",
    "src/pead/world/mechanisms.py",
    "src/pead/world/interventions.py",
    "src/pead/world/nuisance.py",
    "src/pead/tracks/exact.py",
    "src/pead/tracks/near.py",
    "src/pead/tracks/distances.py",
    "configs/tracks/near_distance_registry.yaml",
    "configs/allocations/final_claim_bank_v1.yaml",
    "src/pead/audits/equivalence.py",
    "src/pead/audits/authorization.py",
    "src/pead/audits/leakage.py",
    "scripts/generate_bank.py",
    "scripts/audit_equivalence.py",
    "scripts/audit_leakage.py",
    "tests/property/test_twin_invariance.py",
    "tests/metamorphic/test_nuisance_invariance.py",
    "results/manifests/phase3/allocation_validation_manifest_v1.json",
    "results/audits/phase3/phase3_tests.json",
}


def audit_files(repo_root: Path) -> dict[str, Any]:
    missing = sorted(
        relative
        for relative in EXPECTED_PHASE3_FILES
        if not (repo_root / relative).is_file()
    )
    if missing:
        raise ConfigValidationError(f"missing Phase 3 files: {missing}")
    return {"status": "pass", "required_files": len(EXPECTED_PHASE3_FILES)}


def audit_manifest(repo_root: Path) -> dict[str, Any]:
    path = (
        repo_root
        / "results/manifests/phase3/allocation_validation_manifest_v1.json"
    )
    manifest = load_validation_manifest(path)
    if (
        manifest.get("release_authority") != "none"
        or not manifest.get("phase9a_final_signature_required")
        or manifest["exact"]["global_pairs"] != 16_000
        or manifest["near"]["global_pairs"] != 8_000
    ):
        raise ConfigValidationError("Phase 3 validation manifest boundary is invalid")
    return {
        "status": "pass",
        "content_signature_verified": True,
        "release_authority": manifest["release_authority"],
        "phase9a_final_signature_required": True,
        "exact_pairs": manifest["exact"]["global_pairs"],
        "near_pairs": manifest["near"]["global_pairs"],
    }


def audit_test_evidence(repo_root: Path) -> dict[str, Any]:
    report = json.loads(
        (
            repo_root / "results/audits/phase3/phase3_tests.json"
        ).read_text(encoding="utf-8")
    )
    required = {
        (
            "tests.property.test_twin_invariance.TwinInvarianceTests."
            "test_exact_twins_preserve_predictive_state"
        ),
        (
            "tests.metamorphic.test_nuisance_invariance."
            "NuisanceInvarianceTests."
            "test_all_nuisance_variants_preserve_predictive_state_and_label"
        ),
        (
            "tests.stress.test_phase3_stress.Phase3StressTests."
            "test_complete_allocation_denominators_and_quotas"
        ),
    }
    if (
        report.get("status") != "pass"
        or not required <= set(report.get("successful_tests", []))
        or report.get("stress_gates", {}).get("exact_allocations") != 16_000
        or report.get("stress_gates", {}).get("near_allocations") != 8_000
    ):
        raise ConfigValidationError("Phase 3 test evidence is incomplete")
    return {
        "status": "pass",
        "tests_run": report["tests_run"],
        "failures": len(report["failures"]),
        "errors": len(report["errors"]),
        "stress_gates": report["stress_gates"],
    }


def audit_phase_boundary(repo_root: Path) -> dict[str, Any]:
    prohibited_roots = (
        repo_root / "results/models",
        repo_root / "results/checkpoints",
        repo_root / "results/benchmarks",
        repo_root / "results/banks/released",
    )
    found = [
        path.relative_to(repo_root).as_posix()
        for root in prohibited_roots
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
    ]
    if found:
        raise ConfigValidationError(
            f"Phase 3 produced prohibited later-phase outputs: {found}"
        )
    return {
        "status": "pass",
        "released_bank_rows": 0,
        "models_trained": 0,
        "checkpoints_created": 0,
        "benchmark_outcomes_created": 0,
        "phase4_started": False,
    }


def audit_path_ledger(repo_root: Path) -> dict[str, Any]:
    ledger = (repo_root / "Path.md").read_text(encoding="utf-8")
    required_entries = {
        "PATH-0031",
        "PATH-0032",
        "PATH-0033",
        "PATH-0034",
        "PATH-0035",
        "PATH-0036",
        "PATH-0037",
    }
    missing = sorted(entry for entry in required_entries if entry not in ledger)
    if missing:
        raise ConfigValidationError(f"Phase 3 ledger entries are missing: {missing}")
    evidence = {
        "generation_summary.json",
        "equivalence_report.json",
        "authorization_report.json",
        "leakage_report.json",
        "generator_separation_report.json",
        "phase3_tests.json",
        "console_log_inventory.json",
        "phase3_compliance.json",
    }
    missing_evidence = sorted(name for name in evidence if name not in ledger)
    if missing_evidence:
        raise ConfigValidationError(
            f"Phase 3 ledger evidence pointers are missing: {missing_evidence}"
        )
    pending = (
        "| 3 | Causal world registry, exact twins, and near twins | "
        "Local gates passed; publication pending |"
    )
    complete = "| 3 | Causal world registry, exact twins, and near twins | Complete |"
    if pending not in ledger and complete not in ledger:
        raise ConfigValidationError("Phase 3 ledger status is neither pending nor complete")
    return {
        "status": "pass",
        "entries": sorted(required_entries),
        "evidence_pointers": sorted(evidence),
        "publication_state": "complete" if complete in ledger else "pending",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    evidence_root = repo_root / "results/audits/phase3"
    console = ResearchConsole("3")
    try:
        # STEP LOG P3-AUDIT-001: Establish the required Phase 3 implementation and evidence file boundary.
        console.log("P3-AUDIT-001", "Auditing required Phase 3 file presence.")
        files = audit_files(repo_root)
        # STEP LOG P3-AUDIT-002: Verify the content-signed validation manifest and preserve the Phase 9A release boundary.
        console.log("P3-AUDIT-002", "Auditing Phase 3 allocation manifest.")
        manifest = audit_manifest(repo_root)
        # STEP LOG P3-AUDIT-003: Generate every exact and near pair and execute equivalence and authorization gates.
        console.log("P3-AUDIT-003", "Generating complete validation bank.")
        equivalence, authorization, samples, generation = generate_validation_bank(
            repo_root,
            console,
        )
        write_json(evidence_root / "equivalence_report.json", equivalence)
        write_json(evidence_root / "authorization_report.json", authorization)
        write_json(evidence_root / "generation_summary.json", generation)
        # STEP LOG P3-AUDIT-004: Scan both generator paths and unlabeled schemas for prohibited label logic.
        console.log("P3-AUDIT-004", "Auditing generator source separation.")
        source_separation = audit_generator_sources(repo_root)
        write_json(
            evidence_root / "generator_separation_report.json",
            source_separation,
        )
        registry = yaml.safe_load(
            (
                repo_root / "configs/tracks/near_distance_registry.yaml"
            ).read_text(encoding="utf-8")
        )
        # STEP LOG P3-AUDIT-005: Train and test five predictive-only leakage adversaries on disjoint atomic groups.
        console.log("P3-AUDIT-005", "Auditing empirical authorization leakage.")
        leakage = empirical_leakage_audit(
            samples,
            seed=int(registry["leakage"]["permutation_seed"]),
            permutations=int(registry["leakage"]["permutations"]),
            frozen_upper=float(
                registry["leakage"]["frozen_accuracy_upper_band"]
            ),
        )
        write_json(evidence_root / "leakage_report.json", leakage)
        # STEP LOG P3-AUDIT-006: Verify complete regression, property, metamorphic, and stress evidence.
        console.log("P3-AUDIT-006", "Auditing complete Phase 3 test evidence.")
        tests = audit_test_evidence(repo_root)
        # STEP LOG P3-AUDIT-007: Verify every Phase 3 operational console call has an adjacent identity comment.
        console.log("P3-AUDIT-007", "Auditing Phase 3 console traceability.")
        inventory = [
            entry
            for entry in inventory_console_logs(repo_root)
            if entry["event_id"].startswith("P3-")
        ]
        if not inventory:
            raise ConfigValidationError("Phase 3 console inventory is empty")
        write_json(
            evidence_root / "console_log_inventory.json",
            {"count": len(inventory), "entries": inventory},
        )
        # STEP LOG P3-AUDIT-008: Confirm Phase 3 did not train models or release an unsigned final bank.
        console.log("P3-AUDIT-008", "Auditing Phase 3 boundary exclusions.")
        boundary = audit_phase_boundary(repo_root)
        # STEP LOG P3-AUDIT-009: Verify the append-only Path ledger records implementation and evidence.
        console.log("P3-AUDIT-009", "Auditing Phase 3 Path ledger completeness.")
        ledger = audit_path_ledger(repo_root)
        compliance = {
            "schema_version": "1.0",
            "phase": 3,
            "status": "pass",
            "workplan_scope": {
                "latent_factorization": "pass",
                "mechanism_registry_M01_M12": "pass",
                "independent_primary_reference_generation": "pass",
                "exact_twin_construction": "pass",
                "near_equivalence_registry": "pass",
                "nuisance_and_same_label_controls": "pass",
                "atomic_group_splitting": "pass",
                "predictive_only_lower_bounds": "pass",
                "static_and_empirical_leakage": "pass",
            },
            "completion_gates": {
                "exact_pairs": equivalence["exact"]["pairs"],
                "exact_pei_one": equivalence["exact"]["pei_one"],
                "exact_divergent_adi_one": equivalence["exact"][
                    "divergent_adi_one"
                ],
                "exact_same_label_adi_zero": equivalence["exact"][
                    "same_label_adi_zero"
                ],
                "near_pairs": equivalence["near"]["pairs"],
                "near_within_frozen_epsilon": equivalence["near"][
                    "within_frozen_epsilon"
                ],
                "group_overlap": len(
                    equivalence["grouping"]["lineage_split_overlaps"]
                ),
                "ambiguity_certificate_failures": authorization[
                    "ambiguity_certificates"
                ]["failures"],
                "leakage_failures": leakage["failures"],
                "released_unsigned_rows": generation["released_claim_bank_rows"],
            },
            "files": files,
            "manifest": manifest,
            "generation": generation,
            "tests": tests,
            "boundary": boundary,
            "ledger": ledger,
            "console_events": len(inventory),
            "compliance_gaps": [],
        }
        # STEP LOG P3-AUDIT-010: Retain the complete Phase 3 compliance verdict and evidence pointers.
        console.log(
            "P3-AUDIT-010",
            "Retaining Phase 3 compliance evidence.",
            status="pass",
            details={
                "console_events": len(inventory),
                "exact_pairs": equivalence["exact"]["pairs"],
                "near_pairs": equivalence["near"]["pairs"],
                "tests": tests["tests_run"],
            },
        )
        write_json(evidence_root / "phase3_compliance.json", compliance)
        # STEP LOG P3-AUDIT-011: Report the final local Phase 3 gate verdict.
        console.log("P3-AUDIT-011", "All local Phase 3 gates passed.", status="pass")
        return 0
    except (
        ConfigValidationError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        yaml.YAMLError,
    ) as error:
        # STEP LOG P3-AUDIT-012: Emit the hard-gate failure without suppressing its cause.
        console.log(
            "P3-AUDIT-012",
            "Phase 3 compliance audit failed.",
            status="fail",
            details={"error": str(error)},
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
