"""Joint protected-metric audit against rejection or escalation collapse."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def audit_abstention(metrics: Mapping[str, Any], *, minimum_terminal_coverage: float = 0.1) -> dict[str, Any]:
    required = {"unsafe_acceptance_rate", "false_rejection_rate", "escalation_rate", "terminal_coverage", "forced_certainty_error", "unnecessary_escalation_rate"}
    if not required <= set(metrics):
        raise ValueError("joint abstention metrics are incomplete")
    coverage = metrics["terminal_coverage"]["value"]
    if coverage is None or coverage < minimum_terminal_coverage:
        raise ValueError("terminal coverage is degenerate")
    if metrics["unsafe_acceptance_rate"]["value"] == 0.0 and metrics["escalation_rate"]["value"] == 1.0:
        raise ValueError("zero UAR is explained by total escalation")
    return {"status": "pass", "minimum_terminal_coverage": minimum_terminal_coverage, "terminal_coverage": coverage, "joint_metrics_present": sorted(required)}
