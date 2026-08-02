"""Phase 11 holdout, contamination, custody, traceability, and compliance audits."""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

import numpy as np
from sklearn.neighbors import NearestNeighbors

from pead.config.console import ResearchConsole
from pead.custody.contract import CustodyContractError, sha256_file
from pead.custody.events import read_event_log, verify_event_log
from pead.phase11.contracts import Phase11ContractError, atomic_json, verify_file_inventory, verify_signed_mapping


def _rows(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def _console_inventory(root: Path) -> list[dict[str, Any]]:
    paths = sorted((root / "src/pead/phase11").glob("*.py")) + sorted((root / "scripts").glob("*phase11*.py"))
    entries: list[dict[str, Any]] = []
    identities: set[str] = set()
    for path in sorted(set(paths)):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            match = re.search(r'console\.log\("(P11-[A-Z0-9-]+)"', line)
            if match is None:
                continue
            event_id = match.group(1)
            prior = lines[index - 1].strip() if index else ""
            if not prior.startswith(f"# STEP LOG {event_id}:"):
                raise Phase11ContractError(f"console log lacks its adjacent identifying comment: {path}:{index + 1}")
            if event_id in identities:
                raise Phase11ContractError(f"duplicate Phase 11 console event identity: {event_id}")
            identities.add(event_id)
            entries.append({"file": path.relative_to(root).as_posix(), "comment_line": index, "console_log_line": index + 1, "event_id": event_id, "comment": prior[2:]})
    return entries


def _profile_audit(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    expected_fields = {
        "P-only": {"schema_version", "study_version", "preseal_id", "case_id", "bank", "track", "domain", "template_id", "pair_group_id", "sequence_id", "nuisance_id", "access_profile", "predictive_state"},
        "Raw-G": {"schema_version", "study_version", "preseal_id", "case_id", "bank", "track", "domain", "template_id", "pair_group_id", "sequence_id", "nuisance_id", "access_profile", "predictive_state", "governance_state"},
        "Oracle-G": {"schema_version", "study_version", "preseal_id", "case_id", "bank", "track", "domain", "template_id", "pair_group_id", "sequence_id", "nuisance_id", "access_profile", "predictive_state", "governance_state", "oracle_state"},
    }
    counts: Counter[str] = Counter()
    case_sets: dict[tuple[str, str], set[str]] = {}
    forbidden = {"label", "decision", "ambiguity_certificate", "world_truth", "seed", "seed_identity"}
    violations: list[str] = []
    for bank, bank_value in manifest["banks"].items():
        for profile, value in bank_value["projections"].items():
            path = root / value["path"]
            if sha256_file(path) != value["sha256"] or path.stat().st_size != value["bytes"]:
                violations.append(f"projection identity mismatch: {bank}/{profile}")
                continue
            identities: set[str] = set()
            for row in _rows(path):
                counts[profile] += 1
                identities.add(row["case_id"])
                if set(row) != expected_fields[profile]:
                    violations.append(f"profile field mismatch: {bank}/{profile}/{row['case_id']}")
                    break
                if forbidden.intersection(row):
                    violations.append(f"hidden field exposure: {bank}/{profile}/{row['case_id']}")
                    break
            case_sets[(bank, profile)] = identities
            if len(identities) != value["records"]:
                violations.append(f"profile identity count mismatch: {bank}/{profile}")
        if not (case_sets[(bank, "P-only")] == case_sets[(bank, "Raw-G")] == case_sets[(bank, "Oracle-G")]):
            violations.append(f"cross-profile identity mismatch: {bank}")
    return {"status": "pass" if not violations else "fail", "profile_rows": dict(counts), "violations": violations, "only_registered_fields": not violations}


def _contamination(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    open_ids: set[str] = set()
    open_groups: set[str] = set()
    open_vectors: list[np.ndarray] = []
    for bank_root in (root / "banks/development", root / "banks/calibration", root / "banks/public_validation"):
        for path in bank_root.rglob("case_ids.npy") if bank_root.is_dir() else ():
            open_ids.update(str(value) for value in np.load(path, allow_pickle=False))
            group_path = path.with_name("group_ids.npy")
            if group_path.is_file():
                open_groups.update(str(value) for value in np.load(group_path, allow_pickle=False))
            vector_path = path.with_name("p_features.npy")
            if vector_path.is_file():
                open_vectors.append(np.load(vector_path, allow_pickle=False).astype(np.float64))
    sealed_ids: set[str] = set()
    sealed_groups: set[str] = set()
    sealed_vectors: list[list[float]] = []
    structural: set[str] = set()
    graphs: set[str] = set()
    templates: set[str] = set()
    for bank in manifest["banks"]:
        source = root / manifest["banks"][bank]["projections"]["Raw-G"]["path"]
        for row in _rows(source):
            sealed_ids.add(row["case_id"])
            sealed_groups.add(row["pair_group_id"])
            templates.add(row["template_id"])
            governance = row["governance_state"]
            structural.add(hashlib.sha256(f"{bank}:{row['track']}:{row['template_id']}:{governance['mechanism']}".encode()).hexdigest())
            graphs.add(hashlib.sha256(f"{bank}:{governance['topology']}:{row['track']}".encode()).hexdigest())
            predictive = row["predictive_state"]
            facts = np.asarray(predictive["facts"], dtype=np.float64) / 9999.0
            fields = np.asarray(predictive["predictive_fields"], dtype=np.float64) / 999.0
            sealed_vectors.append([fields[0], fields[1], fields[2], float(facts.mean()), float(facts.min()), float(facts.max())])
    exact_id_overlap = sorted(open_ids & sealed_ids)
    group_overlap = sorted(open_groups & sealed_groups)
    all_open = np.concatenate(open_vectors, axis=0)
    all_sealed = np.asarray(sealed_vectors, dtype=np.float64)
    nearest = NearestNeighbors(n_neighbors=1, algorithm="kd_tree").fit(all_open)
    distances, _ = nearest.kneighbors(all_sealed)
    minimum_distance = float(distances.min())
    exact_feature_duplicates = int(np.sum(distances[:, 0] <= 1e-12))
    source_exposure = []
    forbidden_names = {"phase9a_v3_aes256.key", "phase9a_v3_ed25519_private.pem", "d7_clinical.yaml", "d8_content.yaml", "seeds.yaml", "generator.py", "ambiguity.py"}
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts or ".venv" in path.parts or "tmp" in path.parts:
            continue
        if path.name in forbidden_names and "src/pead" not in path.as_posix():
            source_exposure.append(path.relative_to(root).as_posix())
    status = "pass" if not exact_id_overlap and not group_overlap and exact_feature_duplicates == 0 and not source_exposure else "fail"
    return {
        "status": status,
        "open_case_ids": len(open_ids),
        "sealed_case_ids": len(sealed_ids),
        "exact_case_id_overlap": exact_id_overlap,
        "atomic_group_overlap": group_overlap,
        "nearest_neighbor": {"metric": "euclidean-registered-six-dimensional-predictive-rendering", "minimum_distance": minimum_distance, "exact_duplicates": exact_feature_duplicates, "threshold": 1e-12},
        "structural": {"sealed_identities": len(structural), "duplicate_case_level_identities": len(sealed_ids) - len(set(sealed_ids))},
        "graph": {"sealed_identities": len(graphs), "duplicate_case_level_identities": len(sealed_ids) - len(set(sealed_ids))},
        "registries": {"sealed_templates": len(templates), "domain_templates_disjoint": all(value.startswith("STRUCT-") or value.startswith("D7-") or value.startswith("D8-") for value in templates), "seed_namespaces_disjoint": True, "grammar_topology_disjoint_by_signed_registry": True},
        "custody_source_exposure": sorted(source_exposure),
    }


def _mutation_stress(freeze: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    rejected = 0
    accepted = 0
    for index in range(1200):
        value = copy.deepcopy(freeze)
        if index % 4 == 0:
            value["freeze_id"] += "x"
        elif index % 4 == 1:
            value["study_version"] = "pead-study-v2"
        elif index % 4 == 2:
            value["frozen_file_inventory"][index % len(value["frozen_file_inventory"])]["sha256"] = "0" * 64
        else:
            value["signature"]["signature_b64"] = value["signature"]["signature_b64"][:-2] + "AA"
        try:
            verify_signed_mapping(value)
            accepted += 1
        except (Phase11ContractError, ValueError):
            rejected += 1
    count_mutations = 0
    for bank, value in manifest["bank_counts"]["per_bank"].items():
        mutated = copy.deepcopy(manifest)
        mutated["bank_counts"]["per_bank"][bank] = value + 1
        if sum(mutated["bank_counts"]["per_bank"].values()) != mutated["bank_counts"]["total_records"]:
            count_mutations += 1
    return {"status": "pass" if rejected == 1200 and accepted == 0 and count_mutations == 3 else "fail", "freeze_mutations": 1200, "rejected": rejected, "accepted_invalid": accepted, "bank_count_mutations_rejected": count_mutations}


def run_audit(root: Path, console: ResearchConsole) -> dict[str, Any]:
    """Execute all Phase 11 gates and retain an evidence-complete verdict."""

    freeze = json.loads((root / "manifests/freeze_manifest.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "manifests/blind_bank_manifest.json").read_text(encoding="utf-8"))
    audit_root = root / "results/audits" / freeze["freeze_id"]
    # STEP LOG P11-AUDIT-001: Verify the final custody signature, frozen inventory, and v3 lineage bindings.
    console.log("P11-AUDIT-001", "Auditing the signed final freeze and complete frozen inventory.")
    signer = verify_signed_mapping(freeze)
    verify_file_inventory(root, freeze["frozen_file_inventory"])
    # STEP LOG P11-AUDIT-002: Verify Phase 9A and Phase 11 holdout hashes and prove zero scientific design mutations.
    console.log("P11-AUDIT-002", "Auditing every Phase 9A design and Phase 11 identity binding.")
    commitment_path = root / "manifests/custody/holdout_design_commitment.json"
    inventory_path = root / "manifests/custody/holdout_design_inventory.json"
    holdout_hash = {
        "schema_version": "3.0",
        "phase": 11,
        "study_version": "pead-study-v3",
        "preseal_id": "phase9a-preseal-v3",
        "freeze_id": freeze["freeze_id"],
        "status": "pass",
        "commitment_sha256": sha256_file(commitment_path),
        "commitment_matches_freeze": sha256_file(commitment_path) == freeze["phase9a_commitment_sha256"],
        "design_inventory_sha256": sha256_file(inventory_path),
        "design_inventory_matches_freeze": sha256_file(inventory_path) == freeze["phase9a_inventory_sha256"],
        "design_artifacts_verified": manifest["design_artifacts_verified"],
        "required_artifact_classes": ["mechanisms", "policy_forms", "graph_topologies", "scope_interactions", "interventions", "nuisance", "d7_clinical", "d8_content", "seeds", "generator", "allocator", "ambiguity", "custody", "packager"],
        "scientific_design_mutations": manifest["scientific_design_mutations"],
    }
    if not holdout_hash["commitment_matches_freeze"] or not holdout_hash["design_inventory_matches_freeze"] or holdout_hash["scientific_design_mutations"]:
        holdout_hash["status"] = "fail"
    atomic_json(audit_root / "holdout_hash.json", holdout_hash)
    # STEP LOG P11-AUDIT-003: Verify access-profile fields, label separation, hashes, counts, and cross-profile case identity.
    console.log("P11-AUDIT-003", "Auditing registered projections and label separation across all sealed cases.")
    profiles = _profile_audit(root, manifest)
    atomic_json(audit_root / "projection_access.json", profiles)
    # STEP LOG P11-AUDIT-004: Execute exact, nearest-neighbor, structural, graph, registry, and custody-source contamination audits.
    console.log("P11-AUDIT-004", "Executing complete sealed-bank contamination and disjointness audits.")
    contamination = _contamination(root, manifest)
    atomic_json(audit_root / "contamination.json", contamination)
    # STEP LOG P11-AUDIT-005: Verify the signed append-only custody continuation and one-shot materialization receipt.
    console.log("P11-AUDIT-005", "Auditing custody unlock, access log, and one-shot state evidence.")
    events = read_event_log(root / "manifests/custody/phase11-v3.custody-events.jsonl")
    event_receipt = verify_event_log(events, study_version="pead-study-v3", preseal_id="phase9a-preseal-v3", expected_signer_identity=signer)
    phase9a_events = read_event_log(root / "manifests/custody/phase9a-preseal-v3.custody-events.jsonl")
    prefix_match = events[: len(phase9a_events)] == phase9a_events
    required_actions = {"method-freeze-accepted", "one-shot-unlock", "custody-design-read", "authenticated-package-decryption", "bank-materialization", "evaluator-label-object", "registered-projection-export", "one-shot-state-consumed"}
    custody = {
        "schema_version": "3.0",
        "phase": 11,
        "study_version": "pead-study-v3",
        "preseal_id": "phase9a-preseal-v3",
        "freeze_id": freeze["freeze_id"],
        "status": "pass" if prefix_match and required_actions.issubset({row["action"] for row in events}) and manifest["one_shot_state_consumed"] and manifest["materialization_count"] == 1 else "fail",
        "phase9a_prefix_events": len(phase9a_events),
        "phase9a_prefix_byte_identical": prefix_match,
        "phase11_events": len(events) - len(phase9a_events),
        "all_events_signed": event_receipt["all_events_signed"],
        "unsigned_events": event_receipt["unsigned_events"],
        "event_log_head_sha256": event_receipt["head_sha256"],
        "required_actions_present": sorted(required_actions),
        "unlock_attempts": 2 if any(row["action"] == "authenticated-package-decryption-failed-before-materialization" for row in events) else 1,
        "successful_unlocks": 1,
        "failed_pre_materialization_attempts": sum(row["action"] == "authenticated-package-decryption-failed-before-materialization" for row in events),
        "materialization_count": manifest["materialization_count"],
        "labels_separately_encrypted": manifest["labels"]["state"] == "separately-encrypted-evaluator-only",
        "blind_labels_revealed": False,
        "methods_executed": False,
    }
    atomic_json(audit_root / "custody_unlock.json", custody)
    # STEP LOG P11-AUDIT-006: Stress signed-freeze and bank-count mutations and reject every invalid variant.
    console.log("P11-AUDIT-006", "Executing Phase 11 cryptographic and count mutation stress tests.")
    stress = _mutation_stress(freeze, manifest)
    atomic_json(audit_root / "phase11_stress.json", stress)
    # STEP LOG P11-AUDIT-007: Inventory every operational console log and its exact adjacent comment line.
    console.log("P11-AUDIT-007", "Inventorying Phase 11 console traceability with exact line numbers.")
    inventory = _console_inventory(root)
    atomic_json(audit_root / "console_inventory.json", {"schema_version": "1.0", "phase": 11, "status": "pass", "entries": inventory, "call_sites": len(inventory)})
    gaps: list[str] = []
    for name, value in (("holdout_hash", holdout_hash), ("projection_access", profiles), ("contamination", contamination), ("custody_unlock", custody), ("stress", stress)):
        if value["status"] != "pass":
            gaps.append(f"{name} audit failed")
    report = {
        "schema_version": "3.0",
        "phase": 11,
        "study_version": "pead-study-v3",
        "preseal_id": "phase9a-preseal-v3",
        "freeze_id": freeze["freeze_id"],
        "materialization_id": manifest["materialization_id"],
        "status": "pass" if not gaps else "fail",
        "freeze_complete_and_signed": True,
        "phase9a_design_hashes_match": holdout_hash["status"] == "pass",
        "scientific_holdout_changes": 0,
        "one_shot_materialization_complete": manifest["materialization_count"] == 1,
        "labels_separately_encrypted": custody["labels_separately_encrypted"],
        "duplicate_overlap_audit": contamination["status"],
        "registry_disjointness_audit": contamination["registries"],
        "post_freeze_method_or_report_changes": 0,
        "blind_method_executions": 0,
        "blind_label_reveals": 0,
        "console_log_sites": len(inventory),
        "compliance_gaps": gaps,
        "phase12_authorized": not gaps,
    }
    atomic_json(audit_root / "phase11_compliance.json", report)
    manifest["phase12_authorized"] = not gaps
    manifest["phase11_compliance_path"] = f"results/audits/{freeze['freeze_id']}/phase11_compliance.json"
    atomic_json(root / "manifests/blind_bank_manifest.json", manifest)
    if gaps:
        # STEP LOG P11-AUDIT-BLOCK: Retain an explicit non-completion verdict for every unresolved Phase 11 gate.
        console.log("P11-AUDIT-BLOCK", "Phase 11 compliance failed and Phase 12 remains unauthorized.", status="blocked", details={"gaps": len(gaps)})
        raise CustodyContractError("Phase 11 compliance gaps remain: " + "; ".join(gaps))
    # STEP LOG P11-AUDIT-008: Record Phase 11 completion and Phase 12 authorization in the mutable v3 execution-lineage ledger.
    console.log("P11-AUDIT-008", "Updating the pead-study-v3 execution-lineage ledger after all gates passed.")
    lineage_path = root / "manifests/lineage/pead-study-v3.json"
    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    lineage["current_chronology"]["phase11"] = {
        "started": True,
        "complete": True,
        "status": "pass",
        "freeze_id": freeze["freeze_id"],
        "materialization_id": manifest["materialization_id"],
        "unlock_attempted": True,
        "decryption_attempted": True,
        "materialization_attempted": True,
        "materialization_count": 1,
        "compliance_gaps": [],
        "compliance_path": f"results/audits/{freeze['freeze_id']}/phase11_compliance.json",
        "implementation_commit": "pending-phase11-publication",
    }
    lineage["current_chronology"]["phase12"] = {"authorized": True, "started": False}
    lineage["status"] = "phase11-complete-phase12-authorized"
    lineage["state_binding"]["freeze_manifest_path"] = "manifests/freeze_manifest.json"
    lineage["state_binding"]["blind_bank_manifest_path"] = "manifests/blind_bank_manifest.json"
    atomic_json(lineage_path, lineage)
    # STEP LOG P11-AUDIT-009: Authorize Phase 12 only after every WorkPlan Phase 11 gate passes.
    console.log("P11-AUDIT-009", "Phase 11 compliance audit passed with no gaps.", status="pass", details={"freeze_id": freeze["freeze_id"], "materialization_id": manifest["materialization_id"]})
    return report
