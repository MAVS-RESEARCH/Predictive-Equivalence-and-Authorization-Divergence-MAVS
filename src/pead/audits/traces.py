"""Headline trace completeness, identity, and chronology audit."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

REQUIRED = {
    "run_id", "config_hash", "commit_hash", "environment_hash", "world_id",
    "atomic_group_id", "split_id", "method_id", "projection_hash", "decision_hash",
    "trace_hash", "decision_commit_time", "label_reveal_time", "raw_trace_id",
}


def audit_traces(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("headline trace set is empty")
    failures = []
    for index, row in enumerate(rows):
        if not REQUIRED <= set(row) or any(not row.get(field) for field in REQUIRED):
            failures.append(f"row-{index}:missing")
            continue
        commit = datetime.fromisoformat(str(row["decision_commit_time"]).replace("Z", "+00:00"))
        reveal = datetime.fromisoformat(str(row["label_reveal_time"]).replace("Z", "+00:00"))
        if reveal < commit:
            failures.append(f"row-{index}:chronology")
    if failures:
        raise ValueError(f"trace completeness failed: {failures}")
    return {"status": "pass", "traces": len(rows), "complete": len(rows), "failures": []}
