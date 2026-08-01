"""Diagnostic Sciences scope, influence, composition, and boundary metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DiagnosticObservation:
    case_id: str
    diagnostic_id: str
    bank: str
    in_scope: bool
    target_present: bool
    signal_active: bool
    decision_changed: bool
    correct_with: bool
    correct_without: bool
    protected_error_with: bool
    protected_error_without: bool
    escalated_with: bool
    escalated_without: bool
    nuisance_signal_changed: bool = False
    nuisance_decision_changed: bool = False
    individual_gain: float = 0.0
    joint_gain: float = 0.0
    boundary_distance: float = 1.0
    boundary_influence_delta: float = 0.0

    def __post_init__(self) -> None:
        if self.bank not in {"positive", "matched_negative", "boundary", "adversarial_out_of_scope"}:
            raise ValueError("unknown diagnostic scope bank")
        if self.boundary_distance < 0.0:
            raise ValueError("boundary distance cannot be negative")


def _fraction(numerator: int, denominator: int) -> dict[str, float | int | None]:
    return {"numerator": numerator, "denominator": denominator, "value": None if denominator == 0 else numerator / denominator}


def diagnostic_science_metrics(rows: tuple[DiagnosticObservation, ...]) -> dict[str, Any]:
    if not rows:
        raise ValueError("diagnostic metric rows are empty")
    positive = [row for row in rows if row.in_scope and row.target_present]
    negative = [row for row in rows if row.in_scope and not row.target_present]
    inside = [row for row in rows if row.in_scope]
    outside = [row for row in rows if not row.in_scope]
    boundary = [row for row in rows if row.bank == "boundary"]
    conditional = [row for row in positive if not row.correct_without]
    pairwise = [row for row in rows if row.joint_gain != 0.0 or row.individual_gain != 0.0]
    def mean(values: list[float]) -> float | None:
        return None if not values else sum(values) / len(values)
    return {
        "in_scope_sensitivity": _fraction(sum(row.signal_active for row in positive), len(positive)),
        "scope_matched_specificity": _fraction(sum(not row.signal_active for row in negative), len(negative)),
        "conditional_perception_extension": _fraction(sum(row.correct_with for row in conditional), len(conditional)),
        "intended_decision_influence_I_in": _fraction(sum(row.decision_changed for row in inside), len(inside)),
        "out_of_scope_influence_I_out": _fraction(sum(row.decision_changed for row in outside), len(outside)),
        "redundancy": _fraction(sum(row.signal_active and row.correct_without for row in positive), len(positive)),
        "nuisance_signal_instability": _fraction(sum(row.nuisance_signal_changed for row in rows), len(rows)),
        "nuisance_decision_instability": _fraction(sum(row.nuisance_decision_changed for row in rows), len(rows)),
        "pairwise_harmful_composition": mean([row.joint_gain - row.individual_gain for row in pairwise]),
        "set_level_harmful_composition": (sum(row.joint_gain for row in pairwise) - sum(row.individual_gain for row in pairwise)) if pairwise else None,
        "protected_error_delta": mean([float(row.protected_error_with) - float(row.protected_error_without) for row in rows]),
        "escalation_delta": mean([float(row.escalated_with) - float(row.escalated_without) for row in rows]),
        "scope_leakage": _fraction(sum(row.signal_active or row.decision_changed for row in outside), len(outside)),
        "boundary_discontinuity": mean([abs(row.boundary_influence_delta) / max(row.boundary_distance, 1e-12) for row in boundary]),
    }
