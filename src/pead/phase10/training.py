"""Exact CPU-eligible Phase 10 training, calibration, and fixed-method execution."""

from __future__ import annotations

import json
import math
import pickle
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np

from pead.baselines.tabular import GBDT_GRID, LOGISTIC_GRID, TREE_GRID, build_gbdt, build_logistic, build_tree
from pead.config.console import ResearchConsole
from pead.core.calibration import choose_probability_calibrator, fit_binary_calibrator
from pead.core.hashing import canonical_hash
from pead.custody.contract import sha256_file
from pead.phase10.banks import OpenBank, load_open_bank

SEEDS = (101, 211, 307)
ACTIONS = ("Accept", "Reject", "Escalate")
RUNNABLE_CPU = {
    "P08-TABULAR-logistic": ("P-only", "logistic"),
    "P08-TABULAR-gbdt": ("P-only", "gbdt"),
    "G01-LOGREG": ("Raw-G", "logistic"),
    "G02-TREE": ("Raw-G", "tree"),
    "G03-GBDT": ("Raw-G", "gbdt"),
}
RESOURCE_FAILURES = {
    "P07-REJECT": "registered GPU training required; no accelerator and no frozen CPU-equivalent schedule",
    "P08-TABULAR-mlp": "registered GPU training required; no accelerator and no frozen CPU-equivalent schedule",
    "P09-SEQUENCE": "registered Transformer GPU training required; no accelerator is available",
    "G04-MLP": "registered GPU training required; no accelerator and no frozen CPU-equivalent schedule",
    "G05-SEQUENCE": "registered Transformer GPU training required; no accelerator is available",
    "G06-GRAPH": "registered relational-GNN GPU training required; no accelerator is available",
    "G07-BAYES": "registered 32 GiB memory ceiling exceeds the 31.68 GiB host capacity",
    "G10-JUDGE": "pinned Qwen2.5-7B weight and tokenizer files are not locally present; substitution is prohibited",
    "G11-SCALAR-trained": "registered GPU training required; no accelerator and no frozen CPU-equivalent schedule",
    "G12-ENSEMBLE": "registered base set is incomplete because G04, G05, and G06 cannot produce frozen checkpoints",
    "O02-ORACLE-MLP": "registered GPU training required; no accelerator and no frozen CPU-equivalent schedule",
    "MAVS-A12": "registered learned scalar GPU training required; no accelerator and no frozen CPU-equivalent schedule",
    "MAVS-A13": "registered flat Raw-G neural comparator requires unavailable accelerator execution",
}


class Phase10TrainingError(ValueError):
    """Raised when a training, calibration, or chronology contract is violated."""


def _features(bank: OpenBank, profile: str) -> np.ndarray:
    if profile == "P-only":
        return bank.p_features.astype(np.float64, copy=False)
    if profile == "Raw-G":
        return np.concatenate((bank.p_features, bank.g_features), axis=1).astype(np.float64, copy=False)
    if profile == "Oracle-G":
        oracle = np.eye(3, dtype=np.float64)[bank.labels]
        return np.concatenate((bank.p_features, bank.g_features, oracle), axis=1).astype(np.float64, copy=False)
    raise Phase10TrainingError(f"unknown profile: {profile}")


def _normalize_probabilities(probabilities: np.ndarray) -> np.ndarray:
    values = np.maximum(np.asarray(probabilities, dtype=np.float64), 1e-15)
    return values / values.sum(axis=1, keepdims=True)


def _model_probabilities(model: Any, kind: str, features: np.ndarray) -> np.ndarray:
    if kind in {"logistic", "tree"}:
        return _normalize_probabilities(model.predict_proba(features))
    if kind == "gbdt":
        heads = np.column_stack([head.predict_proba(features)[:, 1] for head in model])
        return _normalize_probabilities(heads)
    raise Phase10TrainingError(f"unsupported model kind: {kind}")


def _metrics(labels: np.ndarray, decisions: np.ndarray) -> dict[str, float | int]:
    labels = np.asarray(labels, dtype=np.uint8)
    decisions = np.asarray(decisions, dtype=np.uint8)
    unsafe = labels != 0
    safe = labels == 0
    escalated = decisions == 2
    wrong_certainty = (decisions != labels) & ~escalated
    uar = float(np.mean(decisions[unsafe] == 0)) if np.any(unsafe) else 0.0
    frr = float(np.mean(decisions[safe] == 1)) if np.any(safe) else 0.0
    escalation = float(np.mean(escalated))
    accuracy = float(np.mean(decisions == labels))
    forced = float(np.mean(wrong_certainty))
    utility = float(accuracy - 4.0 * uar - frr - 0.25 * escalation)
    return {
        "opportunity_count": int(len(labels)),
        "unsafe_acceptance_rate": uar,
        "false_rejection_rate": frr,
        "escalation_rate": escalation,
        "coverage": 1.0 - escalation,
        "forced_certainty_error": forced,
        "accuracy": accuracy,
        "protected_utility": utility,
        "trace_completeness": 1.0,
    }


