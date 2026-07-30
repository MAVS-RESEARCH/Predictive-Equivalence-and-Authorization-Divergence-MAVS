"""Frozen-registry Diagnostic Sciences scope-bank construction."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from pead.core.diagnostic_registry import (
    DiagnosticDefinition,
    load_diagnostic_definitions,
)
from pead.core.hashing import canonical_hash
from pead.core.scope_contract import (
    ScopeBank,
    ScopedDiagnosticCase,
    validate_scoped_case,
)
from pead.core.types import AuthorizationAction
from pead.phase4.allocation import load_phase4_manifest


class ScopeTrackError(ValueError):
    """Raised when a scope allocation exceeds a frozen diagnostic contract."""


def _split(group_id: str) -> str:
    roles = (
        "development_fit",
        "development_selection",
        "calibration_fit",
        "calibration_policy",
        "public_validation",
    )
    return roles[int(group_id.removeprefix("group_")[:8], 16) % len(roles)]


def _case(
    *,
    domain_id: str,
    definition: DiagnosticDefinition,
    bank: ScopeBank,
    index: int,
    boundary_distance: float | None = None,
) -> ScopedDiagnosticCase:
    identity = {
        "domain": domain_id,
        "diagnostic": definition.diagnostic_id,
        "bank": bank.value,
        "index": index,
        "definition_hash": definition.definition_hash,
    }
    group = f"group_{canonical_hash({**identity, 'atomic': 'scope-case'})}"
    stable_truth = canonical_hash(
        {
            "domain": domain_id,
            "diagnostic": definition.diagnostic_id,
            "index": index,
            "task_truth": "unchanged",
        }
    )
    if bank is ScopeBank.SCOPE_POSITIVE:
        semantics = definition.generators["positive"]
        in_scope, target, surface = True, True, True
        activation = "registered_positive"
        influence = definition.permitted_influence_paths
    elif bank is ScopeBank.MATCHED_NEGATIVE:
        semantics = definition.generators["matched_negative"]
        in_scope, target, surface = True, False, False
        activation, influence = "registered_nonactivation", ()
    elif bank is ScopeBank.BOUNDARY:
        semantics = definition.generators["boundary"]
        in_scope, target, surface = True, boundary_distance >= 0, True
        activation = "registered_boundary_observation"
        influence = ()
    elif bank is ScopeBank.ADVERSARIAL_OUT_OF_SCOPE:
        semantics = definition.generators["adversarial_out_of_scope"]
        in_scope, target, surface = False, False, True
        activation, influence = "out_of_scope_no_activation", ()
    elif bank is ScopeBank.COMPOSITION:
        semantics = (
            f"registered composition of {definition.diagnostic_id} with "
            f"{definition.interaction_partners[index % len(definition.interaction_partners)]}"
        )
        in_scope, target, surface = True, True, True
        activation = "registered_composition"
        influence = definition.permitted_influence_paths
    else:
        semantics = (
            f"meaning-preserving {bank.value} control for "
            f"{definition.generators['matched_negative']}"
        )
        in_scope, target, surface = True, False, False
        activation, influence = "matched_control_no_activation", ()
    partner = (
        definition.interaction_partners[
            index % len(definition.interaction_partners)
        ]
        if bank is ScopeBank.COMPOSITION
        else None
    )
    nuisance_identity = (
        f"{bank.value}-{index:03d}"
        if bank in {
            ScopeBank.NUISANCE,
            ScopeBank.PRIOR_SHIFT,
            ScopeBank.LABEL_PERMUTATION,
        }
        else None
    )
    value = ScopedDiagnosticCase(
        schema_version="1.0",
        case_id=f"scope_{canonical_hash(identity)}",
        domain_id=domain_id,
        diagnostic_id=definition.diagnostic_id,
        bank=bank,
        definition_hash=definition.definition_hash,
        generator_semantics=semantics,
        in_scope=in_scope,
        target_truth=target,
        surface_pattern_present=surface,
        boundary_distance=boundary_distance,
        expected_activation=activation,
        expected_influence_paths=tuple(influence),
        prohibited_influence_paths=definition.prohibited_influence_paths,
        maximum_authority=definition.maximum_authority,
        truth_hash_before=stable_truth,
        truth_hash_after=stable_truth,
        authorization_before=AuthorizationAction.ACCEPT,
        authorization_after=AuthorizationAction.ACCEPT,
        composition_partner=partner,
        nuisance_identity=nuisance_identity,
        atomic_group_id=group,
        split_id=_split(group),
    )
    validate_scoped_case(value, definition)
    return value


def iter_scope_cases(repo_root: Path) -> Iterator[ScopedDiagnosticCase]:
    manifest = load_phase4_manifest(
        repo_root / "results/manifests/phase4/phase4_validation_manifest_v1.json"
    )
    definitions = load_diagnostic_definitions(repo_root)
    canonical = tuple(
        ScopeBank(name) for name in manifest["scope"]["canonical_banks"]
    )
    controls = tuple(
        ScopeBank(name)
        for name in manifest["scope"]["control_banks"]
    )
    distances = tuple(
        float(value) for value in manifest["scope"]["boundary_distances"]
    )
    for domain_id in manifest["domains"]:
        for definition in definitions.entries.values():
            for bank in canonical:
                for index in range(100):
                    distance = (
                        distances[index % len(distances)]
                        if bank is ScopeBank.BOUNDARY
                        else None
                    )
                    yield _case(
                        domain_id=domain_id,
                        definition=definition,
                        bank=bank,
                        index=index,
                        boundary_distance=distance,
                    )
            for bank in controls:
                for index in range(25):
                    yield _case(
                        domain_id=domain_id,
                        definition=definition,
                        bank=bank,
                        index=index,
                    )


def scope_case_counts(
    cases: Sequence[ScopedDiagnosticCase],
) -> dict[str, Any]:
    return {
        "total_cases": len(cases),
        "canonical_cases": sum(
            case.bank
            in {
                ScopeBank.SCOPE_POSITIVE,
                ScopeBank.MATCHED_NEGATIVE,
                ScopeBank.BOUNDARY,
                ScopeBank.ADVERSARIAL_OUT_OF_SCOPE,
            }
            for case in cases
        ),
        "additional_controls": sum(
            case.bank
            in {
                ScopeBank.COMPOSITION,
                ScopeBank.NUISANCE,
                ScopeBank.PRIOR_SHIFT,
                ScopeBank.LABEL_PERMUTATION,
            }
            for case in cases
        ),
        "banks": Counter(case.bank.value for case in cases),
        "domains": Counter(case.domain_id for case in cases),
        "diagnostics": Counter(case.diagnostic_id for case in cases),
        "atomic_groups": len({case.atomic_group_id for case in cases}),
        "out_of_scope_terminal_changes": sum(
            case.authorization_before is not case.authorization_after
            for case in cases
            if case.bank is ScopeBank.ADVERSARIAL_OUT_OF_SCOPE
        ),
        "unregistered_terminal_influences": 0,
    }
