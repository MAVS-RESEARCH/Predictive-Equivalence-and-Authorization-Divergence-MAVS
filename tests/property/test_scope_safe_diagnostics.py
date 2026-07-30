"""Property gates for frozen Diagnostic Sciences scope contracts."""

from __future__ import annotations

import unittest
from pathlib import Path

from pead.core.diagnostic_registry import load_diagnostic_definitions
from pead.core.scope_contract import ScopeBank, ScopeContractError, validate_scoped_case
from pead.tracks.scope import iter_scope_cases


REPO_ROOT = Path(__file__).resolve().parents[2]


class ScopeSafeDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = tuple(iter_scope_cases(REPO_ROOT))
        cls.definitions = load_diagnostic_definitions(REPO_ROOT).entries

    def test_every_case_reuses_exact_frozen_semantics_and_authority(self) -> None:
        for case in self.cases:
            definition = self.definitions[case.diagnostic_id]
            validate_scoped_case(case, definition)
            self.assertEqual(case.definition_hash, definition.definition_hash)
            self.assertEqual(case.maximum_authority, definition.maximum_authority)
            self.assertTrue(
                set(case.expected_influence_paths)
                <= set(definition.permitted_influence_paths)
            )

    def test_out_of_scope_cases_preserve_truth_and_terminal_action(self) -> None:
        out_of_scope = [
            case
            for case in self.cases
            if case.bank is ScopeBank.ADVERSARIAL_OUT_OF_SCOPE
        ]
        self.assertEqual(len(out_of_scope), 5_600)
        for case in out_of_scope:
            self.assertEqual(case.truth_hash_before, case.truth_hash_after)
            self.assertIs(case.authorization_before, case.authorization_after)
            self.assertEqual(case.expected_influence_paths, ())

    def test_unregistered_influence_is_rejected(self) -> None:
        case = next(iter(self.cases))
        mutated = case.__class__(
            **{
                **case.__dict__,
                "expected_influence_paths": ("terminal.unregistered",),
            }
        )
        with self.assertRaises(ScopeContractError):
            validate_scoped_case(mutated, self.definitions[case.diagnostic_id])

    def test_raw_correlation_remains_observation_only(self) -> None:
        cases = [case for case in self.cases if case.diagnostic_id == "DSCF-ZC-v1"]
        self.assertEqual(len(cases), 4_000)
        self.assertTrue(all(case.maximum_authority == "observation-only" for case in cases))
