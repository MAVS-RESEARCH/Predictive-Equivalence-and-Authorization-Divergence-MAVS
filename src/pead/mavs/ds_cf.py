"""Seven-dimensional DS-CF sensor layer bound to frozen stable field IDs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pead.config.console import ResearchConsole
from pead.core.diagnostic_registry import load_diagnostic_definitions
from pead.projections import tabular
from pead.projections.firewall import SealedMethodInput

SIGNAL_TO_DIAGNOSTIC = {
    "z_c": "DSCF-ZC-v1",
    "z_h": "DSCF-ZH-v1",
    "z_s": "DSCF-ZS-v1",
    "z_m": "DSCF-ZM-v1",
    "z_p": "DSCF-ZP-v1",
    "z_o": "DSCF-ZO-v1",
    "z_f": "DSCF-ZF-v1",
}
REQUIRED_STABLE_IDS = {
    "P-SUPPORT-v1", "P-CONFIDENCE-v1", "P-AGREEMENT-v1",
    "G-PROVENANCE-v1", "G-AUTHORITY-v1", "G-POLICY-v1",
    "G-EVIDENCE-v1", "G-DEPENDENCY-v1", "G-CFVIEW-v1",
}


class DSCFContractError(ValueError):
    """Raised when DS-CF input, scope, or frozen semantics are violated."""


@dataclass(frozen=True)
class DSCFVector:
    z_c: float
    z_h: float
    z_s: float
    z_m: float
    z_p: float
    z_o: float
    z_f: float
    definition_hashes: Mapping[str, str]
    evidence_fields: Mapping[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        if any(not 0.0 <= value <= 1.0 for value in self.values().values()):
            raise DSCFContractError("DS-CF signals must be in [0,1]")
        if set(self.definition_hashes) != set(SIGNAL_TO_DIAGNOSTIC.values()):
            raise DSCFContractError("DS-CF definition hash set is incomplete")

    def values(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in SIGNAL_TO_DIAGNOSTIC}


def _clip(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Mapping):
        for key in (
            "value", "score", "support", "support_delta", "fraction",
            "correlation", "shared_source_fraction", "independent_support",
            "missing_fraction", "conflict", "probability", "confidence", "agreement",
        ):
            if key in value:
                return _number(value[key], default)
    return default


def _flag(value: Any, names: tuple[str, ...]) -> bool:
    if isinstance(value, Mapping):
        for name in names:
            if name in value and bool(value[name]):
                return True
        return any(_flag(item, names) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_flag(item, names) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(name.replace("_", " ") in lowered or name in lowered for name in names)
    return False


def _supports(value: Any) -> tuple[float, ...]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (float(value),)
    if isinstance(value, Mapping):
        rows = tuple(_number(item) for key, item in sorted(value.items()) if key in {"score", "support", "support_delta", "value"})
        return rows or tuple(item for nested in value.values() for item in _supports(nested))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(item for nested in value for item in _supports(nested))
    return ()


def _scope_enabled(facts: Mapping[str, Any], signal: str) -> bool:
    for stable_id in ("G-EVIDENCE-v1", "G-POLICY-v1", "G-DEPENDENCY-v1"):
        value = facts.get(stable_id)
        if isinstance(value, Mapping) and isinstance(value.get("scope"), Mapping):
            scoped = value["scope"].get(signal)
            if scoped is not None:
                return bool(scoped)
    return True


@lru_cache(maxsize=4)
def _frozen_definition_hashes(repository_root: Path) -> dict[str, str]:
    definitions = load_diagnostic_definitions(repository_root).entries
    return {
        diagnostic_id: definitions[diagnostic_id].definition_hash
        for diagnostic_id in SIGNAL_TO_DIAGNOSTIC.values()
    }


def evaluate_ds_cf(
    method_input: SealedMethodInput,
    *,
    repository_root: Path,
    console: ResearchConsole,
    enforce_scope: bool = True,
    masked_stable_ids: frozenset[str] = frozenset(),
) -> tuple[tuple[float, ...], DSCFVector]:
    """Evaluate all seven signals using only registered visible stable fields."""

    if method_input.access_profile != "Raw-G" or method_input.representation_id != "canonical-tabular-v1":
        raise DSCFContractError("DS-CF requires canonical tabular Raw-G input")
    facts = tabular.reconstruct(method_input.payload)
    missing = sorted(REQUIRED_STABLE_IDS - set(facts))
    if missing:
        raise DSCFContractError(f"DS-CF stable field inputs are incomplete: {missing}")
    benign_replacements: dict[str, Any] = {
        "G-DEPENDENCY-v1": {}, "G-PROVENANCE-v1": {"independent_support": 1.0},
        "G-POLICY-v1": {}, "G-AUTHORITY-v1": {}, "G-EVIDENCE-v1": {},
        "G-CFVIEW-v1": (),
    }
    facts = {
        stable_id: benign_replacements.get(stable_id, value) if stable_id in masked_stable_ids else value
        for stable_id, value in facts.items()
    }
    supports = _supports(facts["P-SUPPORT-v1"])
    if not supports:
        raise DSCFContractError("specialist support evidence is empty")
    support_strength = _clip(sum(max(0.0, value) for value in supports) / len(supports))
    dependency = facts["G-DEPENDENCY-v1"]
    provenance = facts["G-PROVENANCE-v1"]
    policy = facts["G-POLICY-v1"]
    authority = facts["G-AUTHORITY-v1"]
    evidence = facts["G-EVIDENCE-v1"]
    views = facts["G-CFVIEW-v1"]
    correlation = _clip(_number(dependency, 1.0 if _flag(dependency, ("shared", "correlated", "dependent")) else 0.0))
    independent = _clip(_number(provenance, 0.0 if _flag(provenance, ("compromised", "shared")) else 1.0))
    policy_conflict = 1.0 if _flag(policy, ("conflict", "prohibited", "invalid", "revoked")) else _clip(_number(policy))
    authority_invalid = _flag(authority, ("invalid", "revoked", "expired", "unauthorized"))
    missing_evidence = 1.0 if _flag(evidence, ("missing", "masked", "unknown", "unavailable")) else _clip(_number(evidence))
    confidence = _clip(_number(facts["P-CONFIDENCE-v1"], support_strength))
    agreement = _clip(_number(facts["P-AGREEMENT-v1"], support_strength))
    view_deltas = _supports(views)
    fragility = _clip(max((abs(value) for value in view_deltas), default=0.0))
    safe_consistency = _clip(min(agreement, support_strength, independent))
    if policy_conflict > 0.0 or authority_invalid or missing_evidence >= 1.0:
        safe_consistency = 0.0
    overconfidence = _clip(confidence - support_strength * independent)
    danger_witness = max(policy_conflict, missing_evidence, fragility, 1.0 if authority_invalid else 0.0)
    harmful = _clip(correlation * (1.0 - safe_consistency) * danger_witness)
    values = {
        "z_c": correlation, "z_h": harmful, "z_s": safe_consistency,
        "z_m": missing_evidence, "z_p": policy_conflict,
        "z_o": overconfidence, "z_f": fragility,
    }
    if enforce_scope:
        values = {name: value if _scope_enabled(facts, name) else 0.0 for name, value in values.items()}
    definition_hashes = _frozen_definition_hashes(repository_root.resolve())
    evidence_fields = {
        "z_c": ("G-DEPENDENCY-v1", "G-PROVENANCE-v1"),
        "z_h": ("G-DEPENDENCY-v1", "G-PROVENANCE-v1", "G-POLICY-v1", "G-EVIDENCE-v1", "G-CFVIEW-v1"),
        "z_s": ("P-SUPPORT-v1", "P-AGREEMENT-v1", "G-PROVENANCE-v1", "G-AUTHORITY-v1", "G-POLICY-v1"),
        "z_m": ("G-EVIDENCE-v1",), "z_p": ("G-POLICY-v1",),
        "z_o": ("P-CONFIDENCE-v1", "P-SUPPORT-v1", "G-PROVENANCE-v1"),
        "z_f": ("G-CFVIEW-v1",),
    }
    vector = DSCFVector(**values, definition_hashes=definition_hashes, evidence_fields=evidence_fields)
    # STEP LOG P8-DSCF-001: Evaluate all seven scoped DS-CF signals from only their registered stable visible fields.
    console.log(
        "P8-DSCF-001",
        "Seven-dimensional DS-CF vector evaluated.",
        details={
            "masked_stable_ids": sorted(masked_stable_ids),
            "projection_hash": method_input.projection_hash,
            "scope_enforced": enforce_scope,
            "signals": vector.values(),
        },
    )
    return tuple(_clip(value) for value in supports), vector
