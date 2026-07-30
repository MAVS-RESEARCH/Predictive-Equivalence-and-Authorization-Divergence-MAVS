"""Strict compliance audit for WorkPlan Phase 1."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from pead.config.console import ResearchConsole
from pead.config.models import ConfigValidationError
from pead.core.diagnostic_registry import load_diagnostic_registry
from pead.core.hashing import (
    CANONICALIZATION_ID,
    FLOAT_QUANTUM,
    canonical_bytes,
    canonical_hash,
)
from pead.core.ids import derive_content_id
from pead.core.requirement_registry import load_requirement_registry
from pead.core.seeds import SEED_NAMESPACES
from pead.core.traces import REQUIRED_TRACE_FIELDS
from pead.phase0.audit import inventory_console_logs

EXPECTED_PHASE1_FILES = {
    "README.md",
    "pyproject.toml",
    "src/pead/core/__init__.py",
    "src/pead/core/types.py",
    "src/pead/core/ids.py",
    "src/pead/core/hashing.py",
    "src/pead/core/seeds.py",
    "src/pead/core/config.py",
    "src/pead/core/registry.py",
    "src/pead/core/runner.py",
    "src/pead/core/traces.py",
    "src/pead/core/paths.py",
    "src/pead/core/diagnostic_registry.py",
    "src/pead/core/requirement_registry.py",
    "src/pead/phase1/__init__.py",
    "src/pead/phase1/audit.py",
    "src/pead/phase1/test_runner.py",
    "scripts/clear_results.py",
    "scripts/validate_config.py",
    "scripts/audit_phase1.py",
    "scripts/run_phase1_tests.py",
    "tests/unit/test_types.py",
    "tests/unit/test_ids.py",
    "tests/unit/test_hashing.py",
    "tests/unit/test_seeds.py",
    "tests/unit/test_config.py",
    "tests/unit/test_paths.py",
    "tests/unit/test_traces.py",
    "tests/unit/test_registry.py",
    "tests/unit/test_runner.py",
    "tests/phase1_fixtures.py",
    "tests/property/__init__.py",
    "tests/property/test_canonicalization.py",
    "tests/stress/test_phase1_stress.py",
    "results/manifests/cleanup/pead.json",
    "results/audits/phase1/phase1_tests.json",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def assert_files(repo_root: Path) -> None:
    missing = sorted(
        relative for relative in EXPECTED_PHASE1_FILES if not (repo_root / relative).is_file()
    )
    if missing:
        raise ConfigValidationError(f"missing Phase 1 files: {missing}")


def audit_determinism() -> dict[str, Any]:
    left = {
        "z": {"beta", "alpha"},
        "graph": {
            "nodes": [{"id": "n2"}, {"id": "n1"}],
            "edges": [{"source": "n1", "target": "n2", "type": "r"}],
        },
        "value": 0.1234567890124,
        "text": "cafe\u0301",
    }
    right = {
        "text": "café",
        "value": 0.12345678901249,
        "graph": {
            "edges": [{"type": "r", "target": "n2", "source": "n1"}],
            "nodes": [{"id": "n1"}, {"id": "n2"}],
        },
        "z": {"alpha", "beta"},
    }
    if canonical_bytes(left) != canonical_bytes(right):
        raise ConfigValidationError("canonical determinism fixture is not byte-identical")
    if derive_content_id("artifact", left) != derive_content_id("artifact", right):
        raise ConfigValidationError("canonical determinism fixture changed identity")
    return {
        "status": "pass",
        "canonicalization_id": CANONICALIZATION_ID,
        "float_quantum": str(FLOAT_QUANTUM),
        "canonical_sha256": canonical_hash(left),
        "byte_length": len(canonical_bytes(left)),
    }


def audit_registries(repo_root: Path) -> dict[str, Any]:
    diagnostics = load_diagnostic_registry(repo_root).manifest()
    requirements = load_requirement_registry(repo_root)
    requirement_manifest = requirements.manifest()
    phase1_requirements = sum(
        "1" in entry.phases for entry in requirements.entries.values()
    )
    if diagnostics.entry_count != 7 or requirement_manifest.entry_count != 789:
        raise ConfigValidationError("typed registry denominator mismatch")
    if phase1_requirements == 0:
        raise ConfigValidationError("no clause-level requirements map to Phase 1")
    return {
        "status": "pass",
        "diagnostic_count": diagnostics.entry_count,
        "diagnostic_registry_sha256": diagnostics.registry_sha256,
        "requirement_count": requirement_manifest.entry_count,
        "phase1_requirement_count": phase1_requirements,
        "requirement_registry_sha256": requirement_manifest.registry_sha256,
    }


def audit_test_evidence(repo_root: Path) -> dict[str, Any]:
    report_path = repo_root / "results" / "audits" / "phase1" / "phase1_tests.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("status") != "pass" or report.get("tests_run", 0) < 50:
        raise ConfigValidationError("Phase 1 test evidence is incomplete or failed")
    required_stress = {
        (
            "tests.stress.test_phase1_stress.Phase1StressTests."
            "test_one_hundred_thousand_content_ids_have_no_collision"
        ),
        (
            "tests.stress.test_phase1_stress.Phase1StressTests."
            "test_ten_thousand_trace_records_finalize_without_loss"
        ),
        (
            "tests.property.test_canonicalization.CanonicalizationPropertyTests."
            "test_random_nested_order_changes_preserve_identity"
        ),
    }
    if not required_stress <= set(report.get("successful_tests", [])):
        raise ConfigValidationError("mandatory Phase 1 stress tests are absent")
    return {
        "status": "pass",
        "tests_run": report["tests_run"],
        "stress_gates": report["stress_gates"],
        "failure_count": len(report["failures"]),
        "error_count": len(report["errors"]),
    }


def audit_cleanup_baseline(repo_root: Path) -> dict[str, Any]:
    manifest = json.loads(
        (repo_root / "results/manifests/cleanup/pead.json").read_text(encoding="utf-8")
    )
    if manifest != {
        "entries": [],
        "run_id": None,
        "schema_version": "1.0",
        "scope": "pead",
    }:
        raise ConfigValidationError("initial cleanup manifest is not the verified no-op")
    receipts = sorted((repo_root / "results/audits/cleanup").glob("cleanup_*.json"))
    if not receipts:
        raise ConfigValidationError("cleanup receipts are missing")
    receipt_payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in receipts
    ]
    for receipt in receipt_payloads:
        if receipt.get("target_count") != 0 or receipt.get("deleted") != []:
            raise ConfigValidationError("cleanup baseline receipt is not a no-op")
    modes = {receipt.get("mode") for receipt in receipt_payloads}
    if modes != {"dry-run", "confirm"}:
        raise ConfigValidationError("cleanup requires both dry-run and confirm receipts")
    return {
        "status": "pass",
        "manifest": "results/manifests/cleanup/pead.json",
        "manifest_entries": 0,
        "receipts": [
            path.relative_to(repo_root).as_posix()
            for path in receipts
        ],
        "modes": sorted(modes),
        "deleted": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    evidence_root = repo_root / "results" / "audits" / "phase1"
    console = ResearchConsole("1")
    try:
        # STEP LOG P1-AUDIT-001: Establish the exact Phase 1 source, test, and evidence boundary.
        console.log("P1-AUDIT-001", "Auditing required Phase 1 file presence.")
        assert_files(repo_root)
        # STEP LOG P1-AUDIT-002: Verify duplicate deterministic objects remain byte-identical.
        console.log("P1-AUDIT-002", "Auditing canonical bytes and content identities.")
        determinism = audit_determinism()
        # STEP LOG P1-AUDIT-003: Verify typed diagnostic and requirement registry completeness.
        console.log("P1-AUDIT-003", "Auditing typed immutable registries.")
        registries = audit_registries(repo_root)
        # STEP LOG P1-AUDIT-004: Verify strict trace schema and decision-before-reveal fields.
        console.log("P1-AUDIT-004", "Auditing strict trace schema inventory.")
        if len(REQUIRED_TRACE_FIELDS) != 17:
            raise ConfigValidationError("strict trace schema field count changed")
        # STEP LOG P1-AUDIT-005: Verify full regression, property, and scale-stress evidence.
        console.log("P1-AUDIT-005", "Auditing retained test and stress evidence.")
        tests = audit_test_evidence(repo_root)
        # STEP LOG P1-AUDIT-006: Verify the initial cleanup was a manifest-bound no-op.
        console.log("P1-AUDIT-006", "Auditing cleanup manifest and dry-run receipt.")
        cleanup = audit_cleanup_baseline(repo_root)
        # STEP LOG P1-AUDIT-007: Verify every operational console call has an adjacent identity comment.
        console.log("P1-AUDIT-007", "Auditing console event comments and line identities.")
        full_inventory = inventory_console_logs(repo_root)
        phase1_inventory = [
            entry for entry in full_inventory if entry["event_id"].startswith("P1-")
        ]
        if not phase1_inventory:
            raise ConfigValidationError("Phase 1 console inventory is empty")
        inventory_report = {
            "phase": 1,
            "status": "pass",
            "count": len(phase1_inventory),
            "entries": phase1_inventory,
        }
        write_json(evidence_root / "console_log_inventory.json", inventory_report)
        # STEP LOG P1-AUDIT-008: Confirm Phase 1 generated no bank, model, or benchmark outcome.
        console.log("P1-AUDIT-008", "Auditing the no-training and no-benchmark boundary.")
        for relative in ("banks", "models", "checkpoints", "results/processed", "results/reports"):
            path = repo_root / relative
            if path.exists() and any(path.rglob("*")):
                raise ConfigValidationError(
                    f"Phase 1 contains prohibited scientific output: {relative}"
                )
        report = {
            "phase": 1,
            "status": "pass",
            "gates": {
                "immutable_typed_records": "pass",
                "canonical_serialization": "pass",
                "field_and_record_hashing": "pass",
                "content_derived_ids": "pass",
                "seed_lineage": "pass",
                "configuration_loading": "pass",
                "typed_registries": "pass",
                "immutable_run_layout": "pass",
                "append_only_atomic_traces": "pass",
                "commit_before_reveal": "pass",
                "cleanup_containment": "pass",
                "console_traceability": "pass",
                "no_training_or_benchmark_results": "pass",
            },
            "determinism": determinism,
            "registries": registries,
            "trace_schema_fields": list(REQUIRED_TRACE_FIELDS),
            "seed_namespaces": SEED_NAMESPACES,
            "tests": tests,
            "cleanup": cleanup,
            "console_log_count": len(phase1_inventory),
            "artifact_hashes": {
                relative: file_sha256(repo_root / relative)
                for relative in sorted(EXPECTED_PHASE1_FILES)
                if (repo_root / relative).is_file()
                and not relative.startswith("results/audits/phase1/")
            },
        }
        write_json(evidence_root / "phase1_compliance.json", report)
        # STEP LOG P1-AUDIT-009: Retain the complete Phase 1 compliance verdict.
        console.log(
            "P1-AUDIT-009",
            "Phase 1 compliance evidence retained.",
            status="pass",
            details={
                "console_events": len(phase1_inventory),
                "tests": tests["tests_run"],
                "trace_schema_fields": len(REQUIRED_TRACE_FIELDS),
            },
        )
        # STEP LOG P1-AUDIT-010: Report the final local Phase 1 gate verdict.
        console.log(
            "P1-AUDIT-010",
            "All local Phase 1 gates passed.",
            status="pass",
        )
        return 0
    except (ConfigValidationError, OSError, ValueError, json.JSONDecodeError) as error:
        # STEP LOG P1-AUDIT-011: Emit the hard-gate failure without suppressing evidence.
        console.log(
            "P1-AUDIT-011",
            "Phase 1 compliance audit failed.",
            status="fail",
            details={"error": str(error)},
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
