"""Frozen, versioned original MAVS-GC, DS-CF, and ablation profiles."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from pead.core.hashing import canonical_hash


class MAVSProfileError(ValueError):
    """Raised when a profile changes a registered architecture contract."""


@dataclass(frozen=True)
class MAVSProfile:
    schema_version: str
    profile_id: str
    version: str
    architecture: str
    access_profile: str
    enabled_diagnostics: tuple[str, ...]
    severity_weights: Mapping[str, float]
    base_threshold: float
    severity_multiplier: float
    mitigation_multiplier: float
    mitigation_bound: float
    contextual_weights: bool
    hard_veto: bool
    escalation: bool
    scope_enforced: bool
    scalarization: str
    thresholds: Mapping[str, float]
    status: str
    profile_hash: str

    def __post_init__(self) -> None:
        if self.schema_version != "1.0" or self.status != "frozen":
            raise MAVSProfileError("MAVS profile must be schema 1.0 and frozen")
        if self.access_profile not in {"P-only", "Raw-G"}:
            raise MAVSProfileError("MAVS profile access must be P-only or Raw-G")
        if not 0.0 <= self.mitigation_bound <= 1.0:
            raise MAVSProfileError("mitigation bound must be in [0,1]")
        if self.severity_weights.get("z_c", 0.0) >= self.severity_weights.get("z_h", 0.0):
            raise MAVSProfileError("harmful correlation must dominate raw correlation severity")


def profile_from_mapping(data: Mapping[str, Any]) -> MAVSProfile:
    payload = dict(data)
    profile_hash = canonical_hash(payload)
    return MAVSProfile(
        schema_version=str(payload["schema_version"]),
        profile_id=str(payload["profile_id"]),
        version=str(payload["version"]),
        architecture=str(payload["architecture"]),
        access_profile=str(payload["access_profile"]),
        enabled_diagnostics=tuple(str(item) for item in payload["enabled_diagnostics"]),
        severity_weights={str(key): float(value) for key, value in payload["severity_weights"].items()},
        base_threshold=float(payload["base_threshold"]),
        severity_multiplier=float(payload["severity_multiplier"]),
        mitigation_multiplier=float(payload["mitigation_multiplier"]),
        mitigation_bound=float(payload["mitigation_bound"]),
        contextual_weights=bool(payload["contextual_weights"]),
        hard_veto=bool(payload["hard_veto"]),
        escalation=bool(payload["escalation"]),
        scope_enforced=bool(payload["scope_enforced"]),
        scalarization=str(payload["scalarization"]),
        thresholds={str(key): float(value) for key, value in payload["thresholds"].items()},
        status=str(payload["status"]),
        profile_hash=profile_hash,
    )


def load_profiles(repository_root: Path) -> dict[str, MAVSProfile]:
    path = repository_root / "configs/methods/mavs_profiles_v1.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    profiles = {
        str(item["profile_id"]): profile_from_mapping(item)
        for item in payload["profiles"]
    }
    if len(profiles) != len(payload["profiles"]):
        raise MAVSProfileError("duplicate MAVS profile identity")
    return profiles
