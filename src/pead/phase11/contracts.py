"""Fail-closed contracts for the Phase 11 freeze and custody transition."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class Phase11ContractError(ValueError):
    """Raised when a Phase 11 release-blocking invariant fails."""


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_signed_mapping(value: Mapping[str, Any]) -> None:
    signature = value.get("signature")
    if not isinstance(signature, Mapping):
        raise Phase11ContractError("signed mapping has no signature envelope")
    if set(signature) != {"algorithm", "public_key_b64", "signature_b64"}:
        raise Phase11ContractError("signature envelope fields differ from the registered contract")
    if signature["algorithm"] != "Ed25519":
        raise Phase11ContractError("freeze signatures must use Ed25519")
    unsigned = dict(value)
    unsigned.pop("signature")
    try:
        public = Ed25519PublicKey.from_public_bytes(base64.b64decode(signature["public_key_b64"], validate=True))
        public.verify(base64.b64decode(signature["signature_b64"], validate=True), canonical_bytes(unsigned))
    except (InvalidSignature, ValueError) as exc:
        raise Phase11ContractError("freeze signature verification failed") from exc


def verify_file_inventory(repo_root: Path, entries: list[Mapping[str, Any]]) -> None:
    seen: set[str] = set()
    for entry in entries:
        relative = str(entry.get("path", ""))
        if not relative or relative in seen:
            raise Phase11ContractError("freeze inventory contains a missing or duplicate path")
        seen.add(relative)
        path = (repo_root / relative).resolve()
        if repo_root.resolve() not in path.parents or not path.is_file():
            raise Phase11ContractError(f"freeze inventory path is absent or escapes the repository: {relative}")
        if sha256_file(path) != entry.get("sha256") or path.stat().st_size != entry.get("bytes"):
            raise Phase11ContractError(f"frozen file identity mismatch: {relative}")


def verify_materialization_precommit(index: Mapping[str, Any], allocation_sha256: str) -> dict[str, Any]:
    """Require enough signed metadata to verify a case-bank materialization without redesign."""

    required_index = {
        "allocation_sha256",
        "bank_counts",
        "content_plaintext_sha256",
        "label_plaintext_sha256",
        "seed_selection_sha256",
    }
    missing_index = sorted(required_index - set(index))
    packages = index.get("packages")
    if not isinstance(packages, list):
        raise Phase11ContractError("encrypted package index has no package list")
    required_package = {"plaintext_sha256", "record_count", "allocation_sha256"}
    missing_by_role: dict[str, list[str]] = {}
    for package in packages:
        role = str(package.get("role", "unknown"))
        missing = sorted(required_package - set(package))
        if missing:
            missing_by_role[role] = missing
    roles = {str(package.get("role")) for package in packages}
    if roles != {"content", "labels", "seeds"}:
        raise Phase11ContractError(f"encrypted package roles are incomplete: {sorted(roles)}")
    if missing_index or missing_by_role:
        details = {"missing_index_fields": missing_index, "missing_package_fields": missing_by_role}
        raise Phase11ContractError(
            "Phase 9A lacks signed case-materialization commitments required for Phase 11: "
            + json.dumps(details, sort_keys=True, separators=(",", ":"))
        )
    if index["allocation_sha256"] != allocation_sha256:
        raise Phase11ContractError("encrypted bank allocation binding differs from the signed allocation manifest")
    for package in packages:
        if package["allocation_sha256"] != allocation_sha256:
            raise Phase11ContractError(f"package allocation binding mismatch: {package['role']}")
        if not isinstance(package["record_count"], int) or package["record_count"] <= 0:
            raise Phase11ContractError(f"package record count is invalid: {package['role']}")
    content_count = next(item["record_count"] for item in packages if item["role"] == "content")
    label_count = next(item["record_count"] for item in packages if item["role"] == "labels")
    if content_count != label_count:
        raise Phase11ContractError("content and label package counts differ")
    return {
        "status": "pass",
        "allocation_sha256": allocation_sha256,
        "bank_counts": index["bank_counts"],
        "roles": sorted(roles),
    }
