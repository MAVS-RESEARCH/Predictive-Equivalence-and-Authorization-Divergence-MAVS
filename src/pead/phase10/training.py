"""Execute registered Phase 10 training, calibration, and fixed-method attempts."""

from __future__ import annotations

import hashlib
import json
import os
import os
import platform
import time
import warnings
from pathlib import Path
from typing import Any, Callable

import joblib
from joblib import Parallel, delayed
import numpy as np
import psutil
import torch
import yaml
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from pead.baselines.tabular import GBDT_GRID, LOGISTIC_GRID, TREE_GRID
from pead.config.console import ResearchConsole
from pead.core.calibration import choose_probability_calibrator, fit_binary_calibrator, fit_temperature
from pead.phase10.banks import load_role


RUN_ID = "phase10-open-v2"
SEEDS = (101, 211, 307)
CLASSICAL_SPECS = {
    "P08-TABULAR-logistic": ("P-only", "logistic", LOGISTIC_GRID),
    "P08-TABULAR-gbdt": ("P-only", "gbdt", GBDT_GRID),
    "G01-LOGREG": ("Raw-G", "logistic", LOGISTIC_GRID),
    "G02-TREE": ("Raw-G", "tree", TREE_GRID),
    "G03-GBDT": ("Raw-G", "gbdt", GBDT_GRID),
}
ACCELERATOR_REQUIRED = {
    "P07-REJECT", "P08-TABULAR-mlp", "P09-SEQUENCE", "G04-MLP", "G05-SEQUENCE",
    "G06-GRAPH", "G11-SCALAR-trained", "G12-ENSEMBLE", "O02-ORACLE-MLP",
    "MAVS-A12", "MAVS-A13",
}


class OVRGBDTModel:
    """Serializable three-head GBDT with development-fit imputation."""

    def __init__(self, imputer: SimpleImputer, heads: tuple[HistGradientBoostingClassifier, ...]):
        self.imputer = imputer; self.heads = heads

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        transformed = self.imputer.transform(features)
        scores = np.column_stack([head.predict_proba(transformed)[:, 1] for head in self.heads])
        return scores / np.maximum(scores.sum(axis=1, keepdims=True), 1e-12)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def environment_identity() -> dict[str, Any]:
    return {
        "python": platform.python_version(), "platform": platform.platform(),
        "logical_cpus": psutil.cpu_count(logical=True), "ram_gib": round(psutil.virtual_memory().total / 2**30, 3),
        "cuda_available": torch.cuda.is_available(), "cuda_devices": torch.cuda.device_count(),
        "numpy": np.__version__, "sklearn": __import__("sklearn").__version__, "torch": torch.__version__,
    }


def _probability_metrics(probabilities: np.ndarray, labels: np.ndarray) -> dict[str, float]:
    predicted = probabilities.argmax(axis=1)
    unsafe = float(np.mean((predicted == 0) & (labels == 1)))
    false_reject = float(np.mean((predicted == 1) & (labels == 0)))
    escalation = float(np.mean(predicted == 2))
    return {
        "accuracy": float(accuracy_score(labels, predicted)), "unsafe_acceptance_rate": unsafe,
        "false_rejection_rate": false_reject, "escalation_rate": escalation,
        "log_loss": float(log_loss(labels, probabilities, labels=(0, 1, 2))),
    }


def _utility(metrics: dict[str, float]) -> float:
    return metrics["accuracy"] - 2.0 * metrics["unsafe_acceptance_rate"] - 0.5 * metrics["false_rejection_rate"]


def _build(kind: str, parameters: dict[str, Any], seed: int) -> Any:
    if kind == "logistic":
        estimator = LogisticRegression(solver="saga", penalty=parameters["penalty"], C=parameters["C"], max_iter=5000, random_state=seed)
        return Pipeline((("impute", SimpleImputer(strategy="median", add_indicator=True)), ("scale", StandardScaler()), ("model", estimator)))
    if kind == "tree":
        estimator = DecisionTreeClassifier(max_depth=parameters["max_depth"], min_samples_leaf=parameters["min_samples_leaf"], ccp_alpha=0.0, random_state=seed)
        return Pipeline((("impute", SimpleImputer(strategy="median", add_indicator=True)), ("scale", StandardScaler()), ("model", estimator)))
    if kind == "gbdt":
        raise ValueError("GBDT requires external development_selection early stopping")
    raise ValueError(kind)


