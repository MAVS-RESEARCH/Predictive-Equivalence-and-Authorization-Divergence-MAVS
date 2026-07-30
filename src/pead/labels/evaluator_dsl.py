"""Total deterministic evaluator for parsed declarative authorization policies."""

from __future__ import annotations

import json
import math
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pead.core.types import AuthorizationAction
from pead.labels.dsl import (
    Expression,
    Policy,
    Predicate,
    PredicateOperator,
    TruthValue,
    ValueType,
)
from pead.labels.reasons import LabelEvaluation


class PolicyEvaluationError(ValueError):
    """Raised when serialized latent facts are not a valid JSON fact mapping."""


_MISSING = object()


@dataclass(frozen=True)
class ExpressionOutcome:
    truth: TruthValue
    satisfied: tuple[str, ...]
    violated: tuple[str, ...]
    unknown: tuple[str, ...]


def deserialize_latent_facts(serialized_facts: bytes) -> Mapping[str, Any]:
    if not isinstance(serialized_facts, bytes):
        raise PolicyEvaluationError("serialized latent facts must be bytes")
    try:
        value = json.loads(serialized_facts.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PolicyEvaluationError("serialized latent facts must be UTF-8 JSON") from exc
    if not isinstance(value, Mapping):
        raise PolicyEvaluationError("serialized latent facts must decode to a mapping")
    return value


def _resolve(facts: Mapping[str, Any], path: str) -> Any:
    current: Any = facts
    for component in path.split("."):
        if not isinstance(current, Mapping) or component not in current:
            return _MISSING
        current = current[component]
    return current


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _is_type(value: Any, value_type: ValueType) -> bool:
    if value_type is ValueType.BOOLEAN:
        return isinstance(value, bool)
    if value_type is ValueType.INTEGER:
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type is ValueType.NUMBER:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and (not isinstance(value, float) or math.isfinite(value))
        )
    if value_type is ValueType.STRING:
        return isinstance(value, str)
    if value_type is ValueType.TIMESTAMP:
        return _timestamp(value) is not None
    if value_type is ValueType.SET:
        return isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray)
        )
    if value_type is ValueType.GRAPH:
        return isinstance(value, Mapping)
    return False


def _graph_path_exists(graph: Any, query: Any) -> TruthValue:
    if not isinstance(graph, Mapping) or not isinstance(query, Mapping):
        return TruthValue.UNKNOWN
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    source = query.get("source")
    target = query.get("target")
    edge_type = query.get("edge_type")
    if (
        not isinstance(nodes, list)
        or not isinstance(edges, list)
        or not all(isinstance(value, str) for value in (source, target, edge_type))
    ):
        return TruthValue.UNKNOWN
    node_ids = {
        node.get("id")
        for node in nodes
        if isinstance(node, Mapping) and isinstance(node.get("id"), str)
    }
    if source not in node_ids or target not in node_ids:
        return TruthValue.FALSE
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for edge in edges:
        if not isinstance(edge, Mapping):
            return TruthValue.UNKNOWN
        edge_source = edge.get("source")
        edge_target = edge.get("target")
        relation = edge.get("edge_type")
        if not all(
            isinstance(value, str)
            for value in (edge_source, edge_target, relation)
        ):
            return TruthValue.UNKNOWN
        if relation == edge_type and edge_source in adjacency and edge_target in node_ids:
            adjacency[edge_source].append(edge_target)
    frontier = deque([source])
    visited = {source}
    while frontier:
        current = frontier.popleft()
        if current == target:
            return TruthValue.TRUE
        for neighbor in sorted(adjacency[current]):
            if neighbor not in visited:
                visited.add(neighbor)
                frontier.append(neighbor)
    return TruthValue.FALSE


def _independent_sources_gte(sources: Any, threshold: Any) -> TruthValue:
    if (
        not isinstance(sources, list)
        or not isinstance(threshold, int)
        or isinstance(threshold, bool)
    ):
        return TruthValue.UNKNOWN
    identities: set[str] = set()
    for source in sources:
        if not isinstance(source, Mapping):
            return TruthValue.UNKNOWN
        source_id = source.get("source_id")
        independent = source.get("independent")
        if not isinstance(source_id, str) or not isinstance(independent, bool):
            return TruthValue.UNKNOWN
        if independent:
            identities.add(source_id)
    return (
        TruthValue.TRUE
        if len(identities) >= threshold
        else TruthValue.FALSE
    )


