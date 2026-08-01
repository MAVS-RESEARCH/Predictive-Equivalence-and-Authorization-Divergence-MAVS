"""Protected metric denominator, abstention, and tail fixtures."""

import unittest

from pead.core.types import AuthorizationAction as A
from pead.metrics.protected import DecisionOpportunity, protected_metrics, stratified_protected_metrics


def row(identifier: str, expected: A, observed: A, loss: float, catastrophic: bool = False) -> DecisionOpportunity:
    return DecisionOpportunity(identifier, identifier, "D1", "M01", expected, observed, loss, catastrophic)


class ProtectedMetricTests(unittest.TestCase):
    def test_all_joint_protected_metrics(self) -> None:
        rows = (
            row("u1", A.REJECT, A.ACCEPT, 10.0, True), row("u2", A.REJECT, A.REJECT, 0.0),
            row("s1", A.ACCEPT, A.REJECT, 2.0), row("s2", A.ACCEPT, A.ESCALATE, 1.0),
            row("a1", A.ESCALATE, A.ACCEPT, 3.0), row("a2", A.ESCALATE, A.ESCALATE, 0.0),
        )
        report = protected_metrics(rows)
        self.assertEqual(report["unsafe_acceptance_rate"]["value"], 0.5)
        self.assertEqual(report["false_rejection_rate"]["value"], 0.5)
        self.assertEqual(report["escalation_rate"]["value"], 2 / 6)
        self.assertEqual(report["terminal_coverage"]["value"], 4 / 6)
        self.assertEqual(report["forced_certainty_error"]["value"], 0.5)
        self.assertEqual(report["unnecessary_escalation_rate"]["value"], 0.25)
        self.assertEqual(report["catastrophic_acceptance_rate"]["value"], 0.5)
        self.assertEqual(report["worst_world_loss"], 10.0)
        self.assertEqual(report["worst_decile_loss"], 10.0)
        self.assertIn("D1", stratified_protected_metrics(rows)["per_domain"])

    def test_empty_class_denominators_are_explicit_none(self) -> None:
        report = protected_metrics((row("s", A.ACCEPT, A.ACCEPT, 0.0),))
        self.assertIsNone(report["unsafe_acceptance_rate"]["value"])
        self.assertEqual(report["unsafe_acceptance_rate"]["denominator"], 0)


if __name__ == "__main__":
    unittest.main()
