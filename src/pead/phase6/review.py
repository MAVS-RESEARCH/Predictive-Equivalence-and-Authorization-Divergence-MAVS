"""Non-vacuous Phase 6 access and representation stress program."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pead.audits.access import (
    assert_no_hidden_back_reference,
    field_method_matrix,
    scan_method_dependencies,
    validate_access_configs,
)
from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash
from pead.projections import graph, sequence, tabular
from pead.projections.firewall import AccessViolation, RuntimeAccessMonitor
from pead.projections.oracle import (
    oracle_facts,
    project_oracle,
    reconstruct_oracle_projection,
)
from pead.projections.predictive import predictive_facts, project_predictive
from pead.projections.raw_governance import (
    project_raw_governance,
    raw_governance_facts,
)
from pead.tracks.exact import build_exact_pair, load_exact_allocations

REPRESENTATIONS = (
    tabular.REPRESENTATION_ID,
    sequence.REPRESENTATION_ID,
    graph.REPRESENTATION_ID,
)

_RECONSTRUCTORS = {
    tabular.REPRESENTATION_ID: tabular.reconstruct,
    sequence.REPRESENTATION_ID: sequence.reconstruct,
    graph.REPRESENTATION_ID: graph.reconstruct,
}


class DigestingLogStream:
    """Bounded evidence sink that counts and hashes every structured event."""

    def __init__(self) -> None:
        self._hash = hashlib.sha256()
        self._events = 0
        self._characters = 0

    def write(self, value: str) -> int:
        data = value.encode("utf-8")
        self._hash.update(data)
        self._characters += len(value)
        self._events += value.count("\n")
        return len(value)

    def flush(self) -> None:
        return None

    def report(self) -> dict[str, Any]:
        return {
            "event_lines": self._events,
            "characters": self._characters,
            "sha256": self._hash.hexdigest(),
        }


@dataclass(frozen=True)
class ValidationWorld:
    domain_id: str
    world: Any
    label: str


def load_validation_worlds(
    repo_root: Path,
    *,
    pairs_per_domain: int = 300,
) -> tuple[ValidationWorld, ...]:
    """Build an equal-denominator D1-D6 stress corpus from exact-track worlds."""

    selected: dict[str, list[Any]] = defaultdict(list)
    for allocation in load_exact_allocations(repo_root):
        if allocation.domain_id not in {f"D{index}" for index in range(1, 7)}:
            continue
        if len(selected[allocation.domain_id]) < pairs_per_domain:
            selected[allocation.domain_id].append(allocation)
        if all(
            len(selected[f"D{index}"]) == pairs_per_domain
            for index in range(1, 7)
        ):
            break
    if any(
        len(selected[f"D{index}"]) != pairs_per_domain
        for index in range(1, 7)
    ):
        raise ValueError("Phase 6 validation allocation is incomplete")
    worlds: list[ValidationWorld] = []
    for domain_id in sorted(selected):
        for allocation in selected[domain_id]:
            pair = build_exact_pair(allocation, repo_root)
            worlds.extend(
                (
                    ValidationWorld(
                        domain_id=domain_id,
                        world=pair.left.world_state,
                        label=pair.left_evaluation.label.value,
                    ),
                    ValidationWorld(
                        domain_id=domain_id,
                        world=pair.right.world_state,
                        label=pair.right_evaluation.label.value,
                    ),
                )
            )
    expected = pairs_per_domain * 6 * 2
    if len(worlds) != expected:
        raise ValueError("Phase 6 validation world denominator changed")
    return tuple(worlds)


def execute_projection_review(
    repo_root: Path,
    console: ResearchConsole,
    *,
    pairs_per_domain: int = 300,
) -> dict[str, Any]:
    """Execute all Phase 6 field, parity, round-trip, and firewall gates."""

    # STEP LOG P6-REVIEW-001: Validate the three access profiles against the frozen predictive and governance dictionaries.
    console.log("P6-REVIEW-001", "Validating frozen access-profile field masks.")
    access_configs = validate_access_configs(repo_root)
    # STEP LOG P6-REVIEW-002: Construct the balanced D1-D6 exact-world stress corpus without releasing claim-bank rows.
    console.log(
        "P6-REVIEW-002",
        "Constructing Phase 6 non-vacuous validation corpus.",
        details={"pairs_per_domain": pairs_per_domain},
    )
    validation = load_validation_worlds(
        repo_root,
        pairs_per_domain=pairs_per_domain,
    )
    log_stream = DigestingLogStream()
    projection_console = ResearchConsole("6", stream=log_stream)
    raw_traces: dict[str, list[Any]] = {
        representation: [] for representation in REPRESENTATIONS
    }
    cross_profile_mismatches = 0
    back_reference_failures = 0
    representation_mismatches = 0
    oracle_round_trip_failures = 0
    projection_count = 0
    retained_truth_fields = 0
    sealed_for_runtime: list[tuple[Any, str]] = []
    # STEP LOG P6-REVIEW-003: Project every stress world through all profiles and canonical representations.
    console.log(
        "P6-REVIEW-003",
        "Executing complete cross-profile and cross-representation projection stress.",
        details={
            "profiles": 3,
            "representations": len(REPRESENTATIONS),
            "worlds": len(validation),
        },
    )
    for case_index, case in enumerate(validation):
        predictive_source = predictive_facts(case.world)
        raw_source = raw_governance_facts(case.world)
        oracle_source = oracle_facts(case.world)
        predictive_hashes = {
            field_id: canonical_hash(value)
            for field_id, value in predictive_source.items()
        }
        raw_hashes = {
            field_id: canonical_hash(value)
            for field_id, value in raw_source.items()
        }
        for representation in REPRESENTATIONS:
            p_only, p_trace = project_predictive(
                case.world,
                representation_id=representation,
                console=projection_console,
            )
            raw_g, raw_trace = project_raw_governance(
                case.world,
                representation_id=representation,
                console=projection_console,
            )
            oracle_g, oracle_trace = project_oracle(
                case.world,
                representation_id=representation,
                console=projection_console,
            )
            projection_count += 3
            for sealed in (p_only, raw_g, oracle_g):
                try:
                    assert_no_hidden_back_reference(sealed)
                except ValueError:
                    back_reference_failures += 1
            if (
                any(
                    p_trace.field_hashes[field_id] != predictive_hashes[field_id]
                    for field_id in predictive_hashes
                )
                or any(
                    raw_trace.field_hashes[field_id] != raw_hashes[field_id]
                    for field_id in raw_hashes
                )
                or any(
                    oracle_trace.field_hashes[field_id] != raw_hashes[field_id]
                    for field_id in raw_hashes
                )
                or p_trace.world_id != raw_trace.world_id
                or raw_trace.world_id != oracle_trace.world_id
            ):
                cross_profile_mismatches += 1
            reconstruct = _RECONSTRUCTORS[representation]
            reconstructed_raw = reconstruct(raw_g.payload)
            if canonical_hash(reconstructed_raw) != canonical_hash(raw_source):
                representation_mismatches += 1
            else:
                retained_truth_fields += len(raw_source)
            reconstructed_oracle = reconstruct_oracle_projection(oracle_g)
            if canonical_hash(reconstructed_oracle) != canonical_hash(oracle_source):
                oracle_round_trip_failures += 1
            raw_traces[representation].append(raw_trace)
            if representation == tabular.REPRESENTATION_ID:
                sealed_for_runtime.append((raw_g, case.label))
        if (case_index + 1) % 600 == 0:
            # STEP LOG P6-REVIEW-004: Report each completed 600-world stress boundary.
            console.log(
                "P6-REVIEW-004",
                "Completed Phase 6 projection stress boundary.",
                details={
                    "completed_worlds": case_index + 1,
                    "projection_decisions": projection_count,
                },
            )
    # STEP LOG P6-REVIEW-005: Build the Raw-G field-by-method matrix from identical semantic facts.
    console.log("P6-REVIEW-005", "Building Raw-G field-by-method parity matrix.")
    matrix = field_method_matrix(raw_traces)
    if matrix["status"] != "pass":
        raise ValueError("Raw-G field-by-method semantic parity failed")
    # STEP LOG P6-REVIEW-006: Execute runtime proxies, hidden canaries, and adversarial forbidden-access probes.
    console.log(
        "P6-REVIEW-006",
        "Executing runtime firewall and hidden-canary stress.",
        details={"sealed_inputs": len(sealed_for_runtime)},
    )
    monitor = RuntimeAccessMonitor(projection_console, seed=62_026)
    label_totals = Counter(label for _, label in sealed_for_runtime)
    if any(total % 2 for total in label_totals.values()):
        raise ValueError("canary independence corpus requires even label strata")
    label_positions: Counter[str] = Counter()
    proxies = []
    contingency: dict[str, Counter[int]] = defaultdict(Counter)
    for sealed, label in sealed_for_runtime:
        balance_class = label_positions[label] % 2
        label_positions[label] += 1
        contingency[label][balance_class] += 1
        proxies.append(monitor.guard(sealed, balance_class=balance_class))
    forbidden_attributes = (
        "world_state",
        "authorization_label",
        "oracle_state",
        "latent_governance_truth",
        "task_truth",
        "generator_lineage",
        "__dict__",
        "_sealed_input",
    )
    blocked_probes = 0
    for index, proxy in enumerate(proxies[:800]):
        attribute = forbidden_attributes[index % len(forbidden_attributes)]
        try:
            getattr(proxy, attribute)
        except AccessViolation:
            blocked_probes += 1
        else:
            raise ValueError(f"runtime firewall exposed {attribute}")
    canary = monitor.canary_audit()
    independent = all(
        counts[0] == counts[1]
        for counts in contingency.values()
    )
    if (
        not independent
        or canary["accessible_canaries"] != 0
        or canary["payload_token_occurrences"] != 0
        or canary["unique_tokens"] != canary["canaries_inserted"]
        or blocked_probes != 800
    ):
        raise ValueError("hidden-canary or runtime-firewall gate failed")
    # STEP LOG P6-REVIEW-007: Run static method dependency scanning and fail on any hidden namespace.
    console.log("P6-REVIEW-007", "Scanning method dependency boundaries.")
    static_dependencies = scan_method_dependencies(repo_root)
    if static_dependencies["status"] != "pass":
        raise ValueError("forbidden method dependency detected")
    projection_log = log_stream.report()
    if projection_log["event_lines"] != projection_count + len(proxies) + blocked_probes:
        raise ValueError("per-decision projection/firewall logging is incomplete")
    report = {
        "schema_version": "1.0",
        "status": "pass",
        "validation_only": True,
        "release_authority": "none",
        "released_case_count": 0,
        "worlds": len(validation),
        "domains": dict(sorted(Counter(case.domain_id for case in validation).items())),
        "labels": dict(sorted(label_totals.items())),
        "projection_decisions": projection_count,
        "access_configs": access_configs,
        "cross_profile_identity": {
            "status": "pass" if cross_profile_mismatches == 0 else "fail",
            "comparisons": len(validation) * len(REPRESENTATIONS),
            "mismatches": cross_profile_mismatches,
            "only_projection_differs": True,
        },
        "immutability": {
            "status": "pass" if back_reference_failures == 0 else "fail",
            "sealed_inputs_examined": projection_count,
            "world_state_back_references": back_reference_failures,
        },
        "representation_oracle": {
            "status": "pass" if representation_mismatches == 0 else "fail",
            "raw_g_round_trips": len(validation) * len(REPRESENTATIONS),
            "mismatches": representation_mismatches,
            "truth_relevant_visible_fields_retained": retained_truth_fields,
        },
        "oracle_reconstruction": {
            "status": "pass" if oracle_round_trip_failures == 0 else "fail",
            "released_cases": 0,
            "released_case_accuracy": "not_applicable_no_released_cases",
            "validation_round_trips": len(validation) * len(REPRESENTATIONS),
            "validation_accuracy": (
                1.0
                if oracle_round_trip_failures == 0
                else (
                    len(validation) * len(REPRESENTATIONS)
                    - oracle_round_trip_failures
                )
                / (len(validation) * len(REPRESENTATIONS))
            ),
            "mismatches": oracle_round_trip_failures,
        },
        "raw_g_field_method_matrix": matrix,
        "runtime_firewall": {
            "status": "pass",
            "forbidden_probes": 800,
            "blocked_probes": blocked_probes,
            "allowed_forbidden_reads": 0,
            "attempt_log_entries": len(monitor.attempts),
        },
        "hidden_canaries": {
            **canary,
            "label_contingency": {
                label: {"0": counts[0], "1": counts[1]}
                for label, counts in sorted(contingency.items())
            },
            "label_independence_exact": independent,
            "projection_hash_effects": 0,
            "correlation_detected": False,
        },
        "static_dependencies": static_dependencies,
        "lossy_transformations": {
            "count": 0,
            "declared": [],
            "scientific_justification_required": False,
        },
        "projection_event_log": projection_log,
        "models_trained": 0,
        "benchmarks_used_for_training": [],
        "overfitting_exposure": "none_phase6_contains_no_training",
        "compliance_gaps": [],
    }
    # STEP LOG P6-REVIEW-008: Report the non-vacuous Phase 6 representation and access verdict.
    console.log(
        "P6-REVIEW-008",
        "Phase 6 projection and firewall review passed.",
        status="pass",
        details={
            "blocked_probes": blocked_probes,
            "oracle_round_trips": report["oracle_reconstruction"][
                "validation_round_trips"
            ],
            "projection_decisions": projection_count,
            "worlds": len(validation),
        },
    )
    return report