def _evaluate_predicate(
    predicate: Predicate,
    facts: Mapping[str, Any],
) -> TruthValue:
    actual = _resolve(facts, predicate.path)
    operator = predicate.operator
    if operator is PredicateOperator.EXISTS:
        return TruthValue.TRUE if actual is not _MISSING else TruthValue.FALSE
    if operator is PredicateOperator.IS_UNKNOWN:
        return (
            TruthValue.TRUE
            if actual is _MISSING or actual is None or actual == "unknown"
            else TruthValue.FALSE
        )
    if actual is _MISSING or actual is None:
        return TruthValue.UNKNOWN
    expected = (
        _resolve(facts, predicate.value_path)
        if predicate.value_path is not None
        else predicate.value
    )
    if expected is _MISSING or expected is None:
        return TruthValue.UNKNOWN

    if operator is PredicateOperator.TEMPORAL_CONTAINS:
        if not isinstance(actual, Mapping):
            return TruthValue.UNKNOWN
        start = _timestamp(actual.get("valid_from"))
        end = _timestamp(actual.get("valid_until"))
        instant = _timestamp(expected)
        if start is None or end is None or instant is None or start > end:
            return TruthValue.UNKNOWN
        return TruthValue.TRUE if start <= instant <= end else TruthValue.FALSE
    if operator is PredicateOperator.GRAPH_PATH_EXISTS:
        return _graph_path_exists(actual, expected)
    if operator is PredicateOperator.INDEPENDENT_SOURCES_GTE:
        return _independent_sources_gte(actual, expected)
    if not _is_type(actual, predicate.value_type):
        return TruthValue.UNKNOWN

    try:
        if operator is PredicateOperator.EQ:
            result = actual == expected
        elif operator is PredicateOperator.NE:
            result = actual != expected
        elif operator is PredicateOperator.GT:
            result = actual > expected
        elif operator is PredicateOperator.GTE:
            result = actual >= expected
        elif operator is PredicateOperator.LT:
            result = actual < expected
        elif operator is PredicateOperator.LTE:
            result = actual <= expected
        elif operator is PredicateOperator.IN:
            result = actual in expected
        elif operator is PredicateOperator.CONTAINS:
            result = expected in actual
        else:
            return TruthValue.UNKNOWN
    except (TypeError, ValueError):
        return TruthValue.UNKNOWN
    return TruthValue.TRUE if result else TruthValue.FALSE


def evaluate_expression(
    expression: Expression,
    facts: Mapping[str, Any],
) -> ExpressionOutcome:
    if expression.kind == "predicate":
        assert expression.predicate is not None
        predicate_id = expression.predicate.predicate_id
        truth = _evaluate_predicate(expression.predicate, facts)
        return ExpressionOutcome(
            truth=truth,
            satisfied=(predicate_id,) if truth is TruthValue.TRUE else (),
            violated=(predicate_id,) if truth is TruthValue.FALSE else (),
            unknown=(predicate_id,) if truth is TruthValue.UNKNOWN else (),
        )
    outcomes = tuple(evaluate_expression(child, facts) for child in expression.children)
    if expression.kind == "all":
        if any(outcome.truth is TruthValue.FALSE for outcome in outcomes):
            truth = TruthValue.FALSE
        elif any(outcome.truth is TruthValue.UNKNOWN for outcome in outcomes):
            truth = TruthValue.UNKNOWN
        else:
            truth = TruthValue.TRUE
    elif expression.kind == "any":
        if any(outcome.truth is TruthValue.TRUE for outcome in outcomes):
            truth = TruthValue.TRUE
        elif any(outcome.truth is TruthValue.UNKNOWN for outcome in outcomes):
            truth = TruthValue.UNKNOWN
        else:
            truth = TruthValue.FALSE
    else:
        child_truth = outcomes[0].truth
        truth = {
            TruthValue.TRUE: TruthValue.FALSE,
            TruthValue.FALSE: TruthValue.TRUE,
            TruthValue.UNKNOWN: TruthValue.UNKNOWN,
        }[child_truth]
    return ExpressionOutcome(
        truth=truth,
        satisfied=tuple(
            sorted({item for outcome in outcomes for item in outcome.satisfied})
        ),
        violated=tuple(
            sorted({item for outcome in outcomes for item in outcome.violated})
        ),
        unknown=tuple(
            sorted({item for outcome in outcomes for item in outcome.unknown})
        ),
    )


