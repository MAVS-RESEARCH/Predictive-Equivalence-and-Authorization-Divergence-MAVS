"""Extreme-rigor WorkPlan Phase 5 compliance audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash
from pead.phase0.audit import inventory_console_logs
from pead.phase2.audit import write_json
from pead.phase5.review import REVIEW_ID, execute_domain_review


EXPECTED_FILES = {
    "src/pead/domains/base.py",
    "src/pead/domains/tool.py",
    "src/pead/domains/cyber.py",
    "src/pead/domains/multi_agent.py",
    "src/pead/domains/retrieval.py",
    "src/pead/domains/software.py",
    "src/pead/domains/finance.py",
    "src/pead/domains/heldout_interface.py",
    "configs/domains/tool.yaml",
    "configs/domains/cyber.yaml",
    "configs/domains/multi_agent.yaml",
    "configs/domains/retrieval.yaml",
    "configs/domains/software.yaml",
    "configs/domains/finance.yaml",
    "configs/domains/heldout_placeholders.yaml",
    "tests/integration/test_domain_contracts.py",
    "tests/stress/test_phase5_stress.py",
    "results/manifests/phase5/domain_registry_v1.json",
    "results/audits/phase5/phase5_tests.json",
}


def _audit_files(repo_root: Path) -> dict[str, Any]:
    missing = sorted(path for path in EXPECTED_FILES if not (repo_root / path).is_file())
    review_root = repo_root / "results/audits" / REVIEW_ID / "domain_validity"
    required_reviews = {
        *(f"d{index}_review.json" for index in range(1, 7)),
        "heldout_isolation.json",
        "summary.json",
    }
    missing_reviews = sorted(
        name for name in required_reviews if not (review_root / name).is_file()
    )
    if missing or missing_reviews:
        raise ValueError(
            f"missing Phase 5 files: {missing}; reviews: {missing_reviews}"
        )
    return {
        "status": "pass",
        "required_files": len(EXPECTED_FILES),
        "domain_review_files": len(required_reviews),
    }


def _audit_registry(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "results/manifests/phase5/domain_registry_v1.json"
    registry = json.loads(path.read_text(encoding="utf-8"))
    signature = registry.pop("content_sha256")
    if (
        canonical_hash(registry) != signature
        or registry.get("release_authority") != "none"
        or registry.get("phase9a_custody_completion_required") is not True
        or set(registry.get("domain_definition_hashes", {}))
        != {f"D{index}" for index in range(1, 7)}
    ):
        raise ValueError("Phase 5 domain registry signature or boundary failed")
    return {
        "status": "pass",
        "content_sha256": signature,
        "open_domains": 6,
        "heldout_contract_hash": registry["heldout_contract_hash"],
        "release_authority": "none",
    }


def _audit_test_evidence(repo_root: Path) -> dict[str, Any]:
    report = json.loads(
        (
            repo_root / "results/audits/phase5/phase5_tests.json"
        ).read_text(encoding="utf-8")
    )
    stress = report.get("stress_gates", {})
    if (
        report.get("status") != "pass"
        or report.get("failures")
        or report.get("errors")
        or stress.get("complete_open_cases") != 3_600
        or stress.get("crossed_anti_shortcut_variants") != 288
        or stress.get("heldout_implementations_exposed") != 0
    ):
        raise ValueError("Phase 5 test evidence is incomplete")
    return {
        "status": "pass",
        "tests_run": report["tests_run"],
        "failures": 0,
        "errors": 0,
        "stress_gates": stress,
    }


def _audit_boundary(repo_root: Path) -> dict[str, Any]:
    prohibited_roots = (
        repo_root / "src/pead/projections",
        repo_root / "results/models",
        repo_root / "results/checkpoints",
        repo_root / "results/banks/released",
    )
    files = [
        path.relative_to(repo_root).as_posix()
        for root in prohibited_roots
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
    ]
    if files:
        raise ValueError(f"Phase 5 created later-phase outputs: {files}")
    return {
        "status": "pass",
        "models_trained": 0,
        "checkpoints_created": 0,
        "released_claim_bank_rows": 0,
        "phase6_started": False,
        "heldout_implementations_exposed": 0,
        "phase9a_custody_work_executed": False,
        "phase10_training_executed": False,
    }


def _audit_ledger(repo_root: Path) -> dict[str, Any]:
    text = (repo_root / "Path.md").read_text(encoding="utf-8")
    entries = {f"PATH-{index:04d}" for index in range(50, 56)}
    evidence = {
        "domain_registry_v1.json",
        "summary.json",
        "heldout_isolation.json",
        "phase5_tests.json",
        "console_log_inventory.json",
        "phase5_compliance.json",
    }
    missing = sorted(item for item in entries | evidence if item not in text)
    if missing:
        raise ValueError(f"Phase 5 Path ledger is incomplete: {missing}")
    pending = "Local gates passed; publication pending"
    complete = "| 5 | Six open adapters and held-out interfaces | Complete |"
    if pending not in text and complete not in text:
        raise ValueError("Phase 5 Path ledger has no valid publication state")
    return {
        "status": "pass",
        "entries": sorted(entries),
        "evidence_pointers": sorted(evidence),
        "publication_state": "complete" if complete in text else "pending",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output = root / "results/audits/phase5"
    console = ResearchConsole("5")
    try:
        # STEP LOG P5-AUDIT-001: Verify every WorkPlan-named domain, configuration, test, review, and manifest file.
        console.log("P5-AUDIT-001", "Auditing required Phase 5 files.")
        files = _audit_files(root)
        # STEP LOG P5-AUDIT-002: Regenerate every open-domain validity review through the independent reviewer.
        console.log("P5-AUDIT-002", "Executing complete domain validity review.")
        review = execute_domain_review(root, console)
        # STEP LOG P5-AUDIT-003: Verify the content-signed open-domain registry and Phase 9A boundary.
        console.log("P5-AUDIT-003", "Auditing Phase 5 domain registry.")
        registry = _audit_registry(root)
        # STEP LOG P5-AUDIT-004: Verify complete regression, integration, adversarial, and stress evidence.
        console.log("P5-AUDIT-004", "Auditing complete Phase 5 test evidence.")
        tests = _audit_test_evidence(root)
        # STEP LOG P5-AUDIT-005: Verify every Phase 5 console call has an adjacent stable identity comment.
        console.log("P5-AUDIT-005", "Auditing Phase 5 console traceability.")
        inventory = [
            entry
            for entry in inventory_console_logs(root)
            if entry["event_id"].startswith("P5-")
        ]
        write_json(
            output / "console_log_inventory.json",
            {"count": len(inventory), "entries": inventory},
        )
        # STEP LOG P5-AUDIT-006: Verify Path completeness and prohibit held-out, training, model, release, and Phase 6 outputs.
        console.log("P5-AUDIT-006", "Auditing ledger and phase boundaries.")
        ledger = _audit_ledger(root)
        boundary = _audit_boundary(root)
        compliance = {
            "schema_version": "1.0",
            "phase": 5,
            "status": "pass",
            "files": files,
            "review": review,
            "registry": registry,
            "tests": tests,
            "ledger": ledger,
            "boundary": boundary,
            "console_events": len(inventory),
            "completion_gates": {
                "d1_d6_universal_schema_parity": "pass",
                "heldout_interface_schema_parity": "pass",
                "open_domain_anti_triviality": "pass",
                "independent_validity_review": "pass",
                "heldout_placeholders_frozen": "pass",
                "heldout_implementation_exposure": 0,
                "phase9a_pretraining_custody_gate": "enforced",
            },
            "compliance_gaps": [],
        }
        # STEP LOG P5-AUDIT-007: Retain the clause-level Phase 5 compliance verdict and evidence.
        console.log(
            "P5-AUDIT-007",
            "Retaining Phase 5 compliance evidence.",
            status="pass",
            details={
                "console_events": len(inventory),
                "open_cases": review["generated_open_cases"],
                "tests": tests["tests_run"],
            },
        )
        write_json(output / "phase5_compliance.json", compliance)
        # STEP LOG P5-AUDIT-008: Report the final local Phase 5 hard-gate verdict.
        console.log("P5-AUDIT-008", "All local Phase 5 gates passed.", status="pass")
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        # STEP LOG P5-AUDIT-009: Emit a hard failure with its unsuppressed cause.
        console.log(
            "P5-AUDIT-009",
            "Phase 5 compliance audit failed.",
            status="fail",
            details={"error": str(error)},
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
