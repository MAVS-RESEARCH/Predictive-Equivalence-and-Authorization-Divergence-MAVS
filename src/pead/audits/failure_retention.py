"""Negative-result, failed-method, quarantine, and error retention audit."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def audit_failure_retention(
    expected_ids: Sequence[str], reported: Mapping[str, str], *, allowed_statuses: Sequence[str] = ("pass", "fail", "error", "quarantined", "invalid"),
) -> dict[str, Any]:
    missing = sorted(set(expected_ids) - set(reported))
    extra = sorted(set(reported) - set(expected_ids))
    invalid_status = sorted(key for key, value in reported.items() if value not in allowed_statuses)
    if missing or extra or invalid_status:
        raise ValueError(f"failure retention failed: missing={missing}; extra={extra}; invalid_status={invalid_status}")
    retained_negative = sum(value in {"fail", "error", "quarantined", "invalid"} for value in reported.values())
    return {"status": "pass", "expected": len(expected_ids), "reported": len(reported), "retained_negative": retained_negative, "missing": [], "extra": []}
