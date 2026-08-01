"""Non-scientific deterministic fixtures for Phase 7 interface verification."""

from __future__ import annotations

from pead.core.hashing import canonical_hash
from pead.projections.firewall import SealedMethodInput


def probe_input(access_profile: str, representation_id: str, *, index: int = 0) -> SealedMethodInput:
    """Create a visible-only contract fixture; it is not a benchmark case."""

    field_ids = ("P-CONFIDENCE-v1",) if access_profile == "P-only" else ("P-CONFIDENCE-v1", "G-POLICY-v1")
    if access_profile == "Oracle-G":
        field_ids += ("O-RULE-v1",)
    facts = {field_id: {"fixture": index, "field": field_id} for field_id in field_ids}
    if representation_id == "canonical-tabular-v1":
        payload = facts
    elif representation_id == "canonical-sequence-v1":
        payload = tuple(sorted(facts.items()))
    elif representation_id == "canonical-graph-v1":
        payload = {
            "nodes": tuple({"id": field_id, "value": value} for field_id, value in sorted(facts.items())),
            "edges": tuple(),
        }
    else:
        raise ValueError("unregistered fixture representation")
    return SealedMethodInput(
        schema_version="1.0",
        access_profile=access_profile,
        representation_id=representation_id,
        payload=payload,
        field_ids=field_ids,
        semantic_fact_hash=canonical_hash(facts),
        projection_hash=canonical_hash({"profile": access_profile, "representation": representation_id, "facts": facts}),
    )
