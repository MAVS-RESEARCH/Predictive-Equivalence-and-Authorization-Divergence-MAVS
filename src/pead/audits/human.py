"""Strict signed human-audit checkpoint artifact validation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pead.core.hashing import canonical_hash

CHECKPOINTS = (
    "label_engine_independence", "access_projection_raw_g_parity",
    "domain_mechanism_label_strata", "failures_and_quarantines",
    "benchmark_non_triviality", "baseline_fidelity", "negative_result_retention",
)
FIELDS = {
    "schema_version", "checkpoint_id", "reviewer_role", "independence_relationship",
    "reviewed_component_ids", "checklist_version", "findings", "corrections",
    "unresolved_concerns", "status", "signature_hash",
}


def sign_human_audit(payload: Mapping[str, Any]) -> dict[str, Any]:
    unsigned = dict(payload)
    unsigned.pop("signature_hash", None)
    unsigned["signature_hash"] = canonical_hash(unsigned)
    validate_human_audit(unsigned)
    return unsigned


def validate_human_audit(payload: Mapping[str, Any]) -> None:
    if set(payload) != FIELDS or payload.get("schema_version") != "1.0":
        raise ValueError("human audit artifact fields are not strict")
    if payload.get("checkpoint_id") not in CHECKPOINTS or payload.get("status") != "pass":
        raise ValueError("human audit checkpoint identity or status is invalid")
    if not payload.get("reviewer_role") or not payload.get("independence_relationship") or not payload.get("reviewed_component_ids"):
        raise ValueError("human audit reviewer and scope are incomplete")
    unsigned = dict(payload)
    signature = unsigned.pop("signature_hash")
    if signature != canonical_hash(unsigned):
        raise ValueError("human audit signature hash mismatch")


def audit_human_program(artifacts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    for artifact in artifacts:
        validate_human_audit(artifact)
    identities = [str(artifact["checkpoint_id"]) for artifact in artifacts]
    missing = sorted(set(CHECKPOINTS) - set(identities))
    duplicates = sorted({value for value in identities if identities.count(value) > 1})
    if missing or duplicates:
        raise ValueError(f"human audit program incomplete: missing={missing}; duplicates={duplicates}")
    return {"status": "pass", "checkpoints": len(artifacts), "missing": [], "duplicates": [], "external_human_validation": False}
