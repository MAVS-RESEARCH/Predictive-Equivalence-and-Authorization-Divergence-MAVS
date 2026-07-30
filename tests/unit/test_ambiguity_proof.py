"""Exact proof reconstruction gates for evidence sufficiency."""

from __future__ import annotations

import unittest
from pathlib import Path

from pead.core.types import AuthorizationAction
from pead.labels.ambiguity import verify_certificate
from pead.tracks.evidence_sufficiency import (
    EvidenceClass,
    iter_evidence_cases,
    remove_permitted_resolution_channels,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class AmbiguityProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = tuple(iter_evidence_cases(REPO_ROOT))

    def test_every_certificate_reconstructs_from_complete_worlds(self) -> None:
        for case in self.cases:
            self.assertTrue(
                verify_certificate(case.certificate, case.compatible_worlds)
            )
            self.assertEqual(
                case.certificate.enumerated_worlds,
                case.certificate.compatible_space_size,
            )

    def test_every_ambiguous_case_escalates(self) -> None:
        ambiguous = [
            case
            for case in self.cases
            if case.evidence_class is not EvidenceClass.RESOLVABLE
        ]
        self.assertEqual(len(ambiguous), 8_000)
        self.assertTrue(
            all(case.expected_action is AuthorizationAction.ESCALATE for case in ambiguous)
        )

    def test_channel_removal_converts_reducible_to_irreducible_escalation(self) -> None:
        reducible = next(
            case
            for case in self.cases
            if case.evidence_class is EvidenceClass.REDUCIBLY_AMBIGUOUS
        )
        transformed = remove_permitted_resolution_channels(reducible)
        self.assertEqual(
            transformed.certificate.conclusion,
            "irreducibly_ambiguous_escalate",
        )
        self.assertIs(transformed.expected_action, AuthorizationAction.ESCALATE)
        self.assertIsNot(transformed.expected_action, AuthorizationAction.REJECT)

    def test_resolvable_cases_are_balanced_unique_terminal_classes(self) -> None:
        resolvable = [
            case
            for case in self.cases
            if case.evidence_class is EvidenceClass.RESOLVABLE
        ]
        self.assertEqual(
            sum(case.expected_action is AuthorizationAction.ACCEPT for case in resolvable),
            2_000,
        )
        self.assertEqual(
            sum(case.expected_action is AuthorizationAction.REJECT for case in resolvable),
            2_000,
        )
