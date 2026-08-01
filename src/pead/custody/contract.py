"""Strict shared Phase 9A producer and Phase 11 consumer contract.

This module contains no scientific generator logic.  It defines the exact
public commitment accepted at both sides of the custody boundary.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


CANONICALIZATION_ID = "pead-canonical-json-v1"
SCHEMA_VERSION = "3.0"
ROLES = ("content", "labels", "seeds")
BANKS = ("structural", "domains", "final_blind")
TRACKS = ("exact", "near", "reversal", "scope", "evidence")
HEX64 = re.compile(r"^[0-9a-f]{64}$")

SIGNATURE_FIELDS = frozenset({"algorithm", "public_key_b64", "signer_identity", "signature_b64"})
PACKAGE_FIELDS = frozenset(
    {
        "role",
        "schema_version",
        "canonicalization_id",
        "allocation_sha256",
        "plaintext_sha256",
        "record_count",
        "ciphertext_sha256",
        "ciphertext_byte_count",
        "encryption_algorithm",
        "associated_data_sha256",
        "nonce_b64",
        "signed_inclusion",
        "path",
    }
)
CHRONOLOGY_FIELDS = frozenset(
    {
        "phase9_anchor_sha",
        "phase9a_precedes_phase10",
        "phase10_artifact_count_at_seal",
        "unlock_attempted",
        "decryption_attempted",
        "materialization_attempted",
        "one_shot_state_consumed",
    }
)
COMMITMENT_FIELDS = frozenset(
    {
        "schema_version",
        "study_version",
        "preseal_id",
        "canonicalization_id",
        "allocation_sha256",
        "bank_counts",
        "content_plaintext_sha256",
        "label_plaintext_sha256",
        "seed_selection_sha256",
        "design_commitment_sha256",
        "ciphertext_index_sha256",
        "custody_public_key_identity",
        "custody_log_genesis_sha256",
        "custody_log_head_sha256",
        "custody_event_count",
        "all_events_signed",
        "phase9a_chronology_proof",
        "packages",
        "signer_identity",
        "signature",
    }
)
INDEX_FIELDS = frozenset(
    {
        "schema_version",
        "study_version",
        "preseal_id",
        "canonicalization_id",
        "allocation_sha256",
        "packages",
        "signer_identity",
        "signature",
    }
)
BANK_COUNT_FIELDS = frozenset({"total_records", "per_bank", "per_track", "per_bank_track"})


class CustodyContractError(ValueError):
    """Raised whenever a public custody artifact fails closed."""


def canonical_bytes(value: Any) -> bytes:
    """Return deterministic ASCII JSON bytes used by all custody signatures."""

    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _exact_fields(value: Mapping[str, Any], expected: frozenset[str], name: str) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        unknown = sorted(observed - expected)
        raise CustodyContractError(f"{name} fields differ: missing={missing}, unknown={unknown}")


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CustodyContractError(f"{name} must be a mapping")
    return value


def _hash(value: Any, name: str) -> str:
    if not isinstance(value, str) or HEX64.fullmatch(value) is None:
        raise CustodyContractError(f"{name} must be a lowercase SHA-256 identity")
    return value


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise CustodyContractError(f"{name} must be a positive integer")
    return value


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CustodyContractError(f"{name} must be a nonnegative integer")
    return value


def _decode_b64(value: Any, name: str, expected_bytes: int | None = None) -> bytes:
    if not isinstance(value, str) or not value:
        raise CustodyContractError(f"{name} must be nonempty base64")
    try:
        decoded = base64.b64decode(value, validate=True)
    except ValueError as exc:
        raise CustodyContractError(f"{name} is malformed base64") from exc
    if expected_bytes is not None and len(decoded) != expected_bytes:
        raise CustodyContractError(f"{name} must decode to {expected_bytes} bytes")
    return decoded


def verify_signature(value: Mapping[str, Any], *, expected_signer: str | None = None) -> str:
    """Verify the exact Ed25519 signature envelope on a mapping."""

    envelope = _mapping(value.get("signature"), "signature")
    _exact_fields(envelope, SIGNATURE_FIELDS, "signature")
    if envelope["algorithm"] != "Ed25519":
        raise CustodyContractError("unsupported signature algorithm")
    signer = envelope["signer_identity"]
    if not isinstance(signer, str) or not signer:
        raise CustodyContractError("signature signer identity is absent")
    if expected_signer is not None and signer != expected_signer:
        raise CustodyContractError("signature signer identity mismatch")
    public_raw = _decode_b64(envelope["public_key_b64"], "signature.public_key_b64", 32)
    signature_raw = _decode_b64(envelope["signature_b64"], "signature.signature_b64", 64)
    if sha256_bytes(public_raw) != signer:
        raise CustodyContractError("signer identity does not identify the supplied public key")
    unsigned = dict(value)
    unsigned.pop("signature", None)
    try:
        Ed25519PublicKey.from_public_bytes(public_raw).verify(signature_raw, canonical_bytes(unsigned))
    except InvalidSignature as exc:
        raise CustodyContractError("Ed25519 signature verification failed") from exc
    return signer


def sign_mapping(value: Mapping[str, Any], private_key: Any, signer_identity: str) -> dict[str, Any]:
    """Sign an unsigned mapping with the contract's exact envelope."""

    if "signature" in value:
        raise CustodyContractError("refusing to sign a mapping that already contains a signature")
    public_raw = private_key.public_key().public_bytes_raw()
    if sha256_bytes(public_raw) != signer_identity:
        raise CustodyContractError("private key does not match signer identity")
    signed = dict(value)
    signed["signature"] = {
        "algorithm": "Ed25519",
        "public_key_b64": base64.b64encode(public_raw).decode("ascii"),
        "signer_identity": signer_identity,
        "signature_b64": base64.b64encode(private_key.sign(canonical_bytes(value))).decode("ascii"),
    }
    return signed


