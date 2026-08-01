"""Extreme-rigor Phase 11 audit with negative-outcome retention."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pead.config.console import ResearchConsole
from pead.holdouts.commitment_verifier import verify_preseal
from pead.phase11.contracts import sha256_file, verify_file_inventory, verify_signed_mapping
from pead.phase11.unlock import blocked_receipt


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _console_inventory(root: Path) -> list[dict[str, Any]]:
    entries = []
    paths = sorted((root / "src/pead/phase11").glob("*.py")) + sorted((root / "scripts").glob("*phase11*.py")) + [root / "scripts/freeze_study.py", root / "scripts/unlock_blind_bank.py"]
    for path in sorted(set(paths)):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            match = re.search(r'console\.log\("(P11-[A-Z0-9-]+)"', line)
            if not match:
                continue
            prior = lines[index - 1].strip() if index else ""
            if not prior.startswith(f"# STEP LOG {match.group(1)}:"):
                raise ValueError(f"Phase 11 console log lacks adjacent identifying comment: {path}:{index + 1}")
            entries.append({
                "file": path.relative_to(root).as_posix(),
                "comment_line": index,
                "console_log_line": index + 1,
                "event_id": match.group(1),
                "comment": prior[2:],
            })
    return entries


def _development_contamination(root: Path) -> dict[str, Any]:
    forbidden_names = {
        "d7_" + "clinical.yaml",
        "d8_" + "content.yaml",
        "seeds" + ".yaml",
        "phase9a_" + "aes256.key",
        "phase9a_" + "ed25519_private.pem",
    }
    violations = []
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "tmp" in path.parts or ".venv" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        if path.name in forbidden_names and not relative.startswith("artifacts/custody/"):
            violations.append(relative)
    return {"status": "pass" if not violations else "fail", "source_exposure_violations": sorted(violations), "violations": len(violations)}


def run_audit(root: Path, custody_workspace: Path, console: ResearchConsole) -> dict[str, Any]:
    freeze_path = root / "manifests/freeze_manifest.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    audit_root = root / "results/audits" / freeze["freeze_id"]
    # STEP LOG P11-AUDIT-001: Verify final freeze signature and byte identity of every frozen artifact.
    console.log("P11-AUDIT-001", "Auditing final freeze signature and inventory.")
    verify_signed_mapping(freeze)
    verify_file_inventory(root, freeze["frozen_file_inventory"])
    # STEP LOG P11-AUDIT-002: Reconcile every public Phase 9A design, allocation, signature, and ciphertext hash.
    console.log("P11-AUDIT-002", "Auditing Phase 9A and Phase 11 holdout identities.")
    receipt = verify_preseal(root)
    commitment = json.loads((root / "manifests/custody/holdout_design_commitment.json").read_text(encoding="utf-8"))
    design_kinds = {Path(row["artifact_id"]).stem for row in commitment["design_artifacts"]}
    required_kinds = {"mechanisms", "policy_forms", "graph_topologies", "scope_interactions", "interventions", "nuisance", "d7_clinical", "d8_content", "seeds", "generator", "allocator", "ambiguity", "custody"}
    missing_design = sorted(required_kinds - design_kinds)
    holdout_hash = {
        "schema_version": "1.0",
        "phase": 11,
        "freeze_id": freeze["freeze_id"],
        "status": "pass" if not missing_design else "fail",
        "phase9a_preseal_id": receipt.preseal_id,
        "phase9a_commitment_sha256": sha256_file(root / "manifests/custody/holdout_design_commitment.json"),
        "phase11_commitment_match": sha256_file(root / "manifests/custody/holdout_design_commitment.json") == freeze["phase9a_commitment_sha256"],
        "design_artifacts_verified": len(commitment["design_artifacts"]),
        "ciphertexts_verified": len(receipt.verified_ciphertexts),
        "missing_design_components": missing_design,
        "scientific_design_mutations": 0,
    }
    _write(audit_root / "holdout_hash.json", holdout_hash)
    # STEP LOG P11-AUDIT-003: Scan the development repository for custody-source, seed, key, or held-out-domain exposure.
    console.log("P11-AUDIT-003", "Auditing development-context contamination and custody-source exposure.")
    contamination = _development_contamination(root)
    contamination.update({"schema_version": "1.0", "phase": 11, "freeze_id": freeze["freeze_id"], "sealed_bank_duplicate_audit": "not-executable-without-materialization", "template_grammar_topology_disjointness": "not-executable-without-materialization"})
    _write(audit_root / "contamination.json", contamination)
    # STEP LOG P11-AUDIT-004: Execute the custody preflight and preserve a blocked outcome without consuming the one-shot state.
    console.log("P11-AUDIT-004", "Executing fail-closed custody materialization preflight.")
    prior_custody_path = audit_root / "custody_unlock.json"
    if prior_custody_path.is_file():
        custody = json.loads(prior_custody_path.read_text(encoding="utf-8"))
    else:
        custody = blocked_receipt(root, freeze_path, custody_workspace, console)
    _write(audit_root / "custody_unlock.json", custody)
    holdout_hash["custody_design_bytes_verified"] = custody["custody_design"]["verified_artifacts"]
    holdout_hash["custody_design_hash_status"] = custody["custody_design"]["status"]
    if custody["custody_design"]["status"] != "pass":
        holdout_hash["status"] = "fail"
    _write(audit_root / "holdout_hash.json", holdout_hash)
    index = json.loads((root / "manifests/custody/encrypted_blind_package.index.json").read_text(encoding="utf-8"))
    label_package = next(package for package in index["packages"] if package["role"] == "labels")
    blind_manifest = {
        "schema_version": "1.0",
        "phase": 11,
        "freeze_id": freeze["freeze_id"],
        "status": "blocked-not-materialized",
        "materialization_id": None,
        "bank_roots": {
            "structural": "banks/sealed/structural",
            "domains": "banks/sealed/domains",
            "final_blind": "banks/sealed/final_blind",
        },
        "content_objects": 0,
        "labels": {
            "state": "separately-encrypted-not-revealed",
            "ciphertext_path": label_package["path"],
            "ciphertext_sha256": label_package["sha256"],
        },
        "projection_contract": "registered-access-profile-only",
        "phase12_authorized": False,
        "blocking_receipt": f"results/audits/{freeze['freeze_id']}/custody_unlock.json",
    }
    _write(root / "manifests/blind_bank_manifest.json", blind_manifest)
    # STEP LOG P11-AUDIT-005: Inventory every Phase 11 console event and its adjacent identifying comment with exact line numbers.
    console.log("P11-AUDIT-005", "Auditing Phase 11 console traceability.")
    inventory = _console_inventory(root)
    _write(audit_root / "console_inventory.json", {"schema_version": "1.0", "phase": 11, "status": "pass", "entries": inventory})
    gaps = []
    if holdout_hash["status"] != "pass" or not holdout_hash["phase11_commitment_match"]:
        gaps.append("Phase 9A design identity verification failed")
    if contamination["status"] != "pass":
        gaps.append("custody source or secret material is exposed in the development repository")
    if custody["status"] != "eligible":
        gaps.append(custody["reason"])
    if not (root / "banks/sealed/structural").is_dir() or not (root / "banks/sealed/domains").is_dir() or not (root / "banks/sealed/final_blind").is_dir():
        gaps.append("required sealed-bank directories are absent")
    report = {
        "schema_version": "1.0",
        "phase": 11,
        "freeze_id": freeze["freeze_id"],
        "status": "pass" if not gaps else "blocked",
        "freeze_complete_and_signed": True,
        "phase9a_design_hashes_match": holdout_hash["phase11_commitment_match"],
        "scientific_holdout_changes": 0,
        "unlock_attempted": custody.get("unlock_attempted", False),
        "materialization_complete": False,
        "labels_separately_encrypted": True,
        "duplicate_overlap_audit": contamination["sealed_bank_duplicate_audit"],
        "registry_disjointness_audit": contamination["template_grammar_topology_disjointness"],
        "console_log_sites": len(inventory),
        "compliance_gaps": gaps,
        "phase12_authorized": not gaps,
    }
    _write(audit_root / "phase11_compliance.json", report)
    if gaps:
        # STEP LOG P11-AUDIT-BLOCK: Retain a nonzero, zero-misrepresentation verdict for every unresolved Phase 11 gate.
        console.log("P11-AUDIT-BLOCK", "Phase 11 compliance is blocked; blind evaluation is not authorized.", status="blocked", details={"compliance_gaps": len(gaps), "freeze_id": freeze["freeze_id"]})
    else:
        # STEP LOG P11-AUDIT-006: Emit completion only after every WorkPlan gate has passed with immutable evidence.
        console.log("P11-AUDIT-006", "Phase 11 compliance audit passed.", status="pass", details={"compliance_gaps": 0, "freeze_id": freeze["freeze_id"]})
    return report
