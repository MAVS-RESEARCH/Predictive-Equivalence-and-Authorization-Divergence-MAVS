"""Projection-only execution with commit-before-reveal enforcement."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash
from pead.core.traces import DecisionTrace
from pead.core.types import (
    AuthorizationLabel,
    GovernanceState,
    MethodDecision,
    OracleState,
    PredictiveState,
    WorldState,
)


class RunnerContractError(ValueError):
    """Raised when access or execution chronology is violated."""


@dataclass(frozen=True)
class SealedProjection:
    schema_version: str
    access_profile: str
    payload: PredictiveState | tuple[PredictiveState, GovernanceState] | tuple[
        PredictiveState, GovernanceState, OracleState
    ]
    projection_hash: str

    @classmethod
    def create(
        cls,
        *,
        access_profile: str,
        payload: PredictiveState | tuple[PredictiveState, GovernanceState] | tuple[
            PredictiveState, GovernanceState, OracleState
        ],
    ) -> "SealedProjection":
        if access_profile not in {"P-only", "Raw-G", "Oracle-G"}:
            raise RunnerContractError("unknown access profile")
        if isinstance(payload, WorldState):
            raise RunnerContractError("WorldState cannot be sealed as method input")
        valid_shape = (
            access_profile == "P-only"
            and isinstance(payload, PredictiveState)
            or access_profile == "Raw-G"
            and isinstance(payload, tuple)
            and len(payload) == 2
            and isinstance(payload[0], PredictiveState)
            and isinstance(payload[1], GovernanceState)
            or access_profile == "Oracle-G"
            and isinstance(payload, tuple)
            and len(payload) == 3
            and isinstance(payload[0], PredictiveState)
            and isinstance(payload[1], GovernanceState)
            and isinstance(payload[2], OracleState)
        )
        if not valid_shape:
            raise RunnerContractError(
                f"projection payload does not match access profile {access_profile}"
            )
        return cls(
            schema_version="1.0",
            access_profile=access_profile,
            payload=payload,
            projection_hash=canonical_hash(payload),
        )


def run_committed_case(
    *,
    projection: SealedProjection,
    method: Callable[[SealedProjection], MethodDecision],
    reveal_label: Callable[[str], AuthorizationLabel],
    trace_context: Mapping[str, str],
    console: ResearchConsole,
    clock: Callable[[], str] | None = None,
) -> tuple[MethodDecision, AuthorizationLabel, DecisionTrace]:
    """Execute a method, commit its decision, then reveal the hidden label."""

    required_context = {
        "study_id",
        "run_id",
        "config_hash",
        "commit_hash",
        "environment_hash",
        "world_id",
        "atomic_group_id",
        "split_id",
        "method_id",
        "budget_id",
    }
    if set(trace_context) != required_context:
        raise RunnerContractError("trace_context fields are incomplete")
    # STEP LOG P1-RUNNER-001: Admit only a sealed registered method projection.
    console.log(
        "P1-RUNNER-001",
        "Sealed projection admitted for method execution.",
        details={
            "access_profile": projection.access_profile,
            "projection_hash": projection.projection_hash,
        },
    )
    decision = method(projection)
    if not isinstance(decision, MethodDecision):
        raise RunnerContractError("method must return MethodDecision")
    if decision.visible_projection_hash != projection.projection_hash:
        raise RunnerContractError("method decision references a different projection")
    decision_hash = canonical_hash(decision)
    # STEP LOG P1-RUNNER-002: Commit the complete method decision before label access.
    console.log(
        "P1-RUNNER-002",
        "Method decision committed before hidden-label access.",
        details={"decision_hash": decision_hash},
    )
    reveal_time = (
        clock()
        if clock is not None
        else datetime.now().astimezone().isoformat(timespec="microseconds")
    )
    try:
        commit_timestamp = datetime.fromisoformat(
            decision.commit_time.replace("Z", "+00:00")
        )
        reveal_timestamp = datetime.fromisoformat(reveal_time.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RunnerContractError("commit and reveal clocks must be ISO-8601") from exc
    if commit_timestamp.tzinfo is None or reveal_timestamp.tzinfo is None:
        raise RunnerContractError("commit and reveal clocks require offsets")
    if reveal_timestamp < commit_timestamp:
        raise RunnerContractError("label reveal clock precedes decision commit")
    label = reveal_label(decision_hash)
    if not isinstance(label, AuthorizationLabel):
        raise RunnerContractError("label reveal must return AuthorizationLabel")
    # STEP LOG P1-RUNNER-003: Reveal the hidden label only against the decision commitment.
    console.log(
        "P1-RUNNER-003",
        "Hidden label revealed against committed decision.",
        details={"decision_hash": decision_hash, "label_hash": canonical_hash(label)},
    )
    trace = DecisionTrace(
        schema_version="1.0",
        projection_hash=projection.projection_hash,
        decision_hash=decision_hash,
        decision_commit_time=decision.commit_time,
        label_hash=canonical_hash(label),
        label_reveal_time=reveal_time,
        resource_usage=decision.resource_usage,
        **trace_context,
    )
    # STEP LOG P1-RUNNER-004: Seal the ordered decision and reveal evidence into a trace.
    console.log(
        "P1-RUNNER-004",
        "Ordered decision trace constructed.",
        details={"trace_hash": canonical_hash(trace)},
    )
    return decision, label, trace
