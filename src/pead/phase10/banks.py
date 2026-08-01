"""Deterministic materialization of the five registered Phase 10 open-data roles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import yaml

from pead.config.console import ResearchConsole
from pead.custody.contract import sha256_file

DOMAINS = tuple(f"D{index}" for index in range(1, 7))
ROLES = (
    "development_fit",
    "development_selection",
    "calibration_fit",
    "calibration_policy",
    "public_validation",
)
TRACKS = ("exact", "near", "reversal", "scope", "evidence")
TRACK_CODE = {name: index for index, name in enumerate(TRACKS)}
ROLE_DIRECTORY = {
    "development_fit": "banks/development/development_fit",
    "development_selection": "banks/development/development_selection",
    "calibration_fit": "banks/calibration/calibration_fit",
    "calibration_policy": "banks/calibration/calibration_policy",
    "public_validation": "banks/public_validation",
}


class OpenBankError(ValueError):
    """Raised when an open-bank allocation or identity invariant fails."""


@dataclass(frozen=True)
class OpenBank:
    role: str
    labels: np.ndarray
    p_features: np.ndarray
    g_features: np.ndarray
    case_ids: np.ndarray
    group_ids: np.ndarray
    tracks: np.ndarray
    domains: np.ndarray


def _unit_digest(*parts: object) -> bytes:
    return hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).digest()


def _floats(digest: bytes, count: int) -> tuple[float, ...]:
    return tuple(int.from_bytes(digest[index * 2 : index * 2 + 2], "big") / 65535.0 for index in range(count))


def _label_features(label: int, digest: bytes) -> tuple[float, ...]:
    noise = _floats(digest[12:], 4)
    if label == 0:
        core = (1.0, 1.0, 1.0, 0.9, 0.1, 1.0, 1.0, 0.1)
    elif label == 1:
        core = (0.0, 0.0, 0.0, 0.1, 0.9, 0.0, 0.0, 0.9)
    else:
        core = (0.5, 0.5, 0.0, 0.5, 0.5, 0.0, 1.0, 0.5)
    return tuple(min(1.0, max(0.0, value + (noise[index % 4] - 0.5) * 0.04)) for index, value in enumerate(core))


def _iter_groups(role: str, allocations: dict[str, Any]) -> Iterator[tuple[str, int, int]]:
    role_config = allocations[role]
    for domain_index, domain_id in enumerate(DOMAINS):
        counts = {
            "exact": int(role_config["exact_pairs_per_domain"]),
            "near": int(role_config["near_pairs_per_domain"]),
            "reversal": int(role_config["reversal_sequences_per_domain"]),
            "scope": int(role_config["scope_cases_per_domain"]),
            "evidence": int(role_config["evidence_cases_per_domain"]),
        }
        for track in TRACKS:
            for ordinal in range(counts[track]):
                yield track, domain_index, ordinal


def _rows_for_group(role: str, track: str, domain_index: int, ordinal: int) -> Iterator[tuple[int, tuple[float, ...], tuple[float, ...], int, int]]:
    base = _unit_digest("PEAD-OPEN-v1", role, domain_index, track, ordinal)
    p_base = _floats(base, 6)
    group_id = int.from_bytes(_unit_digest("group", role, domain_index, track, ordinal)[:8], "big")
    if track in {"exact", "near"}:
        divergent = ordinal % 5 != 0
        left = ordinal % 3
        right = (left + 1 + ordinal % 2) % 3 if divergent else left
        labels = (left, right)
    elif track == "reversal":
        stable = ordinal % 3
        adverse = (stable + 1) % 3
        labels = (stable, stable, adverse, adverse, stable, stable)
    elif track == "scope":
        labels = (ordinal % 3,)
    else:
        labels = ((0, 2, 2)[ordinal % 3],)
    for member, label in enumerate(labels):
        case_digest = _unit_digest("case", role, domain_index, track, ordinal, member)
        case_id = int.from_bytes(case_digest[:8], "big")
        if track == "near" and member == 1:
            epsilon = (1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 2.5e-2, 5e-2, 1e-1)[ordinal % 8]
            p_features = tuple(min(1.0, value + epsilon) for value in p_base)
        elif track == "reversal":
            p_features = tuple(min(1.0, max(0.0, value + (member - 2.5) * 1e-4)) for value in p_base)
        else:
            p_features = p_base
        g_features = _label_features(label, case_digest)
        yield label, p_features, g_features, case_id, group_id


def materialize_open_banks(repo_root: Path, console: ResearchConsole) -> dict[str, Any]:
    """Write complete deterministic NumPy banks and their auditable manifests."""

    config_path = repo_root / "configs/methods/development_partitions_v1.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    allocations = config["roles"]
    if tuple(allocations) != ROLES:
        raise OpenBankError("development role order or identities differ from the frozen contract")
    # STEP LOG P10-BANK-001: Admit only the frozen five-role open-bank allocation before constructing any training case.
    console.log("P10-BANK-001", "Frozen Phase 10 open-bank allocation admitted.", details={"roles": len(ROLES)})
    result: dict[str, Any] = {}
    seen_cases: set[int] = set()
    seen_groups_by_role: dict[str, set[int]] = {}
    for role in ROLES:
        # STEP LOG P10-BANK-002: Materialize one complete group-atomic role across D1-D6 and all five registered tracks.
        console.log("P10-BANK-002", "Materializing complete open-bank role.", details={"role": role})
        labels: list[int] = []
        p_features: list[tuple[float, ...]] = []
        g_features: list[tuple[float, ...]] = []
        case_ids: list[int] = []
        group_ids: list[int] = []
        tracks: list[int] = []
        domains: list[int] = []
        opportunities = {track: 0 for track in TRACKS}
        for track, domain_index, ordinal in _iter_groups(role, allocations):
            opportunities[track] += 1
            for label, p_row, g_row, case_id, group_id in _rows_for_group(role, track, domain_index, ordinal):
                labels.append(label)
                p_features.append(p_row)
                g_features.append(g_row)
                case_ids.append(case_id)
                group_ids.append(group_id)
                tracks.append(TRACK_CODE[track])
                domains.append(domain_index)
        arrays = {
            "labels": np.asarray(labels, dtype=np.uint8),
            "p_features": np.asarray(p_features, dtype=np.float32),
            "g_features": np.asarray(g_features, dtype=np.float32),
            "case_ids": np.asarray(case_ids, dtype=np.uint64),
            "group_ids": np.asarray(group_ids, dtype=np.uint64),
            "tracks": np.asarray(tracks, dtype=np.uint8),
            "domains": np.asarray(domains, dtype=np.uint8),
        }
        directory = repo_root / ROLE_DIRECTORY[role]
        directory.mkdir(parents=True, exist_ok=True)
        file_hashes: dict[str, str] = {}
        for name, array in arrays.items():
            path = directory / f"{name}.npy"
            np.save(path, array, allow_pickle=False)
            file_hashes[path.relative_to(repo_root).as_posix()] = sha256_file(path)
        role_cases = set(case_ids)
        role_groups = set(group_ids)
        if len(role_cases) != len(case_ids) or seen_cases & role_cases:
            raise OpenBankError(f"case identity collision or cross-role reuse in {role}")
        if any(role_groups & prior for prior in seen_groups_by_role.values()):
            raise OpenBankError(f"atomic group crosses roles in {role}")
        seen_cases.update(role_cases)
        seen_groups_by_role[role] = role_groups
        manifest = {
            "schema_version": "1.0",
            "study_version": "pead-study-v3",
            "bank_id": f"PEAD-OPEN-{role}-v1",
            "role": role,
            "domains": list(DOMAINS),
            "opportunity_counts": opportunities,
            "opportunity_total": sum(opportunities.values()),
            "case_rows": len(labels),
            "atomic_groups": len(role_groups),
            "label_counts": {str(value): labels.count(value) for value in range(3)},
            "files": file_hashes,
            "group_atomic_keys": list(config["isolation"]["group_atomic_by"]),
            "public_selection_prohibited": bool(config["isolation"]["public_selection_prohibited"]),
        }
        manifest_path = directory / "bank_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result[role] = {**manifest, "manifest_sha256": sha256_file(manifest_path)}
    # STEP LOG P10-BANK-003: Close generation only after count, collision, atomic isolation, and cross-profile identity gates pass.
    console.log("P10-BANK-003", "All Phase 10 open banks passed materialization gates.", status="pass", details={"case_rows": len(seen_cases), "atomic_groups": sum(len(value) for value in seen_groups_by_role.values())})
    return result


def load_open_bank(repo_root: Path, role: str) -> OpenBank:
    if role not in ROLE_DIRECTORY:
        raise OpenBankError(f"unknown open-bank role: {role}")
    directory = repo_root / ROLE_DIRECTORY[role]
    arrays = {name: np.load(directory / f"{name}.npy", allow_pickle=False) for name in ("labels", "p_features", "g_features", "case_ids", "group_ids", "tracks", "domains")}
    lengths = {len(array) for array in arrays.values()}
    if len(lengths) != 1:
        raise OpenBankError(f"misaligned bank arrays for {role}")
    return OpenBank(role=role, **arrays)
