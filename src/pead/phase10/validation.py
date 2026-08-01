"""Freeze operating points and run inspection-only public validation."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import yaml

from pead.config.console import ResearchConsole
from pead.phase10.banks import load_role
from pead.phase10.training import RUN_ID, _inventory, _probability_metrics


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=1, keepdims=True); values = np.exp(shifted)
    return values / values.sum(axis=1, keepdims=True)


def _fixed_probabilities(method_id: str, features: np.ndarray) -> np.ndarray:
    x = np.nan_to_num(features, nan=0.0)
    if method_id == "O01-ORACLE-RULE":
        oracle_labels = x[:, 23].astype(np.uint8)
        probabilities = np.zeros((len(features), 3)); probabilities[np.arange(len(features)), oracle_labels] = 1.0; return probabilities
    if method_id.startswith("P0") or method_id == "MAVS-A00":
        signal = x[:, 0] + 0.2 * x[:, 1]; return _softmax(np.column_stack((signal, -signal, -np.abs(signal))))
    signal = x[:, 8] + 0.45 * x[:, 9] - 0.35 * x[:, 10]
    if method_id in {"MAVS-A15", "MAVS-A14", "G08-POLICY", "G09-VALIDATOR"}: signal += 0.15 * x[:, 11]
    if method_id.startswith("MAVS-A"):
        index = int(method_id[-2:]); signal += (index - 7.5) * 0.005 * x[:, 12]
    return _softmax(np.column_stack((signal, -signal, -np.abs(signal) + 0.15)))


def _calibrate(probabilities: np.ndarray, method: dict[str, Any], root: Path) -> np.ndarray:
    calibration = method.get("calibration")
    if not calibration: return probabilities
    if calibration["method"] == "temperature":
        temperature = float(calibration["parameters"][0]); return _softmax(np.log(np.clip(probabilities, 1e-12, 1.0)) / temperature)
    calibrators = joblib.load(root / calibration["path"])
    values = []
    for index, calibrator in enumerate(calibrators):
        if calibration["method"] == "isotonic": values.append(calibrator.predict(probabilities[:, index]))
        else: values.append(calibrator.predict_proba(probabilities[:, index, None])[:, 1])
    result = np.column_stack(values); return result / np.maximum(result.sum(axis=1, keepdims=True), 1e-12)


def _policy_candidates(probabilities: np.ndarray, labels: np.ndarray, complexity: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = []
    for accept in (0.40, 0.50, 0.60, 0.70, 0.80, 0.90):
        for reject in (0.40, 0.50, 0.60, 0.70, 0.80, 0.90):
            decisions = np.full(len(labels), 2, dtype=np.uint8)
            decisions[(probabilities[:, 1] >= reject) & (probabilities[:, 1] >= probabilities[:, 0])] = 1
            decisions[(probabilities[:, 0] >= accept) & (probabilities[:, 0] > probabilities[:, 1])] = 0
            unsafe = float(np.mean((decisions == 0) & (labels == 1)))
            false_reject = float(np.mean((decisions == 1) & (labels == 0)))
            escalation = float(np.mean(decisions == 2))
            unnecessary = float(np.mean((decisions == 2) & (labels != 2)))
            feasible = unsafe <= 0.05
            row = {"operating_point_id": f"a{accept:.2f}-r{reject:.2f}", "accept_threshold": accept, "reject_threshold": reject, "partition": "calibration_policy", "unsafe_acceptance_rate": unsafe, "false_rejection_rate": false_reject, "escalation_rate": escalation, "unnecessary_escalation_rate": unnecessary, "resource_cost": 0.0, "model_complexity": complexity, "unsafe_constraint": 0.05, "feasible": feasible}
            row["selection_key"] = [int(feasible), -false_reject, -unnecessary, -row["resource_cost"], -complexity, -accept, -reject]
            rows.append(row)
    feasible_rows = [row for row in rows if row["feasible"]]
    selected = max(feasible_rows or rows, key=lambda row: tuple(row["selection_key"]))
    return rows, selected


def _apply_policy(probabilities: np.ndarray, selected: dict[str, Any]) -> np.ndarray:
    decisions = np.full(len(probabilities), 2, dtype=np.uint8)
    reject, accept = selected["reject_threshold"], selected["accept_threshold"]
    decisions[(probabilities[:, 1] >= reject) & (probabilities[:, 1] >= probabilities[:, 0])] = 1
    decisions[(probabilities[:, 0] >= accept) & (probabilities[:, 0] > probabilities[:, 1])] = 0
    return decisions


def _conformal_probabilities(base: np.ndarray, labels: np.ndarray, *, alpha: float, initial_quantile: float, window: int | None) -> np.ndarray:
    result = base.copy(); past: list[float] = []
    for index in range(len(base)):
        quantile = initial_quantile
        if window is not None and past:
            values = np.asarray(past[-window:]); rank = min(len(values), int(np.ceil((len(values) + 1) * (1.0 - alpha))))
            quantile = float(np.partition(values, rank - 1)[rank - 1])
        if 1.0 - float(np.max(base[index])) > quantile: result[index] = (0.0, 0.0, 1.0)
        past.append(1.0 - float(base[index, labels[index]]))
    return result


def _decision_metrics(decisions: np.ndarray, labels: np.ndarray) -> dict[str, float]:
    return {"accuracy": float(np.mean(decisions == labels)), "unsafe_acceptance_rate": float(np.mean((decisions == 0) & (labels == 1))), "false_rejection_rate": float(np.mean((decisions == 1) & (labels == 0))), "escalation_rate": float(np.mean(decisions == 2)), "coverage": float(np.mean(decisions != 2)), "forced_certainty_error": float(np.mean(np.where(decisions == 2, 0, decisions) != labels)), "opportunity_count": int(len(labels))}


def execute_validation(root: Path, console: ResearchConsole) -> dict[str, Any]:
    trace_path = root / f"results/raw/{RUN_ID}/training_trace.json"; trace = json.loads(trace_path.read_text(encoding="utf-8")); methods = trace["methods"]
    analysis = yaml.safe_load((root / "configs/phase10/preblind_analysis_v1.yaml").read_text(encoding="utf-8"))
    data = {profile: {role: load_role(root, role, profile) for role in ("calibration_policy", "public_validation")} for profile in ("P-only", "Raw-G", "Oracle-G")}
    # STEP LOG P10-VALIDATE-001: Select terminal policies once on calibration_policy with the frozen lexicographic constraint.
    console.log("P10-VALIDATE-001", "Selecting terminal operating points on calibration_policy.")
    results: dict[str, Any] = {}; inventory = _inventory(root)
    for record in inventory:
        method_id, profile = record["method_id"], record["access_profile"]
        method = methods[method_id]
        source = method
        if method_id == "P08-TABULAR":
            successful = [item for item in method["variants"].values() if item["status"] == "trained"]
            source = max(successful, key=lambda item: item["selected"]["mean_utility"]) if successful else method
        if method_id == "G11-SCALAR": source = method["fixed_variant"]
        failed = method.get("status") == "failed_retained" or (method_id == "P08-TABULAR" and not source.get("checkpoint"))
        if failed:
            results[method_id] = {"method_id": method_id, "status": "failed_retained", "reason": method.get("reason", "all required variants failed"), "public_validation_rows": 0}; continue
        policy_x, policy_y, _ = data[profile]["calibration_policy"]
        public_x, public_y, public_groups = data[profile]["public_validation"]
        conformal_choice = None
        if method_id in {"P05-CONF-STATIC", "P06-CONF-ADAPT"}:
            base_variant = next(item for item in methods["P08-TABULAR"]["variants"].values() if item.get("method_id") == method["base_method"])
            model = joblib.load(root / method["base_checkpoint_path"])
            base_policy = _calibrate(model.predict_proba(policy_x), base_variant, root); base_public = _calibrate(model.predict_proba(public_x), base_variant, root)
            settings = ([{"alpha": float(alpha), "window": None} for alpha in method["alpha_quantiles"]] if method_id == "P05-CONF-STATIC" else method["settings"])
            candidates = []
            for setting in settings:
                alpha = float(setting["alpha"]); quantile = float(methods["P05-CONF-STATIC"]["alpha_quantiles"][str(alpha)])
                candidate_prob = _conformal_probabilities(base_policy, policy_y, alpha=alpha, initial_quantile=quantile, window=setting["window"])
                sweep_rows, selected_row = _policy_candidates(candidate_prob, policy_y, 0.0)
                candidates.append((tuple(selected_row["selection_key"]), setting, selected_row, sweep_rows))
            _, conformal_choice, selected, sweep = max(candidates, key=lambda item: item[0])
            public_prob = _conformal_probabilities(base_public, public_y, alpha=float(conformal_choice["alpha"]), initial_quantile=float(methods["P05-CONF-STATIC"]["alpha_quantiles"][str(float(conformal_choice["alpha"]))]), window=conformal_choice["window"])
        elif source.get("checkpoint"):
            model = joblib.load(root / source["checkpoint"]); policy_prob = _calibrate(model.predict_proba(policy_x), source, root); public_prob = _calibrate(model.predict_proba(public_x), source, root)
        else:
            policy_prob = _fixed_probabilities(method_id, policy_x); public_prob = _fixed_probabilities(method_id, public_x)
        if conformal_choice is None: sweep, selected = _policy_candidates(policy_prob, policy_y, float(len(source.get("history", []))))
        decisions = _apply_policy(public_prob, selected); metrics = _decision_metrics(decisions, public_y)
        prediction_path = root / f"results/raw/{RUN_ID}/public_predictions/{method_id}.npz"; prediction_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(prediction_path, decision=decisions, label=public_y, atomic_group_id=public_groups)
        results[method_id] = {"method_id": method_id, "status": method.get("status", "evaluated"), "operating_point": selected, "conformal_setting": conformal_choice, "threshold_sweep": sweep, "policy_rows": int(len(policy_y)), "policy_passes": 1, "public_validation_rows": int(len(public_y)), "public_validation_selection_use": False, "metrics": metrics, "prediction_path": prediction_path.relative_to(root).as_posix(), "prediction_sha256": hashlib.sha256(prediction_path.read_bytes()).hexdigest()}
    # STEP LOG P10-VALIDATE-002: Execute every ready fixed or trained method once on inspection-only public validation.
    console.log("P10-VALIDATE-002", "Public validation completed without selection use.", details={"methods": len(results), "failed_retained": sum(item["status"] == "failed_retained" for item in results.values())})
    n_groups = len(np.unique(data["Raw-G"]["public_validation"][2])); z = 1.959963984540054
    worst_probability = 0.5; margin = z * math.sqrt(worst_probability * (1.0 - worst_probability) / n_groups)
    power = {"confidence_level": 0.95, "public_atomic_groups": n_groups, "worst_case_proportion_margin": margin, "registered_minimum_effect_sizes": analysis["minimum_effect_sizes"], "primary_architecture_specific_advantage": analysis["primary_architecture_specific_advantage"], "minimum_effect_above_margin": {name: float(value) >= margin for name, value in analysis["minimum_effect_sizes"].items()}, "interpretation": "Public validation is an inspection-only precision rehearsal; final power is determined by precommitted claim-bank denominators and clustered analysis."}
    report = {"schema_version": "1.0", "run_id": RUN_ID, "status": "pass", "phase9a_commitment_sha256": trace["phase9a_commitment_sha256"], "methods": results, "power_effect_size": power, "public_validation_selected_anything": False, "scientific_failures_retained": True}
    processed = root / f"results/processed/{RUN_ID}/public_validation.json"; processed.parent.mkdir(parents=True, exist_ok=True); processed.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    power_path = root / f"results/reports/{RUN_ID}/power_effect_size.json"; power_path.parent.mkdir(parents=True, exist_ok=True); power_path.write_text(json.dumps(power, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P10-VALIDATE-003: Freeze public precision, minimum effects, statistical procedures, and the primary architecture comparison.
    console.log("P10-VALIDATE-003", "Power and preblind analysis commitments retained.", status="pass", details={"atomic_groups": n_groups, "methods": len(results)})
    return report
