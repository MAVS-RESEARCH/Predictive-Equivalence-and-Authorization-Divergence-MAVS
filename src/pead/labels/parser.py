"""Strict YAML parser for the declarative policy DSL."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

from pead.labels.dsl import (
    Expression,
    Policy,
    PolicyRule,
    Predicate,
    PredicateOperator,
    ValueType,
)


class PolicyParseError(ValueError):
    """Raised when a policy is malformed, incomplete, or unversioned."""


_POLICY_KEYS = {
    "schema_version",
    "policy_id",
    "version",
    "description",
    "action_type",
    "rules",
}
_RULE_KEYS = {
    "rule_id",
    "explanation",
    "when",
    "require",
    "reject_if",
    "escalate_if",
}
def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PolicyParseError(f"{path} must be a mapping")
    return value


def _sequence(value: Any, path: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise PolicyParseError(f"{path} must be a sequence")
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyParseError(f"{path} must be a non-empty string")
    return value


def _exact_keys(
    value: Mapping[str, Any],
    required: set[str],
    optional: set[str],
    path: str,
) -> None:
    missing = sorted(required - set(value))
    extra = sorted(set(value) - required - optional)
    if missing or extra:
        raise PolicyParseError(f"{path} key mismatch; missing={missing}; extra={extra}")


def _parse_predicate(value: Any, path: str) -> Predicate:
    data = _mapping(value, path)
    _exact_keys(
        data,
        {"predicate_id", "path", "operator", "value_type"},
        {"value", "value_path"},
        path,
    )
    try:
        operator = PredicateOperator(_text(data["operator"], f"{path}.operator"))
        value_type = ValueType(_text(data["value_type"], f"{path}.value_type"))
    except ValueError as exc:
        raise PolicyParseError(f"{path} contains an unknown operator or type") from exc
    requires_operand = operator not in {
        PredicateOperator.EXISTS,
        PredicateOperator.IS_UNKNOWN,
    }
    if requires_operand and "value" not in data and "value_path" not in data:
        raise PolicyParseError(f"{path} requires value or value_path")
    if "value" in data and "value_path" in data:
        raise PolicyParseError(f"{path} cannot define both value and value_path")
    predicate = Predicate(
        predicate_id=_text(data["predicate_id"], f"{path}.predicate_id"),
        path=_text(data["path"], f"{path}.path"),
        operator=operator,
        value_type=value_type,
        value=data.get("value"),
        value_path=(
            _text(data["value_path"], f"{path}.value_path")
            if "value_path" in data
            else None
        ),
    )
    _validate_predicate_contract(predicate, path)
    return predicate


def _validate_predicate_contract(predicate: Predicate, path: str) -> None:
    comparison = {
        PredicateOperator.GT,
        PredicateOperator.GTE,
        PredicateOperator.LT,
        PredicateOperator.LTE,
    }
    if predicate.operator in comparison and predicate.value_type not in {
        ValueType.INTEGER,
        ValueType.NUMBER,
        ValueType.TIMESTAMP,
    }:
        raise PolicyParseError(f"{path} comparison requires numeric or timestamp type")
    if (
        predicate.operator is PredicateOperator.CONTAINS
        and predicate.value_type is not ValueType.SET
    ):
        raise PolicyParseError(f"{path} contains requires set type")
    if predicate.operator is PredicateOperator.TEMPORAL_CONTAINS:
        if predicate.value_type is not ValueType.TIMESTAMP or predicate.value_path is None:
            raise PolicyParseError(
                f"{path} temporal_contains requires timestamp type and value_path"
            )
    if predicate.operator is PredicateOperator.GRAPH_PATH_EXISTS:
        if predicate.value_type is not ValueType.GRAPH or not isinstance(
            predicate.value, Mapping
        ):
            raise PolicyParseError(
                f"{path} graph_path_exists requires graph type and query mapping"
            )
        if set(predicate.value) != {"source", "target", "edge_type"}:
            raise PolicyParseError(f"{path} graph query has an invalid shape")
    if predicate.operator is PredicateOperator.INDEPENDENT_SOURCES_GTE:
        if (
            predicate.value_type is not ValueType.SET
            or not isinstance(predicate.value, int)
            or isinstance(predicate.value, bool)
            or predicate.value < 1
        ):
            raise PolicyParseError(
                f"{path} independent_sources_gte requires set type and positive integer"
            )


def parse_expression(value: Any, path: str = "expression") -> Expression:
    data = _mapping(value, path)
    if len(data) != 1:
        raise PolicyParseError(f"{path} requires exactly one expression operator")
    kind, payload = next(iter(data.items()))
    if kind == "predicate":
        return Expression(kind="predicate", predicate=_parse_predicate(payload, path))
    if kind in {"all", "any"}:
        children = tuple(
            parse_expression(item, f"{path}.{kind}[{index}]")
            for index, item in enumerate(_sequence(payload, f"{path}.{kind}"))
        )
        return Expression(kind=kind, children=children)
    if kind == "not":
        return Expression(kind="not", children=(parse_expression(payload, f"{path}.not"),))
    raise PolicyParseError(f"{path} contains unknown expression operator: {kind}")


def parse_policy_mapping(value: Any, path: str = "policy") -> Policy:
    data = _mapping(value, path)
    _exact_keys(data, _POLICY_KEYS, set(), path)
    if data["schema_version"] != "1.0":
        raise PolicyParseError("policy schema_version must be 1.0")
    rules: list[PolicyRule] = []
    observed_rules: set[str] = set()
    observed_predicates: set[str] = set()
    for index, raw_rule in enumerate(_sequence(data["rules"], f"{path}.rules")):
        rule_path = f"{path}.rules[{index}]"
        rule = _mapping(raw_rule, rule_path)
        _exact_keys(rule, _RULE_KEYS, set(), rule_path)
        rule_id = _text(rule["rule_id"], f"{rule_path}.rule_id")
        if rule_id in observed_rules:
            raise PolicyParseError(f"duplicate rule_id: {rule_id}")
        parsed = PolicyRule(
            rule_id=rule_id,
            explanation=_text(rule["explanation"], f"{rule_path}.explanation"),
            when=parse_expression(rule["when"], f"{rule_path}.when"),
            requirements=tuple(
                parse_expression(item, f"{rule_path}.require[{item_index}]")
                for item_index, item in enumerate(
                    _sequence(rule["require"], f"{rule_path}.require")
                )
            ),
            reject_if=tuple(
                parse_expression(item, f"{rule_path}.reject_if[{item_index}]")
                for item_index, item in enumerate(
                    _sequence(rule["reject_if"], f"{rule_path}.reject_if")
                )
            ),
            escalate_if=tuple(
                parse_expression(item, f"{rule_path}.escalate_if[{item_index}]")
                for item_index, item in enumerate(
                    _sequence(rule["escalate_if"], f"{rule_path}.escalate_if")
                )
            ),
        )
        for expression in (
            parsed.when,
            *parsed.requirements,
            *parsed.reject_if,
            *parsed.escalate_if,
        ):
            for predicate_id in _predicate_ids(expression):
                if predicate_id in observed_predicates:
                    raise PolicyParseError(f"duplicate predicate_id: {predicate_id}")
                observed_predicates.add(predicate_id)
        observed_rules.add(rule_id)
        rules.append(parsed)
    if not rules:
        raise PolicyParseError("policy must contain at least one rule")
    return Policy(
        schema_version="1.0",
        policy_id=_text(data["policy_id"], f"{path}.policy_id"),
        version=_text(data["version"], f"{path}.version"),
        description=_text(data["description"], f"{path}.description"),
        action_type=_text(data["action_type"], f"{path}.action_type"),
        rules=tuple(rules),
    )


def _predicate_ids(expression: Expression) -> tuple[str, ...]:
    if expression.kind == "predicate":
        assert expression.predicate is not None
        return (expression.predicate.predicate_id,)
    return tuple(
        predicate_id
        for child in expression.children
        for predicate_id in _predicate_ids(child)
    )


def load_policy(path: Path) -> Policy:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise PolicyParseError(f"cannot load policy: {path}") from exc
    return parse_policy_mapping(raw, path.as_posix())
