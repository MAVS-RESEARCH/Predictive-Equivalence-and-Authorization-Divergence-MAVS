"""Generate and validate the complete Phase 3 exact and near bank in memory."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from pead.audits.authorization import AuthorizationAccumulator
from pead.audits.equivalence import EquivalenceAccumulator
from pead.audits.leakage import LeakageSample, sample_from_predictive
from pead.config.console import ResearchConsole
from pead.tracks.exact import build_exact_pair, load_exact_allocations
from pead.tracks.near import build_near_pair, load_near_allocations


def _samples_for_pair(pair: Any) -> tuple[LeakageSample, LeakageSample]:
    allocation = pair.allocation
    return (
        sample_from_predictive(
            pair.left.predictive_state,
            pair.left_evaluation.label,
            allocation.atomic_group_id,
            allocation.split_id,
        ),
        sample_from_predictive(
            pair.right.predictive_state,
            pair.right_evaluation.label,
            allocation.atomic_group_id,
            allocation.split_id,
        ),
    )


def generate_validation_bank(
    repo_root: Path,
    console: ResearchConsole,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    tuple[LeakageSample, ...],
    dict[str, Any],
]:
    started = time.perf_counter()
    equivalence = EquivalenceAccumulator()
    authorization = AuthorizationAccumulator()
    leakage_samples: list[LeakageSample] = []
    exact_allocations = load_exact_allocations(repo_root)
    near_allocations = load_near_allocations(repo_root)
    # STEP LOG P3-GENERATE-001: Confirm the complete exact and near allocation denominators before world generation.
    console.log(
        "P3-GENERATE-001",
        "Loaded frozen Phase 3 allocation schedules.",
        details={
            "exact_pairs": len(exact_allocations),
            "near_pairs": len(near_allocations),
        },
    )
    if len(exact_allocations) != 16_000 or len(near_allocations) != 8_000:
        raise ValueError("Phase 3 allocation denominators are incomplete")
    for index, allocation in enumerate(exact_allocations, start=1):
        pair = build_exact_pair(allocation, repo_root)
        equivalence.observe_exact(pair)
        authorization.observe_exact(pair)
        leakage_samples.extend(_samples_for_pair(pair))
        if index % 2_000 == 0:
            # STEP LOG P3-GENERATE-002: Report each completed exact-domain generation boundary.
            console.log(
                "P3-GENERATE-002",
                "Completed exact-domain generation boundary.",
                details={
                    "completed_pairs": index,
                    "domain": allocation.domain_id,
                },
            )
    for index, allocation in enumerate(near_allocations, start=1):
        pair = build_near_pair(allocation, repo_root)
        equivalence.observe_near(pair)
        authorization.observe_near(pair)
        leakage_samples.extend(_samples_for_pair(pair))
        if index % 1_000 == 0:
            # STEP LOG P3-GENERATE-003: Report each completed near-domain generation boundary.
            console.log(
                "P3-GENERATE-003",
                "Completed near-domain generation boundary.",
                details={
                    "completed_pairs": index,
                    "domain": allocation.domain_id,
                },
            )
    equivalence_report = equivalence.finalize()
    authorization_report = authorization.finalize()
    summary = {
        "schema_version": "1.0",
        "status": "pass",
        "release_authority": "none",
        "validation_only": True,
        "final_phase_9a_signature_required": True,
        "released_claim_bank_rows": 0,
        "exact_pairs_generated_in_memory": len(exact_allocations),
        "near_pairs_generated_in_memory": len(near_allocations),
        "worlds_generated_in_memory": len(leakage_samples),
        "leakage_samples_retained": len(leakage_samples),
        "elapsed_seconds": round(time.perf_counter() - started, 6),
    }
    # STEP LOG P3-GENERATE-004: Retain the complete in-memory generation verdict without releasing unsigned bank rows.
    console.log(
        "P3-GENERATE-004",
        "Complete Phase 3 validation bank generated in memory.",
        status="pass",
        details={
            "exact_pairs": len(exact_allocations),
            "near_pairs": len(near_allocations),
            "released_rows": 0,
        },
    )
    return (
        equivalence_report,
        authorization_report,
        tuple(leakage_samples),
        summary,
    )
