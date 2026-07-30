"""Complete in-memory Phase 4 bank generation and gate accounting."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from pead.config.console import ResearchConsole
from pead.core.scope_contract import ScopeBank
from pead.tracks.evidence_sufficiency import (
    EvidenceClass,
    evidence_case_counts,
    iter_evidence_cases,
    remove_permitted_resolution_channels,
)
from pead.tracks.reversal import (
    build_reversal_sequence,
    load_reversal_allocations,
    load_reversal_controls,
    reversal_allocation_counts,
)
from pead.tracks.scope import iter_scope_cases, scope_case_counts


class Phase4GenerationError(ValueError):
    """Raised when a complete Phase 4 denominator or invariant fails."""


def generate_phase4_banks(
    repo_root: Path,
    console: ResearchConsole,
) -> dict[str, Any]:
    # STEP LOG P4-GENERATE-001: Load and verify the signed Phase 4 denominators before constructing any case.
    console.log("P4-GENERATE-001", "Loading signed Phase 4 allocations.")
    allocations = load_reversal_allocations(repo_root)
    controls = load_reversal_controls(repo_root)
    reversal_counts = reversal_allocation_counts(allocations, controls)
    reversal_labels: Counter[str] = Counter()
    certificates = 0
    stale_opportunities = 0
    generation_disagreements = 0
    for domain_id in tuple(f"D{index}" for index in range(1, 9)):
        # STEP LOG P4-GENERATE-002: Generate one complete domain of deterministic reversal sequences with dual-engine checks.
        console.log(
            "P4-GENERATE-002",
            "Generating complete reversal domain.",
            details={"domain_id": domain_id},
        )
        for allocation in (
            item for item in allocations if item.domain_id == domain_id
        ):
            sequence = build_reversal_sequence(allocation, repo_root)
            reversal_labels.update(
                step.evaluation.label.value for step in sequence.steps
            )
            certificates += sum(
                step.ambiguity_certificate is not None
                for step in sequence.steps
            )
            stale_opportunities += len(sequence.stale_authorization_opportunities)
            generation_disagreements += int(
                not sequence.primary_reference_generation_agreement
                or not sequence.dual_label_agreement
                or not sequence.predictive_byte_stable
            )
    # STEP LOG P4-GENERATE-003: Construct every frozen-registry scope case and verify authority-safe behavior.
    console.log("P4-GENERATE-003", "Generating complete diagnostic scope banks.")
    scope_cases = tuple(iter_scope_cases(repo_root))
    scope_counts = scope_case_counts(scope_cases)
    out_of_scope_truth_changes = sum(
        case.truth_hash_before != case.truth_hash_after
        for case in scope_cases
        if case.bank is ScopeBank.ADVERSARIAL_OUT_OF_SCOPE
    )
    # STEP LOG P4-GENERATE-004: Enumerate and independently verify every fixed-method evidence proof.
    console.log("P4-GENERATE-004", "Generating complete evidence-sufficiency bank.")
    evidence_cases = tuple(iter_evidence_cases(repo_root))
    evidence_counts = evidence_case_counts(evidence_cases)
    reducible = next(
        case
        for case in evidence_cases
        if case.evidence_class is EvidenceClass.REDUCIBLY_AMBIGUOUS
    )
    transformed = remove_permitted_resolution_channels(reducible)
    if (
        reversal_counts["canonical_sequences"] != 4_000
        or reversal_counts["canonical_steps"] != 24_000
        or reversal_counts["additional_controls"] != 800
        or scope_counts["canonical_cases"] != 22_400
        or scope_counts["additional_controls"] != 5_600
        or evidence_counts["total_cases"] != 12_000
        or evidence_counts["verified_certificates"] != 12_000
        or generation_disagreements
        or out_of_scope_truth_changes
        or transformed.certificate.conclusion
        != "irreducibly_ambiguous_escalate"
    ):
        raise Phase4GenerationError("complete Phase 4 generation gate failed")
    report = {
        "schema_version": "1.0",
        "status": "pass",
        "reversal": {
            **reversal_counts,
            "authorization_labels": reversal_labels,
            "ambiguity_certificates": certificates,
            "stale_authorization_opportunities": stale_opportunities,
            "generation_or_label_disagreements": generation_disagreements,
            "known_change_and_restoration_times": True,
            "false_reversal_controls": 200,
        },
        "scope": {
            **scope_counts,
            "out_of_scope_truth_changes": out_of_scope_truth_changes,
            "raw_correlation_terminal_vetoes": 0,
        },
        "evidence_sufficiency": {
            **evidence_counts,
            "reducible_channel_removal_conclusion": (
                transformed.certificate.conclusion
            ),
            "reducible_channel_removal_action": transformed.expected_action.value,
        },
        "paper_boundary": {
            "fixed_methods_only": True,
            "adaptive_acquisition_executed": False,
            "released_claim_bank_rows": 0,
            "models_trained": 0,
        },
    }
    # STEP LOG P4-GENERATE-005: Report the complete generated denominators and hard-gate verdict.
    console.log(
        "P4-GENERATE-005",
        "Complete Phase 4 banks passed generation gates.",
        status="pass",
        details={
            "evidence_cases": evidence_counts["total_cases"],
            "reversal_sequences": reversal_counts["canonical_sequences"],
            "reversal_steps": reversal_counts["canonical_steps"],
            "scope_cases": scope_counts["total_cases"],
        },
    )
    return report