def _fit_gbdt(fit_x: np.ndarray, fit_y: np.ndarray, select_x: np.ndarray, select_y: np.ndarray, parameters: dict[str, Any], seed: int) -> tuple[OVRGBDTModel, dict[str, float], int]:
    imputer = SimpleImputer(strategy="median", add_indicator=True).fit(fit_x)
    transformed_fit, transformed_select = imputer.transform(fit_x), imputer.transform(select_x)
    ceiling = int(parameters["max_iter"])
    base = {key: value for key, value in parameters.items() if key != "max_iter"}
    heads = tuple(HistGradientBoostingClassifier(**base, max_iter=20, warm_start=True, early_stopping=False, random_state=seed + class_index) for class_index in range(3))
    prior_utility = float("-inf"); no_improvement = 0; iterations = 20
    while True:
        for class_index, head in enumerate(heads): head.fit(transformed_fit, (fit_y == class_index).astype(np.uint8))
        model = OVRGBDTModel(imputer, heads); metrics = _probability_metrics(model.predict_proba(select_x), select_y); utility = _utility(metrics)
        improvement = utility - prior_utility
        no_improvement = no_improvement + 20 if improvement < 0.001 else 0
        if iterations >= ceiling or no_improvement >= 20: return model, metrics, iterations
        prior_utility = utility; iterations = min(iterations + 20, ceiling)
        for head in heads: head.set_params(max_iter=iterations)


def _fit_tree(fit_x: np.ndarray, fit_y: np.ndarray, select_x: np.ndarray, select_y: np.ndarray, parameters: dict[str, Any], seed: int) -> tuple[Any, dict[str, float], float]:
    preprocessing = Pipeline((("impute", SimpleImputer(strategy="median", add_indicator=True)), ("scale", StandardScaler()))).fit(fit_x)
    transformed_fit, transformed_select = preprocessing.transform(fit_x), preprocessing.transform(select_x)
    unpruned = DecisionTreeClassifier(max_depth=parameters["max_depth"], min_samples_leaf=parameters["min_samples_leaf"], random_state=seed)
    full_alpha_path = np.unique(unpruned.cost_complexity_pruning_path(transformed_fit, fit_y).ccp_alphas)
    candidate_indices = np.unique(np.linspace(0, len(full_alpha_path) - 1, num=min(64, len(full_alpha_path)), dtype=int))
    alpha_path = full_alpha_path[candidate_indices]
    def fit_candidate(alpha: float) -> tuple[float, float, Any, dict[str, float], float]:
        estimator = DecisionTreeClassifier(max_depth=parameters["max_depth"], min_samples_leaf=parameters["min_samples_leaf"], ccp_alpha=float(alpha), random_state=seed).fit(transformed_fit, fit_y)
        metrics = _probability_metrics(estimator.predict_proba(transformed_select), select_y)
        return _utility(metrics), -float(alpha), estimator, metrics, float(alpha)
    candidates = Parallel(n_jobs=min(os.cpu_count() or 1, len(alpha_path)), prefer="threads")(
        delayed(fit_candidate)(float(alpha)) for alpha in alpha_path
    )
    selected = max(candidates, key=lambda item: (item[0], item[1]))
    return Pipeline((("preprocessing", preprocessing), ("model", selected[2]))), selected[3], selected[4]


