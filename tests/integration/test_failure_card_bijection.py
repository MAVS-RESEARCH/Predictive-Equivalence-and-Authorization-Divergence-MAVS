"""Strict FailureCard schema, bijection, suppression, and claims tests."""

import unittest

from pead.reports.claim_ledger import build_claim_ledger
from pead.reports.failure_cards import QualifyingEvent, audit_failure_card_bijection, build_failure_card
from pead.reports.tables import ProvenanceCell, audit_table_provenance, build_method_table


def payload(event_id: str) -> dict[str, object]:
    return {
        "case_or_group_id": event_id, "run_id": "run", "commit_hash": "a" * 40,
        "environment_hash": "b" * 64, "config_hash": "c" * 64, "method_id": "MAVS-A15",
        "projection_hash": "d" * 64, "trace_hash": "e" * 64, "domain_id": "D1",
        "mechanism_id": "M01", "partition_id": "fixture", "atomic_group_id": "g1",
        "expected_action": "Reject", "observed_action": "Accept", "visible_evidence_hash": "f" * 64,
        "diagnostic_state": {"z_h": 1.0}, "access_profile": "Raw-G", "scope_contract_id": "DSCF-ZH-v1",
        "root_cause_class": "contract_fixture", "root_cause_evidence": ("trace",),
        "case_validity_verdict": "valid", "containment_status": "contained", "quarantine_status": "not_required",
        "repair_status": "not_attempted", "invalidation_status": "affected_result_invalid",
        "affected_claim_ids": ("C4",), "affected_outcome_tiers": ("architectural-support",),
        "reproduction_command": "python scripts/audit_all.py", "artifact_references": ("trace.jsonl",),
    }


class FailureCardBijectionTests(unittest.TestCase):
    def test_every_qualifying_type_has_exactly_one_strict_card(self) -> None:
        event_types = ("protected error", "scope anomaly", "label disagreement", "access violation", "quarantine", "invalidation", "reproduction mismatch")
        events = tuple(QualifyingEvent(f"event-{index}", event_type, payload(f"event-{index}")) for index, event_type in enumerate(event_types))
        cards = tuple(build_failure_card(event) for event in events)
        report = audit_failure_card_bijection(events, cards)
        self.assertEqual(report["events"], 7)
        self.assertEqual(report["cards"], 7)

    def test_missing_duplicate_and_orphan_cards_fail(self) -> None:
        event = QualifyingEvent("event", "protected error", payload("event"))
        card = build_failure_card(event)
        with self.assertRaises(ValueError):
            audit_failure_card_bijection((event,), ())
        with self.assertRaises(ValueError):
            audit_failure_card_bijection((event,), (card, card))

    def test_reports_retain_failed_methods_and_cell_provenance(self) -> None:
        cell = ProvenanceCell("cell", 0.5, "processed", ("raw",), "config", ("audit",))
        table = build_method_table(("pass", "failed"), {"pass": {"metric": cell}, "failed": {"metric": cell}}, {"pass": "pass", "failed": "fail"})
        self.assertTrue(table["failed_methods_visible"])
        self.assertEqual(audit_table_provenance(table)["complete"], 2)
        with self.assertRaises(ValueError):
            build_method_table(("pass", "failed"), {"pass": {"metric": cell}}, {"pass": "pass", "failed": "fail"})

    def test_ineligible_claim_emission_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            build_claim_ledger({"C1": False}, ("C1",), narrative="", required_evidence={"C1": ("audit",)}, available_evidence=())


if __name__ == "__main__":
    unittest.main()
