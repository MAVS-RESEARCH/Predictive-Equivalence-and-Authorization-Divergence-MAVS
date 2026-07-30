"""Exact compatible-world evidence-sufficiency classes for fixed methods."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from pead.core.hashing import canonical_hash
from pead.core.types import AuthorizationAction
from pead.labels.ambiguity import (
    AmbiguityCertificate,
    CompatibleWorld,
    build_exact_certificate,
    verify_certificate,
)
from pead.phase4.allocation import load_phase4_manifest


class EvidenceTrackError(ValueError):
    """Raised when evidence classification or proof reconstruction fails."""


class EvidenceClass(str, Enum):
    RESOLVABLE = "resolvable"
    REDUCIBLY_AMBIGUOUS = "reducibly_ambiguous"
    IRREDUCIBLY_AMBIGUOUS = "irreducibly_ambiguous"


@dataclass(frozen=True)
class EvidenceSufficiencyCase:
    schema_version: str
    case_id: str
    domain_id: str
    evidence_class: EvidenceClass
    expected_action: AuthorizationAction
    compatible_worlds: tuple[CompatibleWorld, ...]
    certificate: AmbiguityCertificate
    permitted_resolution_channels: tuple[str, ...]
    paper_boundary: str
    adaptive_acquisition_executed: bool
    atomic_group_id: str
    split_id: str

    def __post_init__(self) -> None:
        if self.schema_version != "1.0" or self.adaptive_acquisition_executed:
            raise EvidenceTrackError("evidence case exceeds fixed-method boundary")
        if not verify_certificate(self.certificate, self.compatible_worlds):
            raise EvidenceTrackError("evidence proof failed reconstruction")
        if (
            self.certificate.conclusion == "resolvable_unique"
            and self.expected_action not in {
                AuthorizationAction.ACCEPT,
                AuthorizationAction.REJECT,
            }
        ):
            raise EvidenceTrackError("resolvable case lacks a unique terminal action")
        if (
            self.certificate.conclusion != "resolvable_unique"
            and self.expected_action is not AuthorizationAction.ESCALATE
        ):
            raise EvidenceTrackError("ambiguity must remain explicit")


def _split(group_id: str) -> str:
    roles = (
        "development_fit",
        "development_selection",
        "calibration_fit",
        "calibration_policy",
        "public_validation",
    )
    return roles[int(group_id.removeprefix("group_")[:8], 16) % len(roles)]


def _world(
    case_id: str,
    suffix: str,
    action: AuthorizationAction,
) -> CompatibleWorld:
    facts = {
        "case_id": case_id,
        "latent_completion": suffix,
        "authorization": action.value,
    }
    return CompatibleWorld(
        world_id=f"compatible_{canonical_hash(facts)}",
        facts_hash=canonical_hash(facts),
        authorization=action,
    )


def _build_case(
    domain_id: str,
    evidence_class: EvidenceClass,
    index: int,
    config: Mapping[str, Any],
) -> EvidenceSufficiencyCase:
    identity = {
        "domain": domain_id,
        "class": evidence_class.value,
        "index": index,
    }
    case_id = f"evidence_{canonical_hash(identity)}"
    permitted = tuple(str(item) for item in config["channels"]["permitted"])
    if evidence_class is EvidenceClass.RESOLVABLE:
        expected = (
            AuthorizationAction.ACCEPT
            if index % 2 == 0
            else AuthorizationAction.REJECT
        )
        worlds = (
            _world(case_id, "completion-a", expected),
            _world(case_id, "completion-b", expected),
        )
        available, unavailable, exhausted = (), permitted, ()
        boundary = "Paper_1_primary"
    elif evidence_class is EvidenceClass.REDUCIBLY_AMBIGUOUS:
        expected = AuthorizationAction.ESCALATE
        worlds = (
            _world(case_id, "authorized-completion", AuthorizationAction.ACCEPT),
            _world(case_id, "prohibited-completion", AuthorizationAction.REJECT),
        )
        available = tuple(config["channels"]["reducible_available"])
        unavailable = tuple(config["channels"]["reducible_unavailable"])
        exhausted = ()
        boundary = "Bridge_to_Paper_2"
    else:
        expected = AuthorizationAction.ESCALATE
        worlds = (
            _world(case_id, "authorized-completion", AuthorizationAction.ACCEPT),
            _world(case_id, "prohibited-completion", AuthorizationAction.REJECT),
        )
        available = ()
        unavailable = tuple(config["channels"]["irreducible_unavailable"])
        exhausted = tuple(config["channels"]["irreducible_exhausted"])
        boundary = "Explicit_lower_floor"
    certificate = build_exact_certificate(
        case_id=case_id,
        visible_state_hash=canonical_hash({**identity, "visible": "fixed"}),
        projection_hash=canonical_hash({**identity, "projection": "permitted"}),
        worlds=worlds,
        compatible_space_size=len(worlds),
        permitted_channels=permitted,
        available_channels=available,
        unavailable_channels=unavailable,
        exhausted_channels=exhausted,
        proof_method=str(config["proof"]["method"]),
        solver_name=str(config["proof"]["solver_name"]),
        solver_version=str(config["proof"]["solver_version"]),
        solver_configuration="deterministic;ordered_by_world_id;no_sampling",
    )
    group = f"group_{canonical_hash({**identity, 'atomic': 'evidence-proof'})}"
    return EvidenceSufficiencyCase(
        schema_version="1.0",
        case_id=case_id,
        domain_id=domain_id,
        evidence_class=evidence_class,
        expected_action=expected,
        compatible_worlds=worlds,
        certificate=certificate,
        permitted_resolution_channels=permitted,
        paper_boundary=boundary,
        adaptive_acquisition_executed=False,
        atomic_group_id=group,
        split_id=_split(group),
    )


def iter_evidence_cases(repo_root: Path) -> Iterator[EvidenceSufficiencyCase]:
    manifest = load_phase4_manifest(
        repo_root / "results/manifests/phase4/phase4_validation_manifest_v1.json"
    )
    config = manifest["evidence_sufficiency"]
    classes = tuple(
        EvidenceClass(name)
        for name in config["classes"]
    )
    for domain_id in manifest["domains"]:
        for evidence_class in classes:
            for index in range(500):
                yield _build_case(domain_id, evidence_class, index, config)


def remove_permitted_resolution_channels(
    case: EvidenceSufficiencyCase,
) -> EvidenceSufficiencyCase:
    if case.evidence_class is not EvidenceClass.REDUCIBLY_AMBIGUOUS:
        raise EvidenceTrackError("channel removal applies only to reducible ambiguity")
    certificate = build_exact_certificate(
        case_id=case.case_id,
        visible_state_hash=case.certificate.visible_state_hash,
        projection_hash=case.certificate.projection_hash,
        worlds=case.compatible_worlds,
        compatible_space_size=len(case.compatible_worlds),
        permitted_channels=case.permitted_resolution_channels,
        available_channels=(),
        unavailable_channels=case.permitted_resolution_channels,
        exhausted_channels=(),
        proof_method=case.certificate.proof_method,
        solver_name=case.certificate.solver_name,
        solver_version=case.certificate.solver_version,
        solver_configuration=case.certificate.solver_configuration,
    )
    transformed = EvidenceSufficiencyCase(
        schema_version=case.schema_version,
        case_id=case.case_id,
        domain_id=case.domain_id,
        evidence_class=EvidenceClass.IRREDUCIBLY_AMBIGUOUS,
        expected_action=AuthorizationAction.ESCALATE,
        compatible_worlds=case.compatible_worlds,
        certificate=certificate,
        permitted_resolution_channels=case.permitted_resolution_channels,
        paper_boundary="Explicit_lower_floor",
        adaptive_acquisition_executed=False,
        atomic_group_id=case.atomic_group_id,
        split_id=case.split_id,
    )
    if (
        transformed.certificate.conclusion
        != "irreducibly_ambiguous_escalate"
        or transformed.expected_action is AuthorizationAction.REJECT
    ):
        raise EvidenceTrackError("channel removal produced an invalid policy")
    return transformed


def evidence_case_counts(
    cases: Sequence[EvidenceSufficiencyCase],
) -> dict[str, Any]:
    return {
        "total_cases": len(cases),
        "classes": Counter(case.evidence_class.value for case in cases),
        "domains": Counter(case.domain_id for case in cases),
        "conclusions": Counter(case.certificate.conclusion for case in cases),
        "expected_actions": Counter(case.expected_action.value for case in cases),
        "verified_certificates": sum(
            verify_certificate(case.certificate, case.compatible_worlds)
            for case in cases
        ),
        "adaptive_acquisition_executed": any(
            case.adaptive_acquisition_executed for case in cases
        ),
        "atomic_groups": len({case.atomic_group_id for case in cases}),
    }
