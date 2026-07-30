"""Independent unit tests for the frozen Phase 0 controls."""

from __future__ import annotations

import copy
import io
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pead.config.console import ResearchConsole
from pead.config.models import ConfigValidationError, StateField
from pead.config.validator import Phase0Validator, load_yaml
from pead.phase0.audit import inventory_console_logs
from pead.phase0.requirements import build_registry


class Phase0ConfigurationTests(unittest.TestCase):
    def test_complete_phase0_validation_passes(self) -> None:
        report = Phase0Validator(REPO_ROOT).validate()
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["counts"]["p_only_method_families"], 9)
        self.assertEqual(report["counts"]["raw_g_method_families"], 12)
        self.assertEqual(report["counts"]["diagnostics"], 7)
        self.assertEqual(report["counts"]["PredictiveState_fields"], 9)
        self.assertEqual(report["counts"]["GovernanceState_fields"], 9)
        self.assertEqual(report["counts"]["causal_rejection_concerns"], 13)

    def test_state_schema_rejects_missing_hash_rule(self) -> None:
        config = load_yaml(REPO_ROOT / "configs/access/predictive_state_v1.yaml")
        field = copy.deepcopy(config["fields"][0])
        field.pop("hashing_rule")
        with self.assertRaises(ConfigValidationError):
            StateField.from_mapping(field, "field")

    def test_research_console_emits_canonical_json(self) -> None:
        stream = io.StringIO()
        console = ResearchConsole("0", stream=stream)
        # STEP LOG P0-TEST-001: Exercise canonical structured console serialization.
        console.log("P0-TEST-001", "test event", status="pass", details={"count": 1})
        event = json.loads(stream.getvalue())
        self.assertEqual(
            event,
            {
                "details": {"count": 1},
                "event_id": "P0-TEST-001",
                "message": "test event",
                "phase": "0",
                "status": "pass",
            },
        )

    def test_console_log_calls_have_unique_adjacent_comments(self) -> None:
        inventory = inventory_console_logs(REPO_ROOT)
        event_ids = [entry["event_id"] for entry in inventory]
        self.assertEqual(len(event_ids), len(set(event_ids)))
        self.assertGreaterEqual(len(event_ids), 20)

    def test_requirements_registry_matches_normative_source(self) -> None:
        source = (
            Path.home()
            / "Downloads"
            / "PEAD_Benchmark_Implementation_Specification_v1.0.docx"
        )
        if not source.is_file():
            self.skipTest("Normative source DOCX is not available")
        committed = load_yaml(
            REPO_ROOT / "configs/requirements/pead_v1_requirements.yaml"
        )
        rebuilt = build_registry(source)
        self.assertEqual(committed, rebuilt)
        self.assertGreater(rebuilt["included_clause_count"], 500)
        self.assertEqual(rebuilt["source_document"]["body_paragraph_count"], 578)
        self.assertEqual(rebuilt["source_document"]["body_table_count"], 83)

    def test_holdout_registry_has_one_unlock(self) -> None:
        registry = load_yaml(REPO_ROOT / "configs/holdouts/holdout_registry_v1.yaml")
        chronology = registry["chronology"]
        self.assertTrue(chronology["one_unlock_only"])
        self.assertEqual(chronology["unlock_and_materialize_phase"], 11)
        self.assertEqual(chronology["streamed_evaluation_phase"], 12)

    def test_protected_objective_is_lexicographic(self) -> None:
        objective = load_yaml(
            REPO_ROOT / "configs/metrics/protected_objective_v1.yaml"
        )
        self.assertEqual(objective["selection_partition"], "calibration_policy")
        self.assertEqual(objective["selection_mode"], "lexicographic")
        self.assertEqual(
            [item["metric"] for item in objective["ordered_objectives"]],
            [
                "unsafe_acceptance_rate",
                "false_rejection_rate",
                "unnecessary_escalation_rate",
                "resource_cost",
                "model_complexity",
            ],
        )


if __name__ == "__main__":
    unittest.main()
