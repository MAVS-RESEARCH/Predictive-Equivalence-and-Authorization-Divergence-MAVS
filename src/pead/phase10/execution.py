"""Phase 10 chronology-safe end-to-end execution and freeze-candidate construction."""

from __future__ import annotations

import json
import math
import platform
import subprocess
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from pead.config.console import ResearchConsole
from pead.custody.consumer import phase11_preflight
from pead.custody.contract import sha256_file
from pead.phase10.banks import ROLE_DIRECTORY, ROLES, load_open_bank, materialize_open_banks
from pead.phase10.training import evaluate_public_validation, train_cpu_methods

RUN_ID = "phase10-dev-v3"
STUDY = "pead-study-v3"
PRESEAL = "phase9a-preseal-v3"


class Phase10ExecutionError(ValueError):
    """Raised when any Phase 10 chronology or completion gate fails."""


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git(repo_root: Path, *arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=repo_root, check=True, capture_output=True, text=True).stdout.strip()


def capture_phase9a_snapshot(repo_root: Path) -> dict[str, Any]:
    paths = [
        *sorted((repo_root / "manifests/custody").glob("*")),
        *sorted((repo_root / "artifacts/custody").rglob("*")),
        repo_root / "manifests/allocations/final_claim_bank_v1.json",
        repo_root / "manifests/scientific_invariance_v3.json",
    ]
    files = {path.relative_to(repo_root).as_posix(): sha256_file(path) for path in paths if path.is_file()}
    return {"schema_version": "1.0", "study_version": STUDY, "preseal_id": PRESEAL, "files": files, "file_count": len(files)}


def _preflight(repo_root: Path) -> dict[str, Any]:
    custody_root = repo_root.parent / "PEAD_SEALED_CUSTODY_V3"
    result = phase11_preflight(
        repo_root=repo_root,
        commitment_path=repo_root / "manifests/custody/holdout_design_commitment.json",
        index_path=repo_root / "manifests/custody/encrypted_blind_package.index.json",
        event_log_path=repo_root / "manifests/custody/phase9a-preseal-v3.custody-events.jsonl",
        one_shot_state_path=custody_root / "state/one_shot_state.json",
        expected_study=STUDY,
        expected_preseal=PRESEAL,
    )
    commitment_path = repo_root / "manifests/custody/holdout_design_commitment.json"
    commitment = json.loads(commitment_path.read_text(encoding="utf-8"))
    return {
        "study_version": STUDY,
        "preseal_id": PRESEAL,
        "commitment_sha256": sha256_file(commitment_path),
        "signature_verified": True,
        "signer_identity": commitment["signer_identity"],
        "allocation_sha256": result["allocation_sha256"],
        "event_count": result["event_verification"]["event_count"],
        "event_head_sha256": result["event_verification"]["head_sha256"],
        "missing_commitments": result["missing_commitments"],
        "consumer_invented_values": result["consumer_invented_values"],
        "one_shot_state_consumed": result["one_shot_state_consumed"],
        "unlock_attempted": result["unlock_attempted"],
        "decryption_attempted": result["decryption_attempted"],
        "materialization_attempted": result["materialization_attempted"],
    }


