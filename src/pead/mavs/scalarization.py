"""Fixed/learned one-scalar compression and holdout collision audit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from pead.core.hashing import canonical_hash
from pead.core.types import AuthorizationAction
from pead.mavs.ds_cf import DSCFVector


class ScalarizationError(ValueError):
    """Raised when scalarization is unselected or a holdout audit is invalid."""


FIXED_WEIGHTS = {"z_c": 0.05, "z_h": 0.30, "z_s": -0.15, "z_m": 0.15, "z_p": 0.15, "z_o": 0.08, "z_f": 0.12}


@dataclass(frozen=True)
class LearnedScalarArtifact:
    artifact_id: str
    selected_partition: str
    weights: Mapping[str, float]
    intercept: float
    budget_policy_id: str
    underlying_identity_hash: str

    def __post_init__(self) -> None:
        if self.selected_partition != "development_selection":
            raise ScalarizationError("learned scalar must be selected on development_selection")
        if set(self.weights) != set(FIXED_WEIGHTS):
            raise ScalarizationError("learned scalar weight set is incomplete")


def fixed_scalar(vector: DSCFVector) -> float:
    value = 0.5 + sum(FIXED_WEIGHTS[name] * vector.values()[name] for name in FIXED_WEIGHTS)
    return min(1.0, max(0.0, value))


def learned_scalar(vector: DSCFVector, artifact: LearnedScalarArtifact | None) -> float:
    if artifact is None:
        raise ScalarizationError("learned scalarization requires a selected Phase 10 artifact")
    value = artifact.intercept + sum(artifact.weights[name] * vector.values()[name] for name in artifact.weights)
    return min(1.0, max(0.0, value))


@dataclass(frozen=True)
class ScalarCompressionCase:
    case_id: str
    holdout_kind: str
    vector: Mapping[str, float]
    structured_decision: AuthorizationAction


def audit_scalar_compression(
    cases: Iterable[ScalarCompressionCase],
    *,
    decimals: int = 8,
) -> dict[str, object]:
    """Find structural/domain pairs collapsed to one scalar but different decisions."""

    rows = tuple(cases)
    if not rows or {row.holdout_kind for row in rows} != {"structural", "domain"}:
        raise ScalarizationError("scalar compression audit requires structural and domain holdouts")
    buckets: dict[tuple[str, float], list[ScalarCompressionCase]] = {}
    for row in rows:
        missing = set(FIXED_WEIGHTS) - set(row.vector)
        if missing:
            raise ScalarizationError(f"scalar case missing signals: {sorted(missing)}")
        scalar = round(min(1.0, max(0.0, 0.5 + sum(FIXED_WEIGHTS[name] * row.vector[name] for name in FIXED_WEIGHTS))), decimals)
        buckets.setdefault((row.holdout_kind, scalar), []).append(row)
    collisions = []
    for (kind, scalar), members in sorted(buckets.items()):
        decisions = {member.structured_decision for member in members}
        if len(decisions) > 1:
            collisions.append({
                "holdout_kind": kind, "scalar": scalar,
                "case_ids": sorted(member.case_id for member in members),
                "decisions": sorted(decision.value for decision in decisions),
            })
    return {
        "status": "pass", "cases": len(rows), "holdouts": ["domain", "structural"],
        "collision_count": len(collisions), "collisions": collisions,
        "case_identity_sha256": canonical_hash(tuple(sorted(row.case_id for row in rows))),
    }
