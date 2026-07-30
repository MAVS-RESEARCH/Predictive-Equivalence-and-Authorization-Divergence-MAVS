"""Typed abstract syntax for the declarative authorization policy DSL."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TruthValue(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


class ValueType(str, Enum):
    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    STRING = "string"
    TIMESTAMP = "timestamp"
    SET = "set"
    GRAPH = "graph"


class PredicateOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    CONTAINS = "contains"
    EXISTS = "exists"
    IS_UNKNOWN = "is_unknown"
    TEMPORAL_CONTAINS = "temporal_contains"
    GRAPH_PATH_EXISTS = "graph_path_exists"
    INDEPENDENT_SOURCES_GTE = "independent_sources_gte"


@dataclass(frozen=True)
class Predicate:
    predicate_id: str
    path: str
    operator: PredicateOperator
    value_type: ValueType
    value: Any = None
    value_path: str | None = None


@dataclass(frozen=True)
class Expression:
    kind: str
    predicate: Predicate | None = None
    children: tuple["Expression", ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in {"predicate", "all", "any", "not"}:
            raise ValueError(f"unknown expression kind: {self.kind}")
        if self.kind == "predicate" and self.predicate is None:
            raise ValueError("predicate expression requires a predicate")
        if self.kind != "predicate" and self.predicate is not None:
            raise ValueError("logical expression cannot carry a predicate")
        if self.kind in {"all", "any"} and not self.children:
            raise ValueError(f"{self.kind} expression requires children")
        if self.kind == "not" and len(self.children) != 1:
            raise ValueError("not expression requires exactly one child")


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    explanation: str
    when: Expression
    requirements: tuple[Expression, ...]
    reject_if: tuple[Expression, ...]
    escalate_if: tuple[Expression, ...]


@dataclass(frozen=True)
class Policy:
    schema_version: str
    policy_id: str
    version: str
    description: str
    action_type: str
    rules: tuple[PolicyRule, ...]
