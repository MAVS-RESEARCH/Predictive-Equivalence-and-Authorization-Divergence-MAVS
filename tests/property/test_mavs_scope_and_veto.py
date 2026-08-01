"""Property tests for scope, ambiguity, mitigation, veto, and scalar compression."""

from __future__ import annotations

import ast
import io
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.core.types import AuthorizationAction
from pead.mavs.adapter import MAVSAdapter
from pead.mavs.scalarization import ScalarCompressionCase, audit_scalar_compression
from pead.phase8.fixtures import sealed_raw_g

ROOT = Path(__file__).parents[2]


class MAVSScopeAndVetoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.console = ResearchConsole("8-test", stream=io.StringIO())

    def test_out_of_scope_correlation_has_no_influence_under_full_profile(self) -> None:
        scoped_off = sealed_raw_g(correlation=1.0, scope={"z_c": False, "z_h": False})
        _, trace = MAVSAdapter(ROOT, "MAVS-A15", console=self.console).run(scoped_off)
        self.assertEqual(trace.diagnostic_vector["z_c"], 0.0)
        self.assertEqual(trace.diagnostic_vector["z_h"], 0.0)

    def test_no_scope_ablation_is_the_only_profile_admitting_out_of_scope_signal(self) -> None:
        case = sealed_raw_g(correlation=1.0, policy_conflict=1.0, independent_support=0.0, scope={"z_c": False, "z_h": False})
        _, full = MAVSAdapter(ROOT, "MAVS-A15", console=self.console).run(case)
        _, no_scope = MAVSAdapter(ROOT, "MAVS-A10", console=self.console).run(case)
        self.assertEqual(full.diagnostic_vector["z_c"], 0.0)
        self.assertEqual(no_scope.diagnostic_vector["z_c"], 1.0)

    def test_hard_veto_dominates_safe_support_and_mitigation(self) -> None:
        case = sealed_raw_g(
            supports=(1.0, 1.0), correlation=1.0, independent_support=0.0,
            policy_conflict=1.0, confidence=1.0, agreement=1.0,
        )
        decision, trace = MAVSAdapter(ROOT, "MAVS-A15", console=self.console).run(case)
        self.assertTrue(trace.veto)
        self.assertEqual(decision.decision, AuthorizationAction.REJECT)

    def test_missing_evidence_routes_nonveto_uncertainty_to_escalate(self) -> None:
        case = sealed_raw_g(missing_evidence=1.0, correlation=0.0)
        decision, trace = MAVSAdapter(ROOT, "MAVS-A15", console=self.console).run(case)
        self.assertFalse(trace.veto)
        self.assertTrue(trace.ambiguity)
        self.assertEqual(decision.decision, AuthorizationAction.ESCALATE)

    def test_central_scalar_compression_runs_on_structural_and_domain_holdouts(self) -> None:
        base = {"z_c": 0.0, "z_h": 0.0, "z_s": 0.0, "z_m": 0.0, "z_p": 0.0, "z_o": 0.0, "z_f": 0.0}
        rows = (
            ScalarCompressionCase("s-accept", "structural", base, AuthorizationAction.ACCEPT),
            ScalarCompressionCase("s-reject", "structural", base, AuthorizationAction.REJECT),
            ScalarCompressionCase("d-accept", "domain", base, AuthorizationAction.ACCEPT),
            ScalarCompressionCase("d-escalate", "domain", base, AuthorizationAction.ESCALATE),
        )
        report = audit_scalar_compression(rows)
        self.assertEqual(report["collision_count"], 2)
        self.assertEqual(report["holdouts"], ["domain", "structural"])

    def test_mavs_and_generator_label_dependency_directions_are_sealed(self) -> None:
        for path in (ROOT / "src/pead/mavs").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
            imports |= {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
            self.assertFalse(any(name.startswith(("pead.world", "pead.labels")) for name in imports), path.name)
        for directory in (ROOT / "src/pead/world", ROOT / "src/pead/labels"):
            for path in directory.glob("*.py"):
                self.assertNotIn("pead.mavs", path.read_text(encoding="utf-8"), path.name)


if __name__ == "__main__":
    unittest.main()
