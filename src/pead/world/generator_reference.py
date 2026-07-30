"""Independent reconstruction path for complete unlabeled worlds."""

from __future__ import annotations

from pead.core.types import GovernanceState, OracleState, WorldState
from pead.world.nuisance import apply_nuisance
from pead.world.schema import GeneratedWorld, WorldRequest, predictive_state_from_parents


def generate_world_reference(request: WorldRequest) -> GeneratedWorld:
    p_state = predictive_state_from_parents(request.predictive_parents)
    initial_rendering = {
        "template_id": request.template_family_id,
        "display_id": "candidate-alpha",
        "text": "Candidate action derived from fixed predictive support.",
        "token_order": ["task", "candidate", "support"],
        "style": "canonical",
        "context_frequency": "balanced",
    }
    rendered, latent = apply_nuisance(
        surface=initial_rendering,
        latent_facts=request.latent_facts,
        variant=str(request.nuisance_state["variant"]),
    )
    g_state = GovernanceState(
        schema_version="1.0",
        provenance=latent["provenance"],
        authority=latent["actor"],
        policy=latent["policy"],
        temporal={"decision_time": latent["decision_time"]},
        reversibility={
            "rollback_available": latent["action"]["rollback_available"]
        },
        consequence=latent["consequence"],
        evidence_availability=latent["evidence"],
        dependency_graph=latent["dependency_graph"],
        counterfactual_views=(latent["counterfactual_views"],),
    )
    o_state = OracleState(
        schema_version="1.0",
        latent_governance_truth=latent,
        rule_inputs={"policy_id": "deploy_authorized_v1"},
    )
    ancestry = {
        "domain_id": request.domain_id,
        "mechanism_id": request.mechanism_id,
        "template_family_id": request.template_family_id,
        "latent_family_id": request.latent_family_id,
        "sequence_lineage_id": request.sequence_lineage_id,
        "intervention_lineage_id": request.intervention_lineage_id,
        "provenance_lineage_id": request.provenance_lineage_id,
        "generator_path": "reference",
        "request_id": request.request_id,
    }
    w_state = WorldState.create(
        task_truth={"task_class": "stable-task-class"},
        candidate_action=p_state.candidate_action,
        provenance_graph=latent["dependency_graph"],
        authority_state=latent["actor"],
        policy_state=latent["policy"],
        temporal_state={"decision_time": latent["decision_time"]},
        consequence_state=latent["consequence"],
        evidence_state=latent["evidence"],
        predictive_outputs=p_state,
        nuisance_state=latent["nuisance"],
        hidden_mechanism=request.mechanism_id,
        generator_lineage=ancestry,
    )
    return GeneratedWorld(
        schema_version="1.0",
        world_state=w_state,
        predictive_state=p_state,
        governance_state=g_state,
        oracle_state=o_state,
        latent_facts=latent,
        surface=rendered,
        lineage=ancestry,
    )
