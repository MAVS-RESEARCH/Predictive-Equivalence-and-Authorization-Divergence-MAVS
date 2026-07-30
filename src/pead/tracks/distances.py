"""Typed predictive-state distances with a frozen weighted-maximum aggregate."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from pead.core.types import PredictiveState


class DistanceRegistryError(ValueError):
    """Raised when a distance registry or typed comparison is invalid."""


@dataclass(frozen=True)
class DistanceResult:
    schema_version: str
    aggregate: float
    field_distances: tuple[tuple[str, float], ...]
    registry_id: str


@lru_cache(maxsize=4)
def load_distance_registry(path: Path) -> Mapping[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise DistanceRegistryError("cannot load near-distance registry") from exc
    if not isinstance(value, Mapping) or value.get("schema_version") != "1.0":
        raise DistanceRegistryError("near-distance registry must be version 1.0")
    expected_types = {
        "vector",
        "categorical",
        "calibrated_probability",
        "scalar",
        "set",
        "graph",
        "text",
    }
    observed = {
        entry.get("type")
        for entry in value.get("fields", {}).values()
        if isinstance(entry, Mapping)
    }
    if observed != expected_types:
        raise DistanceRegistryError(
            f"typed distance coverage mismatch: {sorted(observed)}"
        )
    if value.get("aggregate", {}).get("method") != "weighted_max":
        raise DistanceRegistryError("aggregate distance must be weighted_max")
    return value


def _missing(left: Any, right: Any, mismatch_cost: float) -> float | None:
    if left is None and right is None:
        return 0.0
    if left is None or right is None:
        return mismatch_cost
    return None


def _numeric_vector(value: Any) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise DistanceRegistryError("vector value must be a numeric sequence")
    result = tuple(float(item) for item in value)
    if not result or any(not math.isfinite(item) for item in result):
        raise DistanceRegistryError("vector values must be finite and non-empty")
    return result


def _vector(left: Any, right: Any, scale: float) -> float:
    a = _numeric_vector(left)
    b = _numeric_vector(right)
    if len(a) != len(b) or scale <= 0:
        raise DistanceRegistryError("vector dimensions or scale are invalid")
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)) / scale


def _probability(left: Any, right: Any, config: Mapping[str, Any]) -> float:
    low, high = (float(item) for item in config["clipping"])
    scale = float(config["scale"])
    a = min(max(float(left), low), high)
    b = min(max(float(right), low), high)
    if not (0 < low < high < 1) or scale <= 0:
        raise DistanceRegistryError("probability clipping or scale is invalid")
    return abs(math.log(a / (1 - a)) - math.log(b / (1 - b))) / scale


def _weighted_jaccard(left: Any, right: Any) -> float:
    if not isinstance(left, (set, frozenset, list, tuple)) or not isinstance(
        right, (set, frozenset, list, tuple)
    ):
        raise DistanceRegistryError("set distance requires set-like values")
    a = {str(item) for item in left}
    b = {str(item) for item in right}
    union = a | b
    return 0.0 if not union else 1.0 - len(a & b) / len(union)


def _graph_items(graph: Any) -> tuple[set[str], set[str]]:
    if not isinstance(graph, Mapping):
        raise DistanceRegistryError("graph distance requires a mapping")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, Sequence) or not isinstance(edges, Sequence):
        raise DistanceRegistryError("graph requires node and edge sequences")
    node_ids = {
        str(node.get("id"))
        for node in nodes
        if isinstance(node, Mapping) and node.get("id") is not None
    }
    edge_ids = {
        f"{edge.get('source')}|{edge.get('edge_type')}|{edge.get('target')}"
        for edge in edges
        if isinstance(edge, Mapping)
    }
    if len(node_ids) != len(nodes) or len(edge_ids) != len(edges):
        raise DistanceRegistryError("graph items require stable identities")
    return node_ids, edge_ids


def _graph(left: Any, right: Any, config: Mapping[str, Any]) -> float:
    left_nodes, left_edges = _graph_items(left)
    right_nodes, right_edges = _graph_items(right)
    node_denominator = max(len(left_nodes | right_nodes), 1)
    edge_denominator = max(len(left_edges | right_edges), 1)
    node_delta = len(left_nodes ^ right_nodes) / node_denominator
    edge_delta = len(left_edges ^ right_edges) / edge_denominator
    return (
        float(config["node_weight"]) * node_delta
        + float(config["edge_weight"]) * edge_delta
    )


def _tokens(value: Any) -> tuple[str, ...]:
    def plain(item: Any) -> Any:
        if isinstance(item, Mapping):
            return {str(key): plain(nested) for key, nested in item.items()}
        if isinstance(item, (tuple, list)):
            return [plain(nested) for nested in item]
        if isinstance(item, (set, frozenset)):
            return sorted((plain(nested) for nested in item), key=repr)
        return item

    text = json.dumps(
        plain(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return tuple(re.findall(r"[A-Za-z0-9_.-]+", text.lower()))


def _cosine_distance(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    a = Counter(left)
    b = Counter(right)
    dot = sum(a[token] * b[token] for token in a.keys() & b.keys())
    norm_a = math.sqrt(sum(value * value for value in a.values()))
    norm_b = math.sqrt(sum(value * value for value in b.values()))
    if norm_a == 0 and norm_b == 0:
        return 0.0
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - dot / (norm_a * norm_b)


def _edit_distance(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    previous = list(range(len(right) + 1))
    for index, left_token in enumerate(left, start=1):
        current = [index]
        for column, right_token in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (left_token != right_token),
                )
            )
        previous = current
    return previous[-1] / max(len(left), len(right), 1)


def _field_distance(
    left: Any,
    right: Any,
    config: Mapping[str, Any],
    missing_cost: float,
) -> float:
    missing = _missing(left, right, missing_cost)
    if missing is not None:
        return missing
    field_type = config["type"]
    if field_type == "scalar":
        scale = float(config["robust_range"])
        if scale <= 0:
            raise DistanceRegistryError("scalar robust range must be positive")
        return abs(float(left) - float(right)) / scale
    if field_type == "calibrated_probability":
        return _probability(left, right, config)
    if field_type == "vector":
        return _vector(left, right, float(config["scale"]))
    if field_type == "categorical":
        return 0.0 if left == right else float(config["mismatch_cost"])
    if field_type == "set":
        return _weighted_jaccard(left, right)
    if field_type == "graph":
        return _graph(left, right, config)
    if field_type == "text":
        left_tokens = _tokens(left)
        right_tokens = _tokens(right)
        return max(
            _cosine_distance(left_tokens, right_tokens),
            _edit_distance(left_tokens, right_tokens),
        )
    raise DistanceRegistryError(f"unknown field distance type: {field_type}")


def predictive_distance(
    left: PredictiveState,
    right: PredictiveState,
    registry: Mapping[str, Any],
) -> DistanceResult:
    missing_cost = float(registry["missing_value"]["mismatch_cost"])
    distances: list[tuple[str, float]] = []
    for field_name, config in registry["fields"].items():
        distance = _field_distance(
            getattr(left, field_name),
            getattr(right, field_name),
            config,
            missing_cost,
        )
        if not math.isfinite(distance) or distance < 0:
            raise DistanceRegistryError(f"invalid distance for {field_name}")
        distances.append((field_name, distance))
    aggregate = max(
        distance * float(registry["fields"][field]["weight"])
        for field, distance in distances
    )
    return DistanceResult(
        schema_version="1.0",
        aggregate=aggregate,
        field_distances=tuple(distances),
        registry_id=str(registry["registry_id"]),
    )