def validate_bank_counts(value: Any) -> dict[str, int]:
    counts = _mapping(value, "bank_counts")
    _exact_fields(counts, BANK_COUNT_FIELDS, "bank_counts")
    total = _positive_int(counts["total_records"], "bank_counts.total_records")
    per_bank = _mapping(counts["per_bank"], "bank_counts.per_bank")
    per_track = _mapping(counts["per_track"], "bank_counts.per_track")
    matrix = _mapping(counts["per_bank_track"], "bank_counts.per_bank_track")
    if set(per_bank) != set(BANKS) or set(per_track) != set(TRACKS) or set(matrix) != set(BANKS):
        raise CustodyContractError("bank-count axes differ from the registered contract")
    bank_values = {key: _nonnegative_int(per_bank[key], f"per_bank.{key}") for key in BANKS}
    track_values = {key: _nonnegative_int(per_track[key], f"per_track.{key}") for key in TRACKS}
    matrix_values: dict[str, dict[str, int]] = {}
    for bank in BANKS:
        row = _mapping(matrix[bank], f"per_bank_track.{bank}")
        if set(row) != set(TRACKS):
            raise CustodyContractError(f"per-bank track axes differ for {bank}")
        matrix_values[bank] = {track: _nonnegative_int(row[track], f"{bank}.{track}") for track in TRACKS}
        if sum(matrix_values[bank].values()) != bank_values[bank]:
            raise CustodyContractError(f"per-bank track sum differs for {bank}")
    if sum(bank_values.values()) != total or sum(track_values.values()) != total:
        raise CustodyContractError("top-level bank or track count sum differs")
    for track in TRACKS:
        if sum(matrix_values[bank][track] for bank in BANKS) != track_values[track]:
            raise CustodyContractError(f"per-track matrix sum differs for {track}")
    return {"total_records": total, **{f"bank:{k}": v for k, v in bank_values.items()}, **{f"track:{k}": v for k, v in track_values.items()}}


