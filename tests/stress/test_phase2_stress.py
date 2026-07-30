"""Scale and mutation stress gates for the Phase 2 truth system."""

from __future__ import annotations

import copy
import json
import unittest

from pead.core.hashing import canonical_hash
from pead.core.types import AuthorizationAction
from pead.labels.ambiguity import (
    CompatibleWorld,
    build_exact_certificate,
    verify_certificate,
)
from pead.labels.evaluator_dsl import evaluate_policy
from pead.labels.evaluator_reference import evaluate_reference
from tests.phase2_fixtures import policy_for, released_fixtures


class Phase2StressTests(unittest.TestCase):
    def test_one_hundred_thousand_dual_engine_evaluations_agree(self) -> None:
        fixtures = released_fixtures()
        policies = {fixture.case_id: policy_for(fixture) for fixture in fixtures}
        evaluations = 0
        for index in range(50_000):
            fixture = fixtures[index % len(fixtures)]
            policy = policies[fixture.case_id]
            facts = copy.deepcopy(dict(fixture.facts))
            facts["stress_nonce"] = index
            payload = json.dumps(
                facts,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            dsl = evaluate_policy(policy, payload)
            reference = evaluate_reference(policy.policy_id, payload)
            self.assertEqual(dsl, reference)
            evaluations += 2
        self.assertEqual(evaluations, 100_000)

    def test_exact_certificate_verifies_all_4096_worlds(self) -> None:
        proof = tuple(
            CompatibleWorld(
                world_id=f"stress-world-{index:04d}",
                facts_hash=canonical_hash({"index": index}),
                authorization=(
                    AuthorizationAction.ACCEPT
                    if index % 3 == 0
                    else AuthorizationAction.REJECT
                    if index % 3 == 1
                    else AuthorizationAction.ESCALATE
                ),
            )
            for index in range(4_096)
        )
        certificate = build_exact_certificate(
            case_id="stress-exact-4096",
            visible_state_hash=canonical_hash({"visible": "stress"}),
            projection_hash=canonical_hash({"schema": "stress"}),
            worlds=proof,
            compatible_space_size=4_096,
            permitted_channels=("resolver",),
            exhausted_channels=("resolver",),
        )
        self.assertTrue(verify_certificate(certificate, proof))
        self.assertEqual(certificate.enumerated_worlds, 4_096)


if __name__ == "__main__":
    unittest.main()
