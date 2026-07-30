"""Metamorphic chronology and restoration gates for governance reversals."""

from __future__ import annotations

import unittest
from pathlib import Path

from pead.core.types import AuthorizationAction
from pead.tracks.reversal import (
    build_reversal_sequence,
    load_reversal_allocations,
    load_reversal_controls,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class ReversalFidelityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.allocations = load_reversal_allocations(REPO_ROOT)

    def test_all_families_reproduce_change_and_restoration(self) -> None:
        selected = {}
        for allocation in self.allocations:
            selected.setdefault(allocation.family.family_id, allocation)
        self.assertEqual(len(selected), 6)
        for family, allocation in selected.items():
            first = build_reversal_sequence(allocation, REPO_ROOT)
            second = build_reversal_sequence(allocation, REPO_ROOT)
            self.assertEqual(first, second)
            self.assertEqual(
                first.change_timestamp,
                first.steps[allocation.change_index].timestamp,
            )
            self.assertEqual(
                first.restoration_timestamp,
                first.steps[allocation.restoration_index].timestamp,
            )
            self.assertTrue(first.predictive_byte_stable)
            if family == "evidence_restoration":
                self.assertIs(
                    first.steps[allocation.change_index - 1].evaluation.label,
                    AuthorizationAction.ESCALATE,
                )
                self.assertIs(
                    first.steps[allocation.change_index].evaluation.label,
                    AuthorizationAction.ACCEPT,
                )
            else:
                self.assertTrue(first.stale_authorization_opportunities)
                self.assertIs(
                    first.steps[allocation.restoration_index].evaluation.label,
                    AuthorizationAction.ACCEPT,
                )

    def test_false_reversal_controls_preserve_truth_and_authorization(self) -> None:
        controls = load_reversal_controls(REPO_ROOT)
        false_controls = [item for item in controls if item.kind == "false_reversal"]
        self.assertEqual(len(false_controls), 200)
        for control in controls:
            self.assertEqual(control.truth_hash_before, control.truth_hash_after)
            self.assertIs(
                control.expected_authorization_before,
                control.expected_authorization_after,
            )

    def test_atomic_sequence_group_is_not_split(self) -> None:
        by_group = {}
        for allocation in self.allocations:
            by_group.setdefault(allocation.atomic_group_id, set()).add(allocation.split_id)
        self.assertEqual(len(by_group), 4_000)
        self.assertTrue(all(len(splits) == 1 for splits in by_group.values()))
