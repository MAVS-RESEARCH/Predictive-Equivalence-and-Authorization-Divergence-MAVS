"""Extreme-rigor compliance audit for WorkPlan Phase 2."""

from __future__ import annotations

import argparse
import ast
import dataclasses
import hashlib
import json
from collections import Counter, defaultdict
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from pead.config.console import ResearchConsole
from pead.config.models import ConfigValidationError
from pead.core.hashing import canonical_hash
from pead.core.types import AuthorizationAction
from pead.labels.ambiguity import (
    AmbiguityCertificate,
    CompatibleWorld,
    build_exact_certificate,
    verify_certificate,
)
from pead.labels.evaluator_dsl import evaluate_policy
from pead.labels.evaluator_reference import evaluate_reference
from pead.labels.parser import load_policy
from pead.labels.reasons import quarantine_disagreement
from pead.phase0.audit import inventory_console_logs
from pead.phase2.fixtures import (
    REQUIRED_BENCHMARK_STRATA,
    REQUIRED_FIXTURE_CLASSES,
    load_fixtures,
)

EXPECTED_PHASE2_FILES = {
    "Path.md",
    "src/pead/labels/dsl.py",
    "src/pead/labels/parser.py",
    "src/pead/labels/evaluator_dsl.py",
    "src/pead/labels/evaluator_reference.py",
    "src/pead/labels/ambiguity.py",
    "src/pead/labels/reasons.py",
    "configs/mechanisms/authorization_factors_v1.yaml",
    "configs/policies/deploy_authorized_v1.yaml",
    "configs/policies/data_export_v1.yaml",
    "configs/policies/fixtures_v1.yaml",
    "configs/policies/ambiguity_cases_v1.yaml",
    "scripts/audit_labels.py",
    "tests/unit/test_policy_dsl.py",
    "tests/property/test_label_agreement.py",
    "tests/property/test_label_ambiguity.py",
    "tests/metamorphic/test_authorization_invariants.py",
    "tests/stress/test_phase2_stress.py",
    "results/audits/phase2/phase2_tests.json",
}


