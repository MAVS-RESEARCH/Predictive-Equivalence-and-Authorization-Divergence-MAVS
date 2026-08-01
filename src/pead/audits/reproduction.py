"""Tolerance-aware deterministic reproduction and conclusion audit."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def audit_reproduction(
    expected: Mapping[str, float], actual: Mapping[str, float], *, tolerance: float,
    expected_claims: Sequence[str], actual_claims: Sequence[str],
) -> dict[str, Any]:
    if set(expected) != set(actual) or tolerance < 0.0:
        raise ValueError("reproduction metric identities or tolerance are invalid")
    mismatches = {key: abs(expected[key] - actual[key]) for key in expected if abs(expected[key] - actual[key]) > tolerance}
    claim_change = tuple(expected_claims) != tuple(actual_claims)
    if mismatches or claim_change:
        raise ValueError(f"reproduction failed: mismatches={mismatches}; claim_change={claim_change}")
    return {"status": "pass", "metrics": len(expected), "tolerance": tolerance, "mismatches": {}, "claim_change": False}
