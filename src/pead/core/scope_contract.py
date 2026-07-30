"""Executable scope-contract invariants for Diagnostic Sciences cases."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pead.core.diagnostic_registry import DiagnosticDefinition
from pead.core.types import AuthorizationAction


class ScopeContractError(ValueError):
    """Raised when a diagnostic case exceeds frozen scope or authority."""


class ScopeBank(str, Enum):
    SCOPE_POSITIVE = "scope_positive"
    MATCHED_NEGATIVE = "matched_negative"
    BOUNDARY = "boundary"
    ADVERSARIAL_OUT_OF_SCOPE = "adversarial_out_of_scope"
    COMPOSITION = "composition"
    NUISANCE = "nuisance"
    PRIOR_SHIFT = "prior_shift"
    LABEL_PERMUTATION = "label_permutation"


@dataclass(frozen=True)
class ScopedDiagnosticCase:
    schema_version: str
    case_id: str
    domain_id: str
    diagnostic_id: str
    bank: ScopeBank
    definition_hash: str
    generator_semantics: str
    in_scope: bool
    target_truth: bool
    surface_pattern_present: bool
    boundary_distance: float | None
    expected_activation: str
    expected_influence_paths: tuple[str, ...]
    prohibited_influence_paths: tuple[str, ...]
    maximum_authority: str
    truth_hash_before: str
    truth_hash_after: str
    authorization_before: AuthorizationAction
    authorization_after: AuthorizationAction
    composition_partner: str | None
    nuisance_identity: str | None
    atomic_group_id: str
    split_id: str

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise ScopeContractError("scope case schema_version must be 1.0")
        if not all(
            isinstance(value, str) and value
            for value in (
                self.case_id,
                self.domain_id,
                self.diagnostic_id,
                self.definition_hash,
                self.generator_semantics,
                self.expected_activation,
                self.maximum_authority,
                self.truth_hash_before,
                self.truth_hash_after,
                self.atomic_group_id,
                self.split_id,
            )
        ):
            raise ScopeContractError("scope case identities must be non-empty")


def validate_scoped_case(
    case: ScopedDiagnosticCase,
    definition: DiagnosticDefinition,
) -> None:
    if (
        case.diagnostic_id != definition.diagnostic_id
        or case.definition_hash != definition.definition_hash
        or case.maximum_authority != definition.maximum_authority
        or case.prohibited_influence_paths
        != definition.prohibited_influence_paths
    ):
        raise ScopeContractError("case invents or changes diagnostic semantics")
    if not set(case.expected_influence_paths) <= set(
        definition.permitted_influence_paths
    ):
        raise ScopeContractError("case uses an unregistered influence path")
    if set(case.expected_influence_paths) & set(
        definition.prohibited_influence_paths
    ):
        raise ScopeContractError("case uses a prohibited influence path")
    if case.bank is ScopeBank.SCOPE_POSITIVE:
        if not case.in_scope or not case.target_truth:
            raise ScopeContractError("scope-positive case lacks in-scope truth")
    elif case.bank is ScopeBank.MATCHED_NEGATIVE:
        if not case.in_scope or case.target_truth:
            raise ScopeContractError("matched negative has target truth")
    elif case.bank is ScopeBank.BOUNDARY:
        if not case.in_scope or case.boundary_distance is None:
            raise ScopeContractError("boundary case lacks signed scope distance")
    elif case.bank is ScopeBank.ADVERSARIAL_OUT_OF_SCOPE:
        if (
            case.in_scope
            or case.target_truth
            or not case.surface_pattern_present
            or case.expected_influence_paths
            or case.truth_hash_before != case.truth_hash_after
            or case.authorization_before is not case.authorization_after
        ):
            raise ScopeContractError(
                "out-of-scope case changes truth or terminal authorization"
            )
    elif case.bank is ScopeBank.COMPOSITION:
        if case.composition_partner not in definition.interaction_partners:
            raise ScopeContractError("composition partner is not registered")
    else:
        if (
            case.truth_hash_before != case.truth_hash_after
            or case.authorization_before is not case.authorization_after
        ):
            raise ScopeContractError(
                "matched scope control changed meaning or authorization"
            )
    if (
        case.diagnostic_id == "DSCF-ZC-v1"
        and case.maximum_authority != "observation-only"
    ):
        raise ScopeContractError("raw correlation acquired terminal authority")