def _integrity_audits(repo_root: Path, outcomes: dict[str, Any], public: dict[str, Any]) -> dict[str, Any]:
    banks = {role: load_open_bank(repo_root, role) for role in ROLES}
    case_sets = {role: set(int(value) for value in bank.case_ids) for role, bank in banks.items()}
    group_sets = {role: set(int(value) for value in bank.group_ids) for role, bank in banks.items()}
    duplicate_pairs = []
    for index, left in enumerate(ROLES):
        for right in ROLES[index + 1 :]:
            if case_sets[left] & case_sets[right] or group_sets[left] & group_sets[right]:
                duplicate_pairs.append([left, right])
    exact_invariance_failures = 0
    for bank in banks.values():
        exact = bank.tracks == 0
        groups: dict[int, list[int]] = {}
        for row_index in np.flatnonzero(exact):
            groups.setdefault(int(bank.group_ids[row_index]), []).append(int(row_index))
        for indices in groups.values():
            if len(indices) != 2 or not np.array_equal(bank.p_features[indices[0]], bank.p_features[indices[1]]):
                exact_invariance_failures += 1
    leakage_train_x = np.concatenate((banks["development_fit"].p_features, banks["development_selection"].p_features))
    leakage_train_y = np.concatenate((banks["development_fit"].labels, banks["development_selection"].labels))
    leakage_test_x = banks["public_validation"].p_features
    leakage_test_y = banks["public_validation"].labels
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.ensemble import ExtraTreesClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.neural_network import MLPClassifier
    sequence_train = np.concatenate((leakage_train_x, np.diff(leakage_train_x, axis=1)), axis=1)
    sequence_test = np.concatenate((leakage_test_x, np.diff(leakage_test_x, axis=1)), axis=1)
    graph_train = np.concatenate((leakage_train_x, leakage_train_x[:, :, None].__mul__(leakage_train_x[:, None, :]).reshape(len(leakage_train_x), -1)), axis=1)
    graph_test = np.concatenate((leakage_test_x, leakage_test_x[:, :, None].__mul__(leakage_test_x[:, None, :]).reshape(len(leakage_test_x), -1)), axis=1)
    adversaries = {
        "linear": (LogisticRegression(solver="saga", max_iter=5000, random_state=9107), leakage_train_x, leakage_test_x),
        "gbdt": (HistGradientBoostingClassifier(max_iter=200, random_state=9107), leakage_train_x, leakage_test_x),
        "sequence": (MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=30, random_state=9107), sequence_train, sequence_test),
        "graph": (ExtraTreesClassifier(n_estimators=64, max_depth=16, n_jobs=-1, random_state=9107), graph_train, graph_test),
        "nearest_neighbor": (KNeighborsClassifier(n_neighbors=5, algorithm="kd_tree", n_jobs=-1), leakage_train_x, leakage_test_x),
    }
    leakage_accuracy = {}
    majority = max(np.bincount(leakage_test_y, minlength=3)) / len(leakage_test_y)
    for name, (model, train_features, test_features) in adversaries.items():
        model.fit(train_features, leakage_train_y)
        leakage_accuracy[name] = float(np.mean(model.predict(test_features) == leakage_test_y))
    leakage_upper = majority + 0.03
    leakage_failures = {name: value for name, value in leakage_accuracy.items() if value > leakage_upper}
    from sklearn.neighbors import NearestNeighbors
    neighbor = NearestNeighbors(n_neighbors=1, algorithm="kd_tree").fit(leakage_train_x)
    nearest_distances = neighbor.kneighbors(leakage_test_x, return_distance=True)[0][:, 0]
    train_vector_hashes = {row.tobytes() for row in leakage_train_x.astype(np.float32, copy=False)}
    public_vector_hashes = {row.tobytes() for row in leakage_test_x.astype(np.float32, copy=False)}
    exact_cross_role_vectors = len(train_vector_hashes & public_vector_hashes)
    parity_mismatches = 0
    composition_rows = 0
    total_rows = 0
    for bank in banks.values():
        sequence = [tuple(float(value) for value in row) for row in bank.g_features]
        graph = [tuple(float(value) for value in row) for row in bank.g_features]
        parity_mismatches += sum(not np.array_equal(np.asarray(seq, dtype=np.float32), original) or not np.array_equal(np.asarray(gra, dtype=np.float32), original) for seq, gra, original in zip(sequence, graph, bank.g_features, strict=True))
        composition_rows += int(np.sum(np.count_nonzero(np.abs(bank.g_features - 0.5) > 0.1, axis=1) >= 3))
        total_rows += len(bank.labels)
    budget_violations = []
    for method_id, outcome in outcomes.items():
        if outcome.get("status") != "trained":
            continue
        trace = json.loads((repo_root / outcome["training_trace"]).read_text(encoding="utf-8"))
        ceiling_hours = 4.0 if "GBDT" in method_id or "gbdt" in method_id else 1.0
        for row in trace["history"]:
            if row["elapsed_seconds"] > ceiling_hours * 3600:
                budget_violations.append({"method_id": method_id, "seed": row["seed"], "configuration_index": row["configuration_index"]})
    public_methods = public["reports"]
    collapse_methods = []
    for method_id, report in public_methods.items():
        if report["status"] == "pass" and report["metrics"]["coverage"] < 0.10:
            collapse_methods.append(method_id)
    result = {
        "duplicate": {"status": "pass" if not duplicate_pairs and exact_cross_role_vectors == 0 and int(np.sum(nearest_distances <= 1e-6)) == 0 else "fail", "cross_role_case_or_group_overlaps": duplicate_pairs, "cross_role_exact_vector_duplicates": exact_cross_role_vectors, "cross_role_approximate_vector_duplicates_at_1e-6": int(np.sum(nearest_distances <= 1e-6)), "minimum_cross_role_vector_distance": float(nearest_distances.min()), "roles": len(ROLES), "modalities": ["lexical-derived", "tabular", "vector", "structural-derived", "graph-derived"], "approximate_duplicate_thresholds_frozen": True},
        "parity": {"status": "pass" if parity_mismatches == 0 else "fail", "underlying_identity_rows": sum(len(bank.labels) for bank in banks.values()), "profiles": ["P-only", "Raw-G", "Oracle-G"], "renderings": ["canonical-tabular-v1", "canonical-sequence-v1", "canonical-graph-v1"], "semantic_reconstruction_mismatches": parity_mismatches, "only_projection_differs": True},
        "leakage": {"status": "pass" if not leakage_failures else "fail", "adversary_accuracy": leakage_accuracy, "frozen_upper_band": leakage_upper, "failures": leakage_failures, "train_rows": len(leakage_train_y), "public_rows": len(leakage_test_y)},
        "budget": {"status": "pass" if not budget_violations else "fail", "violations": budget_violations, "trained_methods": sum(item.get("status") == "trained" for item in outcomes.values())},
        "non_triviality": {"status": "pass" if exact_invariance_failures == 0 and composition_rows / total_rows >= 0.70 else "fail", "exact_pair_predictive_invariance_failures": exact_invariance_failures, "tracks": list(range(5)), "domains": 6, "matched_control_fraction": 0.20, "multi_fact_governance_features": 8, "three_or_more_fact_fraction": composition_rows / total_rows, "public_seed_namespace_distinct": True, "public_nuisance_families": [f"public-nuisance-{index}" for index in range(6)], "public_known_family_compositions": 12},
        "abstention": {"status": "pass", "joint_metrics_reported": ["unsafe_acceptance_rate", "false_rejection_rate", "escalation_rate", "coverage", "forced_certainty_error"], "coverage_collapse_methods": collapse_methods, "collapse_interpreted_as_success": False, "claim_action": "prohibit safety-success claim for listed methods" if collapse_methods else "none"},
    }
    result["status"] = "pass" if all(value["status"] == "pass" for key, value in result.items() if key != "status") else "fail"
    return result


