"""Typed Phase 0 configuration contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


class ConfigValidationError(ValueError):
    """Raised when a frozen research configuration violates its contract."""


def require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigValidationError(f"{path} must be a mapping")
    return value


def require_sequence(value: Any, path: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ConfigValidationError(f"{path} must be a sequence")
    return value


def require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigValidationError(f"{path} must be a non-empty string")
    return value


def require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigValidationError(f"{path} must be a boolean")
    return value


def require_keys(mapping: Mapping[str, Any], keys: Iterable[str], path: str) -> None:
    missing = sorted(set(keys) - set(mapping))
    if missing:
        raise ConfigValidationError(f"{path} is missing required keys: {missing}")


def require_unique(values: Iterable[str], path: str) -> None:
    observed: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in observed:
            duplicates.add(value)
        observed.add(value)
    if duplicates:
        raise ConfigValidationError(f"{path} contains duplicate identifiers: {sorted(duplicates)}")


@dataclass(frozen=True)
class StateField:
    stable_id: str
    name: str
    semantic_definition: str
    data_type: str
    shape: str
    units_or_range: str
    canonicalization: str
    visibility: tuple[str, ...]
    hashing_rule: str
    near_distance_rule: str
    exact_twin_equal: bool
    missing_value_rule: str
    permitted_transformations: tuple[str, ...]
    prohibited_derived_information: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Any, path: str) -> "StateField":
        data = require_mapping(value, path)
        required = (
            "stable_id",
            "name",
            "semantic_definition",
            "data_type",
            "shape",
            "units_or_range",
            "canonicalization",
            "visibility",
            "hashing_rule",
            "near_distance_rule",
            "exact_twin_equal",
            "missing_value_rule",
            "permitted_transformations",
            "prohibited_derived_information",
        )
        require_keys(data, required, path)
        return cls(
            stable_id=require_string(data["stable_id"], f"{path}.stable_id"),
            name=require_string(data["name"], f"{path}.name"),
            semantic_definition=require_string(
                data["semantic_definition"], f"{path}.semantic_definition"
            ),
            data_type=require_string(data["data_type"], f"{path}.data_type"),
            shape=require_string(data["shape"], f"{path}.shape"),
            units_or_range=require_string(data["units_or_range"], f"{path}.units_or_range"),
            canonicalization=require_string(
                data["canonicalization"], f"{path}.canonicalization"
            ),
            visibility=tuple(
                require_string(item, f"{path}.visibility")
                for item in require_sequence(data["visibility"], f"{path}.visibility")
            ),
            hashing_rule=require_string(data["hashing_rule"], f"{path}.hashing_rule"),
            near_distance_rule=require_string(
                data["near_distance_rule"], f"{path}.near_distance_rule"
            ),
            exact_twin_equal=require_bool(
                data["exact_twin_equal"], f"{path}.exact_twin_equal"
            ),
            missing_value_rule=require_string(
                data["missing_value_rule"], f"{path}.missing_value_rule"
            ),
            permitted_transformations=tuple(
                require_string(item, f"{path}.permitted_transformations")
                for item in require_sequence(
                    data["permitted_transformations"], f"{path}.permitted_transformations"
                )
            ),
            prohibited_derived_information=tuple(
                require_string(item, f"{path}.prohibited_derived_information")
                for item in require_sequence(
                    data["prohibited_derived_information"],
                    f"{path}.prohibited_derived_information",
                )
            ),
        )


@dataclass(frozen=True)
class MethodEntry:
    method_id: str
    family: str
    access_profile: str
    training_status: str
    implementation_file: str
    fidelity_class: str
    mandatory_tracks: tuple[str, ...]
    compute_class: str
    method_card_id: str
    reporting_role: str

    @classmethod
    def from_mapping(cls, value: Any, path: str) -> "MethodEntry":
        data = require_mapping(value, path)
        required = (
            "method_id",
            "family",
            "access_profile",
            "training_status",
            "implementation_file",
            "fidelity_class",
            "mandatory_tracks",
            "compute_class",
            "method_card_id",
            "reporting_role",
        )
        require_keys(data, required, path)
        return cls(
            method_id=require_string(data["method_id"], f"{path}.method_id"),
            family=require_string(data["family"], f"{path}.family"),
            access_profile=require_string(
                data["access_profile"], f"{path}.access_profile"
            ),
            training_status=require_string(
                data["training_status"], f"{path}.training_status"
            ),
            implementation_file=require_string(
                data["implementation_file"], f"{path}.implementation_file"
            ),
            fidelity_class=require_string(
                data["fidelity_class"], f"{path}.fidelity_class"
            ),
            mandatory_tracks=tuple(
                require_string(item, f"{path}.mandatory_tracks")
                for item in require_sequence(
                    data["mandatory_tracks"], f"{path}.mandatory_tracks"
                )
            ),
            compute_class=require_string(data["compute_class"], f"{path}.compute_class"),
            method_card_id=require_string(
                data["method_card_id"], f"{path}.method_card_id"
            ),
            reporting_role=require_string(
                data["reporting_role"], f"{path}.reporting_role"
            ),
        )


@dataclass(frozen=True)
class RequirementEntry:
    requirement_id: str
    source_locator: str
    exact_source_clause: str
    source_clause_sha256: str
    normative_class: str
    phases: tuple[str, ...]
    files: tuple[str, ...]
    tests: tuple[str, ...]
    produced_artifact: str
    release_failure_condition: str
    affected_claims: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Any, path: str) -> "RequirementEntry":
        data = require_mapping(value, path)
        required = (
            "requirement_id",
            "source_locator",
            "exact_source_clause",
            "source_clause_sha256",
            "normative_class",
            "phases",
            "files",
            "tests",
            "produced_artifact",
            "release_failure_condition",
            "affected_claims",
        )
        require_keys(data, required, path)
        return cls(
            requirement_id=require_string(
                data["requirement_id"], f"{path}.requirement_id"
            ),
            source_locator=require_string(
                data["source_locator"], f"{path}.source_locator"
            ),
            exact_source_clause=require_string(
                data["exact_source_clause"], f"{path}.exact_source_clause"
            ),
            source_clause_sha256=require_string(
                data["source_clause_sha256"], f"{path}.source_clause_sha256"
            ),
            normative_class=require_string(
                data["normative_class"], f"{path}.normative_class"
            ),
            phases=tuple(
                str(item)
                for item in require_sequence(data["phases"], f"{path}.phases")
            ),
            files=tuple(
                require_string(item, f"{path}.files")
                for item in require_sequence(data["files"], f"{path}.files")
            ),
            tests=tuple(
                require_string(item, f"{path}.tests")
                for item in require_sequence(data["tests"], f"{path}.tests")
            ),
            produced_artifact=require_string(
                data["produced_artifact"], f"{path}.produced_artifact"
            ),
            release_failure_condition=require_string(
                data["release_failure_condition"],
                f"{path}.release_failure_condition",
            ),
            affected_claims=tuple(
                require_string(item, f"{path}.affected_claims")
                for item in require_sequence(
                    data["affected_claims"], f"{path}.affected_claims"
                )
            ),
        )
