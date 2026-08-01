"""Verify Phase 9A signatures and ciphertext without generating holdouts."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from pead.config.console import ResearchConsole
from pead.holdouts.interface import HoldoutContractError, HoldoutPackageIndex, VerificationReceipt


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_signed_mapping(value: Mapping[str, Any], public_key_b64: str | None = None) -> None:
    signature = value.get("signature")
    if not isinstance(signature, Mapping) or set(signature) != {"algorithm", "public_key_b64", "signature_b64"}:
        raise HoldoutContractError("registered Ed25519 signature envelope is required")
    if signature["algorithm"] != "Ed25519":
        raise HoldoutContractError("only Ed25519 signatures are registered")
    if public_key_b64 is not None and signature["public_key_b64"] != public_key_b64:
        raise HoldoutContractError("signer public key differs from the registered preseal key")
    unsigned = dict(value)
    unsigned.pop("signature")
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(signature["public_key_b64"], validate=True)).verify(
            base64.b64decode(signature["signature_b64"], validate=True), canonical_bytes(unsigned)
        )
    except (InvalidSignature, ValueError) as exc:
        raise HoldoutContractError("signature verification failed") from exc


def verify_preseal(repo_root: Path) -> VerificationReceipt:
    commitment_path = repo_root / "manifests/custody/holdout_design_commitment.json"
    index_path = repo_root / "manifests/custody/encrypted_blind_package.index.json"
    allocation_path = repo_root / "manifests/allocations/final_claim_bank_v1.json"
    commitment = json.loads(commitment_path.read_text(encoding="utf-8"))
    index_raw = json.loads(index_path.read_text(encoding="utf-8"))
    allocation = json.loads(allocation_path.read_text(encoding="utf-8"))
    verify_signed_mapping(commitment)
    public_key = commitment["signature"]["public_key_b64"]
    verify_signed_mapping(index_raw, public_key)
    verify_signed_mapping(allocation, public_key)
    index = HoldoutPackageIndex.from_mapping(index_raw)
    if index.public_key_b64 != public_key or index.preseal_id != commitment["preseal_id"]:
        raise HoldoutContractError("preseal signer or identity mismatch")
    verified = []
    for package in index.packages:
        package_path = (repo_root / package["path"]).resolve()
        if repo_root.resolve() not in package_path.parents:
            raise HoldoutContractError("ciphertext path escapes repository")
        if sha256_file(package_path) != package["sha256"] or package_path.stat().st_size != package["bytes"]:
            raise HoldoutContractError(f"ciphertext identity mismatch: {package['package_id']}")
        verified.append(package["package_id"])
    expected = {item["artifact_id"]: item["sha256"] for item in commitment["public_artifacts"]}
    actual = {
        "allocation_manifest": sha256_file(allocation_path),
        "encrypted_package_index": sha256_file(index_path),
    }
    if expected != actual:
        raise HoldoutContractError("public artifact commitment mismatch")
    return VerificationReceipt(index.preseal_id, "pass", tuple(sorted(actual)), tuple(sorted(verified)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    args = parser.parse_args()
    console = ResearchConsole("9A")
    # STEP LOG P9A-VERIFY-001: Load only public commitments, signatures, allocation metadata, and ciphertext identities.
    console.log("P9A-VERIFY-001", "Loading nonrevealing Phase 9A commitment surfaces.")
    receipt = verify_preseal(args.repo_root.resolve())
    # STEP LOG P9A-VERIFY-002: Verify every registered signature, public artifact hash, and encrypted package hash.
    console.log("P9A-VERIFY-002", "Phase 9A commitments and ciphertext identities verified.", status=receipt.status, details={"ciphertexts": len(receipt.verified_ciphertexts), "preseal_id": receipt.preseal_id})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
