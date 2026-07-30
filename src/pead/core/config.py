"""Immutable configuration loading with content identity."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import yaml

from pead.core.hashing import canonical_bytes, canonical_hash
from pead.core.types import deep_freeze


class CoreConfigError(ValueError):
    """Raised when a core configuration is unsafe or incomplete."""


@dataclass(frozen=True)
class LoadedConfig:
    schema_version: str
    config_id: str
    source_path: str
    canonical_sha256: str
    canonical_payload: bytes
    data: Mapping[str, Any]


def resolve_repository_path(repository_root: Path, path: Path) -> Path:
    """Resolve a repository-relative path and reject escapes."""

    root = repository_root.resolve(strict=True)
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve(strict=True)
    if resolved == root or root not in resolved.parents:
        raise CoreConfigError("configuration path must be a file below repository root")
    if not resolved.is_file():
        raise CoreConfigError("configuration path must resolve to a file")
    return resolved


def load_config(repository_root: Path, path: Path) -> LoadedConfig:
    """Load one YAML mapping and retain its canonical bytes and identity."""

    resolved = resolve_repository_path(repository_root, path)
    try:
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise CoreConfigError(f"failed to load configuration: {resolved}") from exc
    if not isinstance(raw, dict):
        raise CoreConfigError("configuration root must be a mapping")
    schema_version = raw.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version:
        raise CoreConfigError("configuration requires schema_version")
    payload = canonical_bytes(raw)
    digest = canonical_hash(raw)
    return LoadedConfig(
        schema_version=schema_version,
        config_id=f"config_{digest}",
        source_path=resolved.relative_to(repository_root.resolve()).as_posix(),
        canonical_sha256=digest,
        canonical_payload=payload,
        data=deep_freeze(raw),
    )
