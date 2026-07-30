"""Strict, immutable authorization result and quarantine records."""

from __future__ import annotations

from dataclasses import dataclass

from pead.core.hashing import canonical_hash
from pead.core.types import AuthorizationAction


@dataclass(frozen=True)
class LabelEvaluation:
    schema_version: str
    label: AuthorizationAction
    reason_class: str
    satisfied_constraints: tuple[str, ...]
    violated_constraints: tuple[str, ...]
    ambiguity_basis: tuple[str, ...]
    rule_lineage: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("LabelEvaluation schema_version must be 1.0")
        if not self.reason_class:
            raise ValueError("reason_class must be non-empty")
        if not self.rule_lineage:
            raise ValueError("rule_lineage must be non-empty")
        for name in (
            "satisfied_constraints",
            "violated_constraints",
            "ambiguity_basis",
            "rule_lineage",
        ):
            values = getattr(self, name)
            if len(values) != len(set(values)):
                raise ValueError(f"{name} contains duplicate identities")

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self)


@dataclass(frozen=True)
class LabelDisagreement:
    schema_version: str
    case_id: str
    policy_id: str
    dsl_hash: str
    reference_hash: str
    status: str
    invalidation_scope: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("LabelDisagreement schema_version must be 1.0")
        if self.status != "quarantined":
            raise ValueError("a label disagreement must be quarantined")
        if not self.invalidation_scope:
            raise ValueError("label disagreement requires invalidation scope")


def quarantine_disagreement(
    *,
    case_id: str,
    policy_id: str,
    dsl_result: LabelEvaluation,
    reference_result: LabelEvaluation,
    invalidation_scope: tuple[str, ...],
) -> LabelDisagreement | None:
    """Return a release-blocking quarantine record for any non-identical result."""

    if dsl_result == reference_result:
        return None
    return LabelDisagreement(
        schema_version="1.0",
        case_id=case_id,
        policy_id=policy_id,
        dsl_hash=dsl_result.evaluation_hash,
        reference_hash=reference_result.evaluation_hash,
        status="quarantined",
        invalidation_scope=invalidation_scope,
    )
