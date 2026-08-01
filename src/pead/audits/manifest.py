"""Immutable artifact-manifest identity audit."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def audit_manifest(expected: Mapping[str, str], actual: Mapping[str, str]) -> dict[str, Any]:
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    changed = sorted(key for key in set(expected) & set(actual) if expected[key] != actual[key])
    if missing or extra or changed:
        raise ValueError(f"manifest mismatch: missing={missing}; extra={extra}; changed={changed}")
    return {"status": "pass", "artifacts": len(expected), "missing": [], "extra": [], "changed": []}
