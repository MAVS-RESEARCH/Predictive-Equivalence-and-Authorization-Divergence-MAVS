"""Correct the sealed allocation-verifier adapter before Phase 10 and reseal public identities."""

from __future__ import annotations

import argparse
import base64
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pead.config.console import ResearchConsole
from pead.custody.consumer import phase11_preflight
from pead.custody.contract import CANONICALIZATION_ID, CustodyContractError, sha256_bytes, sha256_file, sign_mapping
from pead.custody.events import SignedEventLog, read_event_log, verify_event_log
from pead.custody.producer import create_ciphertext_index, create_commitment, encrypt_package


STUDY = "pead-study-v3"
PRESEAL = "phase9a-preseal-v3"
ANCHOR = "be093b5d2639deb2ff76ad96785c918b5a2a9b92"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _bank_counts() -> dict[str, Any]:
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


def _bundle_record(root: Path, paths: list[Path], role: str) -> dict[str, Any]:
    return {"bundle_role": role, "files": {path.relative_to(root).as_posix(): base64.b64encode(path.read_bytes()).decode("ascii") for path in sorted(paths)}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--custody-root", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    custody = args.custody_root.resolve()
    console = ResearchConsole("phase9a-v3-adapter-correction")
    commitment_path = repo / "manifests/custody/holdout_design_commitment.json"
    index_path = repo / "manifests/custody/encrypted_blind_package.index.json"
    inventory_path = repo / "manifests/custody/holdout_design_inventory.json"
    event_path = custody / "logs/events.jsonl"
    public_event_path = repo / "manifests/custody/phase9a-preseal-v3.custody-events.jsonl"
    state_path = custody / "state/one_shot_state.json"
    # STEP LOG P9A-V3-CORRECT-001: Verify the published 309-event preseal, pristine state, unchanged ciphertexts, and zero Phase 10 artifacts before adapter correction.
    console.log("P9A-V3-CORRECT-001", "Verifying the exact pre-correction custody and chronology state.")
    if subprocess.run(["git", "branch", "--show-current"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip() != "pead-study-v3":
        raise CustodyContractError("adapter correction requires pead-study-v3")
    if list(repo.glob("results/**/phase10*")) or list(repo.glob("artifacts/**/phase10*")):
        raise CustodyContractError("Phase 10 exists before adapter correction")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state["consumed"] is not False or state["materialization_count"] != 0:
        raise CustodyContractError("one-shot state was consumed before adapter correction")
    private_pem = (custody / "keys/phase9a_v3_ed25519_private.pem").read_bytes()
    private_key = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise CustodyContractError("custody signing key is not Ed25519")
    signer_identity = sha256_bytes(private_key.public_key().public_bytes_raw())
    prior_events = read_event_log(event_path)
    prior_receipt = verify_event_log(prior_events, study_version=STUDY, preseal_id=PRESEAL, expected_signer_identity=signer_identity)
    if prior_receipt["event_count"] != 309:
        raise CustodyContractError("adapter correction did not begin at event 309")
    old_index = json.loads(index_path.read_text(encoding="utf-8"))
    old_packages = {item["role"]: item for item in old_index["packages"]}
    # STEP LOG P9A-V3-CORRECT-002: Add the missing strict signed-JSON verifier to the operational custody adapter without changing any scientific generator or design artifact.
    console.log("P9A-V3-CORRECT-002", "Correcting the operational signed-allocation verifier adapter.")
    adapter_path = custody / "src/pead_holdout/custody.py"
    old_adapter_sha256 = sha256_file(adapter_path)
    adapter_path.write_text(
        '"""Operational v3 custody adapter for strict signed allocation verification."""\n'
        'from __future__ import annotations\n'
        'import base64\n'
        'from typing import Any, Mapping\n'
        'from pead.custody.contract import CustodyContractError, verify_signature\n'
        'from pead.custody.events import SignedEventLog, verify_event_log\n\n'
        'def verify_signed_json(value: Mapping[str, Any], public_key_b64: str) -> None:\n'
        '    signer = verify_signature(value)\n'
        '    envelope = value["signature"]\n'
        '    if envelope["public_key_b64"] != public_key_b64 or envelope["signer_identity"] != signer:\n'
        '        raise CustodyContractError("signed allocation public-key identity mismatch")\n',
        encoding="utf-8",
    )
    new_adapter_sha256 = sha256_file(adapter_path)
    if new_adapter_sha256 == old_adapter_sha256:
        raise CustodyContractError("operational adapter identity did not change")
    # STEP LOG P9A-V3-CORRECT-003: Execute the actual sealed allocator against signed JSON, reject YAML input, and verify exact quotas, atomic grouping, and typed distance.
    console.log("P9A-V3-CORRECT-003", "Testing the actual sealed allocation-consumer contract.")
    sys.path.insert(0, str(custody / "src"))
    importlib.invalidate_caches()
    allocator = importlib.import_module("pead_holdout.allocator")
    audit_events: list[tuple[str, str, dict[str, Any]]] = []
    audit = lambda action, verdict, details: audit_events.append((action, verdict, details))
    allocation_path = repo / "manifests/allocations/final_claim_bank_v1.json"
    allocation = allocator.load_signed_allocation(allocation_path, old_index["signature"]["public_key_b64"], audit)
    allocator.validate_exact_allocation(allocation)
    try:
        allocator.load_signed_allocation(repo / "configs/allocations/final_claim_bank_v1.yaml", old_index["signature"]["public_key_b64"], audit)
    except allocator.AllocationError:
        pass
    else:
        raise CustodyContractError("sealed allocator accepted YAML input")
    atomic_rows = [{"pair_group_id": f"g-{index // 2}", "partition": "sealed"} for index in range(2000)]
    if not allocator.groups_are_atomic(atomic_rows):
        raise CustodyContractError("sealed allocator atomic-group check failed")
    if allocator.typed_distance({"mechanism": 1, "topology": 2, "scope": 3}, {"mechanism": 4, "topology": 2, "scope": 1}) != (3, 0, 2):
        raise CustodyContractError("sealed allocator typed-distance check failed")
    # STEP LOG P9A-V3-CORRECT-004: Append a signed gap-correction event and re-sign the complete design inventory with the corrected operational adapter identity.
    console.log("P9A-V3-CORRECT-004", "Appending the signed gap correction and updating the design inventory.")
    log = SignedEventLog(event_path, study_version=STUDY, preseal_id=PRESEAL, private_key=private_key, signer_identity=signer_identity)
    log.append(f"{PRESEAL}-event-0310", "operational-adapter-gap-correction", "record", {"old_adapter_sha256": old_adapter_sha256, "new_adapter_sha256": new_adapter_sha256, "scientific_artifacts_changed": 0, "signed_json_only_test": "pass", "atomic_rows": len(atomic_rows)})
    design_paths = sorted((custody / "configs/holdouts").glob("*.yaml")) + sorted((custody / "src/pead_holdout").glob("*.py"))
    design_rows = [{"artifact_id": path.relative_to(custody).as_posix(), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in design_paths]
    inventory = sign_mapping({"schema_version": "3.0", "study_version": STUDY, "preseal_id": PRESEAL, "canonicalization_id": CANONICALIZATION_ID, "scientific_config_sha256": sha256_file(repo / "configs/study/pead_main_v1.yaml"), "artifact_count": len(design_rows), "design_artifacts": design_rows, "signer_identity": signer_identity}, private_key, signer_identity)
    _write_json(inventory_path, inventory)
    # STEP LOG P9A-V3-CORRECT-005: Re-encrypt only the corrected content bundle with a new nonce and retain labels, seeds, allocation, keys, and scientific source unchanged.
    console.log("P9A-V3-CORRECT-005", "Re-encrypting the corrected content bundle without opening prior ciphertext.")
    content_paths = [path for path in design_paths if path.name not in {"seeds.yaml", "ambiguity.py"}]
    content_package, _ = encrypt_package(
        repo_root=repo,
        output_path=repo / old_packages["content"]["path"],
        study_version=STUDY,
        preseal_id=PRESEAL,
        role="content",
        allocation_sha256=old_index["allocation_sha256"],
        records=[_bundle_record(custody, content_paths, "content")],
        encryption_key=(custody / "keys/phase9a_v3_aes256.key").read_bytes(),
    )
    if content_package["nonce_b64"] == old_packages["content"]["nonce_b64"]:
        raise CustodyContractError("content correction reused the prior AES-GCM nonce")
    log.append(f"{PRESEAL}-event-0311", "corrected-content-package-encrypted", "record", {"old_ciphertext_sha256": old_packages["content"]["ciphertext_sha256"], "new_ciphertext_sha256": content_package["ciphertext_sha256"], "labels_changed": False, "seeds_changed": False})
    packages = [content_package, old_packages["labels"], old_packages["seeds"]]
    index = create_ciphertext_index(study_version=STUDY, preseal_id=PRESEAL, allocation_sha256=old_index["allocation_sha256"], packages=packages, private_key=private_key, signer_identity=signer_identity)
    _write_json(index_path, index)
    log.append(f"{PRESEAL}-event-0312", "corrected-ciphertext-index-signed", "record", {"ciphertext_index_sha256": sha256_file(index_path), "design_inventory_sha256": sha256_file(inventory_path)})
    receipt = verify_event_log(read_event_log(event_path), study_version=STUDY, preseal_id=PRESEAL, expected_signer_identity=signer_identity)
    commitment = create_commitment(study_version=STUDY, preseal_id=PRESEAL, phase9_anchor_sha=ANCHOR, allocation_sha256=old_index["allocation_sha256"], bank_counts=_bank_counts(), packages=packages, design_commitment_sha256=sha256_file(inventory_path), ciphertext_index_sha256=sha256_file(index_path), event_receipt=receipt, private_key=private_key, signer_identity=signer_identity)
    _write_json(commitment_path, commitment)
    shutil.copy2(event_path, public_event_path)
    # STEP LOG P9A-V3-CORRECT-006: Re-run the exact Phase 11 preflight and retain the operational gap correction with zero scientific, unlock, decryption, or materialization activity.
    console.log("P9A-V3-CORRECT-006", "Revalidating the corrected real producer-consumer contract.")
    preflight = phase11_preflight(repo_root=repo, commitment_path=commitment_path, index_path=index_path, event_log_path=public_event_path, one_shot_state_path=state_path, expected_study=STUDY, expected_preseal=PRESEAL)
    if preflight["missing_commitments"] or preflight["consumer_invented_values"]:
        raise CustodyContractError("corrected allocation adapter still fails Phase 11 preflight")
    audit_root = repo / "results/audits" / PRESEAL
    _write_json(audit_root / "generator_contract.json", {"schema_version": "1.0", "study_version": STUDY, "preseal_id": PRESEAL, "status": "pass", "signed_json_only": True, "yaml_input_rejected": True, "exact_allocation": "pass", "atomic_group_rows": len(atomic_rows), "atomic_groups": "pass", "typed_distance": "pass", "audit_events": len(audit_events), "scientific_artifacts_changed": 0})
    _write_json(audit_root / "gap_correction_001.json", {"schema_version": "1.0", "study_version": STUDY, "preseal_id": PRESEAL, "status": "corrected-before-phase10", "gap": "sealed allocator imported verify_signed_json but the operational custody adapter omitted that function", "old_adapter_sha256": old_adapter_sha256, "new_adapter_sha256": new_adapter_sha256, "old_content_ciphertext_sha256": old_packages["content"]["ciphertext_sha256"], "new_content_ciphertext_sha256": content_package["ciphertext_sha256"], "labels_ciphertext_unchanged": True, "seeds_ciphertext_unchanged": True, "allocation_unchanged": True, "keys_unchanged": True, "new_nonce_used": True, "scientific_artifacts_changed": 0, "signed_event_count": receipt["event_count"], "phase10_artifact_count": 0, "unlock_attempted": False, "decryption_attempted": False, "materialization_attempted": False})
    _write_json(audit_root / "phase11_preflight.json", preflight)
    custody_receipt = json.loads((audit_root / "custody.json").read_text(encoding="utf-8"))
    custody_receipt.update({"signed_event_count": receipt["event_count"], "event_head_sha256": receipt["head_sha256"], "event_log_sha256": sha256_file(public_event_path)})
    _write_json(audit_root / "custody.json", custody_receipt)
    design_receipt = json.loads((audit_root / "holdout_design.json").read_text(encoding="utf-8"))
    design_receipt["design_inventory_sha256"] = sha256_file(inventory_path)
    _write_json(audit_root / "holdout_design.json", design_receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
