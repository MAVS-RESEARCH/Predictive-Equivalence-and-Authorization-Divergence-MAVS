from __future__ import annotations

import dataclasses
import unittest

from pead.core.hashing import canonical_hash
from pead.core.types import (
    AuthorizationAction,
    PairRecord,
    RecordValidationError,
    ScopeContract,
    SequenceRecord,
)
from tests.phase1_fixtures import predictive_state, world_state


class ImmutableTypeTests(unittest.TestCase):
    def test_world_id_and_record_are_deterministic_and_deeply_frozen(self) -> None:
        first = world_state()
        second = world_state()
        self.assertEqual(first, second)
        self.assertEqual(first.world_id, second.world_id)
        self.assertEqual(canonical_hash(first), canonical_hash(second))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            first.world_id = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            first.policy_state["policy"] = "changed"  # type: ignore[index]

    def test_predictive_candidate_action_cannot_carry_governance(self) -> None:
        source = predictive_state()
        data = {
            field.name: getattr(source, field.name)
            for field in dataclasses.fields(source)
        }
        data["candidate_action"] = {
            **dict(source.candidate_action),
            "authority": "admin",
        }
        with self.assertRaises(ValueError):
            type(predictive_state())(**data)

    def test_pair_record_implements_all_appendix_fields(self) -> None:
        pair = PairRecord.create(
            track_id="exact",
            world_a_id=world_state().world_id,
            world_b_id=world_state().world_id,
            predictive_hash_a="a" * 64,
            predictive_hash_b="a" * 64,
            governance_hash_a="b" * 64,
            governance_hash_b="c" * 64,
            distance_p=0.0,
            intervention_id="I-A-001",
            intervention_proof={"changed": ("authority_state",), "frozen": ("predictive_outputs",)},
            label_a=AuthorizationAction.ACCEPT,
            label_b=AuthorizationAction.REJECT,
            label_reason_a={"rule_lineage": ("rule-a",)},
            label_reason_b={"rule_lineage": ("rule-b",)},
            split_id="development_fit",
            leakage_audit_id="audit:pending",
        )
        expected = {
            "schema_version",
            "pair_id",
            "track_id",
            "world_a_id",
            "world_b_id",
            "predictive_hash_a",
            "predictive_hash_b",
            "governance_hash_a",
            "governance_hash_b",
            "distance_p",
            "intervention_id",
            "intervention_proof",
            "label_a",
            "label_b",
            "label_reason_a",
            "label_reason_b",
            "split_id",
            "leakage_audit_id",
        }
        self.assertEqual({field.name for field in dataclasses.fields(pair)}, expected)

    def test_scope_contract_rejects_missing_influence(self) -> None:
        with self.assertRaises(RecordValidationError):
            ScopeContract(
                schema_version="1.0",
                diagnostic_id="DSCF-ZC-v1",
                failure_family="correlation",
                context="multi-specialist",
                response="observe",
                influence=(),
                positive_generator="positive",
                negative_generator="negative",
                boundary_generator="boundary",
                out_of_scope_generator="out",
                monotonicity_rules="observation only",
                maximum_authority="observation-only",
                version="1.0.0",
            )

    def test_sequence_requires_aligned_nonempty_series(self) -> None:
        with self.assertRaises(RecordValidationError):
            SequenceRecord.create(
                world_ids=("world:a",),
                timestamps=(),
                authorization_labels=(AuthorizationAction.ACCEPT,),
                reversal_indices=(),
                lineage={"seed": 1},
                split_id="development_fit",
            )


if __name__ == "__main__":
    unittest.main()
