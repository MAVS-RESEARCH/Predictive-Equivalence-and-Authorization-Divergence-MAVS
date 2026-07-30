"""Typed immutable registry primitives."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Generic, Mapping, TypeVar

from pead.core.hashing import canonical_hash

T = TypeVar("T")


class RegistryValidationError(ValueError):
    """Raised when a registry entry or identity is invalid."""


@dataclass(frozen=True)
class RegistryManifest:
    schema_version: str
    registry_id: str
    entry_count: int
    entry_ids: tuple[str, ...]
    registry_sha256: str


class FrozenRegistry(Generic[T]):
    """Duplicate-rejecting registry frozen at construction."""

    def __init__(
        self,
        *,
        registry_id: str,
        entries: Iterable[T],
        identity: Callable[[T], str],
    ) -> None:
        if not registry_id:
            raise RegistryValidationError("registry_id must be non-empty")
        indexed: dict[str, T] = {}
        for entry in entries:
            entry_id = identity(entry)
            if not entry_id:
                raise RegistryValidationError("registry entry identity must be non-empty")
            if entry_id in indexed:
                raise RegistryValidationError(f"duplicate registry entry: {entry_id}")
            indexed[entry_id] = entry
        if not indexed:
            raise RegistryValidationError("registry must contain at least one entry")
        self._registry_id = registry_id
        self._entries: Mapping[str, T] = MappingProxyType(
            {key: indexed[key] for key in sorted(indexed)}
        )

    @property
    def registry_id(self) -> str:
        return self._registry_id

    @property
    def entries(self) -> Mapping[str, T]:
        return self._entries

    def require(self, entry_id: str) -> T:
        try:
            return self._entries[entry_id]
        except KeyError as exc:
            raise RegistryValidationError(f"unknown registry entry: {entry_id}") from exc

    def manifest(self) -> RegistryManifest:
        payload = {
            "schema_version": "1.0",
            "registry_id": self.registry_id,
            "entries": self.entries,
        }
        return RegistryManifest(
            schema_version="1.0",
            registry_id=self.registry_id,
            entry_count=len(self.entries),
            entry_ids=tuple(self.entries),
            registry_sha256=canonical_hash(payload),
        )
