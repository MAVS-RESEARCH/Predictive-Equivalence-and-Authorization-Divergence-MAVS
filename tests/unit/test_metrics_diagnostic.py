"""Every registered Diagnostic Sciences metric on known fixtures."""

import unittest

from pead.metrics.scope import DiagnosticObservation, diagnostic_science_metrics


def obs(case: str, bank: str, inside: bool, target: bool, active: bool, changed: bool, **kwargs: object) -> DiagnosticObservation:
    return DiagnosticObservation(case, "DSCF-ZH-v1", bank, inside, target, active, changed, kwargs.pop("correct_with", True), kwargs.pop("correct_without", False), kwargs.pop("protected_error_with", False), kwargs.pop("protected_error_without", True), kwargs.pop("escalated_with", False), kwargs.pop("escalated_without", True), **kwargs)


class DiagnosticMetricTests(unittest.TestCase):
    def test_all_fourteen_diagnostic_metrics(self) -> None:
        rows = (
            obs("p", "positive", True, True, True, True, nuisance_signal_changed=True, individual_gain=0.2, joint_gain=0.7),
            obs("n", "matched_negative", True, False, False, False, correct_without=True, protected_error_without=False, escalated_without=False),
            obs("o", "adversarial_out_of_scope", False, False, False, False, correct_without=True, protected_error_without=False, escalated_without=False),
            obs("b", "boundary", True, True, True, True, boundary_distance=0.5, boundary_influence_delta=0.25),
        )
        report = diagnostic_science_metrics(rows)
        expected = {
            "in_scope_sensitivity", "scope_matched_specificity", "conditional_perception_extension",
            "intended_decision_influence_I_in", "out_of_scope_influence_I_out", "redundancy",
            "nuisance_signal_instability", "nuisance_decision_instability", "pairwise_harmful_composition",
            "set_level_harmful_composition", "protected_error_delta", "escalation_delta",
            "scope_leakage", "boundary_discontinuity",
        }
        self.assertEqual(set(report), expected)
        self.assertEqual(report["in_scope_sensitivity"]["value"], 1.0)
        self.assertEqual(report["scope_matched_specificity"]["value"], 1.0)
        self.assertEqual(report["out_of_scope_influence_I_out"]["value"], 0.0)
        self.assertEqual(report["scope_leakage"]["value"], 0.0)
        self.assertEqual(report["boundary_discontinuity"], 0.5)

    def test_missing_out_of_scope_denominator_is_explicit(self) -> None:
        report = diagnostic_science_metrics((obs("p", "positive", True, True, True, True),))
        self.assertIsNone(report["out_of_scope_influence_I_out"]["value"])


if __name__ == "__main__":
    unittest.main()
