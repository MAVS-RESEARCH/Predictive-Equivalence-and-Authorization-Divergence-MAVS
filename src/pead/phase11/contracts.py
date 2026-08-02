"""Fail-closed contracts used at every Phase 11 custody boundary."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from pead.custody.contract import canonical_bytes, sha256_file


class Phase11ContractError(ValueError):
    """Raised when a release-blocking Phase 11 invariant fails."""


def atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    """Write canonical reviewable JSON through an atomic replacement."""

    temporary = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def verify_signed_mapping(value: Mapping[str, Any], expected_signer: str | None = None) -> str:
    """Verify the exact Ed25519 envelope used by the PEAD custody authority."""

    signature = value.get("signature")
    if not isinstance(signature, Mapping):
        raise Phase11ContractError("signed mapping has no signature envelope")
    if set(signature) != {"algorithm", "public_key_b64", "signature_b64", "signer_identity"}:
        raise Phase11ContractError("signed mapping signature envelope differs from the custody contract")
    if signature["algorithm"] != "Ed25519":
        raise Phase11ContractError("custody signatures must use Ed25519")
    unsigned = dict(value)
    unsigned.pop("signature")
    public_bytes = base64.b64decode(str(signature["public_key_b64"]), validate=True)
    signer = hashlib.sha256(public_bytes).hexdigest()
    if signature["signer_identity"] != signer or unsigned.get("signer_identity") != signer:
        raise Phase11ContractError("signed mapping signer identity is inconsistent")
    if expected_signer is not None and signer != expected_signer:
        raise Phase11ContractError("signed mapping uses an unregistered custody signer")
    try:
        Ed25519PublicKey.from_public_bytes(public_bytes).verify(
            base64.b64decode(str(signature["signature_b64"]), validate=True), canonical_bytes(unsigned)
        )
    except (InvalidSignature, ValueError) as exc:
        raise Phase11ContractError("signed mapping signature verification failed") from exc
    return signer


def inventory_rows(mapping: Mapping[str, str], root: Path) -> list[dict[str, Any]]:
    """Convert a path-to-hash map to a size-bound, sorted freeze inventory."""

    rows: list[dict[str, Any]] = []
    for relative in sorted(mapping):
        path = (root / relative).resolve()
        if root.resolve() not in path.parents or not path.is_file():
            raise Phase11ContractError(f"freeze path is absent or escapes the repository: {relative}")
        rows.append({"path": relative, "sha256": mapping[relative], "bytes": path.stat().st_size})
    return rows


def verify_file_inventory(root: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    """Verify uniqueness, containment, byte count, and SHA-256 for all frozen files."""

    seen: set[str] = set()
    resolved_root = root.resolve()
    for row in rows:
        relative = str(row.get("path", ""))
        if not relative or relative in seen:
            raise Phase11ContractError("freeze inventory contains an absent or duplicate path")
        seen.add(relative)
        path = (root / relative).resolve()
        if resolved_root not in path.parents or not path.is_file():
            raise Phase11ContractError(f"frozen path is absent or escapes the repository: {relative}")
        if path.stat().st_size != row.get("bytes") or sha256_file(path) != row.get("sha256"):
            raise Phase11ContractError(f"frozen byte identity mismatch: {relative}")


def assert_lineage(value: Mapping[str, Any]) -> None:
    """Reject an artifact that is not bound to the active v3 execution lineage."""

    if value.get("study_version") != "pead-study-v3" or value.get("preseal_id") != "phase9a-preseal-v3":
        raise Phase11ContractError("artifact is not bound to pead-study-v3/phase9a-preseal-v3")


def content_hash(value: Mapping[str, Any]) -> str:
    """Return the canonical identity of a mapping."""

    return hashlib.sha256(canonical_bytes(value)).hexdigest()

