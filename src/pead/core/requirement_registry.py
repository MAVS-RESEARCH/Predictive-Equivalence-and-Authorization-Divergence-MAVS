"""Typed clause-level requirement registry."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Mapping

from pead.config.models import RequirementEntry
from pead.core.config import load_config
from pead.core.registry import FrozenRegistry, RegistryValidationError

_TRACEABILITY_FIELDS = (
    "phases",
    "files",
    "tests",
    "produced_artifact",
    "release_failure_condition",
    "affected_claims",
)


def _validate_traceability(data: Mapping[str, Any]) -> None:
    for key in _TRACEABILITY_FIELDS:
        value = data.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            if not value or any(not str(item).strip() for item in value):
                raise RegistryValidationError(f"requirement {key} must be non-empty")
        elif not isinstance(value, str) or not value.strip():
            raise RegistryValidationError(f"requirement {key} must be non-empty")


def requirement_entry_from_mapping(
    data: Mapping[str, Any], path: str = "requirement"
) -> RequirementEntry:
    """Validate traceability before constructing one immutable requirement."""

    _validate_traceability(data)
    try:
        return RequirementEntry.from_mapping(data, path)
    except ValueError as exc:
        raise RegistryValidationError(str(exc)) from exc


def load_requirement_registry(
    repository_root: Path,
) -> FrozenRegistry[RequirementEntry]:
    loaded = load_config(
        repository_root, Path("configs/requirements/pead_v1_requirements.yaml")
    )
    data = loaded.data
    if data.get("schema_version") != "1.0":
        raise RegistryValidationError("requirement registry must be version 1.0")
    requirements = data.get("requirements")
    if not isinstance(requirements, tuple) or not requirements:
        raise RegistryValidationError("requirements must be a non-empty sequence")
    entries: list[RequirementEntry] = []
    for index, raw in enumerate(requirements):
        if not isinstance(raw, Mapping):
            raise RegistryValidationError(f"requirement {index} must be a mapping")
        entries.append(
            requirement_entry_from_mapping(raw, f"requirements[{index}]")
        )
    return FrozenRegistry(
        registry_id=str(data.get("registry_id", "")),
        entries=entries,
        identity=lambda entry: entry.requirement_id,
    )
