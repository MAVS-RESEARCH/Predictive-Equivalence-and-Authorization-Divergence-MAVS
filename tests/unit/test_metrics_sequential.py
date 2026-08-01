"""All registered sequential metrics including false reversals."""

import unittest

from pead.core.types import AuthorizationAction as A
from pead.metrics.sequential import SequenceObservation, sequential_metrics


class SequentialMetricTests(unittest.TestCase):
    def test_all_eight_sequence_metrics(self) -> None:
        changed = SequenceObservation("s1", (A.ACCEPT, A.ACCEPT, A.REJECT, A.REJECT, A.ACCEPT), (A.ACCEPT, A.ACCEPT, A.ACCEPT, A.REJECT, A.ACCEPT), 2, 4)
        control = SequenceObservation("s2", (A.ACCEPT, A.ACCEPT, A.ACCEPT), (A.ACCEPT, A.ACCEPT, A.ACCEPT), 1, None, True)
        report = sequential_metrics((changed, control))
        self.assertEqual(len(report), 8)
        self.assertEqual(report["reversal_detection_latency"], 0.5)
        self.assertEqual(report["false_reversal_sensitivity"]["value"], 0.0)
        self.assertEqual(report["recovery_correctness"]["value"], 1.0)
        self.assertEqual(report["recovery_latency"], 0.0)
        self.assertEqual(report["authorization_flip_accuracy_at_change_point"]["value"], 0.5)


if __name__ == "__main__":
    unittest.main()
