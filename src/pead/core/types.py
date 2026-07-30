"""Frozen primary PEAD record schemas."""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from pead.core.hashing import normalize_candidate_action
from pead.core.ids import pair_id, sequence_id, world_id

SCHEMA_VERSION = "1.0"


class RecordValidationError(ValueError):
    """Raised when an immutable primary record is incomplete or invalid."""


class AuthorizationAction(str, Enum):
    ACCEPT = "Accept"
    REJECT = "Reject"
    ESCALATE = "Escalate"


def deep_freeze(value: Any) -> Any:
    """Recursively freeze mutable containers without changing scalar values."""

    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise RecordValidationError("immutable record mapping keys must be strings")
        return MappingProxyType(
            {key: deep_freeze(item) for key, item in value.items()}
        )
    if isinstance(value, Set):
        return frozenset(deep_freeze(item) for item in value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(deep_freeze(item) for item in value)
    return value


def _required_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise RecordValidationError(f"{field_name} must be non-empty")


@dataclass(frozen=True)
class WorldState:
    schema_version: str
    world_id: str
    task_truth: Any
    candidate_action: Mapping[str, Any]
    provenance_graph: Mapping[str, Any]
    authority_state: Mapping[str, Any]
    policy_state: Mapping[str, Any]
    temporal_state: Mapping[str, Any]
    consequence_state: Mapping[str, Any]
    evidence_state: Mapping[str, Any]
    predictive_outputs: Mapping[str, Any]
    nuisance_state: Mapping[str, Any]
    hidden_mechanism: str
    generator_lineage: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise RecordValidationError("WorldState schema_version must be 1.0")
        _required_text(self.world_id, "world_id")
        _required_text(self.hidden_mechanism, "hidden_mechanism")
        object.__setattr__(
            self, "candidate_action", deep_freeze(normalize_candidate_action(self.candidate_action))
        )
        for name in (
            "provenance_graph",
            "authority_state",
            "policy_state",
            "temporal_state",
            "consequence_state",
            "evidence_state",
            "predictive_outputs",
            "nuisance_state",
            "generator_lineage",
        ):
            object.__setattr__(self, name, deep_freeze(getattr(self, name)))

    @classmethod
    def create(cls, **fields: Any) -> "WorldState":
        payload = {"schema_version": SCHEMA_VERSION, **fields}
        return cls(world_id=world_id(payload), **payload)


@dataclass(frozen=True)
class PredictiveState:
    schema_version: str
    shared_representation: Any
    specialist_outputs: tuple[Any, ...]
    signed_support: tuple[Any, ...]
    predicted_label: Any
    confidence: Any
    uncertainty: Any
    agreement: Any
    calibration: Any
    candidate_action: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise RecordValidationError("PredictiveState schema_version must be 1.0")
        for name in (
            "shared_representation",
            "specialist_outputs",
            "signed_support",
            "agreement",
            "calibration",
        ):
            object.__setattr__(self, name, deep_freeze(getattr(self, name)))
        object.__setattr__(
            self, "candidate_action", deep_freeze(normalize_candidate_action(self.candidate_action))
        )


@dataclass(frozen=True)
class GovernanceState:
    schema_version: str
    provenance: Mapping[str, Any]
    authority: Mapping[str, Any]
    policy: Mapping[str, Any]
    temporal: Mapping[str, Any]
    reversibility: Mapping[str, Any]
    consequence: Mapping[str, Any]
    evidence_availability: Mapping[str, Any]
    dependency_graph: Mapping[str, Any]
    counterfactual_views: tuple[Any, ...]

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise RecordValidationError("GovernanceState schema_version must be 1.0")
        for name in (
            "provenance",
            "authority",
            "policy",
            "temporal",
            "reversibility",
            "consequence",
            "evidence_availability",
            "dependency_graph",
            "counterfactual_views",
        ):
            object.__setattr__(self, name, deep_freeze(getattr(self, name)))


@dataclass(frozen=True)
class OracleState:
    schema_version: str
    latent_governance_truth: Mapping[str, Any]
    rule_inputs: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise RecordValidationError("OracleState schema_version must be 1.0")
        object.__setattr__(
            self, "latent_governance_truth", deep_freeze(self.latent_governance_truth)
        )
        object.__setattr__(self, "rule_inputs", deep_freeze(self.rule_inputs))


@dataclass(frozen=True)
class AuthorizationLabel:
    schema_version: str
    action: AuthorizationAction
    reason_class: str
    rule_lineage: tuple[str, ...]
    ambiguity_basis: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise RecordValidationError("AuthorizationLabel schema_version must be 1.0")
        _required_text(self.reason_class, "reason_class")
        if not self.rule_lineage:
            raise RecordValidationError("rule_lineage must be non-empty")


@dataclass(frozen=True)
class CaseRecord:
    schema_version: str
    case_id: str
    world_id: str
    predictive_hash: str
    governance_hash: str
    oracle_hash: str
    label_hash: str
    split_id: str
    atomic_group_id: str
    lineage: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise RecordValidationError("CaseRecord schema_version must be 1.0")
        for name in (
            "case_id",
            "world_id",
            "predictive_hash",
            "governance_hash",
            "oracle_hash",
            "label_hash",
            "split_id",
            "atomic_group_id",
        ):
            _required_text(getattr(self, name), name)
        object.__setattr__(self, "lineage", deep_freeze(self.lineage))


@dataclass(frozen=True)
class PairRecord:
    schema_version: str
    pair_id: str
    track_id: str
    world_a_id: str
    world_b_id: str
    predictive_hash_a: str
    predictive_hash_b: str
    governance_hash_a: str
    governance_hash_b: str
    distance_p: Any
    intervention_id: str
    intervention_proof: Mapping[str, Any]
    label_a: AuthorizationAction
    label_b: AuthorizationAction
    label_reason_a: Mapping[str, Any]
    label_reason_b: Mapping[str, Any]
    split_id: str
    leakage_audit_id: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise RecordValidationError("PairRecord schema_version must be 1.0")
        for name in (
            "pair_id",
            "track_id",
            "world_a_id",
            "world_b_id",
            "predictive_hash_a",
            "predictive_hash_b",
            "governance_hash_a",
            "governance_hash_b",
            "intervention_id",
            "split_id",
            "leakage_audit_id",
        ):
            _required_text(getattr(self, name), name)
        object.__setattr__(self, "intervention_proof", deep_freeze(self.intervention_proof))
        object.__setattr__(self, "label_reason_a", deep_freeze(self.label_reason_a))
        object.__setattr__(self, "label_reason_b", deep_freeze(self.label_reason_b))

    @classmethod
    def create(cls, **fields: Any) -> "PairRecord":
        payload = {"schema_version": SCHEMA_VERSION, **fields}
        return cls(pair_id=pair_id(payload), **payload)


@dataclass(frozen=True)
class SequenceRecord:
    schema_version: str
    sequence_id: str
    world_ids: tuple[str, ...]
    timestamps: tuple[str, ...]
    authorization_labels: tuple[AuthorizationAction, ...]
    reversal_indices: tuple[int, ...]
    lineage: Mapping[str, Any]
    split_id: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise RecordValidationError("SequenceRecord schema_version must be 1.0")
        if not self.world_ids or len(self.world_ids) != len(self.timestamps):
            raise RecordValidationError("world_ids and timestamps must be non-empty and aligned")
        if len(self.world_ids) != len(self.authorization_labels):
            raise RecordValidationError("authorization_labels must align with worlds")
        if any(index <= 0 or index >= len(self.world_ids) for index in self.reversal_indices):
            raise RecordValidationError("reversal_indices contain an out-of-range index")
        object.__setattr__(self, "lineage", deep_freeze(self.lineage))

    @classmethod
    def create(cls, **fields: Any) -> "SequenceRecord":
        payload = {"schema_version": SCHEMA_VERSION, **fields}
        return cls(sequence_id=sequence_id(payload), **payload)


@dataclass(frozen=True)
class ScopeContract:
    schema_version: str
    diagnostic_id: str
    failure_family: str
    context: str
    response: str
    influence: tuple[str, ...]
    positive_generator: str
    negative_generator: str
    boundary_generator: str
    out_of_scope_generator: str
    monotonicity_rules: str
    maximum_authority: str
    version: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise RecordValidationError("ScopeContract schema_version must be 1.0")
        for name in (
            "diagnostic_id",
            "failure_family",
            "context",
            "response",
            "positive_generator",
            "negative_generator",
            "boundary_generator",
            "out_of_scope_generator",
            "monotonicity_rules",
            "maximum_authority",
            "version",
        ):
            _required_text(getattr(self, name), name)
        if not self.influence:
            raise RecordValidationError("influence must be non-empty")


@dataclass(frozen=True)
class MethodDecision:
    schema_version: str
    decision: AuthorizationAction
    decision_scores: Mapping[str, Any]
    operating_point_id: str
    rationale: str
    diagnostic_trace: Mapping[str, Any]
    resource_usage: Mapping[str, Any]
    visible_projection_hash: str
    commit_time: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise RecordValidationError("MethodDecision schema_version must be 1.0")
        for name in (
            "operating_point_id",
            "rationale",
            "visible_projection_hash",
            "commit_time",
        ):
            _required_text(getattr(self, name), name)
        if not self.decision_scores:
            raise RecordValidationError("decision_scores must be non-empty")
        object.__setattr__(self, "decision_scores", deep_freeze(self.decision_scores))
        object.__setattr__(self, "diagnostic_trace", deep_freeze(self.diagnostic_trace))
        object.__setattr__(self, "resource_usage", deep_freeze(self.resource_usage))


@dataclass(frozen=True)
class AuditRecord:
    schema_version: str
    audit_id: str
    gate_id: str
    severity: str
    status: str
    evidence_pointers: tuple[str, ...]
    invalidation_scope: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise RecordValidationError("AuditRecord schema_version must be 1.0")
        for name in ("audit_id", "gate_id", "severity", "status"):
            _required_text(getattr(self, name), name)
        if not self.evidence_pointers:
            raise RecordValidationError("evidence_pointers must be non-empty")