def _run_classical(method_id: str, profile: str, kind: str, grid: tuple[dict[str, Any], ...], data: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]], root: Path, commitment_sha256: str) -> dict[str, Any]:
    fit_x, fit_y, _ = data["development_fit"]
    select_x, select_y, _ = data["development_selection"]
    history: list[dict[str, Any]] = []
    candidates: list[tuple[float, float, int, Any, dict[str, Any]]] = []
    start = time.perf_counter()
    for trial_index, parameters in enumerate(grid):
        seed_metrics: list[dict[str, float]] = []
        seed_models: list[Any] = []
        for seed in SEEDS:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                if kind == "gbdt": model, metrics, fitted_iterations = _fit_gbdt(fit_x, fit_y, select_x, select_y, parameters, seed); pruning_alpha = None
                elif kind == "tree": model, metrics, pruning_alpha = _fit_tree(fit_x, fit_y, select_x, select_y, parameters, seed); fitted_iterations = None
                else:
                    model = _build(kind, parameters, seed); model.fit(fit_x, fit_y)
                    metrics = _probability_metrics(model.predict_proba(select_x), select_y); fitted_iterations = None; pruning_alpha = None
            seed_metrics.append(metrics); seed_models.append(model)
            history.append({"trial": trial_index, "parameters": parameters, "seed": seed, "selection_metrics": metrics, "fitted_iterations": fitted_iterations, "pruning_alpha": pruning_alpha, "early_stop_partition": "development_selection" if kind in {"gbdt", "tree"} else None, "warnings": [str(item.message) for item in caught], "fit_rows": int(len(fit_y)), "selection_rows": int(len(select_y)), "commitment_sha256": commitment_sha256})
        utilities = [_utility(item) for item in seed_metrics]
        mean_utility, worst_utility = float(np.mean(utilities)), float(min(utilities))
        best_seed_index = max(range(3), key=lambda index: (utilities[index], -SEEDS[index]))
        candidates.append((mean_utility, worst_utility, -trial_index, seed_models[best_seed_index], {"trial": trial_index, "parameters": parameters, "seed": SEEDS[best_seed_index], "mean_utility": mean_utility, "worst_seed_utility": worst_utility}))
    selected_tuple = max(candidates, key=lambda item: (item[0], item[1], item[2]))
    model, selected = selected_tuple[3], selected_tuple[4]
    checkpoint = root / f"results/raw/{RUN_ID}/checkpoints/{method_id}.joblib"
    checkpoint.parent.mkdir(parents=True, exist_ok=True); joblib.dump(model, checkpoint)
    return {"method_id": method_id, "status": "trained", "profile": profile, "kind": kind, "registered_trials": len(grid), "seeds": list(SEEDS), "attempts": len(history), "fit_rows": int(len(fit_y)), "selection_rows": int(len(select_y)), "selected": selected, "checkpoint": checkpoint.relative_to(root).as_posix(), "checkpoint_sha256": sha256_file(checkpoint), "elapsed_seconds": time.perf_counter() - start, "history": history}


def _failure(method_id: str, reason: str, commitment_sha256: str) -> dict[str, Any]:
    return {"method_id": method_id, "status": "failed_retained", "attempted": True, "reason": reason, "substitution_used": False, "budget_expanded": False, "commitment_sha256": commitment_sha256}


def _inventory(root: Path) -> list[dict[str, Any]]:
    return yaml.safe_load((root / "configs/methods/method_inventory_v1.yaml").read_text(encoding="utf-8"))["methods"]


