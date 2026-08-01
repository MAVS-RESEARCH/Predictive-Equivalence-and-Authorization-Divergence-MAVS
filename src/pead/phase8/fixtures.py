"""Deterministic visible-only fixtures for Phase 8 implementation tests."""

from __future__ import annotations

from typing import Any

from pead.core.hashing import canonical_hash
from pead.projections import tabular
from pead.projections.firewall import SealedMethodInput


def raw_g_facts(
    *,
    supports: tuple[float, ...] = (0.9, 0.8, 0.85),
    correlation: float = 0.0,
    independent_support: float = 1.0,
    policy_conflict: float = 0.0,
    missing_evidence: float = 0.0,
    fragility: float = 0.0,
    confidence: float = 0.85,
    agreement: float = 0.85,
    authority_invalid: bool = False,
    scope: dict[str, bool] | None = None,
) -> dict[str, Any]:
    return {
        "P-SHARED-v1": {"fixture": "phase8"},
        "P-SPECIALISTS-v1": tuple({"specialist_id": f"s{index}", "score": value} for index, value in enumerate(supports)),
        "P-SUPPORT-v1": supports,
        "P-LABEL-v1": "candidate",
        "P-CONFIDENCE-v1": confidence,
        "P-UNCERTAINTY-v1": 1.0 - confidence,
        "P-AGREEMENT-v1": agreement,
        "P-CALIBRATION-v1": {"available": True},
        "P-ACTION-v1": {"action_type": "fixture", "target": "phase8", "parameters": {}},
        "G-PROVENANCE-v1": {"independent_support": independent_support},
        "G-AUTHORITY-v1": {"invalid": authority_invalid},
        "G-POLICY-v1": {"conflict": policy_conflict, "scope": scope or {}},
        "G-TEMPORAL-v1": {"active": True},
        "G-REVERSIBILITY-v1": {"rollback": True},
        "G-CONSEQUENCE-v1": {"tier": "registered"},
        "G-EVIDENCE-v1": {"missing_fraction": missing_evidence, "scope": scope or {}},
        "G-DEPENDENCY-v1": {"correlation": correlation, "scope": scope or {}},
        "G-CFVIEW-v1": ({"support_delta": fragility},),
    }


def sealed_raw_g(**kwargs: Any) -> SealedMethodInput:
    facts = raw_g_facts(**kwargs)
    return SealedMethodInput(
        schema_version="1.0", access_profile="Raw-G",
        representation_id="canonical-tabular-v1", payload=tabular.render(facts),
        field_ids=tuple(sorted(facts)), semantic_fact_hash=canonical_hash(facts),
        projection_hash=canonical_hash({"profile": "Raw-G", "facts": facts}),
    )


def sealed_p_only(*, supports: tuple[float, ...] = (0.9, 0.8, 0.85)) -> SealedMethodInput:
    raw = raw_g_facts(supports=supports)
    facts = {key: value for key, value in raw.items() if key.startswith("P-")}
    return SealedMethodInput(
        schema_version="1.0", access_profile="P-only",
        representation_id="canonical-tabular-v1", payload=tabular.render(facts),
        field_ids=tuple(sorted(facts)), semantic_fact_hash=canonical_hash(facts),
        projection_hash=canonical_hash({"profile": "P-only", "facts": facts}),
    )
