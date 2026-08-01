"""Unit and exhaustive rule-fidelity tests for frozen DS-CF semantics."""

from __future__ import annotations

import io
import itertools
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.core.diagnostic_registry import load_diagnostic_definitions
from pead.mavs.ds_cf import DSCFVector, SIGNAL_TO_DIAGNOSTIC, evaluate_ds_cf
from pead.mavs.governed_consensus import govern, hard_veto
from pead.mavs.profiles import load_profiles
from pead.phase8.fixtures import sealed_raw_g

ROOT = Path(__file__).parents[2]
DEFINITIONS = load_diagnostic_definitions(ROOT).entries
DEFINITION_HASHES = {
    diagnostic_id: DEFINITIONS[diagnostic_id].definition_hash
    for diagnostic_id in SIGNAL_TO_DIAGNOSTIC.values()
}


def vector(**overrides: float) -> DSCFVector:
    values = {name: 0.0 for name in SIGNAL_TO_DIAGNOSTIC}
    values.update(overrides)
    return DSCFVector(
        **values,
        definition_hashes=DEFINITION_HASHES,
        evidence_fields={name: () for name in SIGNAL_TO_DIAGNOSTIC},
    )


class DSCFInvariantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.console = ResearchConsole("8-test", stream=io.StringIO())
        self.profile = load_profiles(ROOT)["MAVS-GC-DSCF-v1"]

    def test_all_signals_bind_to_frozen_pre_phase4_definitions(self) -> None:
        _, observed = evaluate_ds_cf(sealed_raw_g(), repository_root=ROOT, console=self.console)
        self.assertEqual(
            observed.definition_hashes,
            DEFINITION_HASHES,
        )

    def test_raw_correlation_alone_cannot_hard_veto(self) -> None:
        for correlation in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
            self.assertFalse(hard_veto(vector(z_c=correlation), self.profile))

    def test_safe_consistency_cannot_override_certified_veto(self) -> None:
        dangerous = vector(z_c=1.0, z_h=1.0, z_s=0.0, z_p=1.0)
        trace = govern(
            profile=self.profile, method_id="MAVS-A15", projection_hash="a" * 64,
            supports=(1.0, 1.0), vector=dangerous, console=self.console,
        )
        self.assertTrue(trace.veto)
        self.assertEqual(trace.terminal_decision.value, "Reject")
        self.assertLessEqual(trace.mitigation, self.profile.mitigation_bound)

    def test_mitigation_is_bounded(self) -> None:
        trace = govern(
            profile=self.profile, method_id="MAVS-A15", projection_hash="a" * 64,
            supports=(0.8, 0.8), vector=vector(z_s=1.0), console=self.console,
        )
        self.assertGreaterEqual(trace.mitigation, 0.0)
        self.assertLessEqual(trace.mitigation, 1.0)

    def test_increasing_certified_severity_cannot_ease_acceptance(self) -> None:
        low = govern(profile=self.profile, method_id="MAVS-A15", projection_hash="a" * 64, supports=(0.7, 0.7), vector=vector(z_h=0.2), console=self.console)
        high = govern(profile=self.profile, method_id="MAVS-A15", projection_hash="a" * 64, supports=(0.7, 0.7), vector=vector(z_h=0.6), console=self.console)
        self.assertGreaterEqual(high.threshold, low.threshold)
        self.assertFalse(low.terminal_decision.value == "Reject" and high.terminal_decision.value == "Accept")

    def test_exhaustive_279936_vector_rule_fidelity(self) -> None:
        levels = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        active = 0
        violations = 0
        for values in itertools.product(levels, repeat=7):
            current = vector(**dict(zip(SIGNAL_TO_DIAGNOSTIC, values, strict=True)))
            veto = hard_veto(current, self.profile)
            active += int(veto)
            if veto and (
                current.z_h < 0.7
                or current.z_s >= 0.4
                or max(current.z_f, current.z_m, current.z_p) < 0.5
            ):
                violations += 1
        self.assertEqual(active, 27_216)
        self.assertEqual(violations, 0)


if __name__ == "__main__":
    unittest.main()
