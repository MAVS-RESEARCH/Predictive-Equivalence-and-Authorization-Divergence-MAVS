"""Independent high-volume Phase 9 metric, audit, report, and human-checkpoint review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from pead.audits.human import CHECKPOINTS, audit_human_program, sign_human_audit
from pead.audits.master import AUDIT_IDS, execute_master_audit
from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash
from pead.core.types import AuthorizationAction as A
from pead.metrics.paradigm import paired_paradigm_metrics
from pead.metrics.protected import DecisionOpportunity, protected_metrics
from pead.metrics.scope import DiagnosticObservation, diagnostic_science_metrics
from pead.metrics.sequential import SequenceObservation, sequential_metrics
from pead.metrics.statistics import exact_binomial_interval, holm_correction, mechanism_domain_bootstrap
from pead.phase2.audit import write_json
from pead.phase9.fixtures import human_payload, machine_audit_reports
from pead.reports.claim_ledger import build_claim_ledger
from pead.reports.failure_cards import QualifyingEvent, audit_failure_card_bijection, build_failure_card
from pead.reports.figures import build_figure_spec
from pead.reports.tables import ProvenanceCell, audit_table_provenance, build_method_table


def metric_review(root: Path) -> dict[str, Any]:
    registry = yaml.safe_load((root / "configs/metrics/metric_registry_v1.yaml").read_text(encoding="utf-8"))
    families = registry["families"]
    names = {name for family in families.values() for name in family["metrics"]}
    if len(names) != 38:
        raise ValueError(f"registered metric inventory must contain 38 unique metrics, found {len(names)}")
    paradigm = paired_paradigm_metrics(
        p_only_error=0.5, lower_bound=0.5, raw_g_utility=0.8, p_only_utility=0.4,
        mavs_utility=0.9, flat_raw_g_utility=0.7,
        expected_pairs={"p": ("Accept", "Reject")}, observed_pairs={"p": ("Accept", "Reject")},
    )
    protected = protected_metrics((
        DecisionOpportunity("u", "w1", "D1", "M01", A.REJECT, A.REJECT),
        DecisionOpportunity("s", "w2", "D1", "M01", A.ACCEPT, A.ACCEPT),
        DecisionOpportunity("a", "w3", "D1", "M01", A.ESCALATE, A.ESCALATE),
    ))
    diagnostic = diagnostic_science_metrics((
        DiagnosticObservation("p", "DSCF-ZH-v1", "positive", True, True, True, True, True, False, False, True, False, True),
        DiagnosticObservation("n", "DSCF-ZH-v1", "matched_negative", True, False, False, False, True, True, False, False, False, False),
        DiagnosticObservation("o", "DSCF-ZH-v1", "adversarial_out_of_scope", False, False, False, False, True, True, False, False, False, False),
        DiagnosticObservation("b", "DSCF-ZH-v1", "boundary", True, True, True, True, True, False, False, True, False, True, boundary_distance=0.5, boundary_influence_delta=0.25),
    ))
    sequential = sequential_metrics((SequenceObservation("s", (A.ACCEPT, A.ACCEPT, A.REJECT), (A.ACCEPT, A.ACCEPT, A.REJECT), 2, None),))
    if set(paradigm) - {"paired_units"} != set(families["paradigm"]["metrics"]):
        raise ValueError("paradigm metric implementation differs from registry")
    if set(protected) - {"opportunity_count"} != set(families["protected"]["metrics"]):
        raise ValueError("protected metric implementation differs from registry")
    if set(diagnostic) != set(families["diagnostic_sciences"]["metrics"]):
        raise ValueError("Diagnostic Sciences implementation differs from registry")
    if set(sequential) != set(families["sequential"]["metrics"]):
        raise ValueError("sequential metric implementation differs from registry")
    return {"status": "pass", "registered_metrics": len(names), "families": {key: len(value["metrics"]) for key, value in families.items()}, "analytic_fixtures": 4}


def statistical_stress() -> dict[str, Any]:
    effects = {f"unit-{index:05d}": ((index % 17) - 8) / 16 for index in range(10_000)}
    mechanisms = {unit: f"M{index % 12 + 1:02d}" for index, unit in enumerate(effects)}
    domains = {unit: f"D{index % 8 + 1}" for index, unit in enumerate(effects)}
    first = mechanism_domain_bootstrap(effects, mechanisms, domains, repetitions=2_000, seed=9107)
    second = mechanism_domain_bootstrap(effects, mechanisms, domains, repetitions=2_000, seed=9107)
    zero_interval = exact_binomial_interval(0, 10_000)
    correction = holm_correction({f"A{index:02d}": min(1.0, index / 100) for index in range(1, 16)})
    if first != second or zero_interval[0] != 0.0 or len(correction) != 15:
        raise ValueError("statistical stress review failed")
    return {"status": "pass", "paired_units": 10_000, "bootstrap_repetitions": 2_000, "deterministic_replays": 2, "clusters": first["clusters"], "zero_count_trials": 10_000, "zero_count_interval": zero_interval, "holm_hypotheses": 15}


def master_mutation_review(root: Path, console: ResearchConsole) -> dict[str, Any]:
    passed = execute_master_audit(machine_audit_reports(root), console=console)
    blocked = []
    for audit_id in AUDIT_IDS:
        reports = machine_audit_reports(root)
        reports[audit_id] = {"status": "fail", "fixture": f"release-block-{audit_id}"}
        try:
            execute_master_audit(reports, console=console)
        except ValueError:
            blocked.append(audit_id)
    if tuple(blocked) != AUDIT_IDS:
        raise ValueError("not every release-blocking audit mutation was rejected")
    return {"status": "pass", "machine_audits": len(AUDIT_IDS), "positive_master": passed, "release_blocking_mutations": len(blocked), "blocked_audits": blocked}


def failure_and_report_review(root: Path) -> dict[str, Any]:
    base = {
        "run_id": "phase9-contract", "commit_hash": "a" * 40, "environment_hash": "b" * 64,
        "config_hash": "c" * 64, "method_id": "MAVS-A15", "projection_hash": "d" * 64,
        "trace_hash": "e" * 64, "domain_id": "D1", "mechanism_id": "M01", "partition_id": "fixture",
        "atomic_group_id": "group", "expected_action": "Reject", "observed_action": "Accept",
        "visible_evidence_hash": "f" * 64, "diagnostic_state": {"z_h": 1.0}, "access_profile": "Raw-G",
        "scope_contract_id": "DSCF-ZH-v1", "root_cause_class": "contract_fixture",
        "root_cause_evidence": ("trace",), "case_validity_verdict": "valid", "containment_status": "contained",
        "quarantine_status": "not_required", "repair_status": "not_attempted", "invalidation_status": "affected_result_invalid",
        "affected_claim_ids": ("C4",), "affected_outcome_tiers": ("architectural-support",),
        "reproduction_command": "python scripts/audit_all.py", "artifact_references": ("trace.jsonl",),
    }
    event_types = ("protected error", "scope anomaly", "label disagreement", "access violation", "quarantine", "invalidation", "reproduction mismatch")
    events = tuple(QualifyingEvent(f"event-{index}", event_type, {**base, "case_or_group_id": f"event-{index}"}) for index, event_type in enumerate(event_types))
    cards = tuple(build_failure_card(event) for event in events)
    bijection = audit_failure_card_bijection(events, cards)
    inventory = yaml.safe_load((root / "configs/methods/method_inventory_v1.yaml").read_text(encoding="utf-8"))["methods"]
    method_ids = tuple(row["method_id"] for row in inventory)
    cell = lambda method: ProvenanceCell(f"cell-{method}", 0.0, f"processed-{method}", (f"raw-{method}",), "PEAD-METRICS-v1", ("master-audit",))
    table = build_method_table(method_ids, {method: {"contract_value": cell(method)} for method in method_ids}, {method: "fail" if method.endswith("A14") else "not_run" for method in method_ids})
    provenance = audit_table_provenance(table)
    figure = build_figure_spec(method_ids, {method: cell(method) for method in method_ids})
    claims = build_claim_ledger({f"C{i}": False for i in range(1, 7)}, (), narrative="No Phase 9 scientific claims emitted.", required_evidence={}, available_evidence=())
    return {"status": "pass", "failure_card_bijection": bijection, "failure_card_hashes": [card.content_hash() for card in cards], "table": {"methods": len(method_ids), **provenance, "failed_methods_visible": table["failed_methods_visible"]}, "figure_points": len(figure["points"]), "claim_ledger": claims}


def human_review(root: Path) -> dict[str, Any]:
    output = root / "results/audits/phase9/human"
    artifacts = []
    for checkpoint in CHECKPOINTS:
        artifact = sign_human_audit(human_payload(checkpoint))
        write_json(output / f"{checkpoint}.json", artifact)
        artifacts.append(artifact)
    return audit_human_program(artifacts)


def execute_phase9_review(root: Path, console: ResearchConsole) -> dict[str, Any]:
    # STEP LOG P9-REVIEW-001: Reconcile the live implementation with all registered metric identities and analytic fixtures.
    console.log("P9-REVIEW-001", "Auditing registered metric implementations.")
    metrics = metric_review(root)
    # STEP LOG P9-REVIEW-002: Stress deterministic paired cluster inference, exact zero-count intervals, and Holm correction.
    console.log("P9-REVIEW-002", "Executing statistical stress review.")
    statistics = statistical_stress()
    # STEP LOG P9-REVIEW-003: Execute all thirteen machine audits and independently inject one release blocker into each family.
    console.log("P9-REVIEW-003", "Executing master-audit mutation review.")
    master = master_mutation_review(root, console)
    # STEP LOG P9-REVIEW-004: Prove strict failure-card bijection, unsuppressed methods, cell provenance, and claim fail-closure.
    console.log("P9-REVIEW-004", "Auditing failure and report builders.")
    reporting = failure_and_report_review(root)
    # STEP LOG P9-REVIEW-005: Produce and validate all seven signed internal human-checkpoint contract artifacts.
    console.log("P9-REVIEW-005", "Executing signed internal checkpoint review.")
    human = human_review(root)
    # STEP LOG P9-REVIEW-006: Report the complete non-scientific Phase 9 implementation verdict.
    console.log("P9-REVIEW-006", "Phase 9 independent implementation review passed.", status="pass", details={"metrics": metrics["registered_metrics"], "release_blocking_mutations": master["release_blocking_mutations"]})
    return {"status": "pass", "metrics": metrics, "statistics": statistics, "master_audit": master, "reporting": reporting, "human_program": human, "scientific_results": 0, "trained_models": 0}
