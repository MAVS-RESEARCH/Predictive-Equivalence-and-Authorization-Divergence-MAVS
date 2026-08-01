"""Generate exact-volume, role-isolated open Phase 10 banks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import yaml

from pead.config.console import ResearchConsole


ROLE_ROOTS = {
    "development_fit": "banks/development/development_fit",
    "development_selection": "banks/development/development_selection",
    "calibration_fit": "banks/calibration/calibration_fit",
    "calibration_policy": "banks/calibration/calibration_policy",
    "public_validation": "banks/public_validation/public_validation",
}
TRACK_FIELDS = {
    "exact": "exact_pairs_per_domain", "near": "near_pairs_per_domain",
    "reversal": "reversal_sequences_per_domain", "scope": "scope_cases_per_domain",
    "evidence": "evidence_cases_per_domain",
}
ROLE_CODES = {role: index + 1 for index, role in enumerate(ROLE_ROOTS)}
TRACK_CODES = {track: index + 1 for index, track in enumerate(TRACK_FIELDS)}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _registered_roles(root: Path) -> dict[str, dict[str, Any]]:
    value = yaml.safe_load((root / "configs/methods/development_partitions_v1.yaml").read_text(encoding="utf-8"))
    return value["roles"]


def _track_shape(track: str, units: int) -> tuple[int, int]:
    if track in {"exact", "near"}: return units * 2, 2
    if track == "reversal": return units * 6, 6
    return units, 1


def _bank_arrays(role: str, domain_index: int, track: str, units: int) -> dict[str, np.ndarray]:
    rows, group_size = _track_shape(track, units)
    role_code, track_code = ROLE_CODES[role], TRACK_CODES[track]
    group_ordinal = np.arange(units, dtype=np.uint64)
    group_id = (np.uint64(role_code) << np.uint64(56)) | (np.uint64(domain_index) << np.uint64(48)) | (np.uint64(track_code) << np.uint64(40)) | group_ordinal
    groups = np.repeat(group_id, group_size)
    member = np.tile(np.arange(group_size, dtype=np.uint8), units)
    case_id = groups * np.uint64(8) + member.astype(np.uint64)
    world_id = case_id + np.uint64(10_000_000_000)
    seed = role_code * 3_000_000 + domain_index * 100_000 + track_code * 10_000
    rng = np.random.default_rng(seed)
    base = rng.normal(0.0, 1.0, size=(units, 8)).astype(np.float32)
    predictive = np.repeat(base, group_size, axis=0)
    if track == "near": predictive[:, 0] += member.astype(np.float32) * np.float32(1e-4)
    if track == "reversal": predictive[:, 1] += (member.astype(np.float32) % 2) * np.float32(1e-6)
    governance = rng.normal(0.0, 1.0, size=(rows, 8)).astype(np.float32)
    governance[:, 0] = member.astype(np.float32) - np.float32((group_size - 1) / 2)
    governance[:, 1] = ((groups >> np.uint64(3)) % np.uint64(5)).astype(np.float32) - np.float32(2.0)
    governance[:, 2] = np.float32(domain_index - 3.5)
    if role == "public_validation":
        governance[:, 6] = np.sin(np.arange(rows, dtype=np.float32) / np.float32(7.0))
        governance[:, 7] = np.cos(np.arange(rows, dtype=np.float32) / np.float32(11.0))
    oracle = rng.normal(0.0, 1.0, size=(rows, 8)).astype(np.float32)
    latent_score = governance[:, 0] + np.float32(0.45) * governance[:, 1] - np.float32(0.05) * governance[:, 2] + np.float32(0.2) * oracle[:, 0]
    labels = np.where(latent_score > 0.55, 0, np.where(latent_score < -0.55, 1, 2)).astype(np.uint8)
    if track == "exact":
        same_control = (group_ordinal % np.uint64(5)) == 4
        for group_position in range(units):
            start = group_position * 2; cell = group_position % 3
            if same_control[group_position]:
                labels[start:start + 2] = cell
            else:
                pair = ((0, 1), (0, 2), (1, 2))[cell]
                labels[start:start + 2] = pair if group_position % 2 == 0 else pair[::-1]
    oracle[:, 7] = labels.astype(np.float32)
    features = np.concatenate((predictive, governance, oracle), axis=1)
    missing_key = np.column_stack((np.repeat(groups[:, None], 8, axis=1), np.repeat(case_id[:, None], 16, axis=1)))
    missing_mask = ((missing_key + np.arange(24, dtype=np.uint64)) % np.uint64(211)) == 0
    missing_mask[:, 23] = False
    features[missing_mask] = np.nan
    return {
        "case_id": case_id, "world_id": world_id, "atomic_group_id": groups,
        "member": member, "features": features, "label": labels,
        "domain": np.full(rows, domain_index, dtype=np.uint8),
        "track": np.full(rows, track_code, dtype=np.uint8),
        "role": np.full(rows, role_code, dtype=np.uint8),
    }


def generate_open_banks(root: Path, console: ResearchConsole) -> dict[str, Any]:
    roles = _registered_roles(root)
    files: list[dict[str, Any]] = []
    role_counts: dict[str, dict[str, int]] = {}
    # STEP LOG P10-BANK-001: Load exact Section 5.1.2 volumes and create only registered open-bank roots.
    console.log("P10-BANK-001", "Loading registered open-bank volumes.", details={"roles": len(roles)})
    for role, relative_root in ROLE_ROOTS.items():
        role_counts[role] = {}
        for domain_index in range(1, 7):
            for track, field in TRACK_FIELDS.items():
                units = int(roles[role][field])
                arrays = _bank_arrays(role, domain_index, track, units)
                path = root / relative_root / f"D{domain_index}" / f"{track}.npz"
                path.parent.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(path, **arrays)
                rows = int(len(arrays["label"]))
                role_counts[role][track] = role_counts[role].get(track, 0) + rows
                files.append({"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path), "bytes": path.stat().st_size, "rows": rows, "units": units, "role": role, "domain": f"D{domain_index}", "track": track})
        # STEP LOG P10-BANK-002: Seal one complete role after all six domains and five tracks reach exact denominators.
        console.log("P10-BANK-002", "Open-bank role generated.", details={"role": role, "rows": sum(role_counts[role].values())})
    manifest = {
        "schema_version": "1.0", "bank_id": "phase10-open-banks-v2", "roles": role_counts,
        "files": files, "projection_contract": {"P-only": [0, 8], "Raw-G": [0, 16], "Oracle-G": [0, 24]},
        "identity_alignment": "same case/world/group/role; only projection slice differs",
        "public_validation": "inspection-only", "claim_bearing_content": False,
    }
    manifest_path = root / "results/manifests/phase10/open_bank_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P10-BANK-003: Retain hashes, counts, role isolation, and cross-profile identity alignment for every open-bank shard.
    console.log("P10-BANK-003", "Open-bank manifest retained.", status="pass", details={"files": len(files), "rows": sum(sum(item.values()) for item in role_counts.values())})
    return manifest


def iter_role_arrays(root: Path, role: str) -> Iterator[dict[str, np.ndarray]]:
    if role not in ROLE_ROOTS: raise ValueError(f"unknown role: {role}")
    for path in sorted((root / ROLE_ROOTS[role]).glob("D*/*.npz")):
        with np.load(path) as value:
            yield {name: value[name] for name in value.files}


def load_role(root: Path, role: str, profile: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    end = {"P-only": 8, "Raw-G": 16, "Oracle-G": 24}[profile]
    shards = tuple(iter_role_arrays(root, role))
    return (
        np.concatenate([item["features"][:, :end] for item in shards]),
        np.concatenate([item["label"] for item in shards]),
        np.concatenate([item["atomic_group_id"] for item in shards]),
    )
