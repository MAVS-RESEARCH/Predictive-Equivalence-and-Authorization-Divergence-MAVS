"""Compile the content-signed Phase 4 validation-only allocation manifest."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from pead.core.diagnostic_registry import load_diagnostic_definitions
from pead.core.hashing import canonical_hash
from pead.phase3.allocation import load_validation_manifest


class Phase4AllocationError(ValueError):
    """Raised when Phase 4 allocation sources disagree or exceed authority."""


def _yaml(path: Path) -> Mapping[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise Phase4AllocationError(f"cannot read Phase 4 source: {path}") from exc
    if not isinstance(value, Mapping) or value.get("schema_version") != "1.0":
        raise Phase4AllocationError(f"invalid Phase 4 source: {path}")
    return value


def compile_phase4_manifest(repo_root: Path) -> dict[str, Any]:
    allocation = _yaml(repo_root / "configs/allocations/final_claim_bank_v1.yaml")
    reversal = _yaml(repo_root / "configs/tracks/reversal.yaml")
    scope = _yaml(repo_root / "configs/tracks/scope.yaml")
    evidence = _yaml(repo_root / "configs/tracks/evidence.yaml")
    parent = load_validation_manifest(
        repo_root
        / "results/manifests/phase3/allocation_validation_manifest_v1.json"
    )
    diagnostics = load_diagnostic_definitions(repo_root)
    future = allocation.get("future_tracks")
    if not isinstance(future, Mapping):
        raise Phase4AllocationError("normative future-track allocation is missing")
    if (
        future["reversal"] != {
            "sequences_per_domain": 500,
            "global_steps": 24_000,
        }
        or future["scope"] != {
            "cases_per_diagnostic_domain_bank": 100,
            "global_cases": 22_400,
        }
        or future["evidence_sufficiency"] != {
            "cases_per_class_domain": 500,
            "global_cases": 12_000,
        }
    ):
        raise Phase4AllocationError("normative Phase 4 allocation changed")
    if (
        sum(
            int(count)
            for count in reversal["canonical"]["length_counts_per_domain"].values()
        )
        != 500
        or reversal["canonical"]["global_steps"] != 24_000
        or scope["canonical"]["global_cases"] != 22_400
        or evidence["canonical"]["global_cases"] != 12_000
        or len(diagnostics.entries) != 7
    ):
        raise Phase4AllocationError("Phase 4 track arithmetic is invalid")
    controls = scope["additional_controls"]
    if (
        controls["global_cases"] != 5_600
        or float(controls["fraction_of_canonical"]) < 0.20
        or reversal["controls"]["additional_per_domain"] != 100
        or float(reversal["controls"]["minimum_fraction_of_canonical"]) < 0.20
    ):
        raise Phase4AllocationError("Phase 4 matched-control minimum is invalid")
    domains = tuple(parent["domains"])
    payload = {
        "schema_version": "1.0",
        "manifest_id": "phase4_allocation_validation_v1",
        "manifest_kind": "phase4_implementation_validation",
        "release_authority": "none",
        "phase9a_final_signature_required": True,
        "parent_phase3_content_sha256": parent["content_sha256"],
        "allocation_yaml_sha256": canonical_hash(allocation),
        "track_config_sha256": {
            "reversal": canonical_hash(reversal),
            "scope": canonical_hash(scope),
            "evidence": canonical_hash(evidence),
        },
        "diagnostic_registry_sha256": diagnostics.manifest().registry_sha256,
        "diagnostic_definition_hashes": {
            key: value.definition_hash
            for key, value in diagnostics.entries.items()
        },
        "domains": list(domains),
        "reversal": {
            "canonical_sequences": 4_000,
            "canonical_steps": 24_000,
            "sequences_per_domain": 500,
            "length_counts_per_domain": {"4": 100, "6": 300, "8": 100},
            "additional_controls": 800,
            "families": list(reversal["families"]),
            "controls": dict(reversal["controls"]["kinds"]),
            "timing": dict(reversal["timing"]),
        },
        "scope": {
            "canonical_cases": 22_400,
            "cases_per_bank_diagnostic_domain": 100,
            "canonical_banks": dict(scope["canonical"]["banks"]),
            "additional_controls": 5_600,
            "control_banks": dict(
                scope["additional_controls"]["cases_per_diagnostic_domain"]
            ),
            "boundary_distances": list(scope["boundary"]["signed_distances"]),
            "diagnostics": list(diagnostics.entries),
        },
        "evidence_sufficiency": {
            "canonical_cases": 12_000,
            "cases_per_class_domain": 500,
            "classes": dict(evidence["canonical"]["classes"]),
            "channels": dict(evidence["channels"]),
            "proof": dict(evidence["proof"]),
        },
        "paper_boundary": {
            "fixed_methods_only": True,
            "adaptive_acquisition_executed": False,
            "self_learning_mavs_primary_paper": False,
        },
        "signer": "phase4-deterministic-validation-compiler-v1",
    }
    return {**payload, "content_sha256": canonical_hash(payload)}


def write_phase4_manifest(repo_root: Path) -> Path:
    output = (
        repo_root
        / "results/manifests/phase4/phase4_validation_manifest_v1.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            compile_phase4_manifest(repo_root),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return output


def load_phase4_manifest(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Phase4AllocationError("cannot read Phase 4 manifest") from exc
    if not isinstance(value, Mapping) or "content_sha256" not in value:
        raise Phase4AllocationError("invalid Phase 4 manifest envelope")
    payload = dict(value)
    signature = payload.pop("content_sha256")
    if canonical_hash(payload) != signature:
        raise Phase4AllocationError("Phase 4 manifest signature mismatch")
    if (
        payload.get("manifest_kind") != "phase4_implementation_validation"
        or payload.get("release_authority") != "none"
        or payload.get("phase9a_final_signature_required") is not True
    ):
        raise Phase4AllocationError("Phase 4 manifest exceeds release authority")
    return value