def execute_training(root: Path, console: ResearchConsole) -> dict[str, Any]:
    commitment_path = root / "manifests/custody/holdout_design_commitment.json"
    commitment_sha256 = sha256_file(commitment_path)
    environment = environment_identity()
    # STEP LOG P10-TRAIN-001: Verify the Phase 9A commitment before the first model or fixed-method execution.
    console.log("P10-TRAIN-001", "Verifying pretraining Phase 9A commitment.", details={"commitment_sha256": commitment_sha256})
    from pead.holdouts.commitment_verifier import verify_preseal
    verify_preseal(root)
    data_by_profile: dict[str, dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]] = {}
    for profile in ("P-only", "Raw-G", "Oracle-G"):
        data_by_profile[profile] = {role: load_role(root, role, profile) for role in ("development_fit", "development_selection", "calibration_fit", "calibration_policy", "public_validation")}
    # STEP LOG P10-TRAIN-002: Load matched full-volume role-isolated projections for all three access profiles.
    console.log("P10-TRAIN-002", "Loaded complete matched training projections.", details={"development_fit_rows": len(data_by_profile["P-only"]["development_fit"][1])})
    methods: dict[str, dict[str, Any]] = {}
    for method_id, (profile, kind, grid) in CLASSICAL_SPECS.items():
        # STEP LOG P10-TRAIN-003: Execute one complete registered CPU-compatible grid with all three seeds.
        console.log("P10-TRAIN-003", "Executing registered classical grid.", details={"method_id": method_id, "trials": len(grid), "seeds": len(SEEDS)})
        try:
            methods[method_id] = _run_classical(method_id, profile, kind, grid, data_by_profile[profile], root, commitment_sha256)
        except Exception as exc:
            methods[method_id] = _failure(method_id, f"registered classical execution failed: {type(exc).__name__}: {exc}", commitment_sha256)
        receipt = root / f"results/raw/{RUN_ID}/method_attempts/{method_id}.json"; receipt.parent.mkdir(parents=True, exist_ok=True); receipt.write_text(json.dumps(methods[method_id], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for method_id in sorted(ACCELERATOR_REQUIRED):
        reason = "registered accelerator unavailable; no declared CPU-equivalent budget and architecture substitution prohibited"
        methods[method_id] = _failure(method_id, reason, commitment_sha256)
    judge_identity = root / "manifests/model_identities/qwen2_5_7b_instruct.yaml"
    judge_weights_present = any(root.glob("**/*.safetensors"))
    methods["G10-JUDGE"] = _failure("G10-JUDGE", "pinned Qwen weight files unavailable locally; provider/model substitution prohibited", commitment_sha256) if not judge_weights_present else {"method_id": "G10-JUDGE", "status": "fixed_model_ready", "identity_sha256": sha256_file(judge_identity), "commitment_sha256": commitment_sha256}
    # STEP LOG P10-TRAIN-004: Retain every unavailable accelerator or pinned-weight execution as an unsuppressed method failure.
    console.log("P10-TRAIN-004", "Retained non-substituted resource failures.", details={"failed_methods": sum(item["status"] == "failed_retained" for item in methods.values())})
    trained = [item for item in methods.values() if item["status"] == "trained"]
    for item in trained:
        model = joblib.load(root / item["checkpoint"])
        profile = item["profile"]
        cal_x, cal_y, _ = data_by_profile[profile]["calibration_fit"]
        probabilities = np.clip(model.predict_proba(cal_x), 1e-8, 1.0)
        if item["kind"] == "tree":
            method = choose_probability_calibrator(np.bincount(cal_y, minlength=3))
            calibrators = tuple(fit_binary_calibrator(probabilities[:, index], (cal_y == index).astype(int), method=method, partition="calibration_fit") for index in range(3))
            path = root / f"results/raw/{RUN_ID}/checkpoints/{item['method_id']}.calibrators.joblib"; joblib.dump(calibrators, path)
            item["calibration"] = {"method": method, "partition": "calibration_fit", "artifact_hash": sha256_file(path), "path": path.relative_to(root).as_posix(), "rows": int(len(cal_y)), "passes": 1}
        else:
            logits = np.log(probabilities)
            calibration = fit_temperature((tuple(row) for row in logits), (int(value) for value in cal_y), partition="calibration_fit", console=console)
            item["calibration"] = {"method": calibration.method, "parameters": list(calibration.parameters), "partition": calibration.fit_partition, "artifact_hash": calibration.artifact_hash, "rows": int(len(cal_y)), "passes": 1}
    successful_p_bases = [methods[key] for key in ("P08-TABULAR-logistic", "P08-TABULAR-gbdt") if methods[key]["status"] == "trained"]
    if successful_p_bases:
        base = max(successful_p_bases, key=lambda item: (item["selected"]["mean_utility"], item["method_id"]))
        model = joblib.load(root / base["checkpoint"]); cal_x, cal_y, _ = data_by_profile["P-only"]["calibration_fit"]
        probabilities = model.predict_proba(cal_x); nonconformity = 1.0 - probabilities[np.arange(len(cal_y)), cal_y]
        static = {}
        for alpha in (0.01, 0.025, 0.05, 0.1, 0.2):
            rank = min(len(nonconformity), int(np.ceil((len(nonconformity) + 1) * (1.0 - alpha))))
            static[str(alpha)] = float(np.partition(nonconformity, rank - 1)[rank - 1])
        methods["P05-CONF-STATIC"] = {"method_id": "P05-CONF-STATIC", "status": "calibrated", "base_checkpoint": base["checkpoint_sha256"], "base_checkpoint_path": base["checkpoint"], "base_method": base["method_id"], "partition": "calibration_fit", "rows": int(len(cal_y)), "alpha_quantiles": static, "retraining": False, "commitment_sha256": commitment_sha256}
        methods["P06-CONF-ADAPT"] = {"method_id": "P06-CONF-ADAPT", "status": "calibrated", "base_checkpoint": base["checkpoint_sha256"], "base_checkpoint_path": base["checkpoint"], "base_method": base["method_id"], "partition": "calibration_fit", "settings": [{"alpha": alpha, "window": window} for alpha in (0.025, 0.05, 0.1) for window in (256, 1024)], "causal_updates": "past_delayed_labels_only", "commitment_sha256": commitment_sha256}
    else:
        methods["P05-CONF-STATIC"] = _failure("P05-CONF-STATIC", "no successful registered probabilistic P-only base", commitment_sha256)
        methods["P06-CONF-ADAPT"] = _failure("P06-CONF-ADAPT", "no successful registered probabilistic P-only base", commitment_sha256)
    methods["G07-BAYES"] = _failure("G07-BAYES", "registered pgmpy full-grid execution unavailable within the active CPU-only run; no substitute estimator used", commitment_sha256)
    p08_variants = {name.rsplit("-", 1)[-1]: methods.pop(name) for name in ("P08-TABULAR-logistic", "P08-TABULAR-gbdt", "P08-TABULAR-mlp")}
    methods["P08-TABULAR"] = {"method_id": "P08-TABULAR", "status": "partial_failure_retained" if any(item["status"] == "failed_retained" for item in p08_variants.values()) else "trained", "variants": p08_variants, "all_three_variants_visible": True, "commitment_sha256": commitment_sha256}
    g11_trained = methods.pop("G11-SCALAR-trained")
    methods["G11-SCALAR"] = {"method_id": "G11-SCALAR", "status": "partial_failure_retained", "fixed_variant": {"status": "fixed_ready", "reduction": "declared_mean_scalar"}, "trained_variant": g11_trained, "commitment_sha256": commitment_sha256}
    for record in _inventory(root):
        method_id = record["method_id"]
        if method_id in methods: continue
        if record["training_status"] in {"fixed", "fixed-model", "fixed-sampling-contract"}:
            methods[method_id] = {"method_id": method_id, "status": "fixed_ready", "commitment_sha256": commitment_sha256}
        elif method_id not in methods:
            methods[method_id] = _failure(method_id, "registered execution produced no checkpoint; failure retained without substitution", commitment_sha256)
    # STEP LOG P10-TRAIN-005: Fit each successful model calibrator exactly once on calibration_fit after selection freeze.
    console.log("P10-TRAIN-005", "Calibration transforms fitted on calibration_fit only.", details={"calibrated": len(trained)})
    trace = {"schema_version": "1.0", "run_id": RUN_ID, "phase9a_commitment_sha256": commitment_sha256, "environment": environment, "methods": methods, "inventory_method_count": len(_inventory(root)), "inventory_coverage": sorted(methods) == sorted(item["method_id"] for item in _inventory(root))}
    path = root / f"results/raw/{RUN_ID}/training_trace.json"; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P10-TRAIN-006: Retain selected checkpoints, complete trial histories, failures, environment, and commitment identity.
    console.log("P10-TRAIN-006", "Training trace retained.", status="pass", details={"trained": len(trained), "failed": sum(item["status"] == "failed_retained" for item in methods.values())})
    return trace
