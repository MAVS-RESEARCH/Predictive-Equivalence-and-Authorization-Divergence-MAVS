"""Primary deterministic construction path for complete unlabeled worlds."""

from __future__ import annotations

from pead.core.types import GovernanceState, OracleState, WorldState
from pead.world.nuisance import apply_nuisance
from pead.world.schema import GeneratedWorld, WorldRequest, predictive_state_from_parents


def generate_world(request: WorldRequest) -> GeneratedWorld:
    predictive = predictive_state_from_parents(request.predictive_parents)
    canonical_surface = {
        "template_id": request.template_family_id,
        "display_id": "candidate-alpha",
        "text": "Candidate action derived from fixed predictive support.",
        "token_order": ["task", "candidate", "support"],
        "style": "canonical",
        "context_frequency": "balanced",
    }
    surface, facts = apply_nuisance(
        surface=canonical_surface,
        latent_facts=request.latent_facts,
        variant=str(request.nuisance_state["variant"]),
    )
    governance = GovernanceState(
        schema_version="1.0",
        provenance=facts["provenance"],
        authority=facts["actor"],
        policy=facts["policy"],
        temporal={"decision_time": facts["decision_time"]},
        reversibility={"rollback_available": facts["action"]["rollback_available"]},
        consequence=facts["consequence"],
        evidence_availability=facts["evidence"],
        dependency_graph=facts["dependency_graph"],
        counterfactual_views=(facts["counterfactual_views"],),
    )
    oracle = OracleState(
        schema_version="1.0",
        latent_governance_truth=facts,
        rule_inputs={"policy_id": "deploy_authorized_v1"},
    )
    lineage = {
        "domain_id": request.domain_id,
        "mechanism_id": request.mechanism_id,
        "template_family_id": request.template_family_id,
        "latent_family_id": request.latent_family_id,
        "sequence_lineage_id": request.sequence_lineage_id,
        "intervention_lineage_id": request.intervention_lineage_id,
        "provenance_lineage_id": request.provenance_lineage_id,
        "generator_path": "primary",
        "request_id": request.request_id,
    }
    world = WorldState.create(
        task_truth={"task_class": "stable-task-class"},
        candidate_action=predictive.candidate_action,
        provenance_graph=facts["dependency_graph"],
        authority_state=facts["actor"],
        policy_state=facts["policy"],
        temporal_state={"decision_time": facts["decision_time"]},
        consequence_state=facts["consequence"],
        evidence_state=facts["evidence"],
        predictive_outputs=predictive,
        nuisance_state=facts["nuisance"],
        hidden_mechanism=request.mechanism_id,
        generator_lineage=lineage,
    )
    return GeneratedWorld(
        schema_version="1.0",
        world_state=world,
        predictive_state=predictive,
        governance_state=governance,
        oracle_state=oracle,
        latent_facts=facts,
        surface=surface,
        lineage=lineage,
    )
