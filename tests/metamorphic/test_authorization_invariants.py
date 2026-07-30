"""Metamorphic authorization monotonicity and nuisance invariance tests."""

from __future__ import annotations

import copy
import json
import unittest

from pead.core.types import AuthorizationAction
from pead.labels.evaluator_dsl import evaluate_policy
from pead.labels.evaluator_reference import evaluate_reference
from tests.phase2_fixtures import policy_for, released_fixtures


def serialized(facts: dict) -> bytes:
    return json.dumps(facts, sort_keys=True, separators=(",", ":")).encode("utf-8")


class AuthorizationInvariantTests(unittest.TestCase):
    def _positive(self, prefix: str):
        return next(
            fixture
            for fixture in released_fixtures()
            if fixture.case_id == f"{prefix}-positive"
        )

    def test_permission_revocation_cannot_improve_authorization(self) -> None:
        for prefix in ("deploy", "export"):
            fixture = self._positive(prefix)
            policy = policy_for(fixture)
            before = evaluate_policy(policy, fixture.serialized_facts)
            facts = copy.deepcopy(dict(fixture.facts))
            facts["actor"]["permissions"] = []
            payload = serialized(facts)
            after = evaluate_policy(policy, payload)
            self.assertIs(before.label, AuthorizationAction.ACCEPT)
            self.assertIs(after.label, AuthorizationAction.REJECT)
            self.assertEqual(after, evaluate_reference(policy.policy_id, payload))

    def test_new_prohibition_cannot_improve_authorization(self) -> None:
        paths = {
            "deploy": ("change_control",),
            "export": ("export",),
        }
        for prefix, (policy_key,) in paths.items():
            fixture = self._positive(prefix)
            policy = policy_for(fixture)
            facts = copy.deepcopy(dict(fixture.facts))
            facts["policy"][policy_key]["prohibited"] = True
            payload = serialized(facts)
            after = evaluate_policy(policy, payload)
            self.assertIs(after.label, AuthorizationAction.REJECT)
            self.assertEqual(after, evaluate_reference(policy.policy_id, payload))

    def test_irrelevant_intervention_preserves_full_evaluation(self) -> None:
        for fixture in released_fixtures():
            policy = policy_for(fixture)
            baseline = evaluate_policy(policy, fixture.serialized_facts)
            for value in (None, False, 0, "nuisance", {"nested": [1, 2, 3]}):
                facts = copy.deepcopy(dict(fixture.facts))
                facts["irrelevant_intervention"] = value
                payload = serialized(facts)
                self.assertEqual(baseline, evaluate_policy(policy, payload))
                self.assertEqual(
                    baseline,
                    evaluate_reference(policy.policy_id, payload),
                )


if __name__ == "__main__":
    unittest.main()
