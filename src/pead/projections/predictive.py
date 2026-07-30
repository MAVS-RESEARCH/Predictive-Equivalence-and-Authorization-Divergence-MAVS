"""Frozen P-only projection from complete WorldState."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pead.config.console import ResearchConsole
from pead.core.types import PredictiveState, WorldState
from pead.projections import graph, sequence, tabular
from pead.projections.firewall import (
    AccessProfile,
    ProjectionTrace,
    SealedMethodInput,
    seal_rendering,
)

PREDICTIVE_FIELD_ACCESSORS = {
    "P-SHARED-v1": "shared_representation",
    "P-SPECIALISTS-v1": "specialist_outputs",
    "P-SUPPORT-v1": "signed_support",
    "P-LABEL-v1": "predicted_label",
    "P-CONFIDENCE-v1": "confidence",
    "P-UNCERTAINTY-v1": "uncertainty",
    "P-AGREEMENT-v1": "agreement",
    "P-CALIBRATION-v1": "calibration",
    "P-ACTION-v1": "candidate_action",
}

PREDICTIVE_MISSING_RULES = {
    "P-SHARED-v1": "typed missing marker; missing/missing equal",
    "P-SPECIALISTS-v1": "explicit typed unavailable output",
    "P-SUPPORT-v1": "explicit typed missing component",
    "P-LABEL-v1": "explicit no-prediction ID",
    "P-CONFIDENCE-v1": "typed missing; no implicit zero",
    "P-UNCERTAINTY-v1": "typed missing",
    "P-AGREEMENT-v1": "typed missing per summary",
    "P-CALIBRATION-v1": "typed unavailable estimate",
    "P-ACTION-v1": "candidate action is required",
}

_RENDERERS = {
    tabular.REPRESENTATION_ID: tabular.render,
    sequence.REPRESENTATION_ID: sequence.render,
    graph.REPRESENTATION_ID: graph.render,
}


def predictive_facts(world: WorldState) -> Mapping[str, Any]:
    """Extract exactly the nine frozen prediction-facing fields."""

    predictive = world.predictive_outputs
    if not isinstance(predictive, PredictiveState):
        raise ValueError("WorldState predictive_outputs must be PredictiveState")
    return {
        stable_id: getattr(predictive, attribute)
        for stable_id, attribute in PREDICTIVE_FIELD_ACCESSORS.items()
    }


def project_predictive(
    world: WorldState,
    *,
    representation_id: str,
    console: ResearchConsole,
) -> tuple[SealedMethodInput, ProjectionTrace]:
    """Produce an immutable P-only method input with no hidden back-reference."""

    fields = predictive_facts(world)
    try:
        render = _RENDERERS[representation_id]
    except KeyError as exc:
        raise ValueError(f"unregistered representation: {representation_id}") from exc
    payload = render(fields)
    return seal_rendering(
        world_id=world.world_id,
        access_profile=AccessProfile.P_ONLY,
        representation_id=representation_id,
        semantic_fields=fields,
        rendered_payload=payload,
        transformations=(
            "frozen_predictive_field_selection_v1",
            representation_id,
            "lossless_canonical_serialization_v1",
        ),
        missing_value_behavior=PREDICTIVE_MISSING_RULES,
        console=console,
    )
