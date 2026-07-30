"""Lossless Oracle-G upper-bound projection and round-trip helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pead.config.console import ResearchConsole
from pead.core.types import OracleState, WorldState
from pead.projections import graph, sequence, tabular
from pead.projections.firewall import (
    AccessProfile,
    ProjectionTrace,
    SealedMethodInput,
    seal_rendering,
)
from pead.projections.predictive import PREDICTIVE_MISSING_RULES
from pead.projections.raw_governance import (
    GOVERNANCE_MISSING_RULES,
    raw_governance_facts,
)

ORACLE_FIELD_ACCESSORS = {
    "O-LATENT-GOVERNANCE-v1": "latent_governance_truth",
    "O-RULE-INPUTS-v1": "rule_inputs",
}

ORACLE_MISSING_RULES = {
    "O-LATENT-GOVERNANCE-v1": "latent truth is required for Oracle-G",
    "O-RULE-INPUTS-v1": "registered rule inputs are required for Oracle-G",
}

_RENDERERS = {
    tabular.REPRESENTATION_ID: tabular.render,
    sequence.REPRESENTATION_ID: sequence.render,
    graph.REPRESENTATION_ID: graph.render,
}

_SERIALIZERS = {
    tabular.REPRESENTATION_ID: tabular.serialize,
    sequence.REPRESENTATION_ID: sequence.serialize,
    graph.REPRESENTATION_ID: graph.serialize,
}

_DESERIALIZERS = {
    tabular.REPRESENTATION_ID: tabular.deserialize,
    sequence.REPRESENTATION_ID: sequence.deserialize,
    graph.REPRESENTATION_ID: graph.deserialize,
}


def oracle_facts(world: WorldState) -> Mapping[str, Any]:
    """Extract Raw-G facts plus the two declared latent Oracle fact families."""

    oracle = world.oracle_state
    if not isinstance(oracle, OracleState):
        raise ValueError("WorldState oracle_state must be OracleState")
    fields = dict(raw_governance_facts(world))
    fields.update(
        {
            stable_id: getattr(oracle, attribute)
            for stable_id, attribute in ORACLE_FIELD_ACCESSORS.items()
        }
    )
    return fields


def project_oracle(
    world: WorldState,
    *,
    representation_id: str,
    console: ResearchConsole,
) -> tuple[SealedMethodInput, ProjectionTrace]:
    """Produce a lossless Oracle-G sanity input; never a headline baseline."""

    fields = oracle_facts(world)
    try:
        render = _RENDERERS[representation_id]
    except KeyError as exc:
        raise ValueError(f"unregistered representation: {representation_id}") from exc
    return seal_rendering(
        world_id=world.world_id,
        access_profile=AccessProfile.ORACLE_G,
        representation_id=representation_id,
        semantic_fields=fields,
        rendered_payload=render(fields),
        transformations=(
            "frozen_predictive_field_selection_v1",
            "frozen_raw_governance_field_selection_v1",
            "registered_oracle_truth_selection_v1",
            representation_id,
            "lossless_canonical_serialization_v1",
        ),
        missing_value_behavior={
            **PREDICTIVE_MISSING_RULES,
            **GOVERNANCE_MISSING_RULES,
            **ORACLE_MISSING_RULES,
        },
        console=console,
    )


def reconstruct_oracle_projection(
    sealed_input: SealedMethodInput,
) -> Mapping[str, Any]:
    """Serialize and reconstruct one Oracle projection through its renderer."""

    if sealed_input.access_profile != AccessProfile.ORACLE_G.value:
        raise ValueError("Oracle reconstruction requires Oracle-G input")
    try:
        serialize = _SERIALIZERS[sealed_input.representation_id]
        deserialize = _DESERIALIZERS[sealed_input.representation_id]
    except KeyError as exc:
        raise ValueError("Oracle reconstruction received unknown representation") from exc
    return deserialize(serialize(sealed_input.payload))
