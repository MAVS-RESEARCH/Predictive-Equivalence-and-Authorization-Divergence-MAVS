"""Holdout chronology, contamination, identity, and grouping audit."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def audit_holdouts(
    assignments: Mapping[str, str], group_ids: Mapping[str, str], *,
    contaminated_ids: Sequence[str] = (), post_freeze_changes: Sequence[str] = (),
) -> dict[str, Any]:
    if set(assignments) != set(group_ids) or not assignments:
        raise ValueError("holdout audit requires aligned case and group identities")
    group_roles: dict[str, set[str]] = {}
    for case_id, group_id in group_ids.items():
        group_roles.setdefault(group_id, set()).add(assignments[case_id])
    overlaps = {group: sorted(roles) for group, roles in group_roles.items() if len(roles) > 1}
    if overlaps or contaminated_ids or post_freeze_changes:
        raise ValueError(f"holdout gate failed: overlaps={overlaps}; contamination={list(contaminated_ids)}; changes={list(post_freeze_changes)}")
    return {"status": "pass", "cases": len(assignments), "groups": len(group_roles), "group_role_overlaps": {}, "contaminated_ids": [], "post_freeze_changes": []}
