"""Integration tests for the complete Phase 7 method and training contracts."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from pead.baselines.base import BaselineContractError, ContractProbeAdapter, MethodContract
from pead.baselines.bayesian import BAYES_GRID
from pead.baselines.ensemble import assert_out_of_fold, grouped_fold_assignments
from pead.baselines.judge import JudgeContractError, parse_response, reproduction_equal
from pead.baselines.p_only import AdaptiveConformal, REGISTERED_ADAPTIVE_GRID, REGISTERED_CONFORMAL_ALPHAS
from pead.baselines.registry import ORACLE_IDS, P_ONLY_IDS, RAW_G_IDS, comparator_probes, load_inventory
from pead.baselines.run import run_adapter_case
from pead.config.console import ResearchConsole
from pead.core.budgets import BudgetCeiling, BudgetExceeded, ResourceAccountant
from pead.core.calibration import CalibrationContractError, OperatingPoint, fit_temperature, select_operating_point
from pead.core.training import (
    CheckpointCandidate,
    TrainingContractError,
    TrainingRow,
    assert_holdout_immutable,
    assert_projection_alignment,
    audit_role_isolation,
    deterministic_rows,
    select_checkpoint,
)
from pead.phase7.fixtures import probe_input
from pead.phase7.suite import execute_contract_suite

ROOT = Path(__file__).parents[2]


class Phase7MethodSuiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.console = ResearchConsole("7-test", stream=io.StringIO())

    def test_exact_inventory(self) -> None:
        records = load_inventory(ROOT)
        self.assertEqual(len(records), 39)
        self.assertEqual(len(P_ONLY_IDS), 9)
        self.assertEqual(len(RAW_G_IDS), 12)
        self.assertEqual(len(ORACLE_IDS), 2)

    def test_every_comparator_uses_common_runner(self) -> None:
        report = execute_contract_suite(ROOT, self.console)
        self.assertEqual(report["comparators"], 23)
        self.assertEqual(report["decisions"], 23)
        self.assertEqual(report["scientific_results"], 0)

    def test_all_decisions_have_exact_three_outcomes(self) -> None:
        for adapter in comparator_probes(ROOT, self.console).values():
            method_input = probe_input(adapter.contract.access_profile, adapter.contract.representation_id)
            decision = run_adapter_case(adapter, method_input, execution_mode="contract_probe", commit_time="2026-08-01T00:00:00+00:00")
            self.assertEqual(set(decision.decision_scores), {"Accept", "Reject", "Escalate"})
            self.assertAlmostEqual(sum(decision.decision_scores.values()), 1.0)

    def test_unselected_trained_method_fails_closed_in_production(self) -> None:
        adapter = comparator_probes(ROOT, self.console)["G04-MLP"]
        method_input = probe_input("Raw-G", "canonical-tabular-v1")
        with self.assertRaises(BaselineContractError):
            run_adapter_case(adapter, method_input, execution_mode="production", commit_time="2026-08-01T00:00:00+00:00")

    def test_wrong_access_profile_is_rejected(self) -> None:
        adapter = comparator_probes(ROOT, self.console)["G03-GBDT"]
        with self.assertRaises(BaselineContractError):
            adapter.decide(probe_input("P-only", "canonical-tabular-v1"), execution_mode="contract_probe")

    def test_grid_trial_counts(self) -> None:
        from pead.baselines import graph, neural, scalar, sequence, tabular
        self.assertEqual((len(tabular.LOGISTIC_GRID), len(tabular.TREE_GRID), len(tabular.GBDT_GRID)), (14, 12, 16))
        self.assertEqual((len(neural.MLP_GRID), len(sequence.TRANSFORMER_GRID), len(graph.GRAPH_GRID), len(BAYES_GRID), len(scalar.SCALAR_GRID)), (6, 8, 8, 6, 12))

    def test_registered_seed_set(self) -> None:
        from pead.baselines.neural import MLP_SCHEDULE
        self.assertEqual(MLP_SCHEDULE["seeds"], (101, 211, 307))

    def test_static_and_adaptive_conformal_grids(self) -> None:
        self.assertEqual(len(REGISTERED_CONFORMAL_ALPHAS), 5)
        self.assertEqual(len(REGISTERED_ADAPTIVE_GRID), 6)

    def test_adaptive_conformal_window_is_causal_and_bounded(self) -> None:
        contract = MethodContract("P06-CONF-ADAPT", "adaptive conformal", "P-only", "canonical-tabular-v1", "trained-calibrated", "headline")
        adapter = AdaptiveConformal(contract, console=self.console, alpha=0.05, quantile=0.2, window=256)
        for index in range(300):
            adapter.update_after_label(index / 300)
        self.assertEqual(len(adapter._past_nonconformity), 256)

    def test_calibration_fit_partition_only(self) -> None:
        artifact = fit_temperature(((2.0, 0.0, -1.0), (0.0, 2.0, -1.0)), (0, 1), partition="calibration_fit", console=self.console)
        self.assertEqual(artifact.fit_partition, "calibration_fit")
        with self.assertRaises(CalibrationContractError):
            fit_temperature(((1.0, 0.0, 0.0),), (0,), partition="development_selection", console=self.console)

    def test_policy_selection_partition_and_tie_break(self) -> None:
        rows = (
            OperatingPoint("op-b", 0.8, 0.2, "calibration_policy", (0.9, 0.8)),
            OperatingPoint("op-a", 0.7, 0.2, "calibration_policy", (0.9, 0.8)),
        )
        selected = select_operating_point(rows, partition="calibration_policy", console=self.console)
        self.assertEqual(selected.operating_point_id, "op-a")
        with self.assertRaises(CalibrationContractError):
            select_operating_point(rows, partition="calibration_fit", console=self.console)

    def test_checkpoint_selection_tie_break_order(self) -> None:
        candidates = (
            CheckpointCandidate("large", "G04-MLP", 101, 0.9, 0.8, 1000, 2.0, "a" * 64),
            CheckpointCandidate("small", "G04-MLP", 211, 0.9, 0.8, 500, 3.0, "b" * 64),
        )
        self.assertEqual(select_checkpoint(candidates, console=self.console).checkpoint_id, "small")

    def test_checkpoint_wrong_partition_rejected(self) -> None:
        candidate = CheckpointCandidate("bad", "G04-MLP", 101, 0.9, 0.8, 1, 1.0, "a" * 64, "development_fit")
        with self.assertRaises(TrainingContractError):
            select_checkpoint((candidate,), console=self.console)

    def test_group_atomic_deterministic_loader(self) -> None:
        rows = tuple(TrainingRow(f"c{i}", f"w{i}", f"g{i//2}", "development_fit", f"p{i}", (i,), "Accept") for i in range(8))
        first = deterministic_rows(rows, seed=101)
        second = deterministic_rows(reversed(rows), seed=101)
        self.assertEqual(first, second)
        positions = {row.case_id: index for index, row in enumerate(first)}
        self.assertTrue(all(abs(positions[f"c{i}"] - positions[f"c{i+1}"]) == 1 for i in range(0, 8, 2)))

    def test_role_leakage_is_rejected(self) -> None:
        rows = (
            TrainingRow("c1", "w1", "g1", "development_fit", "p1", (), "Accept"),
            TrainingRow("c2", "w2", "g1", "development_selection", "p2", (), "Reject"),
        )
        with self.assertRaises(TrainingContractError):
            audit_role_isolation(rows)

    def test_equal_information_identity_alignment(self) -> None:
        profiles = {}
        for profile in ("P-only", "Raw-G", "Oracle-G"):
            profiles[profile] = (TrainingRow("c1", "w1", "g1", "development_fit", profile, (), "Accept"),)
        self.assertTrue(assert_projection_alignment(profiles)["only_projection_differs"])
        profiles["Raw-G"] = (TrainingRow("c2", "w2", "g2", "development_fit", "Raw-G", (), "Accept"),)
        with self.assertRaises(TrainingContractError):
            assert_projection_alignment(profiles)

    def test_holdout_mutation_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            before = Path(directory) / "before.yaml"
            after = Path(directory) / "after.yaml"
            before.write_text("sealed: true\n", encoding="utf-8")
            after.write_text("sealed: false\n", encoding="utf-8")
            with self.assertRaises(TrainingContractError):
                assert_holdout_immutable(before, after)

    def test_budget_call_and_token_ceiling(self) -> None:
        accountant = ResourceAccountant(BudgetCeiling("judge", 10.0, 100.0, calls_per_case=1, tokens_per_case=2304), self.console)
        accountant.record_call(input_tokens=2048, output_tokens=256)
        with self.assertRaises(BudgetExceeded):
            accountant.record_call(input_tokens=1, output_tokens=0)

    def test_judge_parser_and_reproduction(self) -> None:
        payload = '{"decision":"Accept","scores":{"Accept":0.8,"Reject":0.1,"Escalate":0.1},"reason":"registered"}'
        first = parse_response(payload)
        second = json.loads(payload)
        second["scores"]["Accept"] += 1e-7
        self.assertTrue(reproduction_equal(first, second))
        second["decision"] = "Reject"
        self.assertFalse(reproduction_equal(first, second))
        with self.assertRaises(JudgeContractError):
            parse_response("not json")

    def test_judge_artifact_identity_is_immutable_and_exact(self) -> None:
        from pead.baselines.judge import MODEL_REVISION, TOKENIZER_MANIFEST_SHA256, WEIGHT_MANIFEST_SHA256
        identity = yaml.safe_load((ROOT / "manifests/model_identities/qwen2_5_7b_instruct.yaml").read_text(encoding="utf-8"))
        self.assertEqual(identity["revision_commit"], MODEL_REVISION)
        self.assertEqual(identity["weight_manifest_sha256"], WEIGHT_MANIFEST_SHA256)
        self.assertEqual(identity["tokenizer_manifest_sha256"], TOKENIZER_MANIFEST_SHA256)
        self.assertEqual(len(identity["weight_shards"]), 4)

    def test_grouped_ensemble_out_of_fold(self) -> None:
        assignments = grouped_fold_assignments((f"g{i}" for i in range(10)))
        self.assertEqual(set(assignments.values()), set(range(5)))
        assert_out_of_fold((("g0", 0, 1),))
        with self.assertRaises(ValueError):
            assert_out_of_fold((("g0", 0, 0),))

    def test_method_cards_are_complete(self) -> None:
        cards = [path for path in (ROOT / "manifests/method_cards").glob("*.yaml") if path.name != "mavs_human_design_disclosure.yaml"]
        self.assertEqual(len(cards), 26)
        for path in cards:
            card = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertTrue(card["claim_boundary"])
            self.assertTrue(card["implementation_hashes"])


if __name__ == "__main__":
    unittest.main()
