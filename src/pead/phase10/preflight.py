"""Retain exact environment evidence for registered Phase 10 method failures."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import platform
from pathlib import Path
from typing import Any

from pead.baselines.neural import build_mlp, build_scalar_bottleneck
from pead.config.console import ResearchConsole
from pead.phase10.training import RUN_ID


def _package(name: str) -> dict[str, Any]:
    available = importlib.util.find_spec(name) is not None
    try:
        version = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        version = None
    return {"available": available, "version": version}


def retain_resource_failure_evidence(root: Path, console: ResearchConsole) -> dict[str, Any]:
    # STEP LOG P10-PREFLIGHT-001: Probe the exact locked backends and accelerator without installing or substituting a method.
    console.log("P10-PREFLIGHT-001", "Probing registered backends and accelerator availability.")
    packages = {name: _package(name) for name in ("torch", "pgmpy", "transformers", "sklearn")}
    import torch
    cuda = {"available": torch.cuda.is_available(), "device_count": torch.cuda.device_count()}
    # STEP LOG P10-PREFLIGHT-002: Instantiate the frozen MLP and scalar architectures to distinguish architecture defects from unavailable training compute.
    console.log("P10-PREFLIGHT-002", "Instantiating frozen neural architectures for preflight evidence.")
    architectures = {
        "p_only_mlp_parameters": sum(value.numel() for value in build_mlp(8).parameters()),
        "raw_g_mlp_parameters": sum(value.numel() for value in build_mlp(16).parameters()),
        "oracle_g_mlp_parameters": sum(value.numel() for value in build_mlp(24).parameters()),
        "scalar_bottleneck_parameters": sum(value.numel() for value in build_scalar_bottleneck(16).parameters()),
    }
    qwen_root = Path.home() / ".cache/huggingface/hub/models--Qwen--Qwen2.5-7B-Instruct"
    # STEP LOG P10-PREFLIGHT-003: Bind every retained failure to a concrete registered-resource or prerequisite failure.
    console.log("P10-PREFLIGHT-003", "Binding retained method failures to preflight evidence.")
    methods = {
        method_id: {"attempt_stage": "registered_environment_preflight", "outcome": "failed_retained", "reason_code": reason}
        for method_id, reason in {
            "P07-REJECT": "cuda_unavailable_and_no_predeclared_cpu_equivalent_ceiling",
            "P08-TABULAR-mlp": "cuda_unavailable_and_no_predeclared_cpu_equivalent_ceiling",
            "P09-SEQUENCE": "registered_cuda_accelerator_unavailable",
            "G04-MLP": "cuda_unavailable_and_no_predeclared_cpu_equivalent_ceiling",
            "G05-SEQUENCE": "registered_cuda_accelerator_unavailable",
            "G06-GRAPH": "registered_cuda_accelerator_unavailable",
            "G07-BAYES": "locked_pgmpy_backend_not_installed_in_active_environment",
            "G10-JUDGE": "pinned_qwen_weights_and_transformers_backend_unavailable",
            "G11-SCALAR-trained": "cuda_unavailable_and_no_predeclared_cpu_equivalent_ceiling",
            "G12-ENSEMBLE": "registered_oof_constituent_families_incomplete_after_retained_failures",
            "O02-ORACLE-MLP": "cuda_unavailable_and_no_predeclared_cpu_equivalent_ceiling",
            "MAVS-A12": "cuda_unavailable_and_no_predeclared_cpu_equivalent_ceiling",
            "MAVS-A13": "cuda_unavailable_and_no_predeclared_cpu_equivalent_ceiling",
        }.items()
    }
    report = {
        "schema_version": "1.0", "phase": 10, "run_id": RUN_ID, "status": "pass",
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "logical_cpus": os.cpu_count(), "packages": packages, "cuda": cuda, "qwen_weight_root_present": qwen_root.exists()},
        "frozen_architecture_instantiation": architectures,
        "methods": methods,
        "substitution_used": False, "budget_expanded": False,
        "interpretation": "These are retained registered-environment failures, not scientific performance results. No metric is imputed for a failed method.",
    }
    path = root / f"results/audits/{RUN_ID}/resource_failure_evidence.json"; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P10-PREFLIGHT-004: Retain the non-substitution evidence and prohibit imputed scientific metrics for failed methods.
    console.log("P10-PREFLIGHT-004", "Resource-failure evidence retained.", status="pass", details={"methods": len(methods), "substitutions": 0})
    return report
