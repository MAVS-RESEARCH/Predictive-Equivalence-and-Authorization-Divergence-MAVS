"""Property checks for dual-engine agreement and hard quarantine behavior."""

from __future__ import annotations

import copy
import json
import random
import unittest
from dataclasses import replace

from pead.core.types import AuthorizationAction
from pead.labels.evaluator_dsl import evaluate_policy
from pead.labels.evaluator_reference import evaluate_reference
from pead.labels.reasons import quarantine_disagreement
from tests.phase2_fixtures import policy_for, released_fixtures


class LabelAgreementPropertyTests(unittest.TestCase):
    def test_all_released_fixtures_have_exact_dual_engine_agreement(self) -> None:
        fixtures = released_fixtures()
        self.assertEqual(len(fixtures), 10)
        for fixture in fixtures:
            policy = policy_for(fixture)
            dsl = evaluate_policy(policy, fixture.serialized_facts)
            reference = evaluate_reference(policy.policy_id, fixture.serialized_facts)
            self.assertEqual(dsl, reference, fixture.case_id)
            self.assertIs(dsl.label, fixture.expected, fixture.case_id)

    def test_deterministic_fact_variations_preserve_dual_engine_agreement(self) -> None:
        rng = random.Random(2202)
        fixtures = released_fixtures()
        for index in range(2_000):
            fixture = fixtures[index % len(fixtures)]
            policy = policy_for(fixture)
            facts = copy.deepcopy(dict(fixture.facts))
            facts["nuisance"] = {
                "nonce": rng.randrange(0, 1_000_000),
                "flag": bool(rng.getrandbits(1)),
            }
            serialized = json.dumps(
                facts,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            self.assertEqual(
                evaluate_policy(policy, serialized),
                evaluate_reference(policy.policy_id, serialized),
            )

    def test_any_disagreement_creates_release_blocking_quarantine(self) -> None:
        fixture = released_fixtures()[0]
        policy = policy_for(fixture)
        dsl = evaluate_policy(policy, fixture.serialized_facts)
        corrupted_reference = replace(
            dsl,
            label=AuthorizationAction.REJECT,
            reason_class="synthetic_disagreement",
        )
        quarantine = quarantine_disagreement(
            case_id=fixture.case_id,
            policy_id=policy.policy_id,
            dsl_result=dsl,
            reference_result=corrupted_reference,
            invalidation_scope=("fixture_bank", "dependent_release"),
        )
        self.assertIsNotNone(quarantine)
        assert quarantine is not None
        self.assertEqual(quarantine.status, "quarantined")
        self.assertIn("dependent_release", quarantine.invalidation_scope)


if __name__ == "__main__":
    unittest.main()
