"""Deterministic non-scientific Phase 9 audit and report fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pead.audits.abstention import audit_abstention
from pead.audits.budget import audit_budgets
from pead.audits.claims import audit_claims
from pead.audits.failure_retention import audit_failure_retention
from pead.audits.holdouts import audit_holdouts
from pead.audits.manifest import audit_manifest
from pead.audits.non_triviality import audit_non_triviality
from pead.audits.reproduction import audit_reproduction
from pead.audits.traces import audit_traces
from pead.core.hashing import canonical_hash
from pead.core.types import AuthorizationAction as A
from pead.metrics.protected import DecisionOpportunity, protected_metrics


def machine_audit_reports(root: Path) -> dict[str, dict[str, Any]]:
    retained = {
        "equivalence": json.loads((root / "results/audits/phase3/equivalence_report.json").read_text(encoding="utf-8")),
        "authorization": json.loads((root / "results/audits/phase3/authorization_report.json").read_text(encoding="utf-8")),
        "leakage": json.loads((root / "results/audits/phase3/leakage_report.json").read_text(encoding="utf-8")),
        "access": json.loads((root / "results/audits/phase6/access_report.json").read_text(encoding="utf-8")),
    }
    opportunities = (
        DecisionOpportunity("u", "w1", "D1", "M01", A.REJECT, A.REJECT),
        DecisionOpportunity("s", "w2", "D1", "M01", A.ACCEPT, A.ACCEPT),
        DecisionOpportunity("a", "w3", "D1", "M01", A.ESCALATE, A.ESCALATE),
    )
    metrics = protected_metrics(opportunities)
    trace = {
        "run_id": "phase9-contract", "config_hash": "a" * 64, "commit_hash": "b" * 40,
        "environment_hash": "c" * 64, "world_id": "w1", "atomic_group_id": "g1",
        "split_id": "development_fixture", "method_id": "MAVS-A15", "projection_hash": "d" * 64,
        "decision_hash": "e" * 64, "trace_hash": "f" * 64,
        "decision_commit_time": "2026-08-01T00:00:00+00:00", "label_reveal_time": "2026-08-01T00:00:01+00:00",
        "raw_trace_id": "trace-contract-1",
    }
    retained.update({
        "holdouts": audit_holdouts({"c1": "development_fit", "c2": "calibration_fit"}, {"c1": "g1", "c2": "g2"}),
        "budget": audit_budgets({"MAVS-A15": {"seconds": 1.0}}, {"MAVS-A15": {"seconds": 2.0}}),
        "traces": audit_traces((trace,)),
        "abstention": audit_abstention(metrics),
        "manifest": audit_manifest({"artifact": "a" * 64}, {"artifact": "a" * 64}),
        "reproduction": audit_reproduction({"metric": 0.5}, {"metric": 0.5}, tolerance=1e-12, expected_claims=(), actual_claims=()),
        "claims": audit_claims({f"C{i}": False for i in range(1, 7)}, (), "No scientific claims emitted.", {}, ()),
        "failure_retention": audit_failure_retention(("method-pass", "method-negative"), {"method-pass": "pass", "method-negative": "fail"}),
        "non_triviality": audit_non_triviality({"compositional_fraction": 0.7, "three_factor_fraction": 0.4, "direct_label_flags": 0, "prior_shift_controls": 1, "label_permutation_controls": 1, "ambiguity_certificates": 1}),
    })
    return retained


def human_payload(checkpoint_id: str) -> dict[str, Any]:
    scopes = {
        "label_engine_independence": (
            ["src/pead/labels/evaluator_dsl.py", "src/pead/labels/evaluator_reference.py", "results/audits/phase2/phase2_compliance.json"],
            ["Both label engines and the retained dual-engine agreement evidence were reviewed; source identities are separate and MAVS-independent."],
        ),
        "access_projection_raw_g_parity": (
            ["configs/access/raw_g.yaml", "results/audits/phase6/access_report.json", "results/audits/phase6/representation_parity_report.json"],
            ["Raw-G field masks, runtime firewall evidence, and tabular/sequence/graph semantic parity were reviewed."],
        ),
        "domain_mechanism_label_strata": (
            ["results/audits/phase3/generation_summary.json", "results/audits/phase4/phase4_compliance.json"],
            ["Available pre-claim-bank domain, mechanism, authorization-label, reversal, scope, and evidence fixture strata were reviewed; D7/D8 remain custody-bound to Phase 9A."],
        ),
        "failures_and_quarantines": (
            ["configs/study/failure_card_schema_v1.yaml", "tests/integration/test_failure_card_bijection.py", "results/reports/phase9_contract/report_contract.json"],
            ["All seven qualifying failure classes were exercised with exact-card bijection; no scientific headline failure or quarantine exists before Phase 10."],
        ),
        "benchmark_non_triviality": (
            ["results/audits/phase3/generation_summary.json", "results/audits/phase3/leakage_report.json", "results/audits/phase4/phase4_compliance.json"],
            ["Composition, three-factor, ambiguity, nuisance/control, and direct-label leakage controls were reviewed against retained fixtures."],
        ),
        "baseline_fidelity": (
            ["results/audits/phase7/method_cards_report.json", "manifests/method_cards", "configs/methods/method_inventory_v1.yaml"],
            ["All 26 comparator/variant cards, fidelity classifications, limitations, and the exact 39-method inventory were reviewed."],
        ),
        "negative_result_retention": (
            ["CLAIMS.md", "src/pead/audits/failure_retention.py", "results/reports/phase9_contract/report_contract.json"],
            ["Negative-result policy and unsuppressed failed-method reporting were reviewed; no scientific result exists yet to retain or omit."],
        ),
    }
    reviewed_component_ids, findings = scopes[checkpoint_id]
    return {
        "schema_version": "1.0", "checkpoint_id": checkpoint_id,
        "reviewer_role": "Phase 9 internal contract auditor",
        "independence_relationship": "Post-implementation audit role using independent fixtures; internal review only, not external human validation.",
        "reviewed_component_ids": reviewed_component_ids, "checklist_version": "PEAD-HUMAN-v1",
        "findings": findings,
        "corrections": [], "unresolved_concerns": [], "status": "pass",
    }