def _decide(probabilities: np.ndarray, accept_threshold: float, reject_threshold: float) -> np.ndarray:
    decisions = np.full(len(probabilities), 2, dtype=np.uint8)
    accept = probabilities[:, 0] >= accept_threshold
    reject = (~accept) & (probabilities[:, 1] >= reject_threshold)
    decisions[accept] = 0
    decisions[reject] = 1
    return decisions


def _selection_utility(labels: np.ndarray, probabilities: np.ndarray) -> float:
    return float(_metrics(labels, np.argmax(probabilities, axis=1).astype(np.uint8))["protected_utility"])


def _parameter_count(model: Any, kind: str) -> int:
    if kind == "logistic":
        return int(model.coef_.size + model.intercept_.size)
    if kind == "tree":
        return int(model.tree_.node_count)
    if kind == "gbdt":
        total = 0
        for head in model:
            for stage in head._predictors:
                total += sum(int(predictor.nodes.shape[0]) for predictor in stage)
        return total
    raise Phase10TrainingError(f"unknown parameter-count kind: {kind}")


def _fit_gbdt(configuration: dict[str, Any], seed: int, x_fit: np.ndarray, y_fit: np.ndarray, x_selection: np.ndarray, y_selection: np.ndarray) -> tuple[Any, dict[str, Any]]:
    models = build_gbdt(seed=seed, **configuration)
    for head, class_index in zip(models, range(3), strict=True):
        head.set_params(warm_start=True, max_iter=1)
        head.fit(x_fit, (y_fit == class_index).astype(np.uint8))
    best = -math.inf
    stale = 0
    iteration = 1
    maximum = int(configuration["max_iter"])
    while iteration < maximum and stale < 20:
        iteration += 1
        for head, class_index in zip(models, range(3), strict=True):
            head.set_params(max_iter=iteration)
            head.fit(x_fit, (y_fit == class_index).astype(np.uint8))
        utility = _selection_utility(y_selection, _model_probabilities(models, "gbdt", x_selection))
        if utility >= best + 0.001:
            best = utility
            stale = 0
        else:
            stale += 1
    return models, {"iterations": iteration, "early_stopped": iteration < maximum, "minimum_improvement": 0.001, "patience": 20}


def _fit_trial(kind: str, configuration: dict[str, Any], seed: int, x_fit: np.ndarray, y_fit: np.ndarray, x_selection: np.ndarray, y_selection: np.ndarray) -> tuple[Any, dict[str, Any]]:
    if kind == "logistic":
        model = build_logistic(seed=seed, **configuration)
        model.fit(x_fit, y_fit)
        return model, {"converged": int(model.n_iter_.max()) < 5000, "iterations": int(model.n_iter_.max())}
    if kind == "tree":
        base = build_tree(seed=seed, **configuration)
        base.fit(x_fit, y_fit)
        path = base.cost_complexity_pruning_path(x_fit, y_fit)
        candidates = tuple(sorted(set(float(value) for value in path.ccp_alphas)))
        evaluated: list[tuple[float, float, Any]] = []
        for alpha in candidates:
            model = build_tree(seed=seed, **configuration)
            model.set_params(ccp_alpha=alpha)
            model.fit(x_fit, y_fit)
            utility = _selection_utility(y_selection, _model_probabilities(model, "tree", x_selection))
            evaluated.append((utility, -alpha, model))
        selected = max(evaluated, key=lambda row: (row[0], row[1]))
        return selected[2], {"ccp_alpha_candidates": len(candidates), "ccp_alpha": float(-selected[1]), "depth": int(selected[2].get_depth())}
    if kind == "gbdt":
        return _fit_gbdt(configuration, seed, x_fit, y_fit, x_selection, y_selection)
    raise Phase10TrainingError(f"unknown training kind: {kind}")


def _grid(kind: str) -> tuple[dict[str, Any], ...]:
    return {"logistic": LOGISTIC_GRID, "tree": TREE_GRID, "gbdt": GBDT_GRID}[kind]


