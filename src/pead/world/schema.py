"""Strict unlabeled schemas for causal-world generation and intervention proof."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pead.core.hashing import canonical_hash
from pead.core.types import (
    GovernanceState,
    OracleState,
    PredictiveState,
    WorldState,
    deep_freeze,
)


class WorldSchemaError(ValueError):
    """Raised when a generation request or proof violates the world contract."""


@dataclass(frozen=True)
class WorldRequest:
    schema_version: str
    request_id: str
    domain_id: str
    mechanism_id: str
    template_family_id: str
    latent_family_id: str
    sequence_lineage_id: str
    intervention_lineage_id: str
    provenance_lineage_id: str
    predictive_parents: Mapping[str, Any]
    latent_facts: Mapping[str, Any]
    nuisance_state: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise WorldSchemaError("WorldRequest schema_version must be 1.0")
        for name in (
            "request_id",
            "domain_id",
            "mechanism_id",
            "template_family_id",
            "latent_family_id",
            "sequence_lineage_id",
            "intervention_lineage_id",
            "provenance_lineage_id",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise WorldSchemaError(f"{name} must be non-empty")
        object.__setattr__(
            self,
            "predictive_parents",
            deep_freeze(self.predictive_parents),
        )
        object.__setattr__(self, "latent_facts", deep_freeze(self.latent_facts))
        object.__setattr__(self, "nuisance_state", deep_freeze(self.nuisance_state))


@dataclass(frozen=True)
class InterventionProof:
    schema_version: str
    mechanism_id: str
    intervention_id: str
    changed_authorization_parents: tuple[str, ...]
    unchanged_predictive_parent_hash_before: str
    unchanged_predictive_parent_hash_after: str
    predictive_parents_byte_equal: bool
    nuisance_only: bool
    construction_only: bool = False

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise WorldSchemaError("InterventionProof schema_version must be 1.0")
        if not self.mechanism_id or not self.intervention_id:
            raise WorldSchemaError("intervention identities must be non-empty")
        if (
            self.unchanged_predictive_parent_hash_before
            != self.unchanged_predictive_parent_hash_after
            or not self.predictive_parents_byte_equal
        ):
            raise WorldSchemaError("predictive parents changed under intervention")
        if (
            not self.nuisance_only
            and not self.construction_only
            and not self.changed_authorization_parents
        ):
            raise WorldSchemaError(
                "causal intervention requires changed authorization parents"
            )


@dataclass(frozen=True)
class GeneratedWorld:
    schema_version: str
    world_state: WorldState
    predictive_state: PredictiveState
    governance_state: GovernanceState
    oracle_state: OracleState
    latent_facts: Mapping[str, Any]
    surface: Mapping[str, Any]
    lineage: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise WorldSchemaError("GeneratedWorld schema_version must be 1.0")
        object.__setattr__(self, "latent_facts", deep_freeze(self.latent_facts))
        object.__setattr__(self, "surface", deep_freeze(self.surface))
        object.__setattr__(self, "lineage", deep_freeze(self.lineage))
        if canonical_hash(self.predictive_state) != canonical_hash(
            self.world_state.predictive_outputs
        ):
            raise WorldSchemaError(
                "world predictive outputs do not match PredictiveState"
            )

    @property
    def predictive_hash(self) -> str:
        return canonical_hash(self.predictive_state)

    @property
    def governance_hash(self) -> str:
        return canonical_hash(self.governance_state)

    @property
    def latent_facts_hash(self) -> str:
        return canonical_hash(self.latent_facts)


def predictive_state_from_parents(parents: Mapping[str, Any]) -> PredictiveState:
    required = {
        "shared_representation",
        "specialist_outputs",
        "signed_support",
        "predicted_label",
        "confidence",
        "uncertainty",
        "agreement",
        "calibration",
        "candidate_action",
    }
    if set(parents) != required:
        raise WorldSchemaError(
            f"predictive parent mismatch; missing={sorted(required - set(parents))}; "
            f"extra={sorted(set(parents) - required)}"
        )
    return PredictiveState(
        schema_version="1.0",
        shared_representation=parents["shared_representation"],
        specialist_outputs=tuple(parents["specialist_outputs"]),
        signed_support=tuple(parents["signed_support"]),
        predicted_label=parents["predicted_label"],
        confidence=parents["confidence"],
        uncertainty=parents["uncertainty"],
        agreement=parents["agreement"],
        calibration=parents["calibration"],
        candidate_action=parents["candidate_action"],
    )
