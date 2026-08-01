"""Benchmark composition, direct-flag, control, and ambiguity non-triviality audit."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def audit_non_triviality(summary: Mapping[str, Any]) -> dict[str, Any]:
    required = {"compositional_fraction", "three_factor_fraction", "direct_label_flags", "prior_shift_controls", "label_permutation_controls", "ambiguity_certificates"}
    if not required <= set(summary):
        raise ValueError("non-triviality summary is incomplete")
    gates = {
        "compositional": summary["compositional_fraction"] >= 0.7,
        "three_factor": summary["three_factor_fraction"] >= 0.4,
        "no_direct_flags": summary["direct_label_flags"] == 0,
        "prior_shift": summary["prior_shift_controls"] > 0,
        "label_permutation": summary["label_permutation_controls"] > 0,
        "ambiguity": summary["ambiguity_certificates"] > 0,
    }
    if not all(gates.values()):
        raise ValueError(f"non-triviality gates failed: {gates}")
    return {"status": "pass", "gates": gates, "summary": dict(summary)}
