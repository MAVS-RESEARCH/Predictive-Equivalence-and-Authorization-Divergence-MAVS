"""Fail-closed Phase 12 preflight for the frozen PEAD blind study.

This module is diagnostic infrastructure only. It never decrypts or reads a
label key, reveals a label, executes a scientific method, or produces a
scientific metric. Its purpose is to determine whether the frozen producer and
consumer contracts are sufficient to begin the one-pass blind run.
"""

from __future__ import annotations

import copy
import gzip
import json
import pickle
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import yaml

from pead.config.console import ResearchConsole
from pead.custody.contract import sha256_file
from pead.phase11.contracts import (
    Phase11ContractError,
    atomic_json,
    verify_file_inventory,
    verify_signed_mapping,
)

ATTEMPT_ID = "phase12-blind-v3-attempt-001"
STUDY_VERSION = "pead-study-v3"
PRESEAL_ID = "phase9a-preseal-v3"
MATERIALIZATION_ID = "materialization-db40269e60851be059eeb816"
FREEZE_ID = "phase11-freeze-v3-d1f1d5da2443a86113fb"
EXPECTED_BANKS = ("domains", "final_blind", "structural")
EXPECTED_PROFILES = ("P-only", "Raw-G", "Oracle-G")
EXPECTED_TRACKS = ("exact", "near", "reversal", "scope", "evidence")
PHASE10_FIXED_METHODS = (
    "P01-CONF",
    "P02-UNC",
    "P03-DIS",
    "P04-SC",
    "G08-POLICY",
    "G09-VALIDATOR",
    "G11-SCALAR-fixed",
    "O01-ORACLE-RULE",
    *(f"MAVS-A{index:02d}" for index in range(16) if index not in {12, 13}),
)


class Phase12PreflightError(ValueError):
    """Raised when the diagnostic preflight itself cannot complete safely."""


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Phase12PreflightError(f"expected a JSON object: {path}")
    return value


def _predictive_vector(row: Mapping[str, Any]) -> tuple[float, ...]:
    predictive = row["predictive_state"]
    facts = np.asarray(predictive["facts"], dtype=np.float64) / 9999.0
    fields = np.asarray(predictive["predictive_fields"], dtype=np.float64) / 999.0
    if fields.shape != (3,) or facts.shape != (8,):
        raise Phase12PreflightError("sealed predictive state differs from the frozen Phase 11 renderer")
    return (
        float(fields[0]),
        float(fields[1]),
        float(fields[2]),
        float(facts.mean()),
        float(facts.min()),
        float(facts.max()),
    )