def validate_package(package: Any, *, study_version: str, preseal_id: str, allocation_sha256: str) -> Mapping[str, Any]:
    item = _mapping(package, "package")
    _exact_fields(item, PACKAGE_FIELDS, "package")
    if item["role"] not in ROLES:
        raise CustodyContractError("package role is unsupported")
    if item["schema_version"] != SCHEMA_VERSION or item["canonicalization_id"] != CANONICALIZATION_ID:
        raise CustodyContractError("package schema or canonicalization mismatch")
    if item["allocation_sha256"] != allocation_sha256:
        raise CustodyContractError("package allocation binding mismatch")
    _hash(item["plaintext_sha256"], "package.plaintext_sha256")
    _positive_int(item["record_count"], "package.record_count")
    _hash(item["ciphertext_sha256"], "package.ciphertext_sha256")
    _positive_int(item["ciphertext_byte_count"], "package.ciphertext_byte_count")
    if item["encryption_algorithm"] != "AES-256-GCM":
        raise CustodyContractError("unsupported package encryption algorithm")
    _hash(item["associated_data_sha256"], "package.associated_data_sha256")
    _decode_b64(item["nonce_b64"], "package.nonce_b64", 12)
    if item["signed_inclusion"] is not True:
        raise CustodyContractError("package is not signed into the top-level commitment")
    path = item["path"]
    if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
        raise CustodyContractError("package path is absent, absolute, or traverses parents")
    return item


def validate_packages(packages: Any, *, study_version: str, preseal_id: str, allocation_sha256: str) -> dict[str, Mapping[str, Any]]:
    if not isinstance(packages, Sequence) or isinstance(packages, (str, bytes)) or len(packages) != len(ROLES):
        raise CustodyContractError("packages must contain exactly content, labels, and seeds")
    by_role: dict[str, Mapping[str, Any]] = {}
    for raw in packages:
        item = validate_package(raw, study_version=study_version, preseal_id=preseal_id, allocation_sha256=allocation_sha256)
        role = str(item["role"])
        if role in by_role:
            raise CustodyContractError("duplicate package role")
        by_role[role] = item
    if set(by_role) != set(ROLES):
        raise CustodyContractError("package roles are incomplete")
    if len({str(item["nonce_b64"]) for item in by_role.values()}) != len(ROLES):
        raise CustodyContractError("AES-GCM nonces must be unique across packages")
    if by_role["content"]["record_count"] != by_role["labels"]["record_count"]:
        raise CustodyContractError("content and label record counts differ")
    return by_role


def validate_index(index: Any, *, expected_study: str, expected_preseal: str) -> dict[str, Mapping[str, Any]]:
    value = _mapping(index, "ciphertext_index")
    _exact_fields(value, INDEX_FIELDS, "ciphertext_index")
    if value["schema_version"] != SCHEMA_VERSION or value["canonicalization_id"] != CANONICALIZATION_ID:
        raise CustodyContractError("ciphertext index schema or canonicalization mismatch")
    if value["study_version"] != expected_study or value["preseal_id"] != expected_preseal:
        raise CustodyContractError("ciphertext index study or preseal mismatch")
    allocation = _hash(value["allocation_sha256"], "ciphertext_index.allocation_sha256")
    signer = value["signer_identity"]
    if not isinstance(signer, str) or not signer:
        raise CustodyContractError("ciphertext index signer identity is absent")
    verify_signature(value, expected_signer=signer)
    return validate_packages(value["packages"], study_version=expected_study, preseal_id=expected_preseal, allocation_sha256=allocation)


