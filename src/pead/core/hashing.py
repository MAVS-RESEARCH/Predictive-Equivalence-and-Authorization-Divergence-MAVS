"""Canonical UTF-8 serialization and SHA-256 hashing."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import unicodedata
from collections.abc import Mapping, Sequence, Set
from decimal import Decimal, ROUND_HALF_EVEN
from enum import Enum
from pathlib import Path
from typing import Any

CANONICALIZATION_ID = "pead-canonical-json-decimal12-v1"
SCHEMA_VERSION = "1.0"
FLOAT_QUANTUM = Decimal("0.000000000001")
_RESERVED_KEY = "__pead_type__"
_FORBIDDEN_ACTION_TOKENS = {
    "authority",
    "authorization",
    "consequence",
    "evidence_availability",
    "governance",
    "jurisdiction",
    "permission",
    "policy",
    "provenance",
    "reversibility",
    "scope",
}


class CanonicalizationError(ValueError):
    """Raised when an object cannot be serialized under the frozen policy."""


def _normalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _normalize_float(value: float) -> dict[str, str]:
    if not math.isfinite(value):
        raise CanonicalizationError("NaN and infinite floats are forbidden")
    quantized = Decimal(str(value)).quantize(FLOAT_QUANTUM, rounding=ROUND_HALF_EVEN)
    if quantized == 0:
        quantized = abs(quantized)
    return {_RESERVED_KEY: "decimal12", "value": format(quantized, ".12f")}


def _stable_identifier(value: Any, candidates: tuple[str, ...]) -> str:
    if not isinstance(value, Mapping):
        raise CanonicalizationError("graph nodes and edges must be mappings")
    for key in candidates:
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate:
            return _normalize_text(candidate)
    raise CanonicalizationError(
        f"graph item requires one stable identifier from {candidates}"
    )


def _normalize_graph(value: Mapping[str, Any]) -> dict[str, Any]:
    nodes = value.get("nodes")
    edges = value.get("edges")
    if not isinstance(nodes, Sequence) or isinstance(nodes, (str, bytes)):
        raise CanonicalizationError("graph.nodes must be a sequence")
    if not isinstance(edges, Sequence) or isinstance(edges, (str, bytes)):
        raise CanonicalizationError("graph.edges must be a sequence")
    sorted_nodes = sorted(
        nodes, key=lambda item: _stable_identifier(item, ("stable_id", "node_id", "id"))
    )
    sorted_edges = sorted(
        edges,
        key=lambda item: (
            _stable_identifier(item, ("source", "source_id")),
            _stable_identifier(item, ("target", "target_id")),
            _stable_identifier(item, ("relation", "edge_type", "type", "stable_id", "id")),
            canonical_bytes(item),
        ),
    )
    remainder = {key: item for key, item in value.items() if key not in {"nodes", "edges"}}
    return {"nodes": sorted_nodes, "edges": sorted_edges, **remainder}


def normalize_candidate_action(value: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a candidate action while rejecting governance annotations."""

    if not isinstance(value, Mapping) or not value:
        raise CanonicalizationError("candidate_action must be a non-empty mapping")

    def normalize(item: Any) -> Any:
        if isinstance(item, str):
            return _normalize_text(item)
        if isinstance(item, float):
            _normalize_float(item)
            return item
        if item is None or isinstance(item, (bool, int)):
            return item
        if isinstance(item, Mapping):
            normalized_mapping: dict[str, Any] = {}
            for key, member in item.items():
                if not isinstance(key, str):
                    raise CanonicalizationError(
                        "candidate_action mapping keys must be strings"
                    )
                normalized_key = _normalize_text(key)
                if normalized_key.strip().lower() in _FORBIDDEN_ACTION_TOKENS:
                    raise CanonicalizationError(
                        "candidate_action contains prohibited governance field: "
                        f"{key}"
                    )
                if normalized_key in normalized_mapping:
                    raise CanonicalizationError(
                        "candidate_action normalization produced duplicate keys"
                    )
                normalized_mapping[normalized_key] = normalize(member)
            return {
                key: normalized_mapping[key]
                for key in sorted(normalized_mapping)
            }
        if isinstance(item, Set):
            return frozenset(normalize(member) for member in item)
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            return tuple(normalize(member) for member in item)
        raise CanonicalizationError(
            f"unsupported candidate_action type: {type(item).__name__}"
        )

    result = normalize(value)
    if not isinstance(result, dict):
        raise CanonicalizationError("candidate_action normalization failed")
    return result


def _canonical_value(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        value = {
            field.name: getattr(value, field.name)
            for field in dataclasses.fields(value)
        }
    elif isinstance(value, Enum):
        value = value.value
    elif isinstance(value, Path):
        value = value.as_posix()

    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        return _normalize_float(value)
    if isinstance(value, Decimal):
        return _normalize_float(float(value))
    if isinstance(value, str):
        return _normalize_text(value)
    if isinstance(value, bytes):
        return {_RESERVED_KEY: "bytes", "hex": value.hex()}
    if isinstance(value, Mapping):
        if _RESERVED_KEY in value:
            raise CanonicalizationError(f"mapping key {_RESERVED_KEY!r} is reserved")
        source = _normalize_graph(value) if {"nodes", "edges"} <= set(value) else value
        normalized: dict[str, Any] = {}
        for key, item in source.items():
            if not isinstance(key, str):
                raise CanonicalizationError("mapping keys must be strings")
            normalized_key = _normalize_text(key)
            if normalized_key in normalized:
                raise CanonicalizationError("Unicode normalization produced duplicate keys")
            normalized[normalized_key] = _canonical_value(item)
        return {key: normalized[key] for key in sorted(normalized)}
    if isinstance(value, Set):
        members = [_canonical_value(item) for item in value]
        members.sort(
            key=lambda item: json.dumps(
                item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        )
        return {_RESERVED_KEY: "set", "items": members}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_canonical_value(item) for item in value]
    raise CanonicalizationError(f"unsupported canonical type: {type(value).__name__}")


def canonical_object(value: Any) -> Any:
    """Return the normalized JSON-compatible object."""

    return _canonical_value(value)


def restore_canonical_object(value: Any) -> Any:
    """Restore frozen tagged scalar/container values from canonical JSON."""

    if isinstance(value, list):
        return tuple(restore_canonical_object(item) for item in value)
    if isinstance(value, dict):
        tag = value.get(_RESERVED_KEY)
        if tag == "decimal12" and set(value) == {_RESERVED_KEY, "value"}:
            return float(value["value"])
        if tag == "bytes" and set(value) == {_RESERVED_KEY, "hex"}:
            return bytes.fromhex(value["hex"])
        if tag == "set" and set(value) == {_RESERVED_KEY, "items"}:
            return frozenset(restore_canonical_object(item) for item in value["items"])
        return {
            key: restore_canonical_object(item)
            for key, item in value.items()
        }
    return value


def canonical_bytes(value: Any) -> bytes:
    """Serialize an object using the frozen canonical UTF-8 policy."""

    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    """Return the lowercase SHA-256 digest of canonical bytes."""

    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def field_hashes(value: Any) -> dict[str, str]:
    """Hash each top-level record field independently."""

    if dataclasses.is_dataclass(value):
        fields = {
            field.name: getattr(value, field.name)
            for field in dataclasses.fields(value)
        }
    elif isinstance(value, Mapping):
        fields = dict(value)
    else:
        raise CanonicalizationError("field_hashes requires a dataclass or mapping")
    return {key: canonical_hash(fields[key]) for key in sorted(fields)}
