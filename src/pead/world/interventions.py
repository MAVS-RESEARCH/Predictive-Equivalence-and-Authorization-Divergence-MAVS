"""Registered latent-parent interventions with predictive-parent proof."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from enum import Enum
from typing import Any

from pead.core.hashing import canonical_bytes, canonical_hash
from pead.world.mechanisms import MECHANISM_BY_ID
from pead.world.schema import InterventionProof, WorldSchemaError


class LatentVariant(str, Enum):
    PERMITTED = "permitted"
    BLOCKED = "blocked"
    UNRESOLVED = "unresolved"
    INVARIANT = "invariant"


def _set_path(target: dict[str, Any], path: str, value: Any) -> None:
    current = target
    components = path.split(".")
    for component in components[:-1]:
        child = current.get(component)
        if not isinstance(child, dict):
            raise WorldSchemaError(f"intervention path is absent: {path}")
        current = child
    if components[-1] not in current:
        raise WorldSchemaError(f"intervention leaf is absent: {path}")
    current[components[-1]] = copy.deepcopy(value)


def _updates(
    mechanism_id: str,
    variant: LatentVariant,
) -> dict[str, Any]:
    independent_sources = [
        {"source_id": "source-a", "independent": True},
        {"source_id": "source-b", "independent": True},
    ]
    shared_sources = [
        {"source_id": "shared-source", "independent": False},
        {"source_id": "shared-source", "independent": False},
    ]
    if mechanism_id == "M01":
        return {
            "actor.permissions": (
                ["production.deploy"]
                if variant is LatentVariant.PERMITTED
                else []
                if variant is LatentVariant.BLOCKED
                else None
            )
        }
    if mechanism_id == "M02":
        return {
            "policy.change_control.active": (
                True if variant is not LatentVariant.UNRESOLVED else None
            ),
            "policy.change_control.prohibited": (
                variant is LatentVariant.BLOCKED
            ),
        }
    if mechanism_id == "M03":
        return {
            "provenance.sources": (
                independent_sources
                if variant is LatentVariant.PERMITTED
                else shared_sources
                if variant is LatentVariant.BLOCKED
                else None
            ),
            "provenance.compromised": (
                variant is LatentVariant.BLOCKED
            ),
        }
    if mechanism_id == "M04":
        return {
            "evidence.provenance_status": (
                "unknown"
                if variant is LatentVariant.UNRESOLVED
                else "verified"
            ),
            "provenance.compromised": variant is LatentVariant.BLOCKED,
        }
    if mechanism_id == "M05":
        return {
            "action.rollback_available": (
                True
                if variant is LatentVariant.PERMITTED
                else False
                if variant is LatentVariant.BLOCKED
                else None
            )
        }
    if mechanism_id == "M06":
        return {
            "consequence.impact_tier": (
                3
                if variant is LatentVariant.PERMITTED
                else 9
                if variant is LatentVariant.BLOCKED
                else None
            )
        }
    if mechanism_id == "M07":
        return {
            "decision_time": (
                "2026-06-01T12:00:00+00:00"
                if variant is LatentVariant.PERMITTED
                else "2027-01-01T00:00:00+00:00"
                if variant is LatentVariant.BLOCKED
                else None
            )
        }
    if mechanism_id == "M08":
        return {
            "provenance.sources": (
                independent_sources
                if variant is LatentVariant.PERMITTED
                else shared_sources
                if variant is LatentVariant.BLOCKED
                else None
            ),
            "provenance.compromised": False,
        }
    if mechanism_id == "M09":
        return {
            "evidence.provenance_status": (
                "unknown"
                if variant is LatentVariant.UNRESOLVED
                else "verified"
            ),
            "provenance.compromised": variant is LatentVariant.BLOCKED,
            "counterfactual_views.fragility": (
                "stable"
                if variant is LatentVariant.PERMITTED
                else "danger"
                if variant is LatentVariant.BLOCKED
                else "unavailable"
            ),
        }
    if mechanism_id == "M10":
        return {
            "policy.change_control.active": (
                True if variant is not LatentVariant.UNRESOLVED else None
            ),
            "policy.change_control.prohibited": variant is LatentVariant.BLOCKED,
            "action.rollback_available": (
                True
                if variant is LatentVariant.PERMITTED
                else False
                if variant is LatentVariant.BLOCKED
                else None
            ),
            "consequence.impact_tier": (
                3
                if variant is LatentVariant.PERMITTED
                else 9
                if variant is LatentVariant.BLOCKED
                else None
            ),
        }
    if mechanism_id == "M12":
        return {
            "evidence.provenance_status": (
                "unknown"
                if variant is LatentVariant.UNRESOLVED
                else "verified"
            ),
            "evidence.resolution_available": (
                False if variant is LatentVariant.UNRESOLVED else True
            ),
            "policy.change_control.prohibited": variant is LatentVariant.BLOCKED,
        }
    if mechanism_id == "M11" and variant is LatentVariant.INVARIANT:
        return {"nuisance.scope_probe": "outside_registered_scope"}
    raise WorldSchemaError(
        f"mechanism {mechanism_id} does not support latent variant {variant.value}"
    )


def apply_intervention(
    *,
    mechanism_id: str,
    variant: LatentVariant,
    latent_facts: Mapping[str, Any],
    predictive_parents: Mapping[str, Any],
    intervention_id: str,
) -> tuple[dict[str, Any], InterventionProof]:
    try:
        definition = MECHANISM_BY_ID[mechanism_id]
    except KeyError as exc:
        raise WorldSchemaError(f"unknown mechanism: {mechanism_id}") from exc
    facts = copy.deepcopy(dict(latent_facts))
    updates = _updates(mechanism_id, variant)
    unauthorized = sorted(set(updates) - set(definition.authorization_parent_paths))
    if unauthorized:
        raise WorldSchemaError(
            f"intervention changes unregistered parents: {unauthorized}"
        )
    before = copy.deepcopy(facts)
    for path, value in updates.items():
        _set_path(facts, path, value)
    changed = tuple(
        sorted(
            path
            for path in updates
            if canonical_hash(_path_value(before, path))
            != canonical_hash(_path_value(facts, path))
        )
    )
    predictive_before = canonical_hash(predictive_parents)
    predictive_after = canonical_hash(predictive_parents)
    proof = InterventionProof(
        schema_version="1.0",
        mechanism_id=mechanism_id,
        intervention_id=intervention_id,
        changed_authorization_parents=changed,
        unchanged_predictive_parent_hash_before=predictive_before,
        unchanged_predictive_parent_hash_after=predictive_after,
        predictive_parents_byte_equal=(
            canonical_bytes(predictive_parents)
            == canonical_bytes(predictive_parents)
        ),
        nuisance_only=variant is LatentVariant.INVARIANT,
        construction_only=True,
    )
    return facts, proof


def _path_value(source: Mapping[str, Any], path: str) -> Any:
    current: Any = source
    for component in path.split("."):
        if not isinstance(current, Mapping) or component not in current:
            raise WorldSchemaError(f"proof path is absent: {path}")
        current = current[component]
    return current
