"""Registered three-class MLP and one-scalar bottleneck architectures."""

from __future__ import annotations

from typing import Any

MLP_GRID = tuple(
    {"learning_rate": learning_rate, "weight_decay": weight_decay}
    for learning_rate in (1e-4, 3e-4, 1e-3)
    for weight_decay in (1e-5, 1e-4)
)
MLP_SCHEDULE = {
    "batch_size": 256,
    "max_epochs": 100,
    "patience": 10,
    "gradient_clip": 1.0,
    "seeds": (101, 211, 307),
}


def build_mlp(input_dimension: int) -> Any:
    """Build d_in-512-256-128-3 LayerNorm/GELU/dropout-0.10 exactly."""

    import torch.nn as nn
    return nn.Sequential(
        nn.Linear(input_dimension, 512),
        nn.LayerNorm(512),
        nn.GELU(),
        nn.Dropout(0.10),
        nn.Linear(512, 256),
        nn.LayerNorm(256),
        nn.GELU(),
        nn.Dropout(0.10),
        nn.Linear(256, 128),
        nn.LayerNorm(128),
        nn.GELU(),
        nn.Dropout(0.10),
        nn.Linear(128, 3),
    )


def build_scalar_bottleneck(input_dimension: int) -> Any:
    """Build the registered MLP capacity with one scalar bottleneck."""

    import torch.nn as nn
    return nn.Sequential(
        nn.Linear(input_dimension, 512),
        nn.LayerNorm(512),
        nn.GELU(),
        nn.Dropout(0.10),
        nn.Linear(512, 256),
        nn.LayerNorm(256),
        nn.GELU(),
        nn.Dropout(0.10),
        nn.Linear(256, 128),
        nn.LayerNorm(128),
        nn.GELU(),
        nn.Dropout(0.10),
        nn.Linear(128, 1),
    )


def configure_determinism(seed: int) -> dict[str, Any]:
    import torch
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    return {
        "seed": seed,
        "deterministic_algorithms": True,
        "cudnn_benchmark": False,
    }
