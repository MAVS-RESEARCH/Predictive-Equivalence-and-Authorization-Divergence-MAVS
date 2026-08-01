"""One-shot custody materializer used only by synthetic rehearsal in Phase 9A."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from pead.custody.consumer import phase11_preflight
from pead.custody.contract import CustodyContractError, canonical_bytes, sha256_bytes, sha256_file
from pead.custody.producer import associated_data


def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical_bytes(value) + b"\n")
    os.replace(temporary, path)


def materialize_once(
    *,
    repo_root: Path,
    commitment_path: Path,
    index_path: Path,
    event_log_path: Path,
    one_shot_state_path: Path,
    output_root: Path,
    encryption_key: bytes,
    expected_study: str,
    expected_preseal: str,
) -> dict[str, Any]:
    preflight = phase11_preflight(
        repo_root=repo_root,
        commitment_path=commitment_path,
        index_path=index_path,
        event_log_path=event_log_path,
        one_shot_state_path=one_shot_state_path,
        expected_study=expected_study,
        expected_preseal=expected_preseal,
    )
    if output_root.exists() and any(output_root.iterdir()):
        raise CustodyContractError("materialization output is not empty")
    commitment = json.loads(commitment_path.read_text(encoding="utf-8"))
    packages = {item["role"]: item for item in commitment["packages"]}
    plaintext: dict[str, list[dict[str, Any]]] = {}
    for role, package in packages.items():
        ciphertext_path = (repo_root / package["path"]).resolve()
        if sha256_file(ciphertext_path) != package["ciphertext_sha256"]:
            raise CustodyContractError(f"ciphertext changed before decryption: {role}")
        aad = associated_data(
            study_version=expected_study,
            preseal_id=expected_preseal,
            role=role,
            allocation_sha256=package["allocation_sha256"],
        )
        if sha256_bytes(aad) != package["associated_data_sha256"]:
            raise CustodyContractError(f"authenticated metadata identity mismatch: {role}")
        try:
            decoded = AESGCM(encryption_key).decrypt(
                base64.b64decode(package["nonce_b64"], validate=True), ciphertext_path.read_bytes(), aad
            )
        except (InvalidTag, ValueError) as exc:
            raise CustodyContractError(f"authenticated decryption failed: {role}") from exc
        if sha256_bytes(decoded) != package["plaintext_sha256"]:
            raise CustodyContractError(f"plaintext commitment mismatch: {role}")
        records = json.loads(decoded.decode("utf-8"))
        if not isinstance(records, list) or len(records) != package["record_count"]:
            raise CustodyContractError(f"plaintext record count mismatch: {role}")
        plaintext[role] = records
    if len(plaintext["content"]) != len(plaintext["labels"]):
        raise CustodyContractError("content and label materializations differ in length")
    observed_bank = {bank: 0 for bank in commitment["bank_counts"]["per_bank"]}
    observed_track = {track: 0 for track in commitment["bank_counts"]["per_track"]}
    observed_matrix = {
        bank: {track: 0 for track in observed_track}
        for bank in observed_bank
    }
    for row in plaintext["content"]:
        bank = row.get("bank")
        track = row.get("track")
        if bank not in observed_bank or track not in observed_track:
            raise CustodyContractError("materialized content has an unknown bank or track")
        observed_bank[bank] += 1
        observed_track[track] += 1
        observed_matrix[bank][track] += 1
    if len(plaintext["content"]) != commitment["bank_counts"]["total_records"]:
        raise CustodyContractError("materialized total differs from committed bank count")
    if observed_bank != commitment["bank_counts"]["per_bank"]:
        raise CustodyContractError("materialized per-bank counts differ from commitment")
    if observed_track != commitment["bank_counts"]["per_track"]:
        raise CustodyContractError("materialized per-track counts differ from commitment")
    if observed_matrix != commitment["bank_counts"]["per_bank_track"]:
        raise CustodyContractError("materialized per-bank/per-track counts differ from commitment")
    output_root.mkdir(parents=True, exist_ok=True)
    content_path = output_root / "content.evaluator.json"
    label_path = output_root / "labels.evaluator.json"
    seed_path = output_root / "seeds.evaluator.json"
    content_path.write_bytes(canonical_bytes(plaintext["content"]) + b"\n")
    label_path.write_bytes(canonical_bytes(plaintext["labels"]) + b"\n")
    seed_path.write_bytes(canonical_bytes(plaintext["seeds"]) + b"\n")
    method_projection = [
        {key: row[key] for key in ("case_id", "visible") if key in row}
        for row in plaintext["content"]
    ]
    method_path = output_root / "method_projection.json"
    method_path.write_bytes(canonical_bytes(method_projection) + b"\n")
    state = {
        "schema_version": "3.0",
        "study_version": expected_study,
        "preseal_id": expected_preseal,
        "consumed": True,
        "materialization_count": 1,
    }
    _atomic_write(one_shot_state_path, state)
    return {
        "status": "pass",
        "preflight": preflight,
        "materialization_count": 1,
        "content_sha256": sha256_file(content_path),
        "labels_sha256": sha256_file(label_path),
        "seeds_sha256": sha256_file(seed_path),
        "method_projection_sha256": sha256_file(method_path),
        "method_projection_fields": sorted({key for row in method_projection for key in row}),
        "labels_evaluator_only": True,
    }