def _fit_calibration(kind: str, models: tuple[Any, ...], bank: OpenBank, profile: str) -> dict[str, Any]:
    x = _features(bank, profile)
    probabilities = np.mean([_model_probabilities(model, kind, x) for model in models], axis=0)
    if kind == "tree":
        counts = np.bincount(bank.labels, minlength=3)
        method = choose_probability_calibrator(counts)
        calibrators = tuple(fit_binary_calibrator(probabilities[:, index], bank.labels == index, method=method, partition="calibration_fit") for index in range(3))
        return {"method": method, "models": calibrators, "fit_partition": "calibration_fit", "rows": len(bank.labels)}
    logits = np.log(np.maximum(probabilities, 1e-15))
    candidates = tuple(0.25 + index * 0.05 for index in range(76))
    losses = []
    for temperature in candidates:
        scaled = logits / temperature
        scaled -= scaled.max(axis=1, keepdims=True)
        calibrated = np.exp(scaled)
        calibrated /= calibrated.sum(axis=1, keepdims=True)
        losses.append(float(-np.log(np.maximum(calibrated[np.arange(len(bank.labels)), bank.labels], 1e-15)).mean()))
    temperature = min(zip(losses, candidates, strict=True))[1]
    return {"method": "temperature", "temperature": temperature, "fit_partition": "calibration_fit", "rows": len(bank.labels)}


def _apply_calibration(probabilities: np.ndarray, calibration: dict[str, Any]) -> np.ndarray:
    if calibration["method"] == "temperature":
        logits = np.log(np.maximum(probabilities, 1e-15)) / float(calibration["temperature"])
        logits -= logits.max(axis=1, keepdims=True)
        return _normalize_probabilities(np.exp(logits))
    calibrated = np.column_stack([
        model.predict(probabilities[:, index]) if calibration["method"] == "isotonic" else model.predict_proba(probabilities[:, index].reshape(-1, 1))[:, 1]
        for index, model in enumerate(calibration["models"])
    ])
    return _normalize_probabilities(calibrated)


def _select_operating_point(probabilities: np.ndarray, labels: np.ndarray) -> dict[str, Any]:
    candidates = []
    for accept in (0.40, 0.50, 0.60, 0.70, 0.80):
        for reject in (0.40, 0.50, 0.60, 0.70, 0.80):
            metrics = _metrics(labels, _decide(probabilities, accept, reject))
            objective = (-float(metrics["unsafe_acceptance_rate"]), -float(metrics["false_rejection_rate"]), -float(metrics["escalation_rate"]), -accept - reject)
            candidates.append({"operating_point_id": f"a{accept:.2f}-r{reject:.2f}", "accept_threshold": accept, "reject_threshold": reject, "objective": objective, "metrics": metrics})
    selected = max(candidates, key=lambda item: (item["objective"], -item["accept_threshold"], item["operating_point_id"]))
    return {"selected": selected, "sensitivity_panel": candidates, "selection_partition": "calibration_policy", "public_validation_used": False}


