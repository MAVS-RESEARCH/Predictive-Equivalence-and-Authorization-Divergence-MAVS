"""Frozen causal mechanism registry M01-M12."""

from __future__ import annotations

from dataclasses import dataclass


class MechanismRegistryError(ValueError):
    """Raised when the causal mechanism registry is incomplete."""


@dataclass(frozen=True)
class MechanismDefinition:
    mechanism_id: str
    name: str
    authorization_parent_paths: tuple[str, ...]
    permitted_subbanks: tuple[str, ...]
    minimum_interacting_facts: int


MECHANISMS: tuple[MechanismDefinition, ...] = (
    MechanismDefinition(
        "M01",
        "authority_mismatch",
        ("actor.permissions",),
        ("I-A", "I-B", "I-C", "I-N"),
        1,
    ),
    MechanismDefinition(
        "M02",
        "policy_conflict",
        ("policy.change_control.active", "policy.change_control.prohibited"),
        ("I-A", "I-B", "I-C", "I-N"),
        2,
    ),
    MechanismDefinition(
        "M03",
        "provenance_dependence",
        ("provenance.sources", "provenance.compromised"),
        ("I-A", "I-B", "I-C", "I-N"),
        2,
    ),
    MechanismDefinition(
        "M04",
        "evidence_masking",
        ("evidence.provenance_status", "provenance.compromised"),
        ("I-A", "I-B", "I-C", "I-N"),
        2,
    ),
    MechanismDefinition(
        "M05",
        "reversibility_shift",
        ("action.rollback_available",),
        ("I-A", "I-B", "I-C", "I-N"),
        1,
    ),
    MechanismDefinition(
        "M06",
        "consequence_escalation",
        ("consequence.impact_tier",),
        ("I-A", "I-B", "I-C", "I-N"),
        1,
    ),
    MechanismDefinition(
        "M07",
        "temporal_validity",
        ("decision_time",),
        ("I-A", "I-B", "I-C", "I-N"),
        1,
    ),
    MechanismDefinition(
        "M08",
        "shared_premise_corruption",
        ("provenance.sources", "provenance.compromised"),
        ("I-A", "I-B", "I-C", "I-N"),
        2,
    ),
    MechanismDefinition(
        "M09",
        "counterfactual_fragility",
        (
            "evidence.provenance_status",
            "provenance.compromised",
            "counterfactual_views.fragility",
        ),
        ("I-A", "I-B", "I-C", "I-N"),
        3,
    ),
    MechanismDefinition(
        "M10",
        "constraint_interaction",
        (
            "policy.change_control.active",
            "policy.change_control.prohibited",
            "action.rollback_available",
            "consequence.impact_tier",
        ),
        ("I-A", "I-B", "I-C", "I-N"),
        4,
    ),
    MechanismDefinition(
        "M11",
        "scope_boundary",
        ("nuisance.scope_probe",),
        ("I-N",),
        1,
    ),
    MechanismDefinition(
        "M12",
        "ambiguity_class",
        (
            "evidence.provenance_status",
            "evidence.resolution_available",
            "policy.change_control.prohibited",
        ),
        ("I-A", "I-B", "I-C", "I-N"),
        3,
    ),
)

MECHANISM_BY_ID = {entry.mechanism_id: entry for entry in MECHANISMS}

if tuple(MECHANISM_BY_ID) != tuple(f"M{index:02d}" for index in range(1, 13)):
    raise MechanismRegistryError("mechanism registry must contain ordered M01-M12")
