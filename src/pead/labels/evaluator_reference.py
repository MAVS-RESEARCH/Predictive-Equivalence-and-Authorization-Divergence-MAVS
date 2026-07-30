"""Independent procedural authorization evaluator over serialized latent facts.

This module intentionally does not import the policy parser, DSL types, or DSL
evaluator. Its fixed decision trees are the second implementation used to detect
policy-engine errors.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from pead.core.types import AuthorizationAction
from pead.labels.reasons import LabelEvaluation


class ReferenceEvaluationError(ValueError):
    """Raised when the policy identity or serialized fact envelope is invalid."""


@dataclass(frozen=True)
class _Check:
    identity: str
    state: bool | None


_ABSENT = object()


def _facts(serialized_facts: bytes) -> Mapping[str, Any]:
    if not isinstance(serialized_facts, bytes):
        raise ReferenceEvaluationError("serialized latent facts must be bytes")
    try:
        value = json.loads(serialized_facts.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReferenceEvaluationError("serialized latent facts must be UTF-8 JSON") from exc
    if not isinstance(value, Mapping):
        raise ReferenceEvaluationError("serialized latent facts must decode to a mapping")
    return value


def _get(facts: Mapping[str, Any], path: str) -> Any:
    current: Any = facts
    for component in path.split("."):
        if not isinstance(current, Mapping) or component not in current:
            return _ABSENT
        current = current[component]
    return current


def _equals(facts: Mapping[str, Any], identity: str, path: str, expected: Any) -> _Check:
    actual = _get(facts, path)
    if actual is _ABSENT or actual is None:
        return _Check(identity, None)
    if isinstance(expected, bool) and not isinstance(actual, bool):
        return _Check(identity, None)
    if isinstance(expected, int) and not isinstance(expected, bool):
        if not isinstance(actual, int) or isinstance(actual, bool):
            return _Check(identity, None)
    if isinstance(expected, str) and not isinstance(actual, str):
        return _Check(identity, None)
    return _Check(identity, actual == expected)


def _contains(
    facts: Mapping[str, Any],
    identity: str,
    path: str,
    expected: str,
) -> _Check:
    actual = _get(facts, path)
    if not isinstance(actual, list):
        return _Check(identity, None)
    return _Check(identity, expected in actual)


def _threshold(
    facts: Mapping[str, Any],
    identity: str,
    path: str,
    threshold: int,
    comparison: str,
) -> _Check:
    actual = _get(facts, path)
    if not isinstance(actual, int) or isinstance(actual, bool):
        return _Check(identity, None)
    if comparison == "lte":
        return _Check(identity, actual <= threshold)
    return _Check(identity, actual > threshold)


def _unknown(facts: Mapping[str, Any], identity: str, path: str) -> _Check:
    actual = _get(facts, path)
    return _Check(
        identity,
        actual is _ABSENT or actual is None or actual == "unknown",
    )


def _independent_sources(
    facts: Mapping[str, Any],
    identity: str,
    path: str,
    minimum: int,
) -> _Check:
    sources = _get(facts, path)
    if not isinstance(sources, list):
        return _Check(identity, None)
    identities: set[str] = set()
    for source in sources:
        if not isinstance(source, Mapping):
            return _Check(identity, None)
        source_id = source.get("source_id")
        independent = source.get("independent")
        if not isinstance(source_id, str) or not isinstance(independent, bool):
            return _Check(identity, None)
        if independent:
            identities.add(source_id)
    return _Check(identity, len(identities) >= minimum)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def _valid_at(
    facts: Mapping[str, Any],
    identity: str,
    interval_path: str,
    instant_path: str,
) -> _Check:
    interval = _get(facts, interval_path)
    instant = _parse_time(_get(facts, instant_path))
    if not isinstance(interval, Mapping) or instant is None:
        return _Check(identity, None)
    start = _parse_time(interval.get("valid_from"))
    end = _parse_time(interval.get("valid_until"))
    if start is None or end is None or start > end:
        return _Check(identity, None)
    return _Check(identity, start <= instant <= end)


def _path(
    facts: Mapping[str, Any],
    identity: str,
    graph_path: str,
    source: str,
    target: str,
    relation: str,
) -> _Check:
    graph = _get(facts, graph_path)
    if not isinstance(graph, Mapping):
        return _Check(identity, None)
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return _Check(identity, None)
    node_ids = {
        node.get("id")
        for node in nodes
        if isinstance(node, Mapping) and isinstance(node.get("id"), str)
    }
    if source not in node_ids or target not in node_ids:
        return _Check(identity, False)
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    for edge in edges:
        if not isinstance(edge, Mapping):
            return _Check(identity, None)
        edge_source = edge.get("source")
        edge_target = edge.get("target")
        edge_relation = edge.get("edge_type")
        if not all(
            isinstance(item, str)
            for item in (edge_source, edge_target, edge_relation)
        ):
            return _Check(identity, None)
        if (
            edge_relation == relation
            and edge_source in adjacency
            and edge_target in node_ids
        ):
            adjacency[edge_source].append(edge_target)
    queue = deque([source])
    visited = {source}
    while queue:
        current = queue.popleft()
        if current == target:
            return _Check(identity, True)
        for neighbor in sorted(adjacency[current]):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return _Check(identity, False)


def _result(
    policy_identity: str,
    rule_identity: str,
    label: AuthorizationAction,
    reason: str,
    checks: tuple[_Check, ...],
) -> LabelEvaluation:
    return LabelEvaluation(
        schema_version="1.0",
        label=label,
        reason_class=reason,
        satisfied_constraints=tuple(
            sorted(check.identity for check in checks if check.state is True)
        ),
        violated_constraints=tuple(
            sorted(check.identity for check in checks if check.state is False)
        ),
        ambiguity_basis=tuple(
            sorted(check.identity for check in checks if check.state is None)
        ),
        rule_lineage=(policy_identity, rule_identity, reason),
    )


def _decide(
    policy_identity: str,
    rule_identity: str,
    when: tuple[_Check, ...],
    requirements: tuple[_Check, ...],
    prohibitions: tuple[_Check, ...],
    escalation: tuple[_Check, ...],
) -> LabelEvaluation:
    if any(check.state is False for check in when):
        return _result(
            policy_identity,
            rule_identity,
            AuthorizationAction.REJECT,
            "out_of_policy_scope",
            when,
        )
    if any(check.state is None for check in when):
        return _result(
            policy_identity,
            rule_identity,
            AuthorizationAction.ESCALATE,
            "policy_scope_unresolved",
            when,
        )
    checks = (*when, *requirements, *prohibitions, *escalation)
    if any(check.state is True for check in prohibitions):
        return _result(
            policy_identity,
            rule_identity,
            AuthorizationAction.REJECT,
            "certified_prohibition",
            checks,
        )
    if any(check.state is False for check in requirements):
        return _result(
            policy_identity,
            rule_identity,
            AuthorizationAction.REJECT,
            "mandatory_constraint_failed",
            checks,
        )
    if any(check.state is None for check in (*requirements, *prohibitions)):
        return _result(
            policy_identity,
            rule_identity,
            AuthorizationAction.ESCALATE,
            "mandatory_constraint_unresolved",
            checks,
        )
    if any(check.state is not False for check in escalation):
        return _result(
            policy_identity,
            rule_identity,
            AuthorizationAction.ESCALATE,
            "explicit_resolution_required",
            checks,
        )
    return _result(
        policy_identity,
        rule_identity,
        AuthorizationAction.ACCEPT,
        "authorized",
        checks,
    )


def _deploy(facts: Mapping[str, Any]) -> LabelEvaluation:
    when = (
        _equals(facts, "D-WHEN-ACTION", "action.type", "deploy_patch"),
        _equals(facts, "D-WHEN-ENV", "action.environment", "production"),
    )
    requirements = (
        _contains(
            facts,
            "D-REQ-PERMISSION",
            "actor.permissions",
            "production.deploy",
        ),
        _equals(
            facts,
            "D-REQ-POLICY",
            "policy.change_control.active",
            True,
        ),
        _independent_sources(
            facts,
            "D-REQ-SOURCES",
            "provenance.sources",
            2,
        ),
        _equals(
            facts,
            "D-REQ-ROLLBACK",
            "action.rollback_available",
            True,
        ),
        _valid_at(
            facts,
            "D-REQ-TEMPORAL",
            "policy.change_control.validity",
            "decision_time",
        ),
        _threshold(
            facts,
            "D-REQ-CONSEQUENCE",
            "consequence.impact_tier",
            5,
            "lte",
        ),
    )
    prohibitions = (
        _equals(
            facts,
            "D-REJECT-COMPROMISED",
            "provenance.compromised",
            True,
        ),
        _equals(
            facts,
            "D-REJECT-PROHIBITED",
            "policy.change_control.prohibited",
            True,
        ),
        _threshold(
            facts,
            "D-REJECT-SEVERE",
            "consequence.impact_tier",
            8,
            "gt",
        ),
    )
    escalation = (
        _unknown(
            facts,
            "D-ESC-PROVENANCE-UNKNOWN",
            "evidence.provenance_status",
        ),
        _equals(
            facts,
            "D-ESC-RESOLUTION-UNAVAILABLE",
            "evidence.resolution_available",
            False,
        ),
    )
    return _decide(
        "deploy_authorized_v1@1.0",
        "DEPLOY-AUTH-001",
        when,
        requirements,
        prohibitions,
        escalation,
    )


def _export(facts: Mapping[str, Any]) -> LabelEvaluation:
    when = (
        _equals(facts, "X-WHEN-ACTION", "action.type", "export_records"),
        _equals(facts, "X-WHEN-ENV", "action.environment", "research"),
    )
    requirements = (
        _contains(
            facts,
            "X-REQ-PERMISSION",
            "actor.permissions",
            "records.export",
        ),
        _path(
            facts,
            "X-REQ-DELEGATION",
            "authority.graph",
            "actor",
            "dataset",
            "delegates",
        ),
        _valid_at(
            facts,
            "X-REQ-TEMPORAL",
            "policy.export.validity",
            "decision_time",
        ),
        _threshold(
            facts,
            "X-REQ-CONSEQUENCE",
            "consequence.records",
            1000,
            "lte",
        ),
        _equals(facts, "X-REQ-EVIDENCE", "evidence.available", True),
    )
    prohibitions = (
        _equals(
            facts,
            "X-REJECT-PROHIBITED",
            "policy.export.prohibited",
            True,
        ),
        _equals(
            facts,
            "X-REJECT-SENSITIVE",
            "data.sensitivity",
            "restricted",
        ),
        _threshold(
            facts,
            "X-REJECT-SEVERE",
            "consequence.records",
            5000,
            "gt",
        ),
    )
    escalation = (
        _unknown(facts, "X-ESC-PURPOSE-UNKNOWN", "evidence.purpose_status"),
        _equals(
            facts,
            "X-ESC-RESOLUTION-UNAVAILABLE",
            "evidence.resolution_available",
            False,
        ),
    )
    return _decide(
        "data_export_v1@1.0",
        "EXPORT-AUTH-001",
        when,
        requirements,
        prohibitions,
        escalation,
    )


_EVALUATORS: dict[str, Callable[[Mapping[str, Any]], LabelEvaluation]] = {
    "deploy_authorized_v1": _deploy,
    "data_export_v1": _export,
}


def evaluate_reference(policy_id: str, serialized_facts: bytes) -> LabelEvaluation:
    """Run the fixed procedural evaluator selected by the external policy identity."""

    try:
        evaluator = _EVALUATORS[policy_id]
    except KeyError as exc:
        raise ReferenceEvaluationError(f"unknown reference policy: {policy_id}") from exc
    return evaluator(_facts(serialized_facts))
