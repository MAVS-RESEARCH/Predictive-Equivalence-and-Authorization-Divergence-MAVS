"""Equal-compute and immutable budget ceiling audit."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def audit_budgets(usage: Mapping[str, Mapping[str, float]], ceilings: Mapping[str, Mapping[str, float]]) -> dict[str, Any]:
    if set(usage) != set(ceilings) or not usage:
        raise ValueError("budget identities are incomplete")
    violations = []
    for method_id, resources in usage.items():
        if set(resources) != set(ceilings[method_id]):
            violations.append(f"{method_id}:resource-set")
            continue
        violations.extend(f"{method_id}:{resource}" for resource, value in resources.items() if value > ceilings[method_id][resource])
    if violations:
        raise ValueError(f"budget ceilings exceeded: {violations}")
    return {"status": "pass", "methods": len(usage), "violations": [], "usage": {key: dict(value) for key, value in usage.items()}}
