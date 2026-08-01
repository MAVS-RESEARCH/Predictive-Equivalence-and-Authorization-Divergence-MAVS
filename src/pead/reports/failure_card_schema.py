"""Immutable strict-schema FailureCard implementation."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Mapping

from pead.core.hashing import canonical_hash
from pead.core.types import AuthorizationAction, deep_freeze


@dataclass(frozen=True)
class FailureCard:
    failure_card_id: str
    case_or_group_id: str
    run_id: str
    commit_hash: str
    environment_hash: str
    config_hash: str
    method_id: str
    projection_hash: str
    trace_hash: str
    domain_id: str
    mechanism_id: str
    partition_id: str
    atomic_group_id: str
    expected_action: str
    observed_action: str
    visible_evidence_hash: str
    protected_error_type: str
    diagnostic_state: Mapping[str, Any]
    access_profile: str
    scope_contract_id: str
    root_cause_class: str
    root_cause_evidence: tuple[str, ...]
    case_validity_verdict: str
    containment_status: str
    quarantine_status: str
    repair_status: str
    invalidation_status: str
    affected_claim_ids: tuple[str, ...]
    affected_outcome_tiers: tuple[str, ...]
    reproduction_command: str
    artifact_references: tuple[str, ...]

    def __post_init__(self) -> None:
        scalar_names = [field.name for field in fields(self) if field.name not in {"diagnostic_state", "root_cause_evidence", "affected_claim_ids", "affected_outcome_tiers", "artifact_references"}]
        if any(not isinstance(getattr(self, name), str) or not getattr(self, name).strip() for name in scalar_names):
            raise ValueError("FailureCard scalar fields must be nonempty strings")
        if self.expected_action not in {action.value for action in AuthorizationAction} or self.observed_action not in {action.value for action in AuthorizationAction}:
            raise ValueError("FailureCard actions are invalid")
        if not all((self.root_cause_evidence, self.affected_claim_ids, self.affected_outcome_tiers, self.artifact_references)):
            raise ValueError("FailureCard evidence, claims, tiers, and references must be nonempty")
        object.__setattr__(self, "diagnostic_state", deep_freeze(self.diagnostic_state))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "FailureCard":
        expected = {field.name for field in fields(cls)}
        if set(value) != expected:
            raise ValueError(f"FailureCard fields are not strict: missing={sorted(expected-set(value))}; extra={sorted(set(value)-expected)}")
        return cls(**value)

    def content_hash(self) -> str:
        return canonical_hash(self)
