"""Shared Phase 9A custody-package producer used by real and synthetic seals."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from pead.custody.contract import (
    CANONICALIZATION_ID,
    SCHEMA_VERSION,
    CustodyContractError,
    canonical_bytes,
    sha256_bytes,
    sha256_file,
    sign_mapping,
    validate_bank_counts,
    validate_commitment,
    validate_index,
)
from pead.custody.events import SignedEventLog, read_event_log, verify_event_log


def associated_data(*, study_version: str, preseal_id: str, role: str, allocation_sha256: str) -> bytes:
    return canonical_bytes(
        {
            "allocation_sha256": allocation_sha256,
            "canonicalization_id": CANONICALIZATION_ID,
            "preseal_id": preseal_id,
            "role": role,
            "schema_version": SCHEMA_VERSION,
            "study_version": study_version,
        }
    )


def canonical_records(records: Sequence[Mapping[str, Any]]) -> bytes:
    if not records or any(not isinstance(item, Mapping) for item in records):
        raise CustodyContractError("package records must be a nonempty sequence of mappings")
    return canonical_bytes([dict(item) for item in records])


def encrypt_package(
    *,
    repo_root: Path,
    output_path: Path,
    study_version: str,
    preseal_id: str,
    role: str,
    allocation_sha256: str,
    records: Sequence[Mapping[str, Any]],
    encryption_key: bytes,
    nonce: bytes | None = None,
) -> tuple[dict[str, Any], bytes]:
    if len(encryption_key) != 32:
        raise CustodyContractError("AES-256-GCM requires a 32-byte key")
    root = repo_root.resolve()
    target = output_path.resolve()
    if root not in target.parents:
        raise CustodyContractError("ciphertext output must remain within the development repository")
    plaintext = canonical_records(records)
    nonce_value = nonce if nonce is not None else os.urandom(12)
    if len(nonce_value) != 12:
        raise CustodyContractError("AES-GCM nonce must contain 12 bytes")
    aad = associated_data(study_version=study_version, preseal_id=preseal_id, role=role, allocation_sha256=allocation_sha256)
    ciphertext = AESGCM(encryption_key).encrypt(nonce_value, plaintext, aad)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(ciphertext)
    relative = target.relative_to(root).as_posix()
    package = {
        "role": role,
        "schema_version": SCHEMA_VERSION,
        "canonicalization_id": CANONICALIZATION_ID,
        "allocation_sha256": allocation_sha256,
        "plaintext_sha256": sha256_bytes(plaintext),
        "record_count": len(records),
        "ciphertext_sha256": sha256_file(target),
        "ciphertext_byte_count": target.stat().st_size,
        "encryption_algorithm": "AES-256-GCM",
        "associated_data_sha256": sha256_bytes(aad),
        "nonce_b64": base64.b64encode(nonce_value).decode("ascii"),
        "signed_inclusion": True,
        "path": relative,
    }
    return package, plaintext


def create_ciphertext_index(
    *,
    study_version: str,
    preseal_id: str,
    allocation_sha256: str,
    packages: Sequence[Mapping[str, Any]],
    private_key: Any,
    signer_identity: str,
) -> dict[str, Any]:
    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "study_version": study_version,
        "preseal_id": preseal_id,
        "canonicalization_id": CANONICALIZATION_ID,
        "allocation_sha256": allocation_sha256,
        "packages": [dict(item) for item in packages],
        "signer_identity": signer_identity,
    }
    signed = sign_mapping(unsigned, private_key, signer_identity)
    validate_index(signed, expected_study=study_version, expected_preseal=preseal_id)
    return signed


def create_commitment(
    *,
    study_version: str,
    preseal_id: str,
    phase9_anchor_sha: str,
    allocation_sha256: str,
    bank_counts: Mapping[str, Any],
    packages: Sequence[Mapping[str, Any]],
    design_commitment_sha256: str,
    ciphertext_index_sha256: str,
    event_receipt: Mapping[str, Any],
    private_key: Any,
    signer_identity: str,
) -> dict[str, Any]:
    validate_bank_counts(bank_counts)
    by_role = {str(item["role"]): item for item in packages}
    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "study_version": study_version,
        "preseal_id": preseal_id,
        "canonicalization_id": CANONICALIZATION_ID,
        "allocation_sha256": allocation_sha256,
        "bank_counts": dict(bank_counts),
        "content_plaintext_sha256": by_role["content"]["plaintext_sha256"],
        "label_plaintext_sha256": by_role["labels"]["plaintext_sha256"],
        "seed_selection_sha256": by_role["seeds"]["plaintext_sha256"],
        "design_commitment_sha256": design_commitment_sha256,
        "ciphertext_index_sha256": ciphertext_index_sha256,
        "custody_public_key_identity": signer_identity,
        "custody_log_genesis_sha256": event_receipt["genesis_sha256"],
        "custody_log_head_sha256": event_receipt["head_sha256"],
        "custody_event_count": event_receipt["event_count"],
        "all_events_signed": event_receipt["all_events_signed"],
        "phase9a_chronology_proof": {
            "phase9_anchor_sha": phase9_anchor_sha,
            "phase9a_precedes_phase10": True,
            "phase10_artifact_count_at_seal": 0,
            "unlock_attempted": False,
            "decryption_attempted": False,
            "materialization_attempted": False,
            "one_shot_state_consumed": False,
        },
        "packages": [dict(item) for item in packages],
        "signer_identity": signer_identity,
    }
    signed = sign_mapping(unsigned, private_key, signer_identity)
    validate_commitment(signed, expected_study=study_version, expected_preseal=preseal_id)
    return signed


def produce_preseal(
    *,
    repo_root: Path,
    custody_root: Path,
    study_version: str,
    preseal_id: str,
    phase9_anchor_sha: str,
    allocation_sha256: str,
    bank_counts: Mapping[str, Any],
    role_records: Mapping[str, Sequence[Mapping[str, Any]]],
    encryption_key: bytes,
    private_key: Any,
    signer_identity: str,
    design_commitment_sha256: str,
    artifact_directory: Path,
    index_path: Path,
    commitment_path: Path,
    event_log_path: Path,
    nonce_by_role: Mapping[str, bytes] | None = None,
    clock: Any = None,
) -> dict[str, Any]:
    """Produce the complete signed contract without decrypting any package."""

    if set(role_records) != {"content", "labels", "seeds"}:
        raise CustodyContractError("producer requires exactly content, labels, and seeds")
    if custody_root.resolve() == repo_root.resolve() or repo_root.resolve() in custody_root.resolve().parents:
        raise CustodyContractError("custody workspace must be outside the development repository")
    log = SignedEventLog(
        event_log_path,
        study_version=study_version,
        preseal_id=preseal_id,
        private_key=private_key,
        signer_identity=signer_identity,
        clock=clock,
    )
    log.append(f"{preseal_id}-event-0001", "custody-genesis", "record", {"study_version": study_version, "preseal_id": preseal_id})
    packages: list[dict[str, Any]] = []
    plaintext_identities: dict[str, str] = {}
    for ordinal, role in enumerate(("content", "labels", "seeds"), start=2):
        package, plaintext = encrypt_package(
            repo_root=repo_root,
            output_path=artifact_directory / f"holdout-{role}-v3.aesgcm",
            study_version=study_version,
            preseal_id=preseal_id,
            role=role,
            allocation_sha256=allocation_sha256,
            records=role_records[role],
            encryption_key=encryption_key,
            nonce=None if nonce_by_role is None else nonce_by_role[role],
        )
        packages.append(package)
        plaintext_identities[role] = sha256_bytes(plaintext)
        log.append(
            f"{preseal_id}-event-{ordinal:04d}",
            "package-encrypted",
            "record",
            {"role": role, "ciphertext_sha256": package["ciphertext_sha256"], "record_count": package["record_count"]},
        )
    index = create_ciphertext_index(
        study_version=study_version,
        preseal_id=preseal_id,
        allocation_sha256=allocation_sha256,
        packages=packages,
        private_key=private_key,
        signer_identity=signer_identity,
    )
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_bytes(canonical_bytes(index) + b"\n")
    log.append(
        f"{preseal_id}-event-0005",
        "public-index-signed",
        "record",
        {"ciphertext_index_sha256": sha256_file(index_path)},
    )
    log.append(
        f"{preseal_id}-event-0006",
        "phase9a-seal-finalized",
        "record",
        {
            "allocation_sha256": allocation_sha256,
            "design_commitment_sha256": design_commitment_sha256,
            "phase10_artifact_count": 0,
        },
    )
    events = read_event_log(event_log_path)
    receipt = verify_event_log(events, study_version=study_version, preseal_id=preseal_id, expected_signer_identity=signer_identity)
    commitment = create_commitment(
        study_version=study_version,
        preseal_id=preseal_id,
        phase9_anchor_sha=phase9_anchor_sha,
        allocation_sha256=allocation_sha256,
        bank_counts=bank_counts,
        packages=packages,
        design_commitment_sha256=design_commitment_sha256,
        ciphertext_index_sha256=sha256_file(index_path),
        event_receipt=receipt,
        private_key=private_key,
        signer_identity=signer_identity,
    )
    commitment_path.parent.mkdir(parents=True, exist_ok=True)
    commitment_path.write_bytes(canonical_bytes(commitment) + b"\n")
    return {
        "commitment": commitment,
        "index": index,
        "event_receipt": receipt,
        "plaintext_identities": plaintext_identities,
        "packages": packages,
    }
