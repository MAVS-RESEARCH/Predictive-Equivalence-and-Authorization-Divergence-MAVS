"""Exact zero-count, clustered bootstrap, strata, and Holm fixtures."""

import unittest

from pead.metrics.statistics import exact_binomial_interval, holm_correction, mechanism_domain_bootstrap, paired_cluster_bootstrap, stratified_effects


class StatisticalMetricTests(unittest.TestCase):
    def test_zero_count_clopper_pearson_is_exact(self) -> None:
        lower, upper = exact_binomial_interval(0, 100)
        self.assertEqual(lower, 0.0)
        self.assertAlmostEqual(upper, 1.0 - 0.025 ** (1 / 100), places=12)

    def test_cluster_and_generalization_bootstrap_are_reproducible(self) -> None:
        effects = {"u1": 1.0, "u2": 0.0, "u3": 0.5, "u4": 0.5}
        clusters = {"u1": "g1", "u2": "g1", "u3": "g2", "u4": "g2"}
        first = paired_cluster_bootstrap(effects, clusters, repetitions=100, seed=9)
        second = paired_cluster_bootstrap(effects, clusters, repetitions=100, seed=9)
        self.assertEqual(first, second)
        general = mechanism_domain_bootstrap(effects, {key: f"M{i%2}" for i, key in enumerate(effects)}, {key: f"D{i//2}" for i, key in enumerate(effects)}, repetitions=100)
        self.assertEqual(general["units"], 4)

    def test_per_stratum_precedes_macro_and_holm_is_monotone(self) -> None:
        report = stratified_effects({"a": 1.0, "b": 0.0}, {"a": "D1", "b": "D2"})
        self.assertEqual(report["macro_average"], 0.5)
        corrected = holm_correction({"A01": 0.01, "A02": 0.04, "A03": 0.2})
        self.assertLessEqual(corrected["A01"]["adjusted"], corrected["A02"]["adjusted"])

    def test_invalid_denominators_fail_closed(self) -> None:
        with self.assertRaises(ValueError):
            exact_binomial_interval(0, 0)


if __name__ == "__main__":
    unittest.main()