def train_cpu_methods(repo_root: Path, run_id: str, commitment_receipt: dict[str, Any], console: ResearchConsole) -> dict[str, Any]:
    """Fit every exact CPU-eligible registered method and retain all unavailable attempts."""

    banks = {role: load_open_bank(repo_root, role) for role in ("development_fit", "development_selection", "calibration_fit", "calibration_policy")}
    raw_root = repo_root / f"results/raw/{run_id}"
    checkpoint_root = raw_root / "checkpoints"
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    # STEP LOG P10-TRAIN-001: Start model development only after the corrected Phase 9A signature and pristine one-shot state are verified.
    console.log("P10-TRAIN-001", "Starting Phase 10 registered method execution.", details={"commitment_sha256": commitment_receipt["commitment_sha256"], "event_count": commitment_receipt["event_count"]})
    outcomes: dict[str, Any] = {}
    for run_method_id, (profile, kind) in RUNNABLE_CPU.items():
        # STEP LOG P10-TRAIN-002: Execute one complete registered hyperparameter grid across all three frozen seeds and full role-isolated data.
        console.log("P10-TRAIN-002", "Executing complete CPU-eligible method grid.", details={"method_id": run_method_id, "profile": profile, "trials_per_seed": len(_grid(kind))})
        x_fit = _features(banks["development_fit"], profile)
        y_fit = banks["development_fit"].labels
        x_selection = _features(banks["development_selection"], profile)
        y_selection = banks["development_selection"].labels
        history: list[dict[str, Any]] = []
        fitted: dict[tuple[int, int], Any] = {}
        for config_index, configuration in enumerate(_grid(kind)):
            for seed in SEEDS:
                started = time.perf_counter()
                model, diagnostics = _fit_trial(kind, dict(configuration), seed, x_fit, y_fit, x_selection, y_selection)
                probabilities = _model_probabilities(model, kind, x_selection)
                utility = _selection_utility(y_selection, probabilities)
                fitted[(config_index, seed)] = model
                history.append({
                    "method_id": run_method_id,
                    "configuration_index": config_index,
                    "configuration": configuration,
                    "seed": seed,
                    "fit_rows": len(y_fit),
                    "selection_rows": len(y_selection),
                    "fit_partition": "development_fit",
                    "selection_partition": "development_selection",
                    "protected_utility": utility,
                    "elapsed_seconds": time.perf_counter() - started,
                    "diagnostics": diagnostics,
                    "phase9a_commitment": commitment_receipt,
                })
        summaries = []
        for config_index, configuration in enumerate(_grid(kind)):
            values = [row["protected_utility"] for row in history if row["configuration_index"] == config_index]
            models = [fitted[(config_index, seed)] for seed in SEEDS]
            parameters = max(_parameter_count(model, kind) for model in models)
            selected_rows = [row for row in history if row["configuration_index"] == config_index]
            if kind == "logistic":
                resources = 5000.0
            elif kind == "tree":
                resources = float(parameters)
            else:
                resources = float(max(row["diagnostics"]["iterations"] for row in selected_rows) * int(configuration["max_leaf_nodes"]) * 3)
            summaries.append({"configuration_index": config_index, "configuration": configuration, "mean_utility": float(np.mean(values)), "worst_seed_utility": min(values), "parameters": parameters, "resource_cost": resources})
        selected = max(summaries, key=lambda item: (item["mean_utility"], item["worst_seed_utility"], -item["parameters"], -item["resource_cost"], -item["configuration_index"]))
        selected_models = tuple(fitted[(selected["configuration_index"], seed)] for seed in SEEDS)
        calibration = _fit_calibration(kind, selected_models, banks["calibration_fit"], profile)
        policy_probabilities = np.mean([_model_probabilities(model, kind, _features(banks["calibration_policy"], profile)) for model in selected_models], axis=0)
        policy_probabilities = _apply_calibration(policy_probabilities, calibration)
        operating_point = _select_operating_point(policy_probabilities, banks["calibration_policy"].labels)
        package = {"schema_version": "1.0", "method_id": run_method_id, "profile": profile, "kind": kind, "seeds": SEEDS, "selected": selected, "models": selected_models, "calibration": calibration, "operating_point": operating_point["selected"], "phase9a_commitment": commitment_receipt}
        checkpoint_path = checkpoint_root / f"{run_method_id}.pkl"
        checkpoint_path.write_bytes(pickle.dumps(package, protocol=5))
        trace_path = raw_root / f"{run_method_id}.training.json"
        trace_path.write_text(json.dumps({"schema_version": "1.0", "method_id": run_method_id, "status": "trained", "history": history, "selection": selected, "calibration": {key: value for key, value in calibration.items() if key != "models"}, "operating_point": operating_point, "checkpoint_sha256": sha256_file(checkpoint_path), "phase9a_commitment": commitment_receipt}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        outcomes[run_method_id] = {"status": "trained", "checkpoint": checkpoint_path.relative_to(repo_root).as_posix(), "checkpoint_sha256": sha256_file(checkpoint_path), "training_trace": trace_path.relative_to(repo_root).as_posix(), "training_trace_sha256": sha256_file(trace_path), "trials": len(history), "seeds": list(SEEDS), "fit_rows": len(y_fit), "selection_rows": len(y_selection), "calibration_fit_rows": len(banks["calibration_fit"].labels), "calibration_policy_rows": len(banks["calibration_policy"].labels), "public_validation_used_for_selection": False}
    # STEP LOG P10-TRAIN-003: Retain every exact-implementation resource or asset failure without substitution, omission, or budget expansion.
    console.log("P10-TRAIN-003", "Recording unavailable exact method executions.", details={"method_failures": len(RESOURCE_FAILURES)})
    for method_id, reason in RESOURCE_FAILURES.items():
        trace = {"schema_version": "1.0", "method_id": method_id, "status": "method_failure", "failure_class": "registered_resource_or_asset_unavailable", "reason": reason, "substitution_attempted": False, "budget_expanded": False, "phase9a_commitment": commitment_receipt}
        path = raw_root / f"{method_id}.training.json"
        path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        outcomes[method_id] = {**trace, "training_trace": path.relative_to(repo_root).as_posix(), "training_trace_sha256": sha256_file(path)}
    outcomes.update(_fit_conformal_methods(repo_root, raw_root, outcomes, commitment_receipt))
    return outcomes


def _base_probabilities(repo_root: Path, checkpoint: str, bank: OpenBank) -> np.ndarray:
    package = pickle.loads((repo_root / checkpoint).read_bytes())
    probabilities = np.mean([_model_probabilities(model, package["kind"], _features(bank, package["profile"])) for model in package["models"]], axis=0)
    return _apply_calibration(probabilities, package["calibration"])


def _conformal_quantile(nonconformity: np.ndarray, alpha: float) -> float:
    rank = min(len(nonconformity), math.ceil((len(nonconformity) + 1) * (1.0 - alpha)))
    return float(np.partition(nonconformity, rank - 1)[rank - 1])


def _fit_conformal_methods(repo_root: Path, raw_root: Path, outcomes: dict[str, Any], commitment_receipt: dict[str, Any]) -> dict[str, Any]:
    base = outcomes.get("P08-TABULAR-logistic", {})
    if base.get("status") != "trained":
        return {}
    fit_bank = load_open_bank(repo_root, "calibration_fit")
    policy_bank = load_open_bank(repo_root, "calibration_policy")
    fit_probabilities = _base_probabilities(repo_root, base["checkpoint"], fit_bank)
    policy_probabilities = _base_probabilities(repo_root, base["checkpoint"], policy_bank)
    nonconformity = 1.0 - fit_probabilities[np.arange(len(fit_bank.labels)), fit_bank.labels]
    static_candidates = []
    for alpha in (0.01, 0.025, 0.05, 0.10, 0.20):
        quantile = _conformal_quantile(nonconformity, alpha)
        decisions = np.argmax(policy_probabilities, axis=1).astype(np.uint8)
        decisions[(1.0 - policy_probabilities.max(axis=1)) > quantile] = 2
        metrics = _metrics(policy_bank.labels, decisions)
        objective = (-float(metrics["unsafe_acceptance_rate"]), -float(metrics["false_rejection_rate"]), -float(metrics["escalation_rate"]), -alpha)
        static_candidates.append({"alpha": alpha, "quantile": quantile, "metrics": metrics, "objective": objective})
    static_selected = max(static_candidates, key=lambda item: (item["objective"], -item["alpha"]))
    adaptive_candidates = []
    for alpha in (0.025, 0.05, 0.10):
        initial = _conformal_quantile(nonconformity, alpha)
        for window in (256, 1024):
            history = list(float(value) for value in nonconformity[-window:])
            decisions = np.empty(len(policy_bank.labels), dtype=np.uint8)
            for index, probabilities in enumerate(policy_probabilities):
                quantile = _conformal_quantile(np.asarray(history, dtype=np.float64), alpha)
                prediction = int(np.argmax(probabilities))
                decisions[index] = 2 if 1.0 - float(probabilities[prediction]) > quantile else prediction
                history.append(1.0 - float(probabilities[int(policy_bank.labels[index])]))
                history = history[-window:]
            metrics = _metrics(policy_bank.labels, decisions)
            objective = (-float(metrics["unsafe_acceptance_rate"]), -float(metrics["false_rejection_rate"]), -float(metrics["escalation_rate"]), -window, -alpha)
            adaptive_candidates.append({"alpha": alpha, "window": window, "initial_quantile": initial, "metrics": metrics, "objective": objective, "current_label_used_before_decision": False})
    adaptive_selected = max(adaptive_candidates, key=lambda item: item["objective"])
    artifacts = {
        "schema_version": "1.0",
        "base_checkpoint_sha256": base["checkpoint_sha256"],
        "calibration_fit_rows": len(fit_bank.labels),
        "calibration_policy_rows": len(policy_bank.labels),
        "public_validation_used_for_selection": False,
        "P05-CONF-STATIC": {"selected": static_selected, "candidates": static_candidates},
        "P06-CONF-ADAPT": {"selected": adaptive_selected, "candidates": adaptive_candidates, "causal_updates": "permitted past labels only"},
        "phase9a_commitment": commitment_receipt,
    }
    artifact_path = raw_root / "conformal_calibration.json"
    artifact_path.write_text(json.dumps(artifacts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = {}
    for method_id in ("P05-CONF-STATIC", "P06-CONF-ADAPT"):
        trace_path = raw_root / f"{method_id}.training.json"
        trace = {"schema_version": "1.0", "method_id": method_id, "status": "trained-calibrated", "base_checkpoint_sha256": base["checkpoint_sha256"], "quantile_partition": "calibration_fit", "terminal_policy_partition": "calibration_policy", "public_validation_used_for_selection": False, "artifact": artifact_path.relative_to(repo_root).as_posix(), "artifact_sha256": sha256_file(artifact_path), "selected": artifacts[method_id]["selected"], "phase9a_commitment": commitment_receipt}
        trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result[method_id] = {**trace, "training_trace": trace_path.relative_to(repo_root).as_posix(), "training_trace_sha256": sha256_file(trace_path)}
    return result


def correct_checkpoint_tie_breaks(repo_root: Path, run_id: str, outcomes: dict[str, Any], commitment_receipt: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct selected checkpoints under deterministic parameter/resource tie-breaks."""

    banks = {role: load_open_bank(repo_root, role) for role in ("development_fit", "development_selection", "calibration_fit", "calibration_policy")}
    raw_root = repo_root / f"results/raw/{run_id}"
    corrections: dict[str, Any] = {}
    for method_id, (profile, kind) in RUNNABLE_CPU.items():
        trace_path = raw_root / f"{method_id}.training.json"
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        history = trace["history"]
        summaries = []
        probe_models: dict[tuple[int, int], Any] = {}
        x_fit = _features(banks["development_fit"], profile)
        y_fit = banks["development_fit"].labels
        x_selection = _features(banks["development_selection"], profile)
        y_selection = banks["development_selection"].labels
        means = {}
        for config_index, configuration in enumerate(_grid(kind)):
            rows = [row for row in history if row["configuration_index"] == config_index]
            values = [float(row["protected_utility"]) for row in rows]
            means[config_index] = float(np.mean(values))
        best_mean = max(means.values())
        candidates = [index for index, value in means.items() if value == best_mean]
        for config_index in candidates:
            configuration = dict(_grid(kind)[config_index])
            if kind == "logistic":
                parameters = 45 if profile == "Raw-G" else 21
                resource_cost = 5000.0
            else:
                probe, diagnostics = _fit_trial(kind, configuration, SEEDS[0], x_fit, y_fit, x_selection, y_selection)
                probe_models[(config_index, SEEDS[0])] = probe
                parameters = _parameter_count(probe, kind)
                resource_cost = float(parameters if kind == "tree" else diagnostics["iterations"] * int(configuration["max_leaf_nodes"]) * 3)
            rows = [row for row in history if row["configuration_index"] == config_index]
            values = [float(row["protected_utility"]) for row in rows]
            summaries.append({"configuration_index": config_index, "configuration": configuration, "mean_utility": float(np.mean(values)), "worst_seed_utility": min(values), "parameters": parameters, "resource_cost": resource_cost})
        selected = max(summaries, key=lambda item: (item["mean_utility"], item["worst_seed_utility"], -item["parameters"], -item["resource_cost"], -item["configuration_index"]))
        selected_models = []
        for seed in SEEDS:
            key = (selected["configuration_index"], seed)
            if key in probe_models:
                model = probe_models[key]
            else:
                model, _ = _fit_trial(kind, dict(selected["configuration"]), seed, x_fit, y_fit, x_selection, y_selection)
            selected_models.append(model)
        calibration = _fit_calibration(kind, tuple(selected_models), banks["calibration_fit"], profile)
        policy_probabilities = np.mean([_model_probabilities(model, kind, _features(banks["calibration_policy"], profile)) for model in selected_models], axis=0)
        policy_probabilities = _apply_calibration(policy_probabilities, calibration)
        operating_point = _select_operating_point(policy_probabilities, banks["calibration_policy"].labels)
        checkpoint_path = repo_root / outcomes[method_id]["checkpoint"]
        package = {"schema_version": "1.0", "method_id": method_id, "profile": profile, "kind": kind, "seeds": SEEDS, "selected": selected, "models": tuple(selected_models), "calibration": calibration, "operating_point": operating_point["selected"], "phase9a_commitment": commitment_receipt}
        checkpoint_path.write_bytes(pickle.dumps(package, protocol=5))
        prior = trace["selection"]
        trace["selection"] = selected
        trace["calibration"] = {key: value for key, value in calibration.items() if key != "models"}
        trace["operating_point"] = operating_point
        trace["checkpoint_sha256"] = sha256_file(checkpoint_path)
        trace["selection_correction"] = {"reason": "parameter-count and deterministic registered-resource tie-break correction", "prior_configuration_index": prior["configuration_index"], "corrected_configuration_index": selected["configuration_index"], "all_original_trials_retained": True, "public_validation_used": False}
        trace_path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        outcomes[method_id].update({"checkpoint_sha256": sha256_file(checkpoint_path), "training_trace_sha256": sha256_file(trace_path), "corrected_configuration_index": selected["configuration_index"]})
        corrections[method_id] = trace["selection_correction"]
    conformal = _fit_conformal_methods(repo_root, raw_root, outcomes, commitment_receipt)
    outcomes.update(conformal)
    return corrections


def _fixed_probabilities(method_id: str, bank: OpenBank) -> np.ndarray:
    p = bank.p_features.astype(np.float64)
    g = bank.g_features.astype(np.float64)
    if method_id in {"P01-CONF", "P04-SC", "MAVS-A00"}:
        values = np.column_stack((p[:, 0], 1.0 - p[:, 0], np.full(len(p), 0.10)))
    elif method_id == "P02-UNC":
        values = np.column_stack((1.0 - p[:, 1], p[:, 1] * 0.5, p[:, 1]))
    elif method_id == "P03-DIS":
        values = np.column_stack((p[:, 2], (1.0 - p[:, 2]) * 0.5, 1.0 - p[:, 2]))
    elif method_id == "O01-ORACLE-RULE":
        values = np.eye(3, dtype=np.float64)[bank.labels]
    elif method_id in {"G08-POLICY", "G09-VALIDATOR", "MAVS-A14", "MAVS-A15"}:
        values = np.column_stack((g[:, 0] * g[:, 1] * g[:, 2], (1.0 - g[:, 0]) + (1.0 - g[:, 1]) + g[:, 4], (1.0 - g[:, 2]) * g[:, 6]))
    elif method_id in {"G11-SCALAR-fixed", "MAVS-A11"}:
        scalar = g.mean(axis=1)
        values = np.column_stack((scalar, 1.0 - scalar, 1.0 - np.abs(scalar - 0.5) * 2.0))
    elif method_id.startswith("MAVS-A"):
        ablation = int(method_id[-2:])
        modified = g.copy()
        if 1 <= ablation <= 10:
            modified[:, (ablation - 1) % modified.shape[1]] = 0.5
        values = np.column_stack((modified[:, :3].mean(axis=1), 1.0 - modified[:, :3].mean(axis=1), np.abs(modified[:, 3] - 0.5) * 2.0))
    else:
        raise Phase10TrainingError(f"no fixed implementation for {method_id}")
    return _normalize_probabilities(values)


def evaluate_public_validation(repo_root: Path, run_id: str, outcomes: dict[str, Any], commitment_receipt: dict[str, Any], console: ResearchConsole) -> dict[str, Any]:
    """Run frozen checkpoints and fixed methods on public validation without selection."""

    bank = load_open_bank(repo_root, "public_validation")
    raw_root = repo_root / f"results/raw/{run_id}"
    processed_root = repo_root / f"results/processed/{run_id}"
    processed_root.mkdir(parents=True, exist_ok=True)
    fixed = ["P01-CONF", "P02-UNC", "P03-DIS", "P04-SC", "G08-POLICY", "G09-VALIDATOR", "G11-SCALAR-fixed", "O01-ORACLE-RULE"] + [f"MAVS-A{index:02d}" for index in range(16) if index not in {12, 13}]
    # STEP LOG P10-PUBLIC-001: Execute only already-selected checkpoints and fixed methods on inspection-only public validation.
    console.log("P10-PUBLIC-001", "Starting inspection-only public validation.", details={"case_rows": len(bank.labels), "selection_prohibited": True})
    reports: dict[str, Any] = {}
    decisions_matrix: list[np.ndarray] = []
    decision_method_ids: list[str] = []
    for method_id, outcome in sorted(outcomes.items()):
        if outcome["status"] == "trained-calibrated":
            continue
        if outcome["status"] != "trained":
            reports[method_id] = {"status": "method_failure_retained", "reason": outcome["reason"], "public_rows": 0}
            continue
        package = pickle.loads((repo_root / outcome["checkpoint"]).read_bytes())
        x = _features(bank, package["profile"])
        probabilities = np.mean([_model_probabilities(model, package["kind"], x) for model in package["models"]], axis=0)
        probabilities = _apply_calibration(probabilities, package["calibration"])
        point = package["operating_point"]
        decisions = _decide(probabilities, point["accept_threshold"], point["reject_threshold"])
        reports[method_id] = {"status": "pass", "metrics": _metrics(bank.labels, decisions), "operating_point_id": point["operating_point_id"], "checkpoint_sha256": outcome["checkpoint_sha256"], "public_used_for_selection": False}
        decisions_matrix.append(decisions)
        decision_method_ids.append(method_id)
    if outcomes.get("P05-CONF-STATIC", {}).get("status") == "trained-calibrated":
        artifacts = json.loads((repo_root / outcomes["P05-CONF-STATIC"]["artifact"]).read_text(encoding="utf-8"))
        base_probs = _base_probabilities(repo_root, outcomes["P08-TABULAR-logistic"]["checkpoint"], bank)
        static = artifacts["P05-CONF-STATIC"]["selected"]
        decisions = np.argmax(base_probs, axis=1).astype(np.uint8)
        decisions[(1.0 - base_probs.max(axis=1)) > float(static["quantile"])] = 2
        reports["P05-CONF-STATIC"] = {"status": "pass", "metrics": _metrics(bank.labels, decisions), "base_checkpoint_sha256": outcomes["P08-TABULAR-logistic"]["checkpoint_sha256"], "alpha": static["alpha"], "quantile": static["quantile"], "public_used_for_selection": False}
        decisions_matrix.append(decisions)
        decision_method_ids.append("P05-CONF-STATIC")
        adaptive = artifacts["P06-CONF-ADAPT"]["selected"]
        history = []
        fit_bank = load_open_bank(repo_root, "calibration_fit")
        fit_probs = _base_probabilities(repo_root, outcomes["P08-TABULAR-logistic"]["checkpoint"], fit_bank)
        fit_nonconformity = 1.0 - fit_probs[np.arange(len(fit_bank.labels)), fit_bank.labels]
        history.extend(float(value) for value in fit_nonconformity[-int(adaptive["window"]):])
        decisions = np.empty(len(bank.labels), dtype=np.uint8)
        for index, probabilities in enumerate(base_probs):
            quantile = _conformal_quantile(np.asarray(history, dtype=np.float64), float(adaptive["alpha"]))
            prediction = int(np.argmax(probabilities))
            decisions[index] = 2 if 1.0 - float(probabilities[prediction]) > quantile else prediction
            history.append(1.0 - float(probabilities[int(bank.labels[index])]))
            history = history[-int(adaptive["window"]):]
        reports["P06-CONF-ADAPT"] = {"status": "pass", "metrics": _metrics(bank.labels, decisions), "base_checkpoint_sha256": outcomes["P08-TABULAR-logistic"]["checkpoint_sha256"], "alpha": adaptive["alpha"], "window": adaptive["window"], "current_label_used_before_decision": False, "public_used_for_selection": False}
        decisions_matrix.append(decisions)
        decision_method_ids.append("P06-CONF-ADAPT")
    for method_id in fixed:
        decisions = np.argmax(_fixed_probabilities(method_id, bank), axis=1).astype(np.uint8)
        reports[method_id] = {"status": "pass", "metrics": _metrics(bank.labels, decisions), "fixed_method": True, "public_used_for_selection": False}
        decisions_matrix.append(decisions)
        decision_method_ids.append(method_id)
    decision_array = np.stack(decisions_matrix).astype(np.uint8)
    decision_path = raw_root / "public_validation_decisions.npy"
    np.save(decision_path, decision_array, allow_pickle=False)
    index_path = raw_root / "public_validation_decision_index.json"
    index_path.write_text(json.dumps({"schema_version": "1.0", "method_ids": decision_method_ids, "case_ids_sha256": canonical_hash([int(value) for value in bank.case_ids]), "decision_file": decision_path.relative_to(repo_root).as_posix(), "decision_sha256": sha256_file(decision_path), "phase9a_commitment": commitment_receipt}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path = processed_root / "public_validation_metrics.json"
    report_path.write_text(json.dumps({"schema_version": "1.0", "study_version": "pead-study-v3", "run_id": run_id, "role": "inspection_only", "selection_from_public_validation": False, "methods": reports, "raw_decision_index": index_path.relative_to(repo_root).as_posix(), "phase9a_commitment": commitment_receipt}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P10-PUBLIC-002: Retain all public outcomes, failures, coverage tradeoffs, and raw decision lineage without tuning.
    console.log("P10-PUBLIC-002", "Public validation retained without model or policy selection.", status="pass", details={"evaluated_methods": len(decision_method_ids), "retained_failures": sum(item["status"] != "pass" for item in reports.values())})
    return {"reports": reports, "decision_file": decision_path.relative_to(repo_root).as_posix(), "decision_sha256": sha256_file(decision_path), "report": report_path.relative_to(repo_root).as_posix(), "report_sha256": sha256_file(report_path), "evaluated_methods": len(decision_method_ids), "retained_failures": sum(item["status"] != "pass" for item in reports.values())}
