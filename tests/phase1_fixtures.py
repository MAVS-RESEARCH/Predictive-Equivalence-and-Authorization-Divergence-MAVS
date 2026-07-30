"""Deterministic fixtures shared by Phase 1 tests."""

from __future__ import annotations

from pead.core.hashing import canonical_hash
from pead.core.types import (
    AuthorizationAction,
    AuthorizationLabel,
    GovernanceState,
    MethodDecision,
    PredictiveState,
    WorldState,
)


def predictive_state() -> PredictiveState:
    return PredictiveState(
        schema_version="1.0",
        shared_representation={"feature_b": 2.0, "feature_a": "cafe\u0301"},
        specialist_outputs=({"specialist_id": "s2", "score": 0.2},),
        signed_support=(0.75, -0.25),
        predicted_label="class-a",
        confidence=0.8,
        uncertainty=0.2,
        agreement={"count": 2},
        calibration={"nonconformity": 0.1},
        candidate_action={
            "action_type": "classify",
            "target": "case-1",
            "parameters": {"label": "class-a"},
        },
    )


def governance_state() -> GovernanceState:
    return GovernanceState(
        schema_version="1.0",
        provenance={"sources": {"source-b", "source-a"}},
        authority={"actor": "reviewer", "active": True},
        policy={"rules": ("rule-2", "rule-1")},
        temporal={"valid_from": "2026-01-01T00:00:00+00:00"},
        reversibility={"rollback": True},
        consequence={"tier": "low"},
        evidence_availability={"status": "observed"},
        dependency_graph={
            "nodes": [{"id": "n2"}, {"id": "n1"}],
            "edges": [
                {"source": "n2", "target": "n1", "type": "supports"},
                {"source": "n1", "target": "n2", "type": "depends"},
            ],
        },
        counterfactual_views=({"view_id": "view-1"},),
    )


def world_state() -> WorldState:
    return WorldState.create(
        task_truth={"label": "class-a"},
        candidate_action={
            "action_type": "classify",
            "target": "case-1",
            "parameters": {"label": "class-a"},
        },
        provenance_graph={
            "nodes": [{"id": "n2"}, {"id": "n1"}],
            "edges": [{"source": "n1", "target": "n2", "type": "supports"}],
        },
        authority_state={"permitted": True},
        policy_state={"policy": "test"},
        temporal_state={"active": True},
        consequence_state={"tier": "low"},
        evidence_state={"available": True},
        predictive_outputs={"support": (0.75, -0.25)},
        nuisance_state={"style": "plain"},
        hidden_mechanism="M01",
        generator_lineage={"seed": 1_000_001, "version": "1.0"},
    )


def authorization_label() -> AuthorizationLabel:
    return AuthorizationLabel(
        schema_version="1.0",
        action=AuthorizationAction.ACCEPT,
        reason_class="authorized",
        rule_lineage=("rule-1",),
    )


def method_decision(projection_hash: str | None = None) -> MethodDecision:
    return MethodDecision(
        schema_version="1.0",
        decision=AuthorizationAction.ACCEPT,
        decision_scores={"Accept": 0.8, "Reject": 0.1, "Escalate": 0.1},
        operating_point_id="op-v1",
        rationale="Highest registered decision score.",
        diagnostic_trace={"features_used": ("support",)},
        resource_usage={"latency_ms": 1.25, "calls": 1},
        visible_projection_hash=projection_hash or canonical_hash(predictive_state()),
        commit_time="2026-07-30T12:00:00+00:00",
    )
