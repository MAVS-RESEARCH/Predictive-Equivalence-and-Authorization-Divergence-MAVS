"""Create the corrected real Phase 9A preseal for pead-study-v3 exactly once."""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from pead.config.console import ResearchConsole
from pead.custody.access import deny_pre_freeze_access
from pead.custody.consumer import phase11_preflight
from pead.custody.contract import (
    CANONICALIZATION_ID,
    CustodyContractError,
    canonical_bytes,
    sha256_bytes,
    sha256_file,
    sign_mapping,
    verify_signature,
)
from pead.custody.events import SignedEventLog, read_event_log, verify_event_log
from pead.custody.invariance import FRESH_IDENTITIES, assert_identity_freshness, assert_semantic_invariance
from pead.custody.producer import create_ciphertext_index, create_commitment, encrypt_package


STUDY = "pead-study-v3"
PRESEAL = "phase9a-preseal-v3"
ANCHOR = "be093b5d2639deb2ff76ad96785c918b5a2a9b92"
REFERENCE_ARTIFACTS = (
    "configs/holdouts/d7_clinical.yaml",
    "configs/holdouts/d8_content.yaml",
    "configs/holdouts/graph_topologies.yaml",
    "configs/holdouts/interventions.yaml",
    "configs/holdouts/mechanisms.yaml",
    "configs/holdouts/nuisance.yaml",
    "configs/holdouts/policy_forms.yaml",
    "configs/holdouts/scope_interactions.yaml",
    "src/pead_holdout/__init__.py",
    "src/pead_holdout/allocator.py",
    "src/pead_holdout/ambiguity.py",
    "src/pead_holdout/generator.py",
)


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _bundle_record(root: Path, paths: list[Path], role: str) -> dict[str, Any]:
    return {
        "bundle_role": role,
        "files": {
            path.relative_to(root).as_posix(): base64.b64encode(path.read_bytes()).decode("ascii")
            for path in sorted(paths)
        },
    }


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