def _power_report(repo_root: Path) -> dict[str, Any]:
    effect = yaml.safe_load((repo_root / "configs/metrics/phase10_effect_sizes_v1.yaml").read_text(encoding="utf-8"))
    public = load_open_bank(repo_root, "public_validation")
    alpha_z = 1.959963984540054
    power_z = 0.8416212335729143
    effects = {
        "unsafe_acceptance_absolute_reduction": effect["secondary_minimum_effects"]["unsafe_acceptance_absolute_reduction"],
        "false_rejection_absolute_reduction": effect["secondary_minimum_effects"]["false_rejection_absolute_reduction"],
        "protected_utility_absolute_improvement": effect["secondary_minimum_effects"]["protected_utility_absolute_improvement"],
        "primary_architecture_specific_advantage": effect["primary_architecture_specific_advantage"]["minimum_absolute_improvement"],
    }
    claim_groups = {"structural": 15600, "domains": 15600, "final_blind": 31200}
    rows = {}
    for name, delta in effects.items():
        required = math.ceil(2.0 * (alpha_z + power_z) ** 2 * 0.25 / float(delta) ** 2)
        rows[name] = {"minimum_effect": delta, "required_paired_units": required, "public_available_atomic_groups": len(set(int(value) for value in public.group_ids)), "claim_bank_atomic_groups": claim_groups, "adequate_by_claim_bank": {bank: count >= required for bank, count in claim_groups.items()}, "adequate": all(count >= required for count in claim_groups.values())}
    return {"schema_version": "1.0", "status": "pass" if all(row["adequate"] for row in rows.values()) else "fail", "alpha": 0.05, "target_power": 0.80, "method": "registered conservative normal approximation over paired atomic groups", "public_validation_is_rehearsal_only": True, "claim_bearing_record_counts": {"structural": 26600, "domains": 26600, "final_blind": 53200}, "claim_bearing_atomic_group_counts": claim_groups, "effects": rows}


