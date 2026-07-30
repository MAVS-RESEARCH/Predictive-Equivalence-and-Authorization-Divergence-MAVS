"""Typed Diagnostic Sciences scope and authority registry."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Mapping

from pead.core.config import load_config
from pead.core.registry import FrozenRegistry, RegistryValidationError
from pead.core.types import ScopeContract

_REQUIRED_FIELDS = {
    "schema_version",
    "diagnostic_id",
    "semantic_name",
    "version",
    "status",
    "failure_family",
    "applicable_context",
    "target_condition",
    "prescribed_response",
    "permitted_influence_paths",
    "prohibited_influence_paths",
    "maximum_authority",
    "generators",
    "monotonicity_contract",
    "interaction_partners",
    "metrics",
    "retirement_rule",
}
_GENERATOR_FIELDS = {
    "positive",
    "matched_negative",
    "boundary",
    "adversarial_out_of_scope",
}
_AUTHORITY_LEVELS = {
    "observation-only",
    "soft-evidence",
    "bounded-mitigation",
    "threshold-pressure",
    "conjunctive-veto-input",
    "hard-veto",
}


def _require_text(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RegistryValidationError(f"diagnostic {key} must be non-empty")
    return value


def scope_contract_from_mapping(data: Mapping[str, Any]) -> ScopeContract:
    missing = sorted(_REQUIRED_FIELDS - set(data))
    if missing:
        raise RegistryValidationError(f"diagnostic missing required fields: {missing}")
    if data.get("schema_version") != "1.0":
        raise RegistryValidationError("diagnostic schema_version must be 1.0")
    generators = data["generators"]
    if not isinstance(generators, Mapping):
        raise RegistryValidationError("diagnostic generators must be a mapping")
    missing_generators = sorted(_GENERATOR_FIELDS - set(generators))
    if missing_generators:
        raise RegistryValidationError(
            f"diagnostic missing generators: {missing_generators}"
        )
    influence = data["permitted_influence_paths"]
    prohibited = data["prohibited_influence_paths"]
    if isinstance(influence, (str, bytes)) or not isinstance(influence, Sequence) or not influence:
        raise RegistryValidationError("diagnostic requires permitted influence paths")
    if (
        isinstance(prohibited, (str, bytes))
        or not isinstance(prohibited, Sequence)
        or not prohibited
    ):
        raise RegistryValidationError("diagnostic requires prohibited influence paths")
    if set(influence) & set(prohibited):
        raise RegistryValidationError("permitted and prohibited influence paths overlap")
    authority = _require_text(data, "maximum_authority")
    if authority not in _AUTHORITY_LEVELS:
        raise RegistryValidationError(f"unknown diagnostic authority: {authority}")
    return ScopeContract(
        schema_version="1.0",
        diagnostic_id=_require_text(data, "diagnostic_id"),
        failure_family=_require_text(data, "failure_family"),
        context=_require_text(data, "applicable_context"),
        response=_require_text(data, "prescribed_response"),
        influence=tuple(str(item) for item in influence),
        positive_generator=_require_text(generators, "positive"),
        negative_generator=_require_text(generators, "matched_negative"),
        boundary_generator=_require_text(generators, "boundary"),
        out_of_scope_generator=_require_text(generators, "adversarial_out_of_scope"),
        monotonicity_rules=_require_text(data, "monotonicity_contract"),
        maximum_authority=authority,
        version=_require_text(data, "version"),
    )


def load_diagnostic_registry(repository_root: Path) -> FrozenRegistry[ScopeContract]:
    diagnostic_dir = repository_root / "configs" / "diagnostics"
    paths = sorted(
        path for path in diagnostic_dir.glob("*.yaml") if path.name != "schema.yaml"
    )
    entries = [
        scope_contract_from_mapping(load_config(repository_root, path).data)
        for path in paths
    ]
    return FrozenRegistry(
        registry_id="PEAD-DIAGNOSTICS-v1",
        entries=entries,
        identity=lambda entry: entry.diagnostic_id,
    )