def validate_commitment(commitment: Any, *, expected_study: str, expected_preseal: str) -> dict[str, Any]:
    value = _mapping(commitment, "commitment")
    _exact_fields(value, COMMITMENT_FIELDS, "commitment")
    if value["schema_version"] != SCHEMA_VERSION or value["canonicalization_id"] != CANONICALIZATION_ID:
        raise CustodyContractError("commitment schema or canonicalization mismatch")
    if value["study_version"] != expected_study or value["preseal_id"] != expected_preseal:
        raise CustodyContractError("commitment study or preseal mismatch")
    allocation = _hash(value["allocation_sha256"], "commitment.allocation_sha256")
    for field in (
        "content_plaintext_sha256",
        "label_plaintext_sha256",
        "seed_selection_sha256",
        "design_commitment_sha256",
        "ciphertext_index_sha256",
        "custody_public_key_identity",
        "custody_log_genesis_sha256",
        "custody_log_head_sha256",
    ):
        _hash(value[field], field)
    counts = validate_bank_counts(value["bank_counts"])
    _positive_int(value["custody_event_count"], "custody_event_count")
    if value["all_events_signed"] is not True:
        raise CustodyContractError("all_events_signed must be true")
    chronology = _mapping(value["phase9a_chronology_proof"], "phase9a_chronology_proof")
    _exact_fields(chronology, CHRONOLOGY_FIELDS, "phase9a_chronology_proof")
    _hash(chronology["phase9_anchor_sha"], "phase9_anchor_sha")
    if chronology["phase9a_precedes_phase10"] is not True or chronology["phase10_artifact_count_at_seal"] != 0:
        raise CustodyContractError("Phase 9A chronology does not precede Phase 10")
    for field in ("unlock_attempted", "decryption_attempted", "materialization_attempted", "one_shot_state_consumed"):
        if chronology[field] is not False:
            raise CustodyContractError(f"real custody state is not pristine: {field}")
    packages = validate_packages(value["packages"], study_version=expected_study, preseal_id=expected_preseal, allocation_sha256=allocation)
    if value["content_plaintext_sha256"] != packages["content"]["plaintext_sha256"]:
        raise CustodyContractError("content plaintext identity differs from package commitment")
    if value["label_plaintext_sha256"] != packages["labels"]["plaintext_sha256"]:
        raise CustodyContractError("label plaintext identity differs from package commitment")
    if value["seed_selection_sha256"] != packages["seeds"]["plaintext_sha256"]:
        raise CustodyContractError("seed plaintext identity differs from package commitment")
    signer = value["signer_identity"]
    if not isinstance(signer, str) or signer != value["custody_public_key_identity"]:
        raise CustodyContractError("commitment signer and custody public-key identities differ")
    verify_signature(value, expected_signer=signer)
    return {"allocation_sha256": allocation, "bank_counts": counts, "packages": packages, "signer_identity": signer}


def verify_public_precommit(
    repo_root: Path,
    commitment_path: Path,
    index_path: Path,
    *,
    expected_study: str,
    expected_preseal: str,
) -> dict[str, Any]:
    """Run the exact future Phase 11 public preflight without decryption."""

    root = repo_root.resolve()
    for path in (commitment_path, index_path):
        resolved = path.resolve()
        if root != resolved and root not in resolved.parents:
            raise CustodyContractError("public artifact path escapes the repository")
        if not resolved.is_file():
            raise CustodyContractError(f"public artifact is absent: {resolved.name}")
    commitment = json.loads(commitment_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    commitment_result = validate_commitment(commitment, expected_study=expected_study, expected_preseal=expected_preseal)
    index_packages = validate_index(index, expected_study=expected_study, expected_preseal=expected_preseal)
    if sha256_file(index_path) != commitment["ciphertext_index_sha256"]:
        raise CustodyContractError("ciphertext index identity differs from the signed commitment")
    if commitment["packages"] != index["packages"]:
        raise CustodyContractError("commitment and index package records differ")
    if index["allocation_sha256"] != commitment_result["allocation_sha256"]:
        raise CustodyContractError("commitment and index allocations differ")
    for role, package in index_packages.items():
        ciphertext = (root / str(package["path"])).resolve()
        if root not in ciphertext.parents or not ciphertext.is_file():
            raise CustodyContractError(f"ciphertext path is absent or escapes repository: {role}")
        if sha256_file(ciphertext) != package["ciphertext_sha256"] or ciphertext.stat().st_size != package["ciphertext_byte_count"]:
            raise CustodyContractError(f"ciphertext identity mismatch: {role}")
    return {
        "status": "pass",
        "study_version": expected_study,
        "preseal_id": expected_preseal,
        "missing_commitments": [],
        "consumer_invented_values": [],
        "package_roles": sorted(index_packages),
        "allocation_sha256": commitment_result["allocation_sha256"],
        "bank_counts": commitment_result["bank_counts"],
    }
