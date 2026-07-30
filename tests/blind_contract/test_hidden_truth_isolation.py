"""Adversarial hidden-truth isolation tests for Phase 6."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from pead.audits.access import scan_method_source
from pead.config.console import ResearchConsole
from pead.projections import tabular
from pead.projections.firewall import AccessViolation, RuntimeAccessMonitor
from pead.projections.raw_governance import project_raw_governance
from pead.tracks.exact import build_exact_pair, load_exact_allocations

REPO_ROOT = Path(__file__).parents[2]


class HiddenTruthIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        allocation = load_exact_allocations(REPO_ROOT)[1]
        cls.world = build_exact_pair(allocation, REPO_ROOT).left.world_state

    def setUp(self) -> None:
        self.stream = io.StringIO()
        self.console = ResearchConsole("6", stream=self.stream)
        self.sealed, _ = project_raw_governance(
            self.world,
            representation_id=tabular.REPRESENTATION_ID,
            console=self.console,
        )

    def test_runtime_proxy_blocks_hidden_attributes_and_private_storage(self) -> None:
        monitor = RuntimeAccessMonitor(self.console, seed=99)
        proxy = monitor.guard(self.sealed, balance_class=0)
        forbidden = (
            "world_state",
            "authorization_label",
            "oracle_state",
            "latent_governance_truth",
            "task_truth",
            "__dict__",
            "_sealed_input",
        )
        for attribute in forbidden:
            with self.assertRaises(AccessViolation):
                getattr(proxy, attribute)
        self.assertEqual(len(monitor.attempts), len(forbidden))
        self.assertTrue(all(attempt.blocked for attempt in monitor.attempts))

    def test_runtime_proxy_blocks_unregistered_field_id(self) -> None:
        monitor = RuntimeAccessMonitor(self.console, seed=100)
        proxy = monitor.guard(self.sealed)
        with self.assertRaises(AccessViolation):
            proxy.get("O-LATENT-GOVERNANCE-v1")
        self.assertEqual(monitor.attempts[0].requested_attribute, "O-LATENT-GOVERNANCE-v1")

    def test_hidden_canary_is_unique_inaccessible_and_absent_from_payload(self) -> None:
        monitor = RuntimeAccessMonitor(self.console, seed=101)
        proxies = [monitor.guard(self.sealed, balance_class=index % 2) for index in range(100)]
        for proxy in proxies:
            with self.assertRaises(AccessViolation):
                getattr(proxy, "hidden_canary")
        report = monitor.canary_audit()
        self.assertEqual(report["canaries_inserted"], 100)
        self.assertEqual(report["unique_tokens"], 100)
        self.assertEqual(report["accessible_canaries"], 0)
        self.assertEqual(report["payload_token_occurrences"], 0)
        self.assertEqual(report["balance_class_0"], report["balance_class_1"])

    def test_static_scanner_rejects_each_hidden_dependency_class(self) -> None:
        source = "\n".join(
            (
                "from pead.world.schema import GeneratedWorld",
                "from pead.labels.evaluator_dsl import evaluate_policy",
                "from pead.audits.access import validate_access_configs",
                "def decide(view):",
                "    return vars(view), view.task_truth, object.__getattribute__(view, '_sealed_input')",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "malicious_method.py"
            path.write_text(source, encoding="utf-8")
            violations = scan_method_source(path)
        kinds = {violation["kind"] for violation in violations}
        self.assertIn("forbidden_import", kinds)
        self.assertIn("forbidden_symbol_import", kinds)
        self.assertIn("forbidden_attribute", kinds)
        self.assertIn("reflection_bypass", kinds)


if __name__ == "__main__":
    unittest.main()
