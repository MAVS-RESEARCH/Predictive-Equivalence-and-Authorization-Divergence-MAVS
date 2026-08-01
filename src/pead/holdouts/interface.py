"""Public, non-generative contracts for sealed holdout commitments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class HoldoutContractError(ValueError):
    """Raised when a public commitment violates its nonrevealing contract."""


@dataclass(frozen=True)
class HoldoutPackageIndex:
    """Metadata sufficient to verify ciphertext without exposing its plaintext."""

    study_version: str
    preseal_id: str
    algorithm: str
    public_key_b64: str
    packages: tuple[Mapping[str, Any], ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "HoldoutPackageIndex":
        required = {"study_version", "preseal_id", "algorithm", "public_key_b64", "packages"}
        missing = required.difference(value)
        if missing:
            raise HoldoutContractError(f"package index missing fields: {sorted(missing)}")
        packages = tuple(value["packages"])
        if not packages or any(set(item) != {"package_id", "path", "sha256", "bytes", "nonce_b64", "role"} for item in packages):
            raise HoldoutContractError("package metadata is absent or contains an unregistered field")
        if {item["role"] for item in packages} != {"content", "labels", "seeds"}:
            raise HoldoutContractError("content, labels, and seeds must be separately encrypted")
        return cls(
            study_version=str(value["study_version"]), preseal_id=str(value["preseal_id"]),
            algorithm=str(value["algorithm"]), public_key_b64=str(value["public_key_b64"]), packages=packages,
        )


@dataclass(frozen=True)
class VerificationReceipt:
    """Result of verifying public signatures, hashes, and ciphertext identities."""

    preseal_id: str
    status: str
    verified_artifacts: tuple[str, ...]
    verified_ciphertexts: tuple[str, ...]