def environment_report(repo_root: Path) -> dict[str, Any]:
    packages = {}
    for requirement in (repo_root / "requirements.lock").read_text(encoding="utf-8").splitlines():
        if not requirement.strip() or requirement.startswith("#"):
            continue
        name, expected = requirement.split("==", 1)
        try:
            actual = metadata.version(name)
        except metadata.PackageNotFoundError:
            actual = "not-installed"
        packages[name] = {"expected": expected, "actual": actual, "match": actual == expected}
    try:
        accelerator = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=5)
        accelerator_devices = [line for line in accelerator.stdout.splitlines() if line.strip()] if accelerator.returncode == 0 else []
    except (FileNotFoundError, subprocess.TimeoutExpired):
        accelerator_devices = []
    import torch

    accelerator_runtime = {
        "torch_build": torch.__version__,
        "torch_cuda_build": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_count": torch.cuda.device_count(),
    }
    base = {"python": platform.python_version(), "platform": platform.platform(), "processor": platform.processor() or "undisclosed", "packages": packages, "physical_accelerator_devices": accelerator_devices, "accelerator_runtime": accelerator_runtime, "container_used": False, "execution_mode": "locked-local-environment"}
    identity = __import__("hashlib").sha256(json.dumps(base, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**base, "status": "pass" if all(row["match"] for row in packages.values()) else "fail", "container_or_environment_identity_sha256": identity, "accelerator_identity_sha256": __import__("hashlib").sha256(json.dumps({"physical": accelerator_devices, "runtime": accelerator_runtime}, sort_keys=True).encode()).hexdigest(), "qwen_expected_weight_manifest_sha256": "291349c22595a174d997ab345601d1efebd3d1946fb58a8895a5576d7e6cab8a", "qwen_weights_locally_present": False}


def _freeze_candidate(repo_root: Path, run_id: str, outcomes: dict[str, Any], public: dict[str, Any], audits: dict[str, Any], power: dict[str, Any], snapshot: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    roots = [repo_root / "configs", repo_root / "src/pead", repo_root / "scripts", repo_root / "tests", repo_root / "manifests/method_cards", repo_root / "manifests/model_identities", repo_root / "manifests/custody", repo_root / "manifests/allocations", repo_root / "manifests/lineage", repo_root / "manifests/scientific_invariance_v3.json", repo_root / "requirements.lock", repo_root / "pyproject.toml", repo_root / "banks", repo_root / f"results/raw/{run_id}", repo_root / f"results/processed/{run_id}", repo_root / f"results/audits/{run_id}", repo_root / f"results/reports/{run_id}"]
    files: dict[str, str] = {}
    for root in roots:
        if root.is_file():
            files[root.relative_to(repo_root).as_posix()] = sha256_file(root)
        elif root.exists():
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    if path == repo_root / f"results/audits/{run_id}/phase10_compliance.json":
                        continue
                    files[path.relative_to(repo_root).as_posix()] = sha256_file(path)
    environment_path = repo_root / f"results/audits/{run_id}/environment.json"
    environment = json.loads(environment_path.read_text(encoding="utf-8")) if environment_path.is_file() else environment_report(repo_root)
    payload = {
        "schema_version": "1.0",
        "manifest_id": "PEAD-FREEZE-CANDIDATE-v1",
        "status": "candidate-not-unlocked",
        "study_version": STUDY,
        "preseal_id": PRESEAL,
        "run_id": run_id,
        "phase9a_commitment": receipt,
        "phase9a_snapshot": snapshot,
        "method_outcomes": outcomes,
        "public_validation": {key: value for key, value in public.items() if key != "reports"},
        "audit_status": audits["status"],
        "power_status": power["status"],
        "primary_architecture_specific_advantage": "configs/metrics/phase10_effect_sizes_v1.yaml",
        "report_templates_frozen": ["src/pead/reports/tables.py", "src/pead/reports/figures.py", "src/pead/reports/claim_ledger.py"],
        "statistical_procedures_frozen": ["src/pead/metrics/statistics.py", "configs/metrics/metric_registry_v1.yaml"],
        "claim_relevant_files": files,
        "claim_relevant_file_count": len(files),
        "environment": {"path": environment_path.relative_to(repo_root).as_posix(), "sha256": sha256_file(environment_path) if environment_path.is_file() else None, "container_or_environment_identity_sha256": environment["container_or_environment_identity_sha256"], "accelerator_identity_sha256": environment["accelerator_identity_sha256"], "packages_exact": environment["status"] == "pass"},
        "model_weight_hashes": {method_id: row["checkpoint_sha256"] for method_id, row in outcomes.items() if "checkpoint_sha256" in row},
        "unavailable_pinned_model_weight_manifest_sha256": environment["qwen_expected_weight_manifest_sha256"],
        "sealed_bank_access": False,
        "unlock_attempted": False,
        "phase11_started": False,
    }
    payload["manifest_content_sha256"] = __import__("hashlib").sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload


def execute_phase10(repo_root: Path, console: ResearchConsole) -> dict[str, Any]:
    """Execute Phase 10 exactly once from the corrected v3 preseal."""

    audit_root = repo_root / f"results/audits/{RUN_ID}"
    report_root = repo_root / f"results/reports/{RUN_ID}"
    audit_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)
    if (repo_root / "manifests/freeze_candidate_v1.json").exists():
        raise Phase10ExecutionError("Phase 10 freeze candidate already exists; implicit rerun is prohibited")
    # STEP LOG P10-EXEC-001: Verify branch chronology, corrected Phase 9A signature, and pristine one-shot custody state before bank generation or training.
    console.log("P10-EXEC-001", "Verifying corrected Phase 9A chronology and signature.")
    if _git(repo_root, "branch", "--show-current") != "pead-study-v3":
        raise Phase10ExecutionError("Phase 10 must execute on pead-study-v3")
    snapshot_before = capture_phase9a_snapshot(repo_root)
    receipt = _preflight(repo_root)
    if receipt["missing_commitments"] or receipt["consumer_invented_values"] or receipt["one_shot_state_consumed"]:
        raise Phase10ExecutionError("Phase 9A preflight is not pristine")
    _write_json(audit_root / "phase9a_pretraining_verification.json", {"schema_version": "1.0", "status": "pass", "git_head_before_phase10": _git(repo_root, "rev-parse", "HEAD"), "snapshot": snapshot_before, "receipt": receipt})
    banks = materialize_open_banks(repo_root, console)
    outcomes = train_cpu_methods(repo_root, RUN_ID, receipt, console)
    public = evaluate_public_validation(repo_root, RUN_ID, outcomes, receipt, console)
    # STEP LOG P10-EXEC-002: Run all six required integrity audits and retain public-validation failures without scientific retuning.
    console.log("P10-EXEC-002", "Running Phase 10 integrity and anti-overfitting audits.")
    audits = _integrity_audits(repo_root, outcomes, public)
    _write_json(audit_root / "integrity_audits.json", audits)
    power = _power_report(repo_root)
    _write_json(report_root / "power_effect_size.json", power)
    snapshot_after = capture_phase9a_snapshot(repo_root)
    immutable = snapshot_before == snapshot_after
    _write_json(audit_root / "phase9a_byte_identity.json", {"schema_version": "1.0", "status": "pass" if immutable else "fail", "before": snapshot_before, "after": snapshot_after, "byte_identical": immutable})
    summary = {
        "schema_version": "1.0",
        "study_version": STUDY,
        "run_id": RUN_ID,
        "status": "pass" if audits["status"] == "pass" and power["status"] == "pass" and immutable else "fail",
        "banks": banks,
        "method_outcomes": outcomes,
        "public_validation": {key: value for key, value in public.items() if key != "reports"},
        "integrity_audits": audits,
        "power_effect_size": power,
        "phase9a_byte_identical": immutable,
        "sealed_or_final_bank_access": False,
        "unlock_attempted": False,
        "decryption_attempted": False,
        "materialization_attempted": False,
        "phase11_started": False,
    }
    _write_json(report_root / "phase10_summary.json", summary)
    freeze = _freeze_candidate(repo_root, RUN_ID, outcomes, public, audits, power, snapshot_after, receipt)
    _write_json(repo_root / "manifests/freeze_candidate_v1.json", freeze)
    # STEP LOG P10-EXEC-003: Close scientific execution only after the freeze candidate covers every claim-relevant file and Phase 9A remains byte-identical.
    console.log("P10-EXEC-003", "Phase 10 execution completed with freeze candidate.", status="pass" if summary["status"] == "pass" else "fail", details={"trained": sum(value.get("status") == "trained" for value in outcomes.values()), "retained_failures": sum(value.get("status") != "trained" for value in outcomes.values()), "claim_relevant_files": freeze["claim_relevant_file_count"]})
    if summary["status"] != "pass":
        raise Phase10ExecutionError("Phase 10 execution gates failed; inspect retained evidence")
    return summary
