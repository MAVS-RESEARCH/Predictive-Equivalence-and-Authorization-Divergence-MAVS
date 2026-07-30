"""Lossless canonical graph rendering over stable field facts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pead.core.hashing import canonical_object, restore_canonical_object
from pead.projections.firewall import rendered_bytes

REPRESENTATION_ID = "canonical-graph-v1"


def render(fields: Mapping[str, Any]) -> Mapping[str, Any]:
    """Render every field as a typed node connected to one projection root."""

    nodes = [{"id": "projection-root", "node_type": "projection_root"}]
    edges = []
    for field_id in sorted(fields):
        nodes.append(
            {
                "id": f"field::{field_id}",
                "node_type": "visible_field",
                "stable_field_id": field_id,
                "value": canonical_object(fields[field_id]),
            }
        )
        edges.append(
            {
                "source": "projection-root",
                "target": f"field::{field_id}",
                "edge_type": "contains_visible_fact",
            }
        )
    return {"nodes": nodes, "edges": edges}


def reconstruct(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Recover every visible stable-field value from graph nodes."""

    nodes = payload.get("nodes")
    edges = payload.get("edges")
    if not isinstance(nodes, (list, tuple)) or not isinstance(edges, (list, tuple)):
        raise ValueError("graph payload requires nodes and edges")
    expected_edges = {
        (
            "projection-root",
            node["id"],
            "contains_visible_fact",
        )
        for node in nodes
        if isinstance(node, Mapping) and node.get("node_type") == "visible_field"
    }
    actual_edges = {
        (edge.get("source"), edge.get("target"), edge.get("edge_type"))
        for edge in edges
        if isinstance(edge, Mapping)
    }
    if actual_edges != expected_edges:
        raise ValueError("graph field containment edges are incomplete or extraneous")
    result: dict[str, Any] = {}
    for node in nodes:
        if not isinstance(node, Mapping) or node.get("node_type") != "visible_field":
            continue
        field_id = node.get("stable_field_id")
        if not isinstance(field_id, str) or field_id in result:
            raise ValueError("graph stable field identity is missing or duplicated")
        result[field_id] = restore_canonical_object(node["value"])
    return {field_id: result[field_id] for field_id in sorted(result)}


def serialize(payload: Mapping[str, Any]) -> str:
    """Serialize the canonical graph payload losslessly."""

    return rendered_bytes(payload).decode("utf-8")


def deserialize(serialized: str) -> dict[str, Any]:
    """Deserialize a payload emitted by :func:`serialize`."""

    value = json.loads(serialized)
    if not isinstance(value, dict):
        raise ValueError("graph serialization must decode to a mapping")
    return reconstruct(value)