def _seed_registry(reference_seed_path: Path) -> tuple[dict[str, Any], dict[str, str], int]:
    reference = yaml.safe_load(reference_seed_path.read_text(encoding="utf-8"))
    old_values = {int(item) for values in reference["streams"].values() for item in values}
    namespaces = {
        "structural": (7_000_000, 7_999_999),
        "domain": (8_000_000, 8_999_999),
        "cross_product": (9_000_000, 9_999_999),
    }
    selected: dict[str, list[int]] = {}
    for name, (lower, upper) in namespaces.items():
        candidates = secrets.SystemRandom().sample(range(lower, upper + 1), 16)
        if old_values.intersection(candidates):
            raise CustodyContractError("new hidden seed selection overlaps predecessor plaintext")
        selected[name] = sorted(candidates)
    if len({value for values in selected.values() for value in values}) != 48:
        raise CustodyContractError("hidden seed selections are not mutually disjoint")
    identities = {f"{name}_seed_selection_sha256": sha256_bytes(canonical_bytes(values)) for name, values in selected.items()}
    registry = {
        "schema_version": "3.0",
        "registry": "PEAD-HIDDEN-SEEDS-v3",
        "study_version": STUDY,
        "preseal_id": PRESEAL,
        "namespaces": {name: {"minimum": low, "maximum": high} for name, (low, high) in namespaces.items()},
        "exact_hidden_seed_lists": selected,
    }
    return registry, identities, len(old_values.intersection({value for values in selected.values() for value in values}))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--reference-custody", type=Path, required=True)
    parser.add_argument("--custody-root", type=Path, required=True)
    parser.add_argument("--resume-pristine-partial", action="store_true")
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    reference = args.reference_custody.resolve()
    custody = args.custody_root.resolve()
    console = ResearchConsole("phase9a-v3")
    # STEP LOG P9A-V3-SEAL-001: Verify unused v3 preseal artifacts, the published bootstrap, clean branch state, and zero Phase 10 artifacts before custody creation.
    console.log("P9A-V3-SEAL-001", "Verifying corrected Phase 9A chronology and unused identities.")
    if _git(repo, "branch", "--show-current") != "pead-study-v3":
        raise CustodyContractError("real Phase 9A requires the pead-study-v3 branch")
    allowed_operator_changes = {
        "?? manifests/allocations/",
        "?? scripts/preseal_phase9a_v3.py",
        "?? scripts/review_phase9a_v3.py",
        "?? src/pead/custody/access.py",
    }
    observed_changes = set(_git(repo, "status", "--porcelain").splitlines())
    if observed_changes != allowed_operator_changes:
        raise CustodyContractError(f"real Phase 9A has unexpected pre-execution worktree changes: {sorted(observed_changes)}")
    if not _git(repo, "log", "-1", "--format=%s").startswith("study-v3: establish shared custody"):
        raise CustodyContractError("shared custody bootstrap is not the published parent")
    sealed_reserved = [
        repo / "artifacts/custody" / PRESEAL,
        repo / "manifests/custody/holdout_design_commitment.json",
        repo / "manifests/custody/encrypted_blind_package.index.json",
    ]
    if any(path.exists() for path in sealed_reserved):
        raise CustodyContractError("study-v3 or preseal-v3 artifact identity is already in use")
    if custody.exists() and not args.resume_pristine_partial:
        raise CustodyContractError("study-v3 custody workspace identity is already in use")
    if not custody.exists() and args.resume_pristine_partial:
        raise CustodyContractError("requested partial resume workspace is absent")
    if custody == repo or repo in custody.parents:
        raise CustodyContractError("v3 custody workspace must be outside the development repository")
    if list(repo.glob("results/**/phase10*")) or list(repo.glob("artifacts/**/phase10*")):
        raise CustodyContractError("Phase 10 artifact exists before the v3 seal")
    # STEP LOG P9A-V3-SEAL-002: Create the new external custody workspace and copy only the frozen v2 semantic reference artifacts byte-for-byte.
    console.log("P9A-V3-SEAL-002", "Creating the isolated v3 custody workspace from frozen semantic references.")
    if not args.resume_pristine_partial:
        (custody / "configs/holdouts").mkdir(parents=True)
        (custody / "src/pead_holdout").mkdir(parents=True)
        (custody / "keys").mkdir()
        (custody / "logs").mkdir()
        (custody / "state").mkdir()
        for relative in REFERENCE_ARTIFACTS:
            target = custody / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(reference / relative, target)
        (custody / "src/pead_holdout/custody.py").write_text(
            '"""Operational v3 custody event adapter."""\nfrom pead.custody.events import SignedEventLog, verify_event_log\n', encoding="utf-8"
        )
        (custody / "src/pead_holdout/packager.py").write_text(
            '"""Operational v3 package adapter."""\nfrom pead.custody.producer import encrypt_package, create_ciphertext_index, create_commitment\n', encoding="utf-8"
        )
    # STEP LOG P9A-V3-SEAL-003: Generate new disjoint structural, domain, and cross-product hidden seed lists, new AES/Ed25519 keys, and pristine one-shot state outside Git.
    console.log("P9A-V3-SEAL-003", "Generating new custody-only seeds, keys, and one-shot state.")
    state_path = custody / "state/one_shot_state.json"
    if args.resume_pristine_partial:
        if (custody / "logs/events.jsonl").exists() or any((custody / "logs").iterdir()):
            raise CustodyContractError("partial resume is not pristine: custody event log already exists")
        expected_partial = {
            "configs/holdouts/seeds.yaml",
            "keys/phase9a_v3_aes256.key",
            "keys/phase9a_v3_ed25519_private.pem",
            "state/one_shot_state.json",
            "signed_allocation.json",
        }
        observed_partial = {path.relative_to(custody).as_posix() for path in custody.rglob("*") if path.is_file()}
        expected_partial.update(REFERENCE_ARTIFACTS)
        expected_partial.update({"src/pead_holdout/custody.py", "src/pead_holdout/packager.py"})
        if observed_partial != expected_partial:
            raise CustodyContractError("partial resume file inventory differs from the stopped pre-genesis attempt")
        seed_registry = yaml.safe_load((custody / "configs/holdouts/seeds.yaml").read_text(encoding="utf-8"))
        selected = seed_registry["exact_hidden_seed_lists"]
        seed_identities = {f"{name}_seed_selection_sha256": sha256_bytes(canonical_bytes(values)) for name, values in selected.items()}
        reference_seeds = yaml.safe_load((reference / "configs/holdouts/seeds.yaml").read_text(encoding="utf-8"))
        old_values = {int(item) for values in reference_seeds["streams"].values() for item in values}
        predecessor_seed_overlap = len(old_values.intersection({value for values in selected.values() for value in values}))
        encryption_key = (custody / "keys/phase9a_v3_aes256.key").read_bytes()
        private_pem = (custody / "keys/phase9a_v3_ed25519_private.pem").read_bytes()
        signing_key = serialization.load_pem_private_key(private_pem, password=None)
        if not isinstance(signing_key, Ed25519PrivateKey):
            raise CustodyContractError("retained signing key is not Ed25519")
        one_shot = json.loads(state_path.read_text(encoding="utf-8"))
        if one_shot != {"schema_version": "3.0", "study_version": STUDY, "preseal_id": PRESEAL, "consumed": False, "materialization_count": 0}:
            raise CustodyContractError("partial resume one-shot state is not pristine")
    else:
        seed_registry, seed_identities, predecessor_seed_overlap = _seed_registry(reference / "configs/holdouts/seeds.yaml")
        (custody / "configs/holdouts/seeds.yaml").write_text(yaml.safe_dump(seed_registry, sort_keys=True), encoding="utf-8")
        encryption_key = AESGCM.generate_key(bit_length=256)
        signing_key = Ed25519PrivateKey.generate()
        private_pem = signing_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        (custody / "keys/phase9a_v3_aes256.key").write_bytes(encryption_key)
        (custody / "keys/phase9a_v3_ed25519_private.pem").write_bytes(private_pem)
        one_shot = {"schema_version": "3.0", "study_version": STUDY, "preseal_id": PRESEAL, "consumed": False, "materialization_count": 0}
        _write_json(state_path, one_shot)
    public_raw = signing_key.public_key().public_bytes_raw()
    signer_identity = sha256_bytes(public_raw)
    # STEP LOG P9A-V3-SEAL-004: Prove semantic identity for frozen scientific artifacts and nonreuse of predecessor seeds, keys, state, and log identities.
    console.log("P9A-V3-SEAL-004", "Verifying scientific invariance and custody identity freshness.")
    invariance = json.loads((repo / "manifests/scientific_invariance_v3.json").read_text(encoding="utf-8"))
    expected_semantics = invariance["must_remain_semantically_identical"]["reference_artifacts"]
    observed_semantics = {path: sha256_file(custody / path) for path in expected_semantics}
    assert_semantic_invariance(expected_semantics, observed_semantics)
    predecessor_key_identities = {
        "encryption_key_sha256": sha256_file(reference / "keys/phase9a_aes256.key"),
        "custody_signing_private_key_sha256": sha256_file(reference / "keys/phase9a_ed25519_private.pem"),
        "seed_file_sha256": sha256_file(reference / "configs/holdouts/seeds.yaml"),
        "custody_log_sha256": sha256_file(reference / "logs/access.jsonl"),
    }
    preliminary_new = {
        **seed_identities,
        "encryption_key_sha256": sha256_bytes(encryption_key),
        "custody_signing_private_key_sha256": sha256_bytes(private_pem),
        "custody_signing_public_key_sha256": signer_identity,
        "one_shot_state_genesis_sha256": sha256_file(state_path),
        "custody_log_genesis_sha256": sha256_bytes(f"{STUDY}:{PRESEAL}:pending-genesis".encode()),
    }
    if set(preliminary_new) != FRESH_IDENTITIES:
        raise CustodyContractError("new custody identity inventory is incomplete")
    assert_identity_freshness(preliminary_new, {"pead-study-v2": predecessor_key_identities})
    # STEP LOG P9A-V3-SEAL-005: Canonicalize and sign the normative allocation without changing any frozen quota, then verify the signed JSON as the sole custody input.
    console.log("P9A-V3-SEAL-005", "Signing and verifying the canonical allocation manifest.")
    normative_path = repo / "configs/allocations/final_claim_bank_v1.yaml"
    allocation = yaml.safe_load(normative_path.read_text(encoding="utf-8"))
    allocation.update(
        {
            "normative_status": "signed_phase_9a_v3",
            "normative_yaml_sha256": sha256_file(normative_path),
            "canonicalization_id": CANONICALIZATION_ID,
            "study_version": STUDY,
            "preseal_id": PRESEAL,
            "signer_identity": signer_identity,
        }
    )
    allocation["final_signature"] = {"phase": "9A", "status": "signed", "required_output": "manifests/allocations/final_claim_bank_v1.json"}
    allocation_path = repo / "manifests/allocations/final_claim_bank_v1.json"
    if args.resume_pristine_partial:
        signed_allocation = json.loads(allocation_path.read_text(encoding="utf-8"))
        if signed_allocation.get("study_version") != STUDY or signed_allocation.get("preseal_id") != PRESEAL:
            raise CustodyContractError("partial signed allocation identity mismatch")
    else:
        signed_allocation = sign_mapping(allocation, signing_key, signer_identity)
        _write_json(allocation_path, signed_allocation)
    verify_signature(json.loads(allocation_path.read_text(encoding="utf-8")), expected_signer=signer_identity)
    allocation_sha256 = sha256_file(allocation_path)
    shutil.copy2(allocation_path, custody / "signed_allocation.json")
    # STEP LOG P9A-V3-SEAL-006: Execute the separate internal review process over allocation, D7/D8 meaning, ambiguity, separation, and frozen semantic hashes before sealing.
    console.log("P9A-V3-SEAL-006", "Running the internal-independent sealed-design review process.")
    audit_root = repo / "results/audits" / PRESEAL
    audit_root.mkdir(parents=True, exist_ok=True)
    if args.resume_pristine_partial:
        _write_json(
            audit_root / "failed_attempt_001.json",
            {
                "schema_version": "1.0",
                "study_version": STUDY,
                "preseal_id": PRESEAL,
                "status": "stopped-before-genesis",
                "failed_gate": "internal-independent-domain-allocation-review",
                "reason": "reviewer required exact allocation mapping equality and rejected permitted frozen subbank metadata",
                "custody_event_count": 0,
                "ciphertext_package_count": 0,
                "commitment_created": False,
                "unlock_attempted": False,
                "decryption_attempted": False,
                "materialization_attempted": False,
                "correction": "validate required exact_pairs and near_pairs keys while retaining and reviewing frozen subbank metadata",
            },
        )
    review_path = audit_root / "human_review.json"
    subprocess.run(
        [sys.executable, str(repo / "scripts/review_phase9a_v3.py"), "--repo-root", str(repo), "--custody-root", str(custody), "--output", str(review_path)],
        cwd=repo,
        check=True,
    )
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if review["status"] != "pass" or review["semantic_mismatches"]:
        raise CustodyContractError("internal-independent sealed-design review did not pass")
    # STEP LOG P9A-V3-SEAL-007: Create and immediately verify every signed custody event from genesis, including 300 denied pre-freeze access attempts.
    console.log("P9A-V3-SEAL-007", "Creating the fully signed append-only custody chronology.")
    event_path = custody / "logs/events.jsonl"
    event_log = SignedEventLog(event_path, study_version=STUDY, preseal_id=PRESEAL, private_key=signing_key, signer_identity=signer_identity)
    event_log.append(f"{PRESEAL}-event-0001", "custody-genesis", "record", {"workspace_identity": sha256_bytes(str(custody).encode()), "public_key_identity": signer_identity})
    event_log.append(f"{PRESEAL}-event-0002", "allocation-signed-json-verified", "allow", {"allocation_sha256": allocation_sha256})
    event_log.append(f"{PRESEAL}-event-0003", "internal-design-review", "allow", {"review_sha256": sha256_file(review_path), "semantic_mismatches": 0})
    denied = 0
    roles = ("development", "training", "method")
    for offset in range(300):
        try:
            deny_pre_freeze_access(
                event_log,
                event_id=f"{PRESEAL}-event-{offset + 4:04d}",
                actor_role=roles[offset % len(roles)],
                requested_action="read-sealed-design",
                details={"attempt_ordinal": offset + 1},
            )
        except PermissionError:
            denied += 1
    if denied != 300:
        raise CustodyContractError("pre-freeze access denial stress did not reject every attempt")
    # STEP LOG P9A-V3-SEAL-008: Sign the complete design inventory and encrypt content, labels, and seeds separately under one signed allocation binding.
    console.log("P9A-V3-SEAL-008", "Signing design identities and encrypting separated custody packages.")
    design_paths = sorted((custody / "configs/holdouts").glob("*.yaml")) + sorted((custody / "src/pead_holdout").glob("*.py"))
    design_rows = [
        {"artifact_id": path.relative_to(custody).as_posix(), "sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in design_paths
    ]
    inventory_unsigned = {
        "schema_version": "3.0",
        "study_version": STUDY,
        "preseal_id": PRESEAL,
        "canonicalization_id": CANONICALIZATION_ID,
        "scientific_config_sha256": sha256_file(repo / "configs/study/pead_main_v1.yaml"),
        "artifact_count": len(design_rows),
        "design_artifacts": design_rows,
        "signer_identity": signer_identity,
    }
    design_inventory = sign_mapping(inventory_unsigned, signing_key, signer_identity)
    inventory_path = repo / "manifests/custody/holdout_design_inventory.json"
    _write_json(inventory_path, design_inventory)
    content_paths = [path for path in design_paths if path.name not in {"seeds.yaml", "ambiguity.py"}]
    label_paths = [custody / "src/pead_holdout/ambiguity.py"]
    seed_paths = [custody / "configs/holdouts/seeds.yaml"]
    role_records = {
        "content": [_bundle_record(custody, content_paths, "content")],
        "labels": [_bundle_record(custody, label_paths, "labels")],
        "seeds": [_bundle_record(custody, seed_paths, "seeds")],
    }
    artifact_root = repo / "artifacts/custody" / PRESEAL
    packages: list[dict[str, Any]] = []
    for ordinal, role in enumerate(("content", "labels", "seeds"), start=304):
        package, _ = encrypt_package(
            repo_root=repo,
            output_path=artifact_root / f"holdout-{role}-v3.aesgcm",
            study_version=STUDY,
            preseal_id=PRESEAL,
            role=role,
            allocation_sha256=allocation_sha256,
            records=role_records[role],
            encryption_key=encryption_key,
        )
        packages.append(package)
        event_log.append(f"{PRESEAL}-event-{ordinal:04d}", "package-encrypted", "record", {"role": role, "ciphertext_sha256": package["ciphertext_sha256"], "record_count": package["record_count"]})
    index = create_ciphertext_index(
        study_version=STUDY,
        preseal_id=PRESEAL,
        allocation_sha256=allocation_sha256,
        packages=packages,
        private_key=signing_key,
        signer_identity=signer_identity,
    )
    index_path = repo / "manifests/custody/encrypted_blind_package.index.json"
    _write_json(index_path, index)
    event_log.append(f"{PRESEAL}-event-0307", "ciphertext-index-signed", "record", {"ciphertext_index_sha256": sha256_file(index_path)})
    event_log.append(f"{PRESEAL}-event-0308", "phase9a-seal-finalized", "record", {"allocation_sha256": allocation_sha256, "design_commitment_sha256": sha256_file(inventory_path), "phase10_artifact_count": 0})
    event_receipt = verify_event_log(read_event_log(event_path), study_version=STUDY, preseal_id=PRESEAL, expected_signer_identity=signer_identity)
    commitment = create_commitment(
        study_version=STUDY,
        preseal_id=PRESEAL,
        phase9_anchor_sha=ANCHOR,
        allocation_sha256=allocation_sha256,
        bank_counts=_bank_counts(),
        packages=packages,
        design_commitment_sha256=sha256_file(inventory_path),
        ciphertext_index_sha256=sha256_file(index_path),
        event_receipt=event_receipt,
        private_key=signing_key,
        signer_identity=signer_identity,
    )
    commitment_path = repo / "manifests/custody/holdout_design_commitment.json"
    _write_json(commitment_path, commitment)
    public_event_path = repo / "manifests/custody/phase9a-preseal-v3.custody-events.jsonl"
    shutil.copy2(event_path, public_event_path)
    # STEP LOG P9A-V3-SEAL-009: Run the exact future Phase 11 preflight against real public v3 artifacts without unlock, decryption, or materialization.
    console.log("P9A-V3-SEAL-009", "Running the exact public Phase 11 preflight without opening the real bank.")
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
        raise CustodyContractError("real Phase 11 preflight requires an invented or missing value")
    final_new = dict(preliminary_new)
    final_new["custody_log_genesis_sha256"] = event_receipt["genesis_sha256"]
    assert_identity_freshness(final_new, {"pead-study-v2": predecessor_key_identities})
    # STEP LOG P9A-V3-SEAL-010: Retain nonrevealing counts, identities, reviews, separation, freshness, chronology, and zero-gap compliance evidence.
    console.log("P9A-V3-SEAL-010", "Writing corrected Phase 9A nonrevealing audit evidence.")
    _write_json(audit_root / "allocation.json", {"schema_version": "1.0", "study_version": STUDY, "preseal_id": PRESEAL, "status": "pass", "allocation_sha256": allocation_sha256, "normative_yaml_sha256": sha256_file(normative_path), "signed_json_only": True, "bank_counts": _bank_counts(), "exact_pairs_per_domain": 2000, "near_pairs_per_domain": 1000})
    _write_json(audit_root / "holdout_design.json", {"schema_version": "1.0", "study_version": STUDY, "preseal_id": PRESEAL, "status": "pass", "design_inventory_sha256": sha256_file(inventory_path), "signed_design_artifacts": len(design_rows), "semantic_reference_artifacts": len(expected_semantics), "semantic_mismatches": [], "seed_artifact_intentionally_changed": True, "performance_inputs_used": []})
    _write_json(audit_root / "custody.json", {"schema_version": "1.0", "study_version": STUDY, "preseal_id": PRESEAL, "status": "pass", "custody_workspace_identity": sha256_bytes(str(custody).encode()), "fresh_identity_hashes": final_new, "predecessor_identity_hashes": predecessor_key_identities, "predecessor_seed_overlap": predecessor_seed_overlap, "denied_pre_freeze_attempts": denied, "signed_event_count": event_receipt["event_count"], "unsigned_event_count": event_receipt["unsigned_events"], "event_genesis_sha256": event_receipt["genesis_sha256"], "event_head_sha256": event_receipt["head_sha256"], "event_log_sha256": sha256_file(public_event_path), "keys_in_development": 0, "one_shot_state_consumed": False})
    _write_json(audit_root / "phase11_preflight.json", preflight)
    _write_json(audit_root / "phase9a_compliance.json", {"schema_version": "1.0", "phase": "9A", "study_version": STUDY, "preseal_id": PRESEAL, "status": "pass", "five_top_level_materialization_commitments": ["allocation_sha256", "bank_counts", "content_plaintext_sha256", "label_plaintext_sha256", "seed_selection_sha256"], "nine_formerly_missing_package_commitments": [{"role": role, "fields": ["allocation_sha256", "plaintext_sha256", "record_count"]} for role in ("content", "labels", "seeds")], "all_required_commitments_present": True, "consumer_invented_values": [], "allocation_agreement_roles": ["content", "labels", "seeds"], "signed_event_count": event_receipt["event_count"], "unsigned_event_count": 0, "new_hidden_seeds": True, "new_encryption_key": True, "new_signing_key": True, "labels_separately_encrypted": True, "real_unlock_attempted": False, "real_decryption_attempted": False, "real_materialization_attempted": False, "one_shot_state_consumed": False, "phase10_artifact_count_at_seal": 0, "scientific_result_generated": False, "compliance_gaps": []})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
