"""Lossless canonical stable-field sequence rendering."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from pead.core.hashing import canonical_object, restore_canonical_object
from pead.projections.firewall import rendered_bytes

REPRESENTATION_ID = "canonical-sequence-v1"


def render(fields: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]:
    """Render stable field/value tokens in lexical stable-ID order."""

    return tuple(
        (field_id, canonical_object(fields[field_id]))
        for field_id in sorted(fields)
    )


def reconstruct(payload: Sequence[Sequence[Any]]) -> dict[str, Any]:
    """Recover the complete stable-field mapping."""

    result: dict[str, Any] = {}
    for item in payload:
        if len(item) != 2 or not isinstance(item[0], str):
            raise ValueError("sequence item must be [stable_field_id, value]")
        field_id = item[0]
        if field_id in result:
            raise ValueError(f"duplicate sequence field: {field_id}")
        result[field_id] = restore_canonical_object(item[1])
    return {field_id: result[field_id] for field_id in sorted(result)}


def serialize(payload: Sequence[Sequence[Any]]) -> str:
    """Serialize the canonical sequence payload losslessly."""

    return rendered_bytes(payload).decode("utf-8")


def deserialize(serialized: str) -> dict[str, Any]:
    """Deserialize a payload emitted by :func:`serialize`."""

    value = json.loads(serialized)
    if not isinstance(value, list):
        raise ValueError("sequence serialization must decode to a list")
    return reconstruct(value)
