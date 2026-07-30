"""Lossless canonical tabular rendering."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pead.core.hashing import canonical_object, restore_canonical_object
from pead.projections.firewall import rendered_bytes

REPRESENTATION_ID = "canonical-tabular-v1"


def render(fields: Mapping[str, Any]) -> Mapping[str, Any]:
    """Render one column per stable field ID without summaries or truncation."""

    return {
        field_id: canonical_object(fields[field_id])
        for field_id in sorted(fields)
    }


def reconstruct(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Recover the complete stable-field mapping."""

    return {
        field_id: restore_canonical_object(value)
        for field_id, value in sorted(payload.items())
    }


def serialize(payload: Mapping[str, Any]) -> str:
    """Serialize the canonical tabular payload losslessly."""

    return rendered_bytes(payload).decode("utf-8")


def deserialize(serialized: str) -> dict[str, Any]:
    """Deserialize a payload emitted by :func:`serialize`."""

    value = json.loads(serialized)
    if not isinstance(value, dict):
        raise ValueError("tabular serialization must decode to a mapping")
    return reconstruct(value)
