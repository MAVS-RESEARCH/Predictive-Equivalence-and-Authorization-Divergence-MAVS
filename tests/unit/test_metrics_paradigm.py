"""Analytic paradigm and causal metric fixtures."""

import unittest

from pead.metrics.causal import pair_sequence_effects
from pead.metrics.paradigm import paired_paradigm_metrics


class ParadigmMetricTests(unittest.TestCase):
    def test_all_paradigm_metrics_match_analytic_fixture(self) -> None:
        report = paired_paradigm_metrics(
            p_only_error=0.5, lower_bound=0.5, raw_g_utility=0.8, p_only_utility=0.4,
            mavs_utility=0.9, flat_raw_g_utility=0.7,
            expected_pairs={"p1": ("Accept", "Reject"), "p2": ("Reject", "Accept")},
            observed_pairs={"p1": ("Accept", "Reject"), "p2": ("Reject", "Reject")},
        )
        self.assertEqual(report["LBG"], 0.0)
        self.assertAlmostEqual(report["GIG"], 0.4)
        self.assertAlmostEqual(report["GAG"], 0.2)
        self.assertEqual(report["AFA"], {"numerator": 1, "denominator": 2, "value": 0.5})

    def test_pair_and_sequence_effects_preserve_pairing(self) -> None:
        report = pair_sequence_effects({"p": 1.0}, {"p": 0.25}, {"s": 0.0}, {"s": 0.5})
        self.assertEqual(report["pairs"]["mean_effect"], 0.75)
        self.assertEqual(report["sequences"]["mean_effect"], -0.5)

    def test_empty_afa_denominator_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            paired_paradigm_metrics(
                p_only_error=0.0, lower_bound=0.0, raw_g_utility=0.0, p_only_utility=0.0,
                mavs_utility=0.0, flat_raw_g_utility=0.0,
                expected_pairs={"p": ("Accept", "Accept")}, observed_pairs={"p": ("Accept", "Accept")},
            )


if __name__ == "__main__":
    unittest.main()