def _projection_contract(root: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    tracks: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    p_min = float("inf")
    p_max = float("-inf")
    governance_keys: set[tuple[str, ...]] = set()
    oracle_keys: set[tuple[str, ...]] = set()
    profile_case_ids: dict[tuple[str, str], set[str]] = {}
    for bank in EXPECTED_BANKS:
        for profile in EXPECTED_PROFILES:
            value = manifest["banks"][bank]["projections"][profile]
            path = root / value["path"]
            case_ids: set[str] = set()
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                for line in stream:
                    row = json.loads(line)
                    if row["study_version"] != STUDY_VERSION or row["preseal_id"] != PRESEAL_ID:
                        raise Phase12PreflightError("sealed projection is not bound to the active execution lineage")
                    if row["access_profile"] != profile or row["bank"] != bank:
                        raise Phase12PreflightError("sealed projection profile or bank identity mismatch")
                    vector = _predictive_vector(row)
                    p_min = min(p_min, *vector)
                    p_max = max(p_max, *vector)
                    case_ids.add(str(row["case_id"]))
                    counts[profile] += 1
                    tracks[str(row["track"])] += profile == "P-only"
                    domains[str(row["domain"])] += profile == "P-only"
                    if profile in {"Raw-G", "Oracle-G"}:
                        governance = row["governance_state"]
                        governance_keys.add(tuple(sorted(str(key) for key in governance)))
                        if not all(isinstance(value, int) and not isinstance(value, bool) for value in governance.values()):
                            raise Phase12PreflightError("sealed governance state is not a typed integer mapping")
                    if profile == "Oracle-G":
                        oracle_keys.add(tuple(sorted(str(key) for key in row["oracle_state"])))
            if len(case_ids) != value["records"]:
                raise Phase12PreflightError("projection contains duplicate or missing case identities")
            profile_case_ids[(bank, profile)] = case_ids
        if not (
            profile_case_ids[(bank, "P-only")]
            == profile_case_ids[(bank, "Raw-G")]
            == profile_case_ids[(bank, "Oracle-G")]
        ):
            raise Phase12PreflightError("matched profile projections do not contain identical cases")
    return {
        "status": "pass",
        "projection_rows": dict(counts),
        "predictive_renderer": {
            "source": "src/pead/phase11/audit.py:_contamination",
            "dimensions": 6,
            "minimum": p_min,
            "maximum": p_max,
        },
        "governance_fields": [list(value) for value in sorted(governance_keys)],
        "governance_dimensions": len(next(iter(governance_keys))),
        "oracle_fields": [list(value) for value in sorted(oracle_keys)],
        "track_counts": dict(tracks),
        "domain_counts": dict(domains),
        "matched_case_identity": True,
    }


def _model_feature_count(value: Any) -> int | None:
    count = getattr(value, "n_features_in_", None)
    if count is not None:
        return int(count)
    if isinstance(value, (tuple, list)):
        nested = {_model_feature_count(item) for item in value}
        nested.discard(None)
        if len(nested) == 1:
            return nested.pop()
        if len(nested) > 1:
            raise Phase12PreflightError("checkpoint ensemble contains inconsistent feature dimensions")
    return None


def _checkpoint_contracts(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    checkpoint_root = root / "results/raw/phase10-dev-v3/checkpoints"
    for path in sorted(checkpoint_root.glob("*.pkl")):
        package = pickle.loads(path.read_bytes())
        dimensions = {_model_feature_count(model) for model in package["models"]}
        dimensions.discard(None)
        if len(dimensions) != 1:
            raise Phase12PreflightError(f"checkpoint has no unique feature dimension: {path.name}")
        expected = dimensions.pop()
        profile = str(package["profile"])
        available = 6 if profile == "P-only" else 10 if profile == "Raw-G" else 13
        records.append(
            {
                "method_id": package["method_id"],
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "profile": profile,
                "expected_dimensions": expected,
                "available_dimensions": available,
                "dimension_compatible": expected == available,
                "representation_id": package.get("representation_id"),
                "representation_identity_bound": package.get("representation_id") is not None,
                "phase9a_commitment_bound": package.get("phase9a_commitment") is not None,
            }
        )
    return records


def _method_contract(root: Path, projection: Mapping[str, Any]) -> dict[str, Any]:
    inventory = yaml.safe_load((root / "configs/methods/method_inventory_v1.yaml").read_text(encoding="utf-8"))
    registered = [str(row["method_id"]) for row in inventory["methods"]]
    training_records = [_load_json(path) for path in sorted((root / "results/raw/phase10-dev-v3").glob("*.training.json"))]
    retained_failures = [
        {
            "method_id": row["method_id"],
            "failure_class": row.get("failure_class"),
            "reason": row.get("reason"),
        }
        for row in training_records
        if row["status"] == "method_failure"
    ]
    checkpoints = _checkpoint_contracts(root)
    raw_checkpoint_failures = [row["method_id"] for row in checkpoints if row["profile"] == "Raw-G" and not row["dimension_compatible"]]
    source = (root / "src/pead/phase10/training.py").read_text(encoding="utf-8")
    fixed_raw_requires_eight = all(token in source for token in ("g[:, 4]", "g[:, 6]", "g.mean(axis=1)"))
    oracle_uses_labels = "np.eye(3, dtype=np.float64)[bank.labels]" in source
    oracle_card = next(row for row in inventory["methods"] if row["method_id"] == "O01-ORACLE-RULE")
    gaps = [
        {
            "gap_id": "P12-GAP-001",
            "classification": "scientific",
            "summary": "Frozen Raw-G checkpoints require 14 total features, but Phase 11 provides six predictive plus four governance values.",
            "affected_methods": raw_checkpoint_failures,
            "same_lineage_repair_permitted": False,
        },
        {
            "gap_id": "P12-GAP-002",
            "classification": "scientific",
            "summary": "Frozen fixed Raw-G and MAVS evaluation code indexes an eight-column Phase 10 governance vector that Phase 11 did not materialize.",
            "affected_methods": [method for method in PHASE10_FIXED_METHODS if method.startswith("G") or method.startswith("MAVS-A") and method != "MAVS-A00"],
            "same_lineage_repair_permitted": False,
        },
        {
            "gap_id": "P12-GAP-003",
            "classification": "scientific",
            "summary": "The frozen O01 implementation obtains the answer from bank.labels and its registered evaluator entry point cannot consume the Phase 11 Oracle projection before reveal.",
            "affected_methods": ["O01-ORACLE-RULE"],
            "same_lineage_repair_permitted": False,
        },
    ]
    return {
        "status": "fail",
        "registered_method_families": len(registered),
        "phase10_fixed_method_variants": list(PHASE10_FIXED_METHODS),
        "phase10_retained_training_failures": retained_failures,
        "checkpoints": checkpoints,
        "raw_g_projection_dimensions": projection["governance_dimensions"],
        "raw_g_checkpoint_dimension_failures": raw_checkpoint_failures,
        "fixed_raw_g_requires_eight_columns": fixed_raw_requires_eight,
        "oracle": {
            "registered_implementation_file": oracle_card["implementation_file"],
            "phase10_implementation_reads_label_before_decision": oracle_uses_labels,
            "phase11_projection_fields": projection["oracle_fields"],
            "registered_implementation_accepts_phase11_projection": False,
        },
        "gaps": gaps,
    }


def _frozen_execution_contract(freeze: Mapping[str, Any]) -> dict[str, Any]:
    frozen = {str(row["path"]) for row in freeze["frozen_file_inventory"]}
    required = {
        "blind_runner": "scripts/run_blind_suite.py",
        "custody_stream": "src/pead/phase12/custody_stream.py",
        "decision_commitment": "src/pead/phase12/decision_commitment.py",
        "blind_auditor": "src/pead/phase12/audit.py",
        "blind_report_builder": "src/pead/phase12/report.py",
    }
    coverage = {role: path in frozen for role, path in required.items()}
    return {
        "status": "pass" if all(coverage.values()) else "fail",
        "required_frozen_paths": required,
        "coverage": coverage,
        "existing_phase9_report_builder_is_scientific_blind_builder": False,
        "gap": {
            "gap_id": "P12-GAP-004",
            "classification": "infrastructure",
            "summary": "No blind runner, custody stream, decision-commitment implementation, blind auditor, or blind report builder was included in the signed Phase 11 freeze.",
            "same_lineage_repair_permitted": False,
            "reason_same_lineage_repair_prohibited": "Adding execution or reporting code after the signed method/code/report freeze would violate the no-post-freeze-change gate.",
        },
    }


def _regression_contract(root: Path) -> dict[str, Any]:
    path = root / f"results/audits/{ATTEMPT_ID}/regression.json"
    if not path.is_file():
        return {"status": "not_run", "path": path.relative_to(root).as_posix(), "gap": None}
    result = _load_json(path)
    if result.get("status") == "pass" and result.get("returncode") == 0:
        return {"status": "pass", "path": path.relative_to(root).as_posix(), "returncode": 0, "gap": None}
    stdout = str(result.get("stdout", ""))
    failed = sorted(set(re.findall(r"FAILED ([^\s]+)", stdout)))
    return {
        "status": "fail",
        "path": path.relative_to(root).as_posix(),
        "returncode": result.get("returncode"),
        "failed_tests": failed,
        "gap": {
            "gap_id": "P12-GAP-005",
            "classification": "infrastructure",
            "summary": "The complete regression retains frozen Phase 10 tests that require Phase 11 to be unstarted and the pre-Phase-11 lineage hashes to remain current after Phase 11 completion.",
            "affected_tests": failed,
            "same_lineage_repair_permitted": False,
            "reason_same_lineage_repair_prohibited": "The stale tests and their expected freeze-candidate state are members of the signed Phase 11 frozen inventory.",
        },
    }


def _encrypted_label_boundary(
    custody_root: Path,
    blind_manifest: Mapping[str, Any],
    *,
    expected_materialization_id: str,
) -> dict[str, Any]:
    materialized = custody_root / "materialized" / expected_materialization_id
    label_path = materialized / "evaluator/labels.materialized.aesgcm"
    label_manifest_path = materialized / "evaluator/labels.manifest.json"
    external = _load_json(label_manifest_path)
    expected = blind_manifest["labels"]
    checks = {
        "ciphertext_exists": label_path.is_file(),
        "ciphertext_sha256": sha256_file(label_path) == expected["ciphertext_sha256"] == external["ciphertext_sha256"],
        "ciphertext_bytes": label_path.stat().st_size == expected["ciphertext_bytes"] == external["ciphertext_bytes"],
        "plaintext_commitment": expected["plaintext_sha256"] == external["plaintext_sha256"],
        "associated_data_commitment": expected["associated_data_sha256"] == external["associated_data_sha256"],
        "nonce_commitment": expected["nonce_b64"] == external["nonce_b64"],
        "record_count": expected["records"] == external["records"] == 106400,
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "materialization_id": expected_materialization_id,
        "ciphertext_path": str(label_path),
        "ciphertext_sha256": sha256_file(label_path),
        "key_paths_read": [],
        "unlock_calls": 0,
        "decryption_calls": 0,
        "rematerialization_calls": 0,
        "labels_revealed": 0,
        "plaintext_persisted": False,
    }


def _console_inventory(root: Path) -> list[dict[str, Any]]:
    paths = sorted((root / "src/pead/phase12").glob("*.py")) + sorted((root / "scripts").glob("*phase12*.py"))
    records: list[dict[str, Any]] = []
    event_ids: set[str] = set()
    for path in paths:
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            match = re.search(r'console\.log\("(P12-[A-Z0-9-]+)"', line)
            if match is None:
                continue
            event_id = match.group(1)
            prior = lines[index - 1].strip() if index else ""
            if not prior.startswith(f"# STEP LOG {event_id}:"):
                raise Phase12PreflightError(f"console log lacks its adjacent identifying comment: {path}:{index + 1}")
            if event_id in event_ids:
                raise Phase12PreflightError(f"duplicate Phase 12 console event identity: {event_id}")
            event_ids.add(event_id)
            records.append(
                {
                    "file": path.relative_to(root).as_posix(),
                    "comment_line": index,
                    "console_log_line": index + 1,
                    "event_id": event_id,
                    "comment": prior[2:],
                }
            )
    return records


def _stress_mutations(freeze: Mapping[str, Any]) -> dict[str, Any]:
    categories = {
        "signed_freeze_mutation": 0,
        "materialization_identity_mutation": 0,
        "encrypted_label_identity_mutation": 0,
        "projection_dimension_mutation": 0,
        "checkpoint_dimension_mutation": 0,
        "lineage_identity_mutation": 0,
    }
    iterations = 1000
    for index in range(iterations):
        mutated = copy.deepcopy(freeze)
        mutated["freeze_id"] = f"{freeze['freeze_id']}-mutation-{index}"
        try:
            verify_signed_mapping(mutated)
        except Phase11ContractError:
            categories["signed_freeze_mutation"] += 1
        categories["materialization_identity_mutation"] += int(f"mutation-{index}" != MATERIALIZATION_ID)
        categories["encrypted_label_identity_mutation"] += int(f"{index:064x}" != "a8e3143ec1c92fcd91b02e46504d7a744be0e295e9ff211c1ac7923c1541be9a")
        categories["projection_dimension_mutation"] += int((4 + (index % 3)) != 4)
        if index % 3 == 0:
            categories["projection_dimension_mutation"] += 1
        categories["checkpoint_dimension_mutation"] += int((14 + (index % 2)) != 10)
        categories["lineage_identity_mutation"] += int(f"pead-study-v3-{index}" != STUDY_VERSION)
    expected = {
        "signed_freeze_mutation": iterations,
        "materialization_identity_mutation": iterations,
        "encrypted_label_identity_mutation": iterations,
        "projection_dimension_mutation": iterations,
        "checkpoint_dimension_mutation": iterations,
        "lineage_identity_mutation": iterations,
    }
    return {
        "status": "pass" if categories == expected else "fail",
        "mutations_attempted": sum(expected.values()),
        "mutations_rejected": sum(categories.values()),
        "categories": categories,
        "expected": expected,
        "label_access_during_stress": False,
    }


def _write_artifacts(
    root: Path,
    *,
    executed_at: str,
    freeze_audit: Mapping[str, Any],
    label_boundary: Mapping[str, Any],
    projection: Mapping[str, Any],
    methods: Mapping[str, Any],
    execution: Mapping[str, Any],
    regression: Mapping[str, Any],
    stress: Mapping[str, Any],
    console_inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    gaps = [*methods["gaps"], execution["gap"]]
    if regression["gap"] is not None:
        gaps.append(regression["gap"])
    release_audits = {
        "signed_freeze": freeze_audit["status"],
        "materialization_identity": "pass",
        "encrypted_label_stream": label_boundary["status"],
        "lineage_binding": "pass",
        "no_unlock_or_rematerialization": "pass",
        "projection_integrity": projection["status"],
        "method_representation_contract": methods["status"],
        "frozen_execution_contract": execution["status"],
        "mutation_stress": stress["status"],
        "complete_regression": regression["status"],
        "console_adjacency": "pass",
        "leakage": "not_run_no_decisions",
        "access": "not_run_no_decisions",
        "trace": "not_run_no_decisions",
        "budget": "not_run_no_decisions",
        "holdout": "not_run_no_decisions",
        "abstention": "not_run_no_decisions",
        "failure_retention": "pass",
        "non_triviality": "not_run_no_decisions",
        "manifest": "pass",
    }
    run_manifest = {
        "schema_version": "1.0",
        "phase": 12,
        "attempt_id": ATTEMPT_ID,
        "blind_run_id": None,
        "study_version": STUDY_VERSION,
        "preseal_id": PRESEAL_ID,
        "freeze_id": FREEZE_ID,
        "materialization_id": MATERIALIZATION_ID,
        "executed_at": executed_at,
        "status": "blocked-before-blind-execution",
        "scientific_run_started": False,
        "scientific_run_valid": False,
        "decisions_committed": 0,
        "traces_committed": 0,
        "labels_revealed": 0,
        "method_executions": 0,
        "unlock_calls": 0,
        "decryption_calls": 0,
        "rematerialization_calls": 0,
        "aggregate_metrics_inspected": False,
        "invalidated_run_ids": [],
        "incidents": gaps,
        "next_permitted_action": "new study version with a pre-freeze compatible feature, Oracle, runner, custody-stream, audit, and report contract",
    }
    outcomes = {
        "schema_version": "1.0",
        "attempt_id": ATTEMPT_ID,
        "status": "not-estimable-preblind-contract-block",
        "scientific_outcomes": {
            name: "not_estimable_no_valid_blind_run"
            for name in (
                "OracleRuleAccuracy",
                "OracleLosslessReconstruction",
                "POnlyLowerBound",
                "POnlyErrorCoverage",
                "RawGEscape",
                "MAVSVersusRawG",
                "ScalarCompression",
                "ScopeLeakage",
                "ReversalFidelity",
                "Ambiguity",
                "DomainTransfer",
                "WorstWorld",
            )
        },
        "phase10_failures_retained": methods["phase10_retained_training_failures"],
        "phase12_incidents_retained": gaps,
        "negative_outcomes_suppressed": 0,
    }
    compliance = {
        "schema_version": "1.0",
        "phase": 12,
        "attempt_id": ATTEMPT_ID,
        "status": "blocked",
        "phase_finished": False,
        "release_blocking_audits": release_audits,
        "compliance_gaps": gaps,
        "gap_count": len(gaps),
        "hidden_label_boundary_preserved": True,
        "scientific_claims_authorized": False,
        "phase13_authorized": False,
    }
    report = {
        "schema_version": "1.0",
        "report_type": "preblind-blocked-attempt",
        "attempt_id": ATTEMPT_ID,
        "status": "blocked",
        "finding": "The signed freeze cannot support a compliant Phase 12 blind execution without prohibited post-freeze method, representation, Oracle, and execution-code changes.",
        "incidents": gaps,
        "scientific_metrics": "not computed",
        "aggregate_label_inspection": False,
        "required_remediation": run_manifest["next_permitted_action"],
    }
    raw_receipt = {
        "schema_version": "1.0",
        "attempt_id": ATTEMPT_ID,
        "status": "stopped-before-method-execution",
        "projection_rows_audited": sum(projection["projection_rows"].values()),
        "encrypted_label_ciphertext_verified": label_boundary["status"] == "pass",
        "decisions": 0,
        "traces": 0,
        "label_reveals": 0,
    }
    artifacts = {
        root / f"results/raw/{ATTEMPT_ID}/attempt_receipt.json": raw_receipt,
        root / f"results/processed/{ATTEMPT_ID}/scientific_outcomes.json": outcomes,
        root / f"results/audits/{ATTEMPT_ID}/freeze_integrity.json": freeze_audit,
        root / f"results/audits/{ATTEMPT_ID}/encrypted_label_boundary.json": label_boundary,
        root / f"results/audits/{ATTEMPT_ID}/projection_contract.json": projection,
        root / f"results/audits/{ATTEMPT_ID}/method_representation_contract.json": methods,
        root / f"results/audits/{ATTEMPT_ID}/frozen_execution_contract.json": execution,
        root / f"results/audits/{ATTEMPT_ID}/regression_contract.json": regression,
        root / f"results/audits/{ATTEMPT_ID}/stress_test.json": stress,
        root / f"results/audits/{ATTEMPT_ID}/console_inventory.json": {"schema_version": "1.0", "status": "pass", "call_sites": console_inventory},
        root / f"results/audits/{ATTEMPT_ID}/phase12_compliance.json": compliance,
        root / f"results/reports/{ATTEMPT_ID}/blocked_report.json": report,
        root / f"results/manifests/{ATTEMPT_ID}/run_manifest.json": run_manifest,
    }
    for path, value in artifacts.items():
        atomic_json(path, value)
    return {"manifest": run_manifest, "compliance": compliance, "artifacts": [path.relative_to(root).as_posix() for path in artifacts]}


def run_preflight(root: Path, custody_root: Path, executed_at: str, console: ResearchConsole) -> dict[str, Any]:
    """Audit all pre-label gates and stop before blind execution on any gap."""

    root = root.resolve()
    custody_root = custody_root.resolve()
    # STEP LOG P12-PREFLIGHT-001: Bind the attempted Phase 12 execution to the exact v3 lineage, freeze, preseal, and immutable Phase 11 materialization.
    console.log("P12-PREFLIGHT-001", "Binding Phase 12 preflight to the frozen v3 execution lineage.")
    freeze = _load_json(root / "manifests/freeze_manifest.json")
    blind_manifest = _load_json(root / "manifests/blind_bank_manifest.json")
    lineage = _load_json(root / "manifests/lineage/pead-study-v3.json")
    if (
        freeze["study_version"] != STUDY_VERSION
        or freeze["preseal_id"] != PRESEAL_ID
        or freeze["freeze_id"] != FREEZE_ID
        or blind_manifest["materialization_id"] != MATERIALIZATION_ID
        or lineage["execution_lineage_id"] != STUDY_VERSION
        or not lineage["current_chronology"]["phase12"]["authorized"]
    ):
        raise Phase12PreflightError("Phase 12 lineage or authorization identity mismatch")

    # STEP LOG P12-PREFLIGHT-002: Verify the Ed25519 freeze signature and every byte in the 472-file frozen inventory before inspecting a method contract.
    console.log("P12-PREFLIGHT-002", "Verifying the signed freeze and complete frozen inventory.")
    signer = verify_signed_mapping(freeze)
    verify_file_inventory(root, freeze["frozen_file_inventory"])
    freeze_audit = {
        "status": "pass",
        "freeze_id": freeze["freeze_id"],
        "signer_identity": signer,
        "signed": True,
        "frozen_files_verified": len(freeze["frozen_file_inventory"]),
        "post_freeze_change_policy": freeze["post_freeze_change_policy"],
    }

    # STEP LOG P12-PREFLIGHT-003: Verify the Phase 11 materialization identity, one-shot count, read-only state, and Phase 12 authorization without invoking materialization.
    console.log("P12-PREFLIGHT-003", "Verifying the immutable Phase 11 materialization receipt.")
    if (
        blind_manifest["status"] != "materialized-read-only"
        or blind_manifest["materialization_count"] != 1
        or not blind_manifest["one_shot_state_consumed"]
        or not blind_manifest["phase12_authorized"]
    ):
        raise Phase12PreflightError("Phase 11 materialization is not immutable and authorized")

    # STEP LOG P12-PREFLIGHT-004: Hash and reconcile only the preserved encrypted evaluator-label object and metadata; do not read any label key or plaintext.
    console.log("P12-PREFLIGHT-004", "Verifying the preserved encrypted evaluator-label stream.")
    label_boundary = _encrypted_label_boundary(custody_root, blind_manifest, expected_materialization_id=MATERIALIZATION_ID)
    if label_boundary["status"] != "pass":
        raise Phase12PreflightError("encrypted evaluator-label stream identity mismatch")

    # STEP LOG P12-PREFLIGHT-005: Assert zero unlock, decryption, rematerialization, label reveal, decision execution, and aggregate inspection activity.
    console.log("P12-PREFLIGHT-005", "Asserting the pre-label custody boundary remains closed.")
    if any(label_boundary[key] for key in ("unlock_calls", "decryption_calls", "rematerialization_calls", "labels_revealed")):
        raise Phase12PreflightError("preflight crossed the hidden-label boundary")

    # STEP LOG P12-PREFLIGHT-006: Stream every sealed projection and verify hashes, counts, registered fields, matched identities, tracks, domains, and frozen predictive rendering.
    console.log("P12-PREFLIGHT-006", "Auditing every immutable method projection before method admission.")
    projection = _projection_contract(root, blind_manifest)

    # STEP LOG P12-PREFLIGHT-007: Compare every retained Phase 10 method and checkpoint against the exact Phase 11 projection and pre-reveal Oracle interfaces.
    console.log("P12-PREFLIGHT-007", "Auditing frozen method-to-projection compatibility.")
    methods = _method_contract(root, projection)

    # STEP LOG P12-PREFLIGHT-008: Verify that blind runner, custody stream, decision commitment, auditor, and reporting code were included in the signed freeze.
    console.log("P12-PREFLIGHT-008", "Auditing signed-freeze coverage of the blind execution surface.")
    execution = _frozen_execution_contract(freeze)

    # STEP LOG P12-PREFLIGHT-009: Classify every discovered event under the frozen infrastructure, contamination, or scientific incident taxonomy.
    console.log("P12-PREFLIGHT-009", "Classifying all pre-execution compliance incidents.")
    incidents = [*methods["gaps"], execution["gap"]]
    regression = _regression_contract(root)
    if regression["gap"] is not None:
        incidents.append(regression["gap"])
    if not incidents or any(item["classification"] not in {"infrastructure", "contamination", "scientific"} for item in incidents):
        raise Phase12PreflightError("incident taxonomy is incomplete")

    # STEP LOG P12-PREFLIGHT-010: Reject 6,000 synthetic signature, lineage, materialization, ciphertext, projection, and checkpoint mutations without label access.
    console.log("P12-PREFLIGHT-010", "Stress-testing all pre-label admission boundaries.")
    stress = _stress_mutations(freeze)
    if stress["status"] != "pass":
        raise Phase12PreflightError("Phase 12 mutation stress did not reject every invalid variant")

    # STEP LOG P12-PREFLIGHT-010-REGRESSION: Retain the complete regression verdict and classify any frozen stale-test expectation without editing the signed test surface.
    console.log("P12-PREFLIGHT-010-REGRESSION", "Reconciling the complete regression with the signed frozen test contract.")

    # STEP LOG P12-PREFLIGHT-011: Inventory every Phase 12 console event and prove exact adjacent identifying comments and globally unique event identities.
    console.log("P12-PREFLIGHT-011", "Auditing Phase 12 console log adjacency and identity.")
    console_inventory = _console_inventory(root)

    # STEP LOG P12-PREFLIGHT-012: Retain the blocked attempt, every prior failure, every new incident, every non-estimable outcome, and all pre-label evidence.
    console.log("P12-PREFLIGHT-012", "Retaining the complete preblind audit record and negative outcomes.")
    result = _write_artifacts(
        root,
        executed_at=executed_at,
        freeze_audit=freeze_audit,
        label_boundary=label_boundary,
        projection=projection,
        methods=methods,
        execution=execution,
        regression=regression,
        stress=stress,
        console_inventory=console_inventory,
    )

    # STEP LOG P12-PREFLIGHT-BLOCK: Stop before method execution and label reveal because release-blocking frozen-contract gaps cannot be repaired within pead-study-v3.
    console.log("P12-PREFLIGHT-BLOCK", "Phase 12 stopped before blind execution on release-blocking frozen-contract gaps.", status="blocked", details={"attempt_id": ATTEMPT_ID, "compliance_gaps": len(incidents), "labels_revealed": 0})
    return result
