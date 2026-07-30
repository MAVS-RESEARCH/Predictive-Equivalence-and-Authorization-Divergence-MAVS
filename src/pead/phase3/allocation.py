"""Compile and verify the content-signed Phase 3 allocation-validation manifest."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from pead.core.hashing import canonical_hash


class AllocationManifestError(ValueError):
    """Raised when allocation arithmetic or signatures are invalid."""


def _load_yaml(path: Path) -> Mapping[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise AllocationManifestError(f"cannot load allocation source: {path}") from exc
    if not isinstance(value, Mapping):
        raise AllocationManifestError("allocation source must be a mapping")
    return value


def _validate_source(source: Mapping[str, Any]) -> None:
    if source.get("schema_version") != "1.0":
        raise AllocationManifestError("allocation schema_version must be 1.0")
    domains = source.get("domains")
    if domains != [f"D{index}" for index in range(1, 9)]:
        raise AllocationManifestError("allocation requires ordered D1-D8")
    exact = source.get("exact")
    near = source.get("near")
    if not isinstance(exact, Mapping) or not isinstance(near, Mapping):
        raise AllocationManifestError("exact and near allocations are required")
    if sum(exact["subbanks"].values()) != 2_000:
        raise AllocationManifestError("exact subbanks must total 2,000 per domain")
    if sum(exact["mechanism_pairs_per_domain"].values()) != 2_000:
        raise AllocationManifestError("mechanism quotas must total 2,000 per domain")
    if exact["global_world_counts"] != {
        "Accept": 10_666,
        "Reject": 10_666,
        "Escalate": 10_668,
    }:
        raise AllocationManifestError("exact global world balance is invalid")
    if len(near["epsilons"]) != 8 or sum(near["per_cell"].values()) != 125:
        raise AllocationManifestError("near epsilon or cell allocation is invalid")
    if near["global_world_counts"] != {
        "Accept": 5_334,
        "Reject": 5_334,
        "Escalate": 5_332,
    }:
        raise AllocationManifestError("near global world balance is invalid")


def compile_validation_manifest(repo_root: Path) -> dict[str, Any]:
    allocation_path = repo_root / "configs/allocations/final_claim_bank_v1.yaml"
    distance_path = repo_root / "configs/tracks/near_distance_registry.yaml"
    source = _load_yaml(allocation_path)
    distances = _load_yaml(distance_path)
    _validate_source(source)
    if distances.get("schema_version") != "1.0":
        raise AllocationManifestError("distance registry schema_version must be 1.0")
    expanded_exact = {
        domain: {
            "pairs": 2_000,
            "subbanks": dict(source["exact"]["subbanks"]),
            "mechanisms": dict(source["exact"]["mechanism_pairs_per_domain"]),
            "simple": 600,
            "compositional": 1_400,
            "three_or_more_facts": 800,
        }
        for domain in source["domains"]
    }
    expanded_near = {
        domain: {
            f"{float(epsilon):.6f}": {
                "pairs": 125,
                "subbanks": dict(source["near"]["per_cell"]),
                "rotation": (domain_index * 8 + epsilon_index) % 3,
            }
            for epsilon_index, epsilon in enumerate(source["near"]["epsilons"])
        }
        for domain_index, domain in enumerate(source["domains"])
    }
    payload = {
        "schema_version": "1.0",
        "manifest_id": "phase3_allocation_validation_v1",
        "manifest_kind": "phase3_implementation_validation",
        "release_authority": "none",
        "phase9a_final_signature_required": True,
        "allocation_yaml_sha256": canonical_hash(source),
        "distance_registry_sha256": canonical_hash(distances),
        "domains": list(source["domains"]),
        "exact": {
            "global_pairs": 16_000,
            "global_world_counts": dict(source["exact"]["global_world_counts"]),
            "expanded_by_domain": expanded_exact,
        },
        "near": {
            "global_pairs": 8_000,
            "global_world_counts": dict(source["near"]["global_world_counts"]),
            "epsilons": list(source["near"]["epsilons"]),
            "expanded_by_domain_epsilon": expanded_near,
        },
        "signer": "phase3-deterministic-validation-compiler-v1",
    }
    return {**payload, "content_sha256": canonical_hash(payload)}


def write_validation_manifest(repo_root: Path) -> Path:
    output = (
        repo_root
        / "results/manifests/phase3/allocation_validation_manifest_v1.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(compile_validation_manifest(repo_root), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return output


def load_validation_manifest(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AllocationManifestError("cannot load validation manifest") from exc
    if not isinstance(value, Mapping) or "content_sha256" not in value:
        raise AllocationManifestError("validation manifest envelope is invalid")
    payload = dict(value)
    signature = payload.pop("content_sha256")
    if canonical_hash(payload) != signature:
        raise AllocationManifestError("validation manifest signature mismatch")
    if (
        payload.get("manifest_kind") != "phase3_implementation_validation"
        or payload.get("release_authority") != "none"
        or payload.get("phase9a_final_signature_required") is not True
    ):
        raise AllocationManifestError("validation manifest exceeds Phase 3 authority")
    return value
