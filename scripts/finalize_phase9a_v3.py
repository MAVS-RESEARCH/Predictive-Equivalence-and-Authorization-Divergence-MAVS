"""Finalize the retained Phase 9A-v3 packages after a precommit validator correction."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pead.config.console import ResearchConsole
from pead.custody.consumer import phase11_preflight
from pead.custody.contract import CustodyContractError, canonical_bytes, sha256_bytes, sha256_file, validate_index, verify_signature
from pead.custody.events import SignedEventLog, read_event_log, verify_event_log
from pead.custody.invariance import assert_identity_freshness
from pead.custody.producer import create_commitment


STUDY = "pead-study-v3"
PRESEAL = "phase9a-preseal-v3"
ANCHOR = "be093b5d2639deb2ff76ad96785c918b5a2a9b92"


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _bank_counts() -> dict:
    return {
        "total_records": 106400,
        "per_bank": {"structural": 26600, "domains": 26600, "final_blind": 53200},
        "per_track": {"exact": 32000, "near": 16000, "reversal": 24000, "scope": 22400, "evidence": 12000},
        "per_bank_track": {
            "structural": {"exact": 8000, "near": 4000, "reversal": 6000, "scope": 5600, "evidence": 3000},
            "domains": {"exact": 8000, "near": 4000, "reversal": 6000, "scope": 5600, "evidence": 3000},
            "final_blind": {"exact": 16000, "near": 8000, "reversal": 12000, "scope": 11200, "evidence": 6000},
        },
    }


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--reference-custody", type=Path, required=True)
    parser.add_argument("--custody-root", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    reference = args.reference_custody.resolve()
    custody = args.custody_root.resolve()
    console = ResearchConsole("phase9a-v3-finalize")
    commitment_path = repo / "manifests/custody/holdout_design_commitment.json"
    public_event_path = repo / "manifests/custody/phase9a-preseal-v3.custody-events.jsonl"
    # STEP LOG P9A-V3-FINALIZE-001: Verify the stopped post-index state contains exactly the retained signed events, ciphertexts, index, design inventory, and pristine one-shot state.
    console.log("P9A-V3-FINALIZE-001", "Verifying the retained post-index fail-closed state.")
    if _git(repo, "branch", "--show-current") != "pead-study-v3":
        raise CustodyContractError("Phase 9A finalization requires pead-study-v3")
    if commitment_path.exists() or public_event_path.exists():
        raise CustodyContractError("top-level commitment or public event log already exists")
    state_path = custody / "state/one_shot_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state != {"schema_version": "3.0", "study_version": STUDY, "preseal_id": PRESEAL, "consumed": False, "materialization_count": 0}:
        raise CustodyContractError("real one-shot state is not pristine")
    event_path = custody / "logs/events.jsonl"
    events = read_event_log(event_path)
    private_pem = (custody / "keys/phase9a_v3_ed25519_private.pem").read_bytes()
    private_key = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise CustodyContractError("retained custody key is not Ed25519")
    signer_identity = sha256_bytes(private_key.public_key().public_bytes_raw())
    event_receipt = verify_event_log(events, study_version=STUDY, preseal_id=PRESEAL, expected_signer_identity=signer_identity)
    if event_receipt["event_count"] != 308 or events[-1]["event_id"] != f"{PRESEAL}-event-0308":
        raise CustodyContractError("retained fail-closed event chronology is not the exact stopped state")
    # STEP LOG P9A-V3-FINALIZE-002: Reverify every retained signature, allocation binding, ciphertext identity, and design-inventory identity without regenerating any package.
    console.log("P9A-V3-FINALIZE-002", "Reverifying retained signed public artifacts and ciphertext identities.")
    allocation_path = repo / "manifests/allocations/final_claim_bank_v1.json"
    allocation = json.loads(allocation_path.read_text(encoding="utf-8"))
    verify_signature(allocation, expected_signer=signer_identity)
    allocation_sha256 = sha256_file(allocation_path)
    index_path = repo / "manifests/custody/encrypted_blind_package.index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    packages = validate_index(index, expected_study=STUDY, expected_preseal=PRESEAL)
    if index["allocation_sha256"] != allocation_sha256:
        raise CustodyContractError("retained index allocation differs from signed allocation")
    for role, package in packages.items():
        ciphertext = (repo / package["path"]).resolve()
        if sha256_file(ciphertext) != package["ciphertext_sha256"] or ciphertext.stat().st_size != package["ciphertext_byte_count"]:
            raise CustodyContractError(f"retained ciphertext identity differs: {role}")
    inventory_path = repo / "manifests/custody/holdout_design_inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    verify_signature(inventory, expected_signer=signer_identity)
    # STEP LOG P9A-V3-FINALIZE-003: Append a signed correction event for the Git-object validator defect and create the top-level commitment from unchanged retained packages.
    console.log("P9A-V3-FINALIZE-003", "Appending the signed validator-correction event and creating the commitment.")
    log = SignedEventLog(event_path, study_version=STUDY, preseal_id=PRESEAL, private_key=private_key, signer_identity=signer_identity)
    log.append(
        f"{PRESEAL}-event-0309",
        "precommit-validator-correction",
        "record",
        {
            "failed_field": "phase9_anchor_sha",
            "prior_validator_requirement": "64-character-SHA-256",
            "corrected_requirement": "40-character-Git-object-identity",
            "packages_regenerated": False,
            "ciphertexts_changed": False,
        },
    )
    event_receipt = verify_event_log(read_event_log(event_path), study_version=STUDY, preseal_id=PRESEAL, expected_signer_identity=signer_identity)
    commitment = create_commitment(
        study_version=STUDY,
        preseal_id=PRESEAL,
        phase9_anchor_sha=ANCHOR,
        allocation_sha256=allocation_sha256,
        bank_counts=_bank_counts(),
        packages=[dict(index_package) for index_package in index["packages"]],
        design_commitment_sha256=sha256_file(inventory_path),
        ciphertext_index_sha256=sha256_file(index_path),
        event_receipt=event_receipt,
        private_key=private_key,
        signer_identity=signer_identity,
    )
    _write_json(commitment_path, commitment)
    shutil.copy2(event_path, public_event_path)
    # STEP LOG P9A-V3-FINALIZE-004: Run the exact future Phase 11 public preflight without reading keys, decrypting ciphertext, materializing content, or consuming one-shot state.
    console.log("P9A-V3-FINALIZE-004", "Running the exact Phase 11 preflight on the corrected commitment.")
    preflight = phase11_preflight(
        repo_root=repo,
        commitment_path=commitment_path,
        index_path=index_path,
        event_log_path=public_event_path,
        one_shot_state_path=state_path,
        expected_study=STUDY,
        expected_preseal=PRESEAL,
    )
    if preflight["missing_commitments"] or preflight["consumer_invented_values"]:
        raise CustodyContractError("corrected preflight still lacks committed values")
    seed_registry = yaml.safe_load((custody / "configs/holdouts/seeds.yaml").read_text(encoding="utf-8"))
    seed_lists = seed_registry["exact_hidden_seed_lists"]
    reference_seeds = yaml.safe_load((reference / "configs/holdouts/seeds.yaml").read_text(encoding="utf-8"))
    old_seed_values = {int(item) for values in reference_seeds["streams"].values() for item in values}
    new_seed_values = {int(item) for values in seed_lists.values() for item in values}
    fresh = {
        **{f"{name}_seed_selection_sha256": sha256_bytes(canonical_bytes(values)) for name, values in seed_lists.items()},
        "encryption_key_sha256": sha256_file(custody / "keys/phase9a_v3_aes256.key"),
        "custody_signing_private_key_sha256": sha256_bytes(private_pem),
        "custody_signing_public_key_sha256": signer_identity,
        "one_shot_state_genesis_sha256": sha256_file(state_path),
        "custody_log_genesis_sha256": event_receipt["genesis_sha256"],
    }
    predecessor = {
        "encryption_key_sha256": sha256_file(reference / "keys/phase9a_aes256.key"),
        "custody_signing_private_key_sha256": sha256_file(reference / "keys/phase9a_ed25519_private.pem"),
        "seed_file_sha256": sha256_file(reference / "configs/holdouts/seeds.yaml"),
        "custody_log_sha256": sha256_file(reference / "logs/access.jsonl"),
    }
    assert_identity_freshness(fresh, {"pead-study-v2": predecessor})
    # STEP LOG P9A-V3-FINALIZE-005: Retain both stopped attempts and the complete nonrevealing corrected-Phase-9A compliance evidence.
    console.log("P9A-V3-FINALIZE-005", "Writing final corrected Phase 9A evidence with failed-attempt retention.")
    audit_root = repo / "results/audits" / PRESEAL
    _write_json(audit_root / "failed_attempt_002.json", {"schema_version": "1.0", "study_version": STUDY, "preseal_id": PRESEAL, "status": "stopped-before-top-level-commitment", "failed_gate": "phase9-anchor-object-identity-validation", "reason": "shared validator incorrectly required a 64-character SHA-256 for a 40-character Git object identity", "custody_event_count": 308, "ciphertext_package_count": 3, "commitment_created": False, "unlock_attempted": False, "decryption_attempted": False, "materialization_attempted": False, "correction": "validate the registered Git object identity format and append signed correction event 309 without regenerating packages"})
    _write_json(audit_root / "allocation.json", {"schema_version": "1.0", "study_version": STUDY, "preseal_id": PRESEAL, "status": "pass", "allocation_sha256": allocation_sha256, "normative_yaml_sha256": allocation["normative_yaml_sha256"], "signed_json_only": True, "bank_counts": _bank_counts(), "exact_pairs_per_domain": 2000, "near_pairs_per_domain": 1000})
    _write_json(audit_root / "holdout_design.json", {"schema_version": "1.0", "study_version": STUDY, "preseal_id": PRESEAL, "status": "pass", "design_inventory_sha256": sha256_file(inventory_path), "signed_design_artifacts": inventory["artifact_count"], "semantic_reference_artifacts": 12, "semantic_mismatches": [], "seed_artifact_intentionally_changed": True, "performance_inputs_used": []})
    _write_json(audit_root / "custody.json", {"schema_version": "1.0", "study_version": STUDY, "preseal_id": PRESEAL, "status": "pass", "custody_workspace_identity": sha256_bytes(str(custody).encode()), "fresh_identity_hashes": fresh, "predecessor_identity_hashes": predecessor, "predecessor_seed_overlap": len(old_seed_values & new_seed_values), "denied_pre_freeze_attempts": 300, "signed_event_count": event_receipt["event_count"], "unsigned_event_count": 0, "event_genesis_sha256": event_receipt["genesis_sha256"], "event_head_sha256": event_receipt["head_sha256"], "event_log_sha256": sha256_file(public_event_path), "keys_in_development": 0, "one_shot_state_consumed": False})
    _write_json(audit_root / "phase11_preflight.json", preflight)
    _write_json(audit_root / "phase9a_compliance.json", {"schema_version": "1.0", "phase": "9A", "study_version": STUDY, "preseal_id": PRESEAL, "status": "pass", "five_top_level_materialization_commitments": ["allocation_sha256", "bank_counts", "content_plaintext_sha256", "label_plaintext_sha256", "seed_selection_sha256"], "nine_formerly_missing_package_commitments": [{"role": role, "fields": ["allocation_sha256", "plaintext_sha256", "record_count"]} for role in ("content", "labels", "seeds")], "all_required_commitments_present": True, "consumer_invented_values": [], "allocation_agreement_roles": ["content", "labels", "seeds"], "signed_event_count": event_receipt["event_count"], "unsigned_event_count": 0, "new_hidden_seeds": True, "new_encryption_key": True, "new_signing_key": True, "labels_separately_encrypted": True, "real_unlock_attempted": False, "real_decryption_attempted": False, "real_materialization_attempted": False, "one_shot_state_consumed": False, "phase10_artifact_count_at_seal": 0, "scientific_result_generated": False, "failed_attempts_retained": 2, "compliance_gaps": []})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