def _make_result(
    policy: Policy,
    rule_ids: Sequence[str],
    label: AuthorizationAction,
    reason_class: str,
    outcomes: Sequence[ExpressionOutcome],
) -> LabelEvaluation:
    return LabelEvaluation(
        schema_version="1.0",
        label=label,
        reason_class=reason_class,
        satisfied_constraints=tuple(
            sorted({item for outcome in outcomes for item in outcome.satisfied})
        ),
        violated_constraints=tuple(
            sorted({item for outcome in outcomes for item in outcome.violated})
        ),
        ambiguity_basis=tuple(
            sorted({item for outcome in outcomes for item in outcome.unknown})
        ),
        rule_lineage=(
            f"{policy.policy_id}@{policy.version}",
            *tuple(rule_ids),
            reason_class,
        ),
    )


def evaluate_policy(policy: Policy, serialized_facts: bytes) -> LabelEvaluation:
    """Evaluate every valid serialized fact mapping with fixed reject-first precedence."""

    facts = deserialize_latent_facts(serialized_facts)
    when_by_rule = tuple(
        (rule, evaluate_expression(rule.when, facts)) for rule in policy.rules
    )
    active = tuple(
        (rule, when)
        for rule, when in when_by_rule
        if when.truth is TruthValue.TRUE
    )
    when_outcomes = tuple(when for _, when in when_by_rule)
    if not active and all(
        when.truth is TruthValue.FALSE for _, when in when_by_rule
    ):
        return _make_result(
            policy,
            ("no_active_rule",),
            AuthorizationAction.REJECT,
            "out_of_policy_scope",
            when_outcomes,
        )
    if not active:
        return _make_result(
            policy,
            ("unresolved_rule_scope",),
            AuthorizationAction.ESCALATE,
            "policy_scope_unresolved",
            when_outcomes,
        )
    active_rule_ids = tuple(rule.rule_id for rule, _ in active)
    active_when = tuple(when for _, when in active)
    reject = tuple(
        evaluate_expression(item, facts)
        for rule, _ in active
        for item in rule.reject_if
    )
    requirements = tuple(
        evaluate_expression(item, facts)
        for rule, _ in active
        for item in rule.requirements
    )
    escalation = tuple(
        evaluate_expression(item, facts)
        for rule, _ in active
        for item in rule.escalate_if
    )
    all_outcomes = (*active_when, *requirements, *reject, *escalation)
    if any(outcome.truth is TruthValue.TRUE for outcome in reject):
        return _make_result(
            policy,
            active_rule_ids,
            AuthorizationAction.REJECT,
            "certified_prohibition",
            all_outcomes,
        )
    if any(outcome.truth is TruthValue.FALSE for outcome in requirements):
        return _make_result(
            policy,
            active_rule_ids,
            AuthorizationAction.REJECT,
            "mandatory_constraint_failed",
            all_outcomes,
        )
    unresolved = any(
        outcome.truth is TruthValue.UNKNOWN
        for outcome in (*requirements, *reject)
    )
    explicit_escalation = any(
        outcome.truth is not TruthValue.FALSE for outcome in escalation
    )
    if unresolved or explicit_escalation:
        return _make_result(
            policy,
            active_rule_ids,
            AuthorizationAction.ESCALATE,
            (
                "mandatory_constraint_unresolved"
                if unresolved
                else "explicit_resolution_required"
            ),
            all_outcomes,
        )
    return _make_result(
        policy,
        active_rule_ids,
        AuthorizationAction.ACCEPT,
        "authorized",
        all_outcomes,
    )
