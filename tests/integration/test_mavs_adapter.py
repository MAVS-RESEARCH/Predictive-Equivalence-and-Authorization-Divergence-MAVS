"""Integration gates for the common MAVS A00-A15 adapter."""

from __future__ import annotations

import io
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.core.types import MethodDecision
from pead.mavs.adapter import MAVSAdapter, MAVSAdapterError
from pead.mavs.ablations import load_ablation_registry
from pead.mavs.profiles import load_profiles
from pead.phase8.fixtures import sealed_p_only, sealed_raw_g

ROOT = Path(__file__).parents[2]


class MAVSAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.console = ResearchConsole("8-test", stream=io.StringIO())

    def test_original_and_ds_cf_profiles_are_frozen_and_versioned(self) -> None:
        profiles = load_profiles(ROOT)
        self.assertEqual(set(profiles), {"MAVS-PREDICTION-ONLY-v1", "MAVS-GC-ORIGINAL-v1", "MAVS-GC-DSCF-v1"})
        self.assertTrue(all(profile.status == "frozen" and profile.version == "1.0.0" for profile in profiles.values()))
        self.assertEqual(len({profile.profile_hash for profile in profiles.values()}), 3)

    def test_exact_A00_A15_inventory_and_access(self) -> None:
        registry = load_ablation_registry(ROOT)
        self.assertEqual(set(registry), {f"MAVS-A{index:02d}" for index in range(16)})
        self.assertEqual(registry["MAVS-A00"]["access_profile"], "P-only")
        self.assertTrue(all(registry[f"MAVS-A{index:02d}"]["access_profile"] == "Raw-G" for index in range(1, 16)))

    def test_all_sixteen_ablation_profiles_emit_complete_method_decisions(self) -> None:
        raw = sealed_raw_g(correlation=1.0, independent_support=0.0, policy_conflict=1.0)
        predictive = sealed_p_only()
        for index in range(16):
            method_id = f"MAVS-A{index:02d}"
            adapter = MAVSAdapter(ROOT, method_id, console=self.console)
            decision, trace = adapter.run(predictive if index == 0 else raw, execution_mode="contract_probe", commit_time="2026-08-01T00:00:00+00:00")
            self.assertIsInstance(decision, MethodDecision)
            self.assertTrue(trace.trace_complete)
            self.assertEqual(len(trace.supports), len(trace.contextual_weights))
            self.assertEqual(set(trace.as_diagnostic_trace()), {
                "profile_id", "method_id", "access_profile", "supports", "diagnostic_vector",
                "diagnostic_definition_hashes", "severity", "contextual_weights", "mitigation",
                "threshold", "veto", "ambiguity", "consensus", "terminal_decision",
                "enabled_components", "ablation_changes", "scope_enforced", "trace_complete",
            })

    def test_all_raw_g_ablations_use_the_same_visible_projection(self) -> None:
        raw = sealed_raw_g()
        hashes = set()
        for index in range(1, 16):
            decision, _ = MAVSAdapter(ROOT, f"MAVS-A{index:02d}", console=self.console).run(raw, execution_mode="contract_probe")
            hashes.add(decision.visible_projection_hash)
        self.assertEqual(hashes, {raw.projection_hash})

    def test_wrong_access_profile_is_rejected(self) -> None:
        with self.assertRaises(MAVSAdapterError):
            MAVSAdapter(ROOT, "MAVS-A15", console=self.console).run(sealed_p_only())

    def test_learned_variants_fail_closed_without_phase10_artifact(self) -> None:
        for method_id in ("MAVS-A12", "MAVS-A13"):
            with self.assertRaises(MAVSAdapterError):
                MAVSAdapter(ROOT, method_id, console=self.console).run(sealed_raw_g(), execution_mode="production")


if __name__ == "__main__":
    unittest.main()
