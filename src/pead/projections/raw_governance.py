"""Frozen equal-information Raw-G projection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pead.config.console import ResearchConsole
from pead.core.types import GovernanceState, WorldState
from pead.projections import graph, sequence, tabular
from pead.projections.firewall import (
    AccessProfile,
    ProjectionTrace,
    SealedMethodInput,
    seal_rendering,
)
from pead.projections.predictive import (
    PREDICTIVE_MISSING_RULES,
    predictive_facts,
)

GOVERNANCE_FIELD_ACCESSORS = {
    "G-PROVENANCE-v1": "provenance",
    "G-AUTHORITY-v1": "authority",
    "G-POLICY-v1": "policy",
    "G-TEMPORAL-v1": "temporal",
    "G-REVERSIBILITY-v1": "reversibility",
    "G-CONSEQUENCE-v1": "consequence",
    "G-EVIDENCE-v1": "evidence_availability",
    "G-DEPENDENCY-v1": "dependency_graph",
    "G-CFVIEW-v1": "counterfactual_views",
}

GOVERNANCE_MISSING_RULES = {
    "G-PROVENANCE-v1": "observed, missing, and unknown are distinct",
    "G-AUTHORITY-v1": "unknown is not permission",
    "G-POLICY-v1": "unknown policy state is explicit",
    "G-TEMPORAL-v1": "unknown time and absent event are distinct",
    "G-REVERSIBILITY-v1": "unknown reversibility is explicit",
    "G-CONSEQUENCE-v1": "unknown consequence is explicit",
    "G-EVIDENCE-v1": "observed, missing, masked, and unknown are distinct",
    "G-DEPENDENCY-v1": "unknown edge and absent edge are distinct",
    "G-CFVIEW-v1": "unavailable and unqueried are distinct",
}

_RENDERERS = {
    tabular.REPRESENTATION_ID: tabular.render,
    sequence.REPRESENTATION_ID: sequence.render,
    graph.REPRESENTATION_ID: graph.render,
}


def raw_governance_facts(world: WorldState) -> Mapping[str, Any]:
    """Extract only declared PredictiveState and raw visible GovernanceState."""

    governance = world.governance_state
    if not isinstance(governance, GovernanceState):
        raise ValueError("WorldState governance_state must be GovernanceState")
    fields = dict(predictive_facts(world))
    fields.update(
        {
            stable_id: getattr(governance, attribute)
            for stable_id, attribute in GOVERNANCE_FIELD_ACCESSORS.items()
        }
    )
    return fields


def project_raw_governance(
    world: WorldState,
    *,
    representation_id: str,
    console: ResearchConsole,
) -> tuple[SealedMethodInput, ProjectionTrace]:
    """Produce a lossless, immutable, equal-information Raw-G method input."""

    fields = raw_governance_facts(world)
    try:
        render = _RENDERERS[representation_id]
    except KeyError as exc:
        raise ValueError(f"unregistered representation: {representation_id}") from exc
    return seal_rendering(
        world_id=world.world_id,
        access_profile=AccessProfile.RAW_G,
        representation_id=representation_id,
        semantic_fields=fields,
        rendered_payload=render(fields),
        transformations=(
            "frozen_predictive_field_selection_v1",
            "frozen_raw_governance_field_selection_v1",
            representation_id,
            "lossless_canonical_serialization_v1",
        ),
        missing_value_behavior={
            **PREDICTIVE_MISSING_RULES,
            **GOVERNANCE_MISSING_RULES,
        },
        console=console,
    )
