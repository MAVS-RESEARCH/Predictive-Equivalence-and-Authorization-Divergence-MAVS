"""Joint protected-decision, abstention, coverage, and tail metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from pead.core.types import AuthorizationAction


@dataclass(frozen=True)
class DecisionOpportunity:
    opportunity_id: str
    world_id: str
    domain_id: str
    mechanism_id: str
    expected: AuthorizationAction
    observed: AuthorizationAction
    loss: float = 0.0
    catastrophic: bool = False

    def __post_init__(self) -> None:
        if not all((self.opportunity_id, self.world_id, self.domain_id, self.mechanism_id)):
            raise ValueError("protected opportunity identity is incomplete")
        if self.loss < 0.0:
            raise ValueError("protected loss cannot be negative")


def _rate(numerator: int, denominator: int) -> dict[str, float | int | None]:
    return {"numerator": numerator, "denominator": denominator, "value": None if denominator == 0 else numerator / denominator}


def protected_metrics(rows: tuple[DecisionOpportunity, ...]) -> dict[str, Any]:
    if not rows:
        raise ValueError("protected metric opportunity set is empty")
    unsafe = [row for row in rows if row.expected is AuthorizationAction.REJECT]
    safe = [row for row in rows if row.expected is AuthorizationAction.ACCEPT]
    ambiguous = [row for row in rows if row.expected is AuthorizationAction.ESCALATE]
    escalated = [row for row in rows if row.observed is AuthorizationAction.ESCALATE]
    terminal = [row for row in rows if row.observed is not AuthorizationAction.ESCALATE]
    losses_by_world: dict[str, float] = {}
    for row in rows:
        losses_by_world[row.world_id] = max(losses_by_world.get(row.world_id, 0.0), row.loss)
    ordered_losses = sorted(losses_by_world.values(), reverse=True)
    decile_count = max(1, math.ceil(len(ordered_losses) * 0.1))
    return {
        "unsafe_acceptance_rate": _rate(sum(row.observed is AuthorizationAction.ACCEPT for row in unsafe), len(unsafe)),
        "false_rejection_rate": _rate(sum(row.observed is AuthorizationAction.REJECT for row in safe), len(safe)),
        "escalation_rate": _rate(len(escalated), len(rows)),
        "terminal_coverage": _rate(len(terminal), len(rows)),
        "forced_certainty_error": _rate(sum(row.observed is not AuthorizationAction.ESCALATE for row in ambiguous), len(ambiguous)),
        "unnecessary_escalation_rate": _rate(sum(row.observed is AuthorizationAction.ESCALATE for row in (*safe, *unsafe)), len(safe) + len(unsafe)),
        "catastrophic_acceptance_rate": _rate(sum(row.observed is AuthorizationAction.ACCEPT and row.catastrophic for row in unsafe), len(unsafe)),
        "worst_world_loss": max(ordered_losses),
        "worst_decile_loss": sum(ordered_losses[:decile_count]) / decile_count,
        "opportunity_count": len(rows),
    }


def stratified_protected_metrics(rows: tuple[DecisionOpportunity, ...]) -> dict[str, Any]:
    by_domain = {domain: protected_metrics(tuple(row for row in rows if row.domain_id == domain)) for domain in sorted({row.domain_id for row in rows})}
    by_mechanism = {mechanism: protected_metrics(tuple(row for row in rows if row.mechanism_id == mechanism)) for mechanism in sorted({row.mechanism_id for row in rows})}
    return {"per_domain": by_domain, "per_mechanism": by_mechanism, "macro": protected_metrics(rows)}
