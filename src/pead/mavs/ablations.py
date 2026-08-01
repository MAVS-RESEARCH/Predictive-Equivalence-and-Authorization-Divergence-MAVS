"""Single-code-path A00-A15 registered architectural ablations."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash
from pead.mavs.profiles import MAVSProfile, load_profiles


class AblationContractError(ValueError):
    """Raised when the exact A00-A15 inventory or access contract changes."""


def load_ablation_registry(repository_root: Path) -> dict[str, dict[str, Any]]:
    payload = yaml.safe_load((repository_root / "configs/methods/mavs_ablations_v1.yaml").read_text(encoding="utf-8"))
    entries = {str(item["method_id"]): dict(item) for item in payload["ablations"]}
    expected = {f"MAVS-A{index:02d}" for index in range(16)}
    if set(entries) != expected:
        raise AblationContractError("MAVS ablation inventory must be exactly A00-A15")
    if entries["MAVS-A00"]["access_profile"] != "P-only" or any(
        entries[method_id]["access_profile"] != "Raw-G"
        for method_id in expected - {"MAVS-A00"}
    ):
        raise AblationContractError("A00 must be P-only and A01-A15 must retain identical Raw-G access")
    return entries


def build_ablation_profile(
    repository_root: Path,
    method_id: str,
    *,
    console: ResearchConsole,
) -> tuple[MAVSProfile, dict[str, Any]]:
    registry = load_ablation_registry(repository_root)
    entry = registry[method_id]
    base = load_profiles(repository_root)[str(entry["base_profile"])]
    disabled = set(str(item) for item in entry.get("disabled_diagnostics", ()))
    enabled = tuple(item for item in base.enabled_diagnostics if item not in disabled)
    overrides = dict(entry.get("overrides", {}))
    profile = replace(
        base,
        profile_id=f"{base.profile_id}:{method_id}",
        access_profile=str(entry["access_profile"]),
        enabled_diagnostics=enabled,
        contextual_weights=bool(overrides.get("contextual_weights", base.contextual_weights)),
        hard_veto=bool(overrides.get("hard_veto", base.hard_veto)),
        escalation=bool(overrides.get("escalation", base.escalation)),
        scope_enforced=bool(overrides.get("scope_enforced", base.scope_enforced)),
        scalarization=str(overrides.get("scalarization", base.scalarization)),
        profile_hash=canonical_hash({"base_profile_hash": base.profile_hash, "entry": entry}),
    )
    # STEP LOG P8-ABLATION-001: Materialize one registered ablation as an explicit delta from a frozen shared profile.
    console.log(
        "P8-ABLATION-001",
        "Registered MAVS ablation profile materialized.",
        details={"access_profile": profile.access_profile, "base_profile": base.profile_id, "method_id": method_id},
    )
    return profile, entry
