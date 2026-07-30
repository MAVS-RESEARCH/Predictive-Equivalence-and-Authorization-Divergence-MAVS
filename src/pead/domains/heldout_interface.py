"""Nonrevealing D7/D8 placeholder interface; no custody implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from pead.core.config import load_config
from pead.core.hashing import canonical_hash
from pead.domains.base import DomainContractError, universal_projection_signature


@dataclass(frozen=True)
class HeldOutPlaceholderContract:
    schema_version: str
    registry_id: str
    placeholder_ids: tuple[str, ...]
    task_shape: Mapping[str, str]
    candidate_shape: Mapping[str, str]
    mechanism_shape: Mapping[str, str]
    projection_signature: tuple[tuple[str, str], ...]
    validation_shape: Mapping[str, str]
    forbidden_repository_content: tuple[str, ...]
    custody_completion_phase: str
    first_training_phase: int
    phase10_blocked_until_custody_sealed: bool
    config_sha256: str

    @property
    def contract_hash(self) -> str:
        return canonical_hash(self)

    def instantiate(self, placeholder_id: str, *_: Any, **__: Any) -> None:
        if placeholder_id not in self.placeholder_ids:
            raise DomainContractError("unknown held-out placeholder")
        raise DomainContractError(
            "held-out implementation is custody-only and cannot be instantiated"
        )


def load_heldout_contract(repo_root: Path) -> HeldOutPlaceholderContract:
    loaded = load_config(
        repo_root,
        Path("configs/domains/heldout_placeholders.yaml"),
    )
    data = loaded.data
    if set(data) != {
        "schema_version",
        "registry_id",
        "placeholder_ids",
        "universal_shapes",
        "forbidden_repository_content",
        "chronology",
    }:
        raise DomainContractError("held-out placeholder fields are not exact")
    shapes = data["universal_shapes"]
    placeholders = tuple(str(item) for item in data["placeholder_ids"])
    if placeholders != ("D7", "D8"):
        raise DomainContractError("held-out placeholder identities changed")
    projection = tuple(
        (str(name), str(value))
        for name, value in shapes["projection"].items()
    )
    if projection != universal_projection_signature():
        raise DomainContractError("held-out projection shape lacks schema parity")
    chronology = data["chronology"]
    if (
        chronology["custody_completion_phase"] != "9A"
        or chronology["first_training_phase"] != 10
        or chronology["phase10_blocked_until_custody_sealed"] is not True
    ):
        raise DomainContractError("held-out custody chronology changed")
    return HeldOutPlaceholderContract(
        schema_version=str(data["schema_version"]),
        registry_id=str(data["registry_id"]),
        placeholder_ids=placeholders,
        task_shape=dict(shapes["task"]),
        candidate_shape=dict(shapes["candidate"]),
        mechanism_shape=dict(shapes["mechanism"]),
        projection_signature=projection,
        validation_shape=dict(shapes["validation"]),
        forbidden_repository_content=tuple(
            str(item) for item in data["forbidden_repository_content"]
        ),
        custody_completion_phase="9A",
        first_training_phase=10,
        phase10_blocked_until_custody_sealed=True,
        config_sha256=loaded.canonical_sha256,
    )
