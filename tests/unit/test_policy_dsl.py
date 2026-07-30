"""Unit verification for the strict typed policy DSL and evaluator."""

from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

import yaml

from pead.core.types import AuthorizationAction
from pead.labels.dsl import TruthValue
from pead.labels.evaluator_dsl import (
    PolicyEvaluationError,
    evaluate_expression,
    evaluate_policy,
)
from pead.labels.evaluator_reference import (
    ReferenceEvaluationError,
    evaluate_reference,
)
from pead.labels.parser import (
    PolicyParseError,
    load_policy,
    parse_expression,
    parse_policy_mapping,
)
from tests.phase2_fixtures import REPO_ROOT, policy_for, released_fixtures


class PolicyDslTests(unittest.TestCase):
    def test_released_policies_parse_with_all_required_feature_operators(self) -> None:
        operators: set[str] = set()
        for path in (
            REPO_ROOT / "configs/policies/deploy_authorized_v1.yaml",
            REPO_ROOT / "configs/policies/data_export_v1.yaml",
        ):
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            policy = load_policy(path)
            self.assertEqual(policy.schema_version, "1.0")
            operators.update(
                predicate["predicate"]["operator"]
                for rule in raw["rules"]
                for group in ("require", "reject_if", "escalate_if")
                for predicate in rule[group]
            )
        self.assertTrue(
            {
                "contains",
                "temporal_contains",
                "graph_path_exists",
                "independent_sources_gte",
                "lte",
                "gt",
                "is_unknown",
            }
            <= operators
        )

    def test_logical_all_any_and_not_use_three_valued_semantics(self) -> None:
        expression = parse_expression(
            {
                "all": [
                    {
                        "predicate": {
                            "predicate_id": "A",
                            "path": "a",
                            "operator": "eq",
                            "value_type": "boolean",
                            "value": True,
                        }
                    },
                    {
                        "any": [
                            {
                                "predicate": {
                                    "predicate_id": "B",
                                    "path": "missing",
                                    "operator": "eq",
                                    "value_type": "boolean",
                                    "value": True,
                                }
                            },
                            {
                                "not": {
                                    "predicate": {
                                        "predicate_id": "C",
                                        "path": "c",
                                        "operator": "eq",
                                        "value_type": "boolean",
                                        "value": True,
                                    }
                                }
                            },
                        ]
                    },
                ]
            }
        )
        outcome = evaluate_expression(expression, {"a": True, "c": True})
        self.assertIs(outcome.truth, TruthValue.UNKNOWN)
        self.assertEqual(outcome.satisfied, ("A", "C"))
        self.assertEqual(outcome.violated, ())
        self.assertEqual(outcome.unknown, ("B",))

    def test_parser_rejects_unknown_keys_duplicate_ids_and_bad_graph_query(self) -> None:
        valid = yaml.safe_load(
            (REPO_ROOT / "configs/policies/data_export_v1.yaml").read_text(
                encoding="utf-8"
            )
        )
        extra = dict(valid)
        extra["unversioned_extension"] = True
        with self.assertRaises(PolicyParseError):
            parse_policy_mapping(extra)
        duplicate = yaml.safe_load(
            (REPO_ROOT / "configs/policies/data_export_v1.yaml").read_text(
                encoding="utf-8"
            )
        )
        duplicate["rules"][0]["require"][1]["predicate"]["predicate_id"] = (
            "X-REQ-PERMISSION"
        )
        with self.assertRaises(PolicyParseError):
            parse_policy_mapping(duplicate)
        with self.assertRaises(PolicyParseError):
            parse_expression(
                {
                    "predicate": {
                        "predicate_id": "G",
                        "path": "graph",
                        "operator": "graph_path_exists",
                        "value_type": "graph",
                        "value": {"source": "a"},
                    }
                }
            )

    def test_every_evaluation_returns_complete_reason_fields(self) -> None:
        for fixture in released_fixtures():
            result = evaluate_policy(policy_for(fixture), fixture.serialized_facts)
            self.assertIsInstance(result.label, AuthorizationAction)
            self.assertTrue(result.reason_class)
            self.assertTrue(result.rule_lineage)
            self.assertIsInstance(result.satisfied_constraints, tuple)
            self.assertIsInstance(result.violated_constraints, tuple)
            self.assertIsInstance(result.ambiguity_basis, tuple)
            self.assertEqual(len(result.evaluation_hash), 64)

    def test_missing_required_fact_is_total_and_escalates(self) -> None:
        fixture = released_fixtures()[0]
        facts = json.loads(fixture.serialized_facts)
        del facts["action"]["rollback_available"]
        result = evaluate_policy(
            policy_for(fixture),
            json.dumps(facts, sort_keys=True).encode("utf-8"),
        )
        self.assertIs(result.label, AuthorizationAction.ESCALATE)
        self.assertIn("D-REQ-ROLLBACK", result.ambiguity_basis)

    def test_total_evaluator_selects_across_multiple_rules(self) -> None:
        policy = parse_policy_mapping(
            {
                "schema_version": "1.0",
                "policy_id": "multi",
                "version": "1.0",
                "description": "Multiple deterministic rule scopes.",
                "action_type": "test",
                "rules": [
                    {
                        "rule_id": "RULE-A",
                        "explanation": "First scope.",
                        "when": {
                            "predicate": {
                                "predicate_id": "WHEN-A",
                                "path": "a",
                                "operator": "eq",
                                "value_type": "integer",
                                "value": 1,
                            }
                        },
                        "require": [],
                        "reject_if": [],
                        "escalate_if": [],
                    },
                    {
                        "rule_id": "RULE-B",
                        "explanation": "Second scope.",
                        "when": {
                            "predicate": {
                                "predicate_id": "WHEN-B",
                                "path": "b",
                                "operator": "eq",
                                "value_type": "integer",
                                "value": 2,
                            }
                        },
                        "require": [],
                        "reject_if": [],
                        "escalate_if": [],
                    },
                ],
            }
        )
        result = evaluate_policy(policy, b'{"a":0,"b":2}')
        self.assertIs(result.label, AuthorizationAction.ACCEPT)
        self.assertIn("RULE-B", result.rule_lineage)

    def test_reject_precedes_explicit_ambiguity(self) -> None:
        fixture = next(
            item
            for item in released_fixtures()
            if item.case_id == "deploy-contradictory"
        )
        result = evaluate_policy(policy_for(fixture), fixture.serialized_facts)
        self.assertIs(result.label, AuthorizationAction.REJECT)
        self.assertEqual(result.reason_class, "certified_prohibition")
        self.assertIn("D-ESC-PROVENANCE-UNKNOWN", result.satisfied_constraints)

    def test_invalid_serialization_and_unknown_reference_policy_are_rejected(self) -> None:
        policy = policy_for(released_fixtures()[0])
        with self.assertRaises(PolicyEvaluationError):
            evaluate_policy(policy, b"\xff")
        with self.assertRaises(ReferenceEvaluationError):
            evaluate_reference("unregistered", b"{}")

    def test_reference_module_has_no_dsl_or_parser_import(self) -> None:
        path = REPO_ROOT / "src/pead/labels/evaluator_reference.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        self.assertFalse(
            imports
            & {
                "pead.labels.dsl",
                "pead.labels.parser",
                "pead.labels.evaluator_dsl",
            }
        )


if __name__ == "__main__":
    unittest.main()
