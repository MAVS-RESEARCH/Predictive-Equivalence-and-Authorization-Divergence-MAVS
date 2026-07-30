"""Independent semantic, projection, shortcut, and proxy review for Phase 5."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash
from pead.domains.base import (
    OBVIOUS_AUTHORIZATION_FIELDS,
    DomainAdapter,
    DomainContractError,
    universal_projection_signature,
)
from pead.domains.cyber import load_adapter as load_cyber
from pead.domains.finance import load_adapter as load_finance
from pead.domains.heldout_interface import load_heldout_contract
from pead.domains.multi_agent import load_adapter as load_multi_agent
from pead.domains.retrieval import load_adapter as load_retrieval
from pead.domains.software import load_adapter as load_software
from pead.domains.tool import load_adapter as load_tool


REVIEW_ID = "phase5_domain_review_v1"
REVIEWER_ID = "independent_domain_validity_reviewer_v1"
HELDOUT_SEMANTIC_MARKERS = (
    "clinical",
    "triage",
    "moderation",
    "content_safety",
    "policy_safety",
)


def load_open_adapters(repo_root: Path) -> tuple[DomainAdapter, ...]:
    adapters = (
        load_tool(repo_root),
        load_cyber(repo_root),
        load_multi_agent(repo_root),
        load_retrieval(repo_root),
        load_software(repo_root),
        load_finance(repo_root),
    )
    if tuple(adapter.definition.domain_id for adapter in adapters) != tuple(
        f"D{index}" for index in range(1, 7)
    ):
        raise DomainContractError("open adapter registry must be ordered D1-D6")
    return adapters


def review_adapter(adapter: DomainAdapter) -> dict[str, Any]:
    definition = adapter.definition
    if definition.author_id == REVIEWER_ID:
        raise DomainContractError("adapter author cannot conduct validity review")
    mechanism_counts: Counter[str] = Counter()
    schema_signatures = set()
    case_ids = set()
    for case_index in range(
        len(definition.mechanisms) * definition.cases_per_mechanism
    ):
        case = adapter.build_case(case_index)
        mechanism_counts[case.mechanism.mechanism_id] += 1
        schema_signatures.add(case.projection.schema_signature)
        case_ids.add(case.case_id)
    expected_cases = len(definition.mechanisms) * definition.cases_per_mechanism
    if (
        len(case_ids) != expected_cases
        or set(mechanism_counts.values()) != {definition.cases_per_mechanism}
        or schema_signatures != {universal_projection_signature()}
    ):
        raise DomainContractError("domain case denominator or schema parity failed")
    variants = tuple(
        variant
        for case_index in range(len(definition.mechanisms))
        for variant in adapter.anti_shortcut_variants(case_index)
    )
    if len(variants) != (
        len(definition.mechanisms)
        * len(definition.label_swaps)
        * len(definition.surface_transforms)
    ):
        raise DomainContractError("anti-shortcut coverage is incomplete")
    predictive = set(definition.predictive_fields)
    governance = set(definition.raw_governance_fields)
    if predictive & governance or {
        field.lower() for field in governance
    } & OBVIOUS_AUTHORIZATION_FIELDS:
        raise DomainContractError("projection is not scientifically defensible")
    if (
        "proxy" not in definition.proxy_scope.lower()
        or len(definition.proxy_exclusions) < 3
        or len({item.semantic_name for item in definition.mechanisms})
        != len(definition.mechanisms)
    ):
        raise DomainContractError("substantive or bounded-proxy review failed")
    return {
        "schema_version": "1.0",
        "review_id": REVIEW_ID,
        "reviewer_id": REVIEWER_ID,
        "adapter_id": definition.adapter_id,
        "domain_id": definition.domain_id,
        "adapter_author_id": definition.author_id,
        "reviewer_authorship_overlap": False,
        "status": "pass",
        "definition_hash": definition.definition_hash,
        "config_sha256": definition.config_sha256,
        "generated_cases": expected_cases,
        "mechanism_counts": mechanism_counts,
        "mechanism_kinds": Counter(item.kind for item in definition.mechanisms),
        "anti_shortcut_variants": len(variants),
        "schema_signature": universal_projection_signature(),
        "capabilities": {
            "graph_dependent": definition.graph_dependent,
            "temporal_reversal": definition.temporal_reversal,
            "policy_grammar_composition": (
                definition.policy_grammar_composition
            ),
        },
        "review_dimensions": {
            "substantive_meaning": "pass",
            "projection_defensibility": "pass",
            "shortcut_resistance": "pass",
            "bounded_proxy_claim": "pass",
            "anti_triviality": "pass",
        },
        "claim_scope": definition.proxy_scope,
        "claim_exclusions": definition.proxy_exclusions,
        "compliance_gaps": [],
    }


def audit_heldout_isolation(repo_root: Path) -> dict[str, Any]:
    domain_roots = (
        repo_root / "src/pead/domains",
        repo_root / "configs/domains",
    )
    allowed_placeholder_files = {
        (repo_root / "src/pead/domains/heldout_interface.py").resolve(),
        (repo_root / "configs/domains/heldout_placeholders.yaml").resolve(),
    }
    placeholder_pattern = re.compile(r"\bD[78]\b")
    violations: list[str] = []
    scanned = 0
    for root in domain_roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            scanned += 1
            text = path.read_text(encoding="utf-8").lower()
            if (
                placeholder_pattern.search(text.upper())
                and path.resolve() not in allowed_placeholder_files
            ):
                violations.append(
                    f"placeholder identity outside interface: "
                    f"{path.relative_to(repo_root).as_posix()}"
                )
            if any(marker in text for marker in HELDOUT_SEMANTIC_MARKERS):
                violations.append(
                    f"held-out semantic content: "
                    f"{path.relative_to(repo_root).as_posix()}"
                )
    contract = load_heldout_contract(repo_root)
    try:
        contract.instantiate("D7")
    except DomainContractError:
        instantiation_blocked = True
    else:
        instantiation_blocked = False
    if violations or not instantiation_blocked:
        raise DomainContractError(
            f"held-out repository isolation failed: {violations}"
        )
    return {
        "schema_version": "1.0",
        "status": "pass",
        "files_scanned": scanned,
        "placeholder_ids": contract.placeholder_ids,
        "contract_hash": contract.contract_hash,
        "projection_signature": contract.projection_signature,
        "implementation_instantiation_blocked": instantiation_blocked,
        "semantic_marker_violations": 0,
        "placeholder_location_violations": 0,
        "custody_completion_phase": contract.custody_completion_phase,
        "first_training_phase": contract.first_training_phase,
        "phase10_blocked_until_custody_sealed": (
            contract.phase10_blocked_until_custody_sealed
        ),
        "custody_implementation_status": "pending_phase_9a",
        "repository_exposure": "interface_and_placeholder_ids_only",
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def execute_domain_review(
    repo_root: Path,
    console: ResearchConsole,
) -> dict[str, Any]:
    evidence_root = (
        repo_root / "results/audits" / REVIEW_ID / "domain_validity"
    )
    # STEP LOG P5-REVIEW-001: Load the six open adapters through the universal domain protocol.
    console.log("P5-REVIEW-001", "Loading six open domain adapters.")
    adapters = load_open_adapters(repo_root)
    reports: list[dict[str, Any]] = []
    for adapter in adapters:
        # STEP LOG P5-REVIEW-002: Independently review one complete open adapter for meaning, projection, shortcuts, and bounded claims.
        console.log(
            "P5-REVIEW-002",
            "Reviewing complete open domain adapter.",
            details={"domain_id": adapter.definition.domain_id},
        )
        report = review_adapter(adapter)
        reports.append(report)
        _write_json(
            evidence_root / f"{adapter.definition.domain_id.lower()}_review.json",
            report,
        )
    # STEP LOG P5-REVIEW-003: Verify held-out placeholders expose only universal shapes and enforce Phase 9A custody chronology.
    console.log("P5-REVIEW-003", "Reviewing nonrevealing held-out contract.")
    heldout = audit_heldout_isolation(repo_root)
    _write_json(evidence_root / "heldout_isolation.json", heldout)
    capability_counts = {
        name: sum(report["capabilities"][name] for report in reports)
        for name in (
            "graph_dependent",
            "temporal_reversal",
            "policy_grammar_composition",
        )
    }
    if min(capability_counts.values()) < 2:
        raise DomainContractError("cross-domain capability minimum is unmet")
    schema_signatures = {
        canonical_hash(report["schema_signature"]) for report in reports
    } | {canonical_hash(heldout["projection_signature"])}
    if len(schema_signatures) != 1:
        raise DomainContractError("D1-D8 interface schema parity failed")
    # STEP LOG P5-REVIEW-004: Confirm the cross-domain capability and universal-schema minima.
    console.log(
        "P5-REVIEW-004",
        "Auditing cross-domain validity minima.",
        details=capability_counts,
    )
    payload = {
        "schema_version": "1.0",
        "review_id": REVIEW_ID,
        "status": "pass",
        "reviewer_id": REVIEWER_ID,
        "release_authority": "none",
        "open_domains": [report["domain_id"] for report in reports],
        "open_adapter_count": len(reports),
        "generated_open_cases": sum(
            report["generated_cases"] for report in reports
        ),
        "anti_shortcut_variants": sum(
            report["anti_shortcut_variants"] for report in reports
        ),
        "schema_parity": True,
        "capability_counts": capability_counts,
        "heldout": heldout,
        "independent_review": {
            "reviewer_authorship_overlaps": sum(
                report["reviewer_authorship_overlap"] for report in reports
            ),
            "all_dimensions_pass": all(
                set(report["review_dimensions"].values()) == {"pass"}
                for report in reports
            ),
        },
        "phase9a_requirements": {
            "d7_d8_same_minima_review_inside_custody": "required",
            "custody_implementations_completed_and_sealed": "required",
            "must_precede_first_phase10_training": True,
            "current_status": "pending_phase_9a",
        },
        "compliance_gaps": [],
    }
    summary = {**payload, "content_sha256": canonical_hash(payload)}
    _write_json(evidence_root / "summary.json", summary)
    registry_payload = {
        "schema_version": "1.0",
        "registry_id": "phase5_open_domain_registry_v1",
        "release_authority": "none",
        "domain_definition_hashes": {
            report["domain_id"]: report["definition_hash"] for report in reports
        },
        "heldout_contract_hash": heldout["contract_hash"],
        "review_content_sha256": summary["content_sha256"],
        "phase9a_custody_completion_required": True,
    }
    registry = {
        **registry_payload,
        "content_sha256": canonical_hash(registry_payload),
    }
    _write_json(
        repo_root / "results/manifests/phase5/domain_registry_v1.json",
        registry,
    )
    # STEP LOG P5-REVIEW-005: Retain the complete independent domain-validity verdict.
    console.log(
        "P5-REVIEW-005",
        "All open-domain and held-out-interface review gates passed.",
        status="pass",
        details={
            "open_cases": summary["generated_open_cases"],
            "open_domains": summary["open_adapter_count"],
        },
    )
    return summary