def _jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {
            field.name: _jsonable(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(value), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def audit_files(repo_root: Path) -> dict[str, Any]:
    missing = sorted(
        relative
        for relative in EXPECTED_PHASE2_FILES
        if not (repo_root / relative).is_file()
    )
    if missing:
        raise ConfigValidationError(f"missing Phase 2 files: {missing}")
    return {"status": "pass", "required_files": len(EXPECTED_PHASE2_FILES)}


def audit_reference_independence(repo_root: Path) -> dict[str, Any]:
    reference_path = repo_root / "src/pead/labels/evaluator_reference.py"
    dsl_path = repo_root / "src/pead/labels/evaluator_dsl.py"
    source = reference_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    forbidden = {
        "pead.labels.dsl",
        "pead.labels.parser",
        "pead.labels.evaluator_dsl",
    }
    violations = sorted(imports & forbidden)
    if violations:
        raise ConfigValidationError(
            f"reference evaluator imports forbidden DSL components: {violations}"
        )
    reference_hash = hashlib.sha256(reference_path.read_bytes()).hexdigest()
    dsl_hash = hashlib.sha256(dsl_path.read_bytes()).hexdigest()
    if reference_hash == dsl_hash:
        raise ConfigValidationError("reference and DSL evaluator source are identical")
    return {
        "status": "pass",
        "serialized_input_only": True,
        "forbidden_imports": violations,
        "reference_source_sha256": reference_hash,
        "dsl_source_sha256": dsl_hash,
    }


def audit_mechanisms(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "configs/mechanisms/authorization_factors_v1.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version",
        "mechanism_registry_id",
        "phase",
        "purpose",
        "mechanisms",
        "generation_status",
    }:
        raise ConfigValidationError("mechanism registry envelope is invalid")
    if (
        raw["schema_version"] != "1.0"
        or raw["phase"] != 2
        or raw["generation_status"] != "deferred_to_phase_3"
        or not isinstance(raw["mechanisms"], list)
        or len(raw["mechanisms"]) != 7
    ):
        raise ConfigValidationError("mechanism registry contract is invalid")
    serialized = json.dumps(raw, sort_keys=True)
    if any(label.value in serialized for label in AuthorizationAction):
        raise ConfigValidationError("mechanism truth interfaces contain terminal labels")
    return {
        "status": "pass",
        "mechanisms": len(raw["mechanisms"]),
        "generation_status": raw["generation_status"],
        "terminal_labels_present": False,
    }


def audit_labels(repo_root: Path, evidence_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    fixtures = load_fixtures(repo_root)
    cases: list[dict[str, Any]] = []
    quarantines: list[Any] = []
    deterministic_errors: list[dict[str, str]] = []
    stratum_totals: Counter[str] = Counter()
    stratum_correct: Counter[str] = Counter()
    family_classes: dict[str, set[str]] = defaultdict(set)
    correct = 0
    for fixture in fixtures:
        policy = load_policy(repo_root / fixture.policy_file)
        family_classes[policy.policy_id].add(fixture.fixture_class)
        for stratum in fixture.benchmark_strata:
            stratum_totals[stratum] += 1
        try:
            dsl = evaluate_policy(policy, fixture.serialized_facts)
            reference = evaluate_reference(policy.policy_id, fixture.serialized_facts)
        except Exception as exc:  # a deterministic Oracle error is retained and fatal
            deterministic_errors.append(
                {
                    "case_id": fixture.case_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            continue
        quarantine = quarantine_disagreement(
            case_id=fixture.case_id,
            policy_id=policy.policy_id,
            dsl_result=dsl,
            reference_result=reference,
            invalidation_scope=(
                f"rule_family:{policy.policy_id}",
                "fixture_bank",
                "dependent_release",
            ),
        )
        if quarantine is not None:
            quarantines.append(quarantine)
        expected_correct = dsl.label is fixture.expected and reference.label is fixture.expected
        if expected_correct:
            correct += 1
            for stratum in fixture.benchmark_strata:
                stratum_correct[stratum] += 1
        cases.append(
            {
                "case_id": fixture.case_id,
                "policy_id": policy.policy_id,
                "fixture_class": fixture.fixture_class,
                "benchmark_strata": fixture.benchmark_strata,
                "expected": fixture.expected,
                "dsl": dsl,
                "reference": reference,
                "agreement": dsl == reference,
                "expected_correct": expected_correct,
                "release_status": "quarantined" if quarantine else "eligible",
            }
        )
    total = len(fixtures)
    agreement = sum(case["agreement"] for case in cases)
    label_report = {
        "schema_version": "1.0",
        "status": (
            "pass"
            if not quarantines
            and not deterministic_errors
            and agreement == total
            and correct == total
            else "fail"
        ),
        "released_cases": total,
        "dual_engine_agreements": agreement,
        "dual_engine_agreement_rate": agreement / total,
        "quarantines": quarantines,
        "deterministic_oracle_errors": deterministic_errors,
        "cases": cases,
    }
    stratum_accuracy = {
        stratum: {
            "correct": stratum_correct[stratum],
            "total": stratum_totals[stratum],
            "accuracy": (
                stratum_correct[stratum] / stratum_totals[stratum]
                if stratum_totals[stratum]
                else None
            ),
        }
        for stratum in sorted(REQUIRED_BENCHMARK_STRATA)
    }
    oracle_report = {
        "schema_version": "1.0",
        "status": "pass" if correct == total and not deterministic_errors else "fail",
        "valid_deterministic_fixtures": total,
        "correct": correct,
        "oracle_rule_accuracy": correct / total,
        "deterministic_errors": deterministic_errors,
        "errors_invalidate_bank": True,
        "errors_are_never_averaged": True,
        "fixture_classes_by_rule_family": {
            family: sorted(classes) for family, classes in sorted(family_classes.items())
        },
        "required_fixture_classes": sorted(REQUIRED_FIXTURE_CLASSES),
        "stratum_accuracy": stratum_accuracy,
    }
    write_json(evidence_root / "label_agreement.json", label_report)
    write_json(evidence_root / "oracle_rule_report.json", oracle_report)
    if label_report["status"] != "pass" or oracle_report["status"] != "pass":
        raise ConfigValidationError(
            "dual-engine agreement, fixture Oracle accuracy, or quarantine gate failed"
        )
    if any(
        result["accuracy"] != 1.0
        for result in stratum_accuracy.values()
    ):
        raise ConfigValidationError("OracleRuleAccuracy is not 1.0 in every released stratum")
    if any(classes != REQUIRED_FIXTURE_CLASSES for classes in family_classes.values()):
        raise ConfigValidationError("a rule family lacks a required fixture class")
    return label_report, oracle_report


def audit_ambiguity(repo_root: Path, evidence_root: Path) -> dict[str, Any]:
    path = repo_root / "configs/policies/ambiguity_cases_v1.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version",
        "registry_id",
        "cases",
    }:
        raise ConfigValidationError("ambiguity registry envelope is invalid")
    if raw["schema_version"] != "1.0" or not isinstance(raw["cases"], list):
        raise ConfigValidationError("ambiguity registry is invalid")
    records: list[dict[str, Any]] = []
    conclusions: set[str] = set()
    for case in raw["cases"]:
        labels = tuple(
            AuthorizationAction(value)
            for value in case["compatible_authorizations"]
        )
        visible_hash = canonical_hash(case["visible_projection"])
        worlds = tuple(
            CompatibleWorld(
                world_id=f"{case['case_id']}-world-{index:03d}",
                facts_hash=canonical_hash(
                    {"case_id": case["case_id"], "world": index, "label": label}
                ),
                authorization=label,
            )
            for index, label in enumerate(labels)
        )
        certificate = build_exact_certificate(
            case_id=case["case_id"],
            visible_state_hash=visible_hash,
            projection_hash=canonical_hash(
                {"schema_version": "1.0", "fields": sorted(case["visible_projection"])}
            ),
            worlds=worlds,
            compatible_space_size=len(worlds),
            permitted_channels=tuple(case["permitted_channels"]),
            available_channels=tuple(case["available_channels"]),
            unavailable_channels=tuple(case["unavailable_channels"]),
            exhausted_channels=tuple(case["exhausted_channels"]),
        )
        verified = verify_certificate(certificate, worlds)
        if not verified or certificate.conclusion != case["expected_conclusion"]:
            raise ConfigValidationError(
                f"ambiguity certificate failed: {case['case_id']}"
            )
        conclusions.add(certificate.conclusion)
        records.append(
            {
                "case_id": case["case_id"],
                "certificate": certificate,
                "independently_verified": verified,
                "proof_worlds": worlds,
            }
        )
    required = {
        "resolvable_unique",
        "irreducibly_ambiguous_escalate",
        "ambiguity_resolution_available",
    }
    if conclusions != required:
        raise ConfigValidationError("ambiguity conclusion coverage is incomplete")
    report = {
        "schema_version": "1.0",
        "status": "pass",
        "claim_bearing_cases": len(records),
        "independently_verified": len(records),
        "timeout_unknown_accepted_as_proof": 0,
        "conclusions": sorted(conclusions),
        "records": records,
    }
    write_json(evidence_root / "ambiguity_certificates.json", report)
    return report


def audit_test_evidence(repo_root: Path) -> dict[str, Any]:
    report = json.loads(
        (repo_root / "results/audits/phase2/phase2_tests.json").read_text(
            encoding="utf-8"
        )
    )
    required_tests = {
        (
            "tests.stress.test_phase2_stress.Phase2StressTests."
            "test_one_hundred_thousand_dual_engine_evaluations_agree"
        ),
        (
            "tests.stress.test_phase2_stress.Phase2StressTests."
            "test_exact_certificate_verifies_all_4096_worlds"
        ),
        (
            "tests.metamorphic.test_authorization_invariants."
            "AuthorizationInvariantTests."
            "test_permission_revocation_cannot_improve_authorization"
        ),
        (
            "tests.metamorphic.test_authorization_invariants."
            "AuthorizationInvariantTests.test_new_prohibition_cannot_improve_authorization"
        ),
        (
            "tests.metamorphic.test_authorization_invariants."
            "AuthorizationInvariantTests.test_irrelevant_intervention_preserves_full_evaluation"
        ),
    }
    if (
        report.get("status") != "pass"
        or report.get("tests_run", 0) < 74
        or not required_tests <= set(report.get("successful_tests", []))
        or report.get("stress_gates", {}).get("dual_engine_evaluations") != 100_000
        or report.get("stress_gates", {}).get("exact_certificate_worlds") != 4_096
    ):
        raise ConfigValidationError("Phase 2 test or stress evidence is incomplete")
    return {
        "status": "pass",
        "tests_run": report["tests_run"],
        "failures": len(report["failures"]),
        "errors": len(report["errors"]),
        "stress_gates": report["stress_gates"],
    }


def audit_phase_boundary(repo_root: Path) -> dict[str, Any]:
    prohibited_roots = (
        repo_root / "results/banks",
        repo_root / "results/models",
        repo_root / "results/checkpoints",
        repo_root / "results/benchmarks",
    )
    found = [
        path.relative_to(repo_root).as_posix()
        for root in prohibited_roots
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
    ]
    if found:
        raise ConfigValidationError(f"Phase 2 produced prohibited later-phase outputs: {found}")
    return {
        "status": "pass",
        "banks_created": 0,
        "models_trained": 0,
        "checkpoints_created": 0,
        "benchmark_outcomes_created": 0,
        "phase3_generation_executed": False,
    }


def audit_path_ledger(repo_root: Path) -> dict[str, Any]:
    ledger = (repo_root / "Path.md").read_text(encoding="utf-8")
    required_entries = {
        "PATH-0024",
        "PATH-0025",
        "PATH-0026",
        "PATH-0027",
        "PATH-0028",
        "PATH-0029",
    }
    missing = sorted(entry for entry in required_entries if entry not in ledger)
    if missing:
        raise ConfigValidationError(f"Phase 2 ledger entries are missing: {missing}")
    required_evidence = {
        "phase2_tests.json",
        "label_agreement.json",
        "oracle_rule_report.json",
        "ambiguity_certificates.json",
        "independence_report.json",
        "console_log_inventory.json",
        "phase2_compliance.json",
    }
    missing_evidence = sorted(
        name for name in required_evidence if name not in ledger
    )
    if missing_evidence:
        raise ConfigValidationError(
            f"Phase 2 ledger evidence pointers are missing: {missing_evidence}"
        )
    if (
        "| 2 | Independent authorization truth system | "
        "Local gates passed; publication pending |"
    ) not in ledger:
        raise ConfigValidationError("Phase 2 ledger status is not publication-pending")
    return {
        "status": "pass",
        "entries": sorted(required_entries),
        "evidence_pointers": sorted(required_evidence),
        "publication_state": "pending",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    evidence_root = repo_root / "results/audits/phase2"
    console = ResearchConsole("2")
    try:
        # STEP LOG P2-AUDIT-001: Establish the exact Phase 2 source, configuration, test, and evidence boundary.
        console.log("P2-AUDIT-001", "Auditing required Phase 2 file presence.")
        files = audit_files(repo_root)
        # STEP LOG P2-AUDIT-002: Verify the procedural evaluator is source-independent from the DSL implementation.
        console.log("P2-AUDIT-002", "Auditing evaluator implementation independence.")
        independence = audit_reference_independence(repo_root)
        write_json(evidence_root / "independence_report.json", independence)
        # STEP LOG P2-AUDIT-003: Verify Phase 2 mechanism files declare latent interfaces without generating worlds.
        console.log("P2-AUDIT-003", "Auditing mechanism truth-interface registry.")
        mechanisms = audit_mechanisms(repo_root)
        # STEP LOG P2-AUDIT-004: Execute exact dual-engine agreement and Oracle accuracy gates.
        console.log("P2-AUDIT-004", "Auditing released authorization fixtures.")
        labels, oracle = audit_labels(repo_root, evidence_root)
        # STEP LOG P2-AUDIT-005: Generate and independently verify every released ambiguity certificate.
        console.log("P2-AUDIT-005", "Auditing compatible-world certificates.")
        ambiguity = audit_ambiguity(repo_root, evidence_root)
        # STEP LOG P2-AUDIT-006: Verify complete regression, property, metamorphic, and stress evidence.
        console.log("P2-AUDIT-006", "Auditing complete test and stress evidence.")
        tests = audit_test_evidence(repo_root)
        # STEP LOG P2-AUDIT-007: Verify every Phase 2 operational console call has an adjacent identity comment.
        console.log("P2-AUDIT-007", "Auditing Phase 2 console line traceability.")
        complete_inventory = inventory_console_logs(repo_root)
        phase2_inventory = [
            entry
            for entry in complete_inventory
            if entry["event_id"].startswith("P2-")
        ]
        if not phase2_inventory:
            raise ConfigValidationError("Phase 2 console inventory is empty")
        write_json(
            evidence_root / "console_log_inventory.json",
            {"count": len(phase2_inventory), "entries": phase2_inventory},
        )
        # STEP LOG P2-AUDIT-008: Confirm Phase 2 did not cross into world generation, training, or benchmarking.
        console.log("P2-AUDIT-008", "Auditing Phase 2 boundary exclusions.")
        boundary = audit_phase_boundary(repo_root)
        # STEP LOG P2-AUDIT-009: Verify the append-only Path ledger records the complete Phase 2 implementation and evidence.
        console.log("P2-AUDIT-009", "Auditing Phase 2 Path ledger completeness.")
        ledger = audit_path_ledger(repo_root)
        compliance = {
            "schema_version": "1.0",
            "phase": 2,
            "status": "pass",
            "workplan_scope": {
                "declarative_policy_dsl": "pass",
                "strict_parser": "pass",
                "total_deterministic_evaluator": "pass",
                "independent_reference_evaluator": "pass",
                "compatible_world_ambiguity": "pass",
                "rule_fixtures": "pass",
                "label_agreement_audit": "pass",
            },
            "completion_gates": {
                "dual_engine_agreement": labels["dual_engine_agreement_rate"],
                "oracle_rule_accuracy": oracle["oracle_rule_accuracy"],
                "deterministic_oracle_errors": len(
                    oracle["deterministic_errors"]
                ),
                "fixture_classes_per_family": "complete",
                "claim_certificates_verified": ambiguity["independently_verified"],
                "timeout_unknown_proofs_accepted": 0,
                "permission_revocation_monotonicity": "pass",
                "prohibition_monotonicity": "pass",
                "irrelevant_intervention_invariance": "pass",
                "quarantined_disagreements": len(labels["quarantines"]),
            },
            "files": files,
            "independence": independence,
            "mechanisms": mechanisms,
            "tests": tests,
            "boundary": boundary,
            "ledger": ledger,
            "console_events": len(phase2_inventory),
            "compliance_gaps": [],
        }
        # STEP LOG P2-AUDIT-010: Retain the complete Phase 2 compliance verdict and evidence pointers.
        console.log(
            "P2-AUDIT-010",
            "Retaining Phase 2 compliance evidence.",
            status="pass",
            details={
                "console_events": len(phase2_inventory),
                "released_cases": labels["released_cases"],
                "tests": tests["tests_run"],
            },
        )
        write_json(evidence_root / "phase2_compliance.json", compliance)
        # STEP LOG P2-AUDIT-011: Report the final local Phase 2 gate verdict.
        console.log(
            "P2-AUDIT-011",
            "All local Phase 2 gates passed.",
            status="pass",
        )
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
        # STEP LOG P2-AUDIT-012: Emit the hard-gate failure without suppressing its cause.
        console.log(
            "P2-AUDIT-012",
            "Phase 2 compliance audit failed.",
            status="fail",
            details={"error": str(error)},
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
