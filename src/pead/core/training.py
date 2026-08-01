"""Deterministic, role-isolated model selection and checkpoint controls."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash

ROLE_ORDER = (
    "development_fit",
    "development_selection",
    "calibration_fit",
    "calibration_policy",
    "public_validation",
)
NEURAL_SEEDS = (101, 211, 307)


class TrainingContractError(ValueError):
    """Raised when model-development role isolation is violated."""


@dataclass(frozen=True)
class TrainingRow:
    case_id: str
    world_id: str
    atomic_group_id: str
    partition: str
    projection_hash: str
    features: Any
    label: str


@dataclass(frozen=True)
class CheckpointCandidate:
    checkpoint_id: str
    method_id: str
    seed: int
    mean_utility: float
    worst_seed_utility: float
    parameters: int
    resource_cost: float
    payload_hash: str
    selection_partition: str = "development_selection"


def deterministic_rows(
    rows: Iterable[TrainingRow], *, seed: int
) -> tuple[TrainingRow, ...]:
    """Return a seed-stable order without changing group membership."""

    ordered = sorted(rows, key=lambda row: (row.atomic_group_id, row.case_id))
    generator = random.Random(seed)
    groups: dict[str, list[TrainingRow]] = {}
    for row in ordered:
        groups.setdefault(row.atomic_group_id, []).append(row)
    group_ids = sorted(groups)
    generator.shuffle(group_ids)
    return tuple(row for group_id in group_ids for row in groups[group_id])


def audit_role_isolation(rows: Iterable[TrainingRow]) -> dict[str, Any]:
    """Prove world/case/group identities do not cross development roles."""

    material = tuple(rows)
    unknown = sorted({row.partition for row in material} - set(ROLE_ORDER))
    if unknown:
        raise TrainingContractError(f"unknown development roles: {unknown}")
    for identity_name in ("case_id", "world_id", "atomic_group_id"):
        observed: dict[str, str] = {}
        for row in material:
            identity = str(getattr(row, identity_name))
            prior = observed.setdefault(identity, row.partition)
            if prior != row.partition:
                raise TrainingContractError(
                    f"{identity_name} {identity} crosses {prior} and {row.partition}"
                )
    return {"status": "pass", "rows": len(material), "roles": sorted({row.partition for row in material})}


def assert_projection_alignment(
    profiles: Mapping[str, Iterable[TrainingRow]],
) -> dict[str, Any]:
    """Require identical identities across P-only, Raw-G, and Oracle-G."""

    required = {"P-only", "Raw-G", "Oracle-G"}
    if set(profiles) != required:
        raise TrainingContractError("all three registered access profiles are required")
    def identities(rows: Iterable[TrainingRow]) -> set[tuple[str, str, str, str]]:
        return {(row.world_id, row.case_id, row.atomic_group_id, row.partition) for row in rows}
    sets = {profile: identities(rows) for profile, rows in profiles.items()}
    first = sets["P-only"]
    if any(values != first for values in sets.values()):
        raise TrainingContractError("underlying identities differ across projections")
    return {"status": "pass", "identities": len(first), "only_projection_differs": True}


def select_checkpoint(
    candidates: Iterable[CheckpointCandidate],
    *,
    console: ResearchConsole,
) -> CheckpointCandidate:
    """Apply mean, worst-seed, parameter, and resource tie-breaks exactly."""

    options = tuple(candidates)
    if not options or any(item.selection_partition != "development_selection" for item in options):
        raise TrainingContractError("checkpoint selection requires development_selection")
    # STEP LOG P7-TRAINING-001: Freeze one checkpoint using only development_selection and the registered tie-break order.
    console.log(
        "P7-TRAINING-001",
        "Selecting checkpoint on development_selection.",
        details={"candidates": len(options)},
    )
    return max(
        options,
        key=lambda item: (
            item.mean_utility,
            item.worst_seed_utility,
            -item.parameters,
            -item.resource_cost,
            item.checkpoint_id,
        ),
    )


def checkpoint_manifest(
    selected: CheckpointCandidate,
    history: Iterable[Mapping[str, Any]],
    *,
    package_environment: Mapping[str, Any],
) -> dict[str, Any]:
    """Create a complete immutable selection record without writing model bytes."""

    trials = tuple(dict(item) for item in history)
    if not trials:
        raise TrainingContractError("complete hyperparameter history is required")
    manifest = {
        "schema_version": "1.0",
        "selected": selected.__dict__,
        "hyperparameter_history": trials,
        "environment": dict(package_environment),
    }
    return {**manifest, "manifest_hash": canonical_hash(manifest)}


def assert_holdout_immutable(before: Path, after: Path) -> None:
    """Reject any development/public process that changes a holdout contract."""

    if before.read_bytes() != after.read_bytes():
        raise TrainingContractError("development or public metrics changed a holdout definition")
