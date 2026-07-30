"""Proof-bearing compatible-world ambiguity certificates and verifier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pead.core.hashing import canonical_hash
from pead.core.types import AuthorizationAction


class AmbiguityCertificateError(ValueError):
    """Raised when a certificate claim is incomplete or internally inconsistent."""


CLAIM_PROOF_METHODS = {
    "exact_finite_enumeration",
    "sat",
    "smt",
    "model_checking",
    "exhaustive_symbolic_evaluation",
    "completeness_justified_conservative_proof",
}


@dataclass(frozen=True)
class CompatibleWorld:
    world_id: str
    facts_hash: str
    authorization: AuthorizationAction


@dataclass(frozen=True)
class AuthorizationWitness:
    authorization: AuthorizationAction
    world_id: str
    facts_hash: str


@dataclass(frozen=True)
class AmbiguityCertificate:
    schema_version: str
    certificate_id: str
    case_id: str
    visible_state_hash: str
    projection_hash: str
    compatible_classes: tuple[AuthorizationAction, ...]
    witnesses: tuple[AuthorizationWitness, ...]
    permitted_channels: tuple[str, ...]
    available_channels: tuple[str, ...]
    unavailable_channels: tuple[str, ...]
    exhausted_channels: tuple[str, ...]
    proof_method: str
    solver_name: str
    solver_version: str
    solver_configuration: str
    proof_hash: str
    completeness_status: str
    enumerated_worlds: int
    compatible_space_size: int
    unique_class_proof: str | None
    irreducible_no_channel_reason: str | None
    conclusion: str
    claim_bearing: bool

    @property
    def certificate_hash(self) -> str:
        return canonical_hash(self)


def _sorted_worlds(worlds: tuple[CompatibleWorld, ...]) -> tuple[CompatibleWorld, ...]:
    return tuple(sorted(worlds, key=lambda world: world.world_id))


def _proof_payload(
    case_id: str,
    visible_state_hash: str,
    projection_hash: str,
    proof_method: str,
    solver_name: str,
    solver_version: str,
    solver_configuration: str,
    compatible_space_size: int,
    worlds: tuple[CompatibleWorld, ...],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "visible_state_hash": visible_state_hash,
        "projection_hash": projection_hash,
        "proof_method": proof_method,
        "solver_name": solver_name,
        "solver_version": solver_version,
        "solver_configuration": solver_configuration,
        "compatible_space_size": compatible_space_size,
        "worlds": _sorted_worlds(worlds),
    }


def _channel_partition(
    permitted: tuple[str, ...],
    available: tuple[str, ...],
    unavailable: tuple[str, ...],
    exhausted: tuple[str, ...],
) -> None:
    sets = tuple(set(values) for values in (permitted, available, unavailable, exhausted))
    if any(len(values) != len(set(values)) for values in (permitted, available, unavailable, exhausted)):
        raise AmbiguityCertificateError("resolution channel identities must be unique")
    if not sets[1] <= sets[0] or not sets[2] <= sets[0] or not sets[3] <= sets[0]:
        raise AmbiguityCertificateError("channel states must be subsets of permitted channels")
    if sets[1] & sets[2] or sets[1] & sets[3] or sets[2] & sets[3]:
        raise AmbiguityCertificateError("channel states must be disjoint")
    if sets[1] | sets[2] | sets[3] != sets[0]:
        raise AmbiguityCertificateError("every permitted channel requires one state")


def build_exact_certificate(
    *,
    case_id: str,
    visible_state_hash: str,
    projection_hash: str,
    worlds: tuple[CompatibleWorld, ...],
    compatible_space_size: int,
    permitted_channels: tuple[str, ...] = (),
    available_channels: tuple[str, ...] = (),
    unavailable_channels: tuple[str, ...] = (),
    exhausted_channels: tuple[str, ...] = (),
    proof_method: str = "exact_finite_enumeration",
    solver_name: str = "pead-exact-enumerator",
    solver_version: str = "1.0",
    solver_configuration: str = "deterministic;ordered_by_world_id",
) -> AmbiguityCertificate:
    """Create a claim only after a complete compatible-world proof."""

    _channel_partition(
        permitted_channels,
        available_channels,
        unavailable_channels,
        exhausted_channels,
    )
    if proof_method not in CLAIM_PROOF_METHODS:
        raise AmbiguityCertificateError(
            "sampling, timeout, unknown, and unapproved methods cannot support a claim"
        )
    ordered_worlds = _sorted_worlds(worlds)
    if compatible_space_size <= 0 or len(ordered_worlds) != compatible_space_size:
        raise AmbiguityCertificateError(
            "claim-bearing enumeration must cover the complete compatible space"
        )
    if len({world.world_id for world in ordered_worlds}) != len(ordered_worlds):
        raise AmbiguityCertificateError("compatible worlds must have unique identities")
    classes = tuple(
        sorted(
            {world.authorization for world in ordered_worlds},
            key=lambda item: item.value,
        )
    )
    witnesses = tuple(
        AuthorizationWitness(
            authorization=authorization,
            world_id=next(
                world.world_id
                for world in ordered_worlds
                if world.authorization is authorization
            ),
            facts_hash=next(
                world.facts_hash
                for world in ordered_worlds
                if world.authorization is authorization
            ),
        )
        for authorization in classes
    )
    if len(classes) == 1:
        conclusion = "resolvable_unique"
        unique_proof = (
            f"All {compatible_space_size} compatible worlds authorize "
            f"{classes[0].value}."
        )
        no_channel_reason = None
    elif available_channels:
        conclusion = "ambiguity_resolution_available"
        unique_proof = None
        no_channel_reason = None
    else:
        conclusion = "irreducibly_ambiguous_escalate"
        unique_proof = None
        no_channel_reason = (
            "Multiple authorization classes remain after complete enumeration; "
            "every permitted resolution channel is unavailable or exhausted."
        )
    payload = _proof_payload(
        case_id,
        visible_state_hash,
        projection_hash,
        proof_method,
        solver_name,
        solver_version,
        solver_configuration,
        compatible_space_size,
        ordered_worlds,
    )
    proof_hash = canonical_hash(payload)
    identity_payload = {
        "case_id": case_id,
        "visible_state_hash": visible_state_hash,
        "projection_hash": projection_hash,
        "proof_hash": proof_hash,
        "conclusion": conclusion,
    }
    return AmbiguityCertificate(
        schema_version="1.0",
        certificate_id=f"ambiguity_{canonical_hash(identity_payload)}",
        case_id=case_id,
        visible_state_hash=visible_state_hash,
        projection_hash=projection_hash,
        compatible_classes=classes,
        witnesses=witnesses,
        permitted_channels=tuple(sorted(permitted_channels)),
        available_channels=tuple(sorted(available_channels)),
        unavailable_channels=tuple(sorted(unavailable_channels)),
        exhausted_channels=tuple(sorted(exhausted_channels)),
        proof_method=proof_method,
        solver_name=solver_name,
        solver_version=solver_version,
        solver_configuration=solver_configuration,
        proof_hash=proof_hash,
        completeness_status="complete",
        enumerated_worlds=len(ordered_worlds),
        compatible_space_size=compatible_space_size,
        unique_class_proof=unique_proof,
        irreducible_no_channel_reason=no_channel_reason,
        conclusion=conclusion,
        claim_bearing=True,
    )


def build_nonclaim_unresolved(
    *,
    case_id: str,
    visible_state_hash: str,
    projection_hash: str,
    worlds_examined: int,
    compatible_space_size: int,
    termination_status: str,
) -> AmbiguityCertificate:
    """Record incomplete work without making uniqueness or ambiguity claims."""

    if termination_status not in {"timeout", "unknown", "incomplete", "sampled"}:
        raise AmbiguityCertificateError("nonclaim termination status is invalid")
    payload = {
        "case_id": case_id,
        "visible_state_hash": visible_state_hash,
        "projection_hash": projection_hash,
        "termination_status": termination_status,
        "worlds_examined": worlds_examined,
        "compatible_space_size": compatible_space_size,
    }
    proof_hash = canonical_hash(payload)
    return AmbiguityCertificate(
        schema_version="1.0",
        certificate_id=f"ambiguity_{canonical_hash(payload)}",
        case_id=case_id,
        visible_state_hash=visible_state_hash,
        projection_hash=projection_hash,
        compatible_classes=(),
        witnesses=(),
        permitted_channels=(),
        available_channels=(),
        unavailable_channels=(),
        exhausted_channels=(),
        proof_method=termination_status,
        solver_name="none",
        solver_version="none",
        solver_configuration="nonclaim",
        proof_hash=proof_hash,
        completeness_status=termination_status,
        enumerated_worlds=worlds_examined,
        compatible_space_size=compatible_space_size,
        unique_class_proof=None,
        irreducible_no_channel_reason=None,
        conclusion="unresolved_nonclaim",
        claim_bearing=False,
    )


def verify_certificate(
    certificate: AmbiguityCertificate,
    proof_worlds: tuple[CompatibleWorld, ...],
) -> bool:
    """Independently recompute the proof, witnesses, channel state, and conclusion."""

    if certificate.schema_version != "1.0":
        raise AmbiguityCertificateError("certificate schema_version must be 1.0")
    if not certificate.claim_bearing:
        if (
            certificate.completeness_status == "complete"
            or certificate.compatible_classes
            or certificate.witnesses
            or certificate.unique_class_proof is not None
            or certificate.irreducible_no_channel_reason is not None
            or certificate.conclusion != "unresolved_nonclaim"
        ):
            raise AmbiguityCertificateError("nonclaim certificate contains a claim")
        nonclaim_payload = {
            "case_id": certificate.case_id,
            "visible_state_hash": certificate.visible_state_hash,
            "projection_hash": certificate.projection_hash,
            "termination_status": certificate.completeness_status,
            "worlds_examined": certificate.enumerated_worlds,
            "compatible_space_size": certificate.compatible_space_size,
        }
        expected_nonclaim_hash = canonical_hash(nonclaim_payload)
        if certificate.proof_hash != expected_nonclaim_hash:
            raise AmbiguityCertificateError("nonclaim evidence hash is invalid")
        if certificate.certificate_id != f"ambiguity_{expected_nonclaim_hash}":
            raise AmbiguityCertificateError("nonclaim certificate identity is invalid")
        return True
    if certificate.proof_method not in CLAIM_PROOF_METHODS:
        raise AmbiguityCertificateError("claim uses an inadmissible proof method")
    if certificate.completeness_status != "complete":
        raise AmbiguityCertificateError("claim-bearing proof is incomplete")
    ordered = tuple(sorted(proof_worlds, key=lambda world: world.world_id))
    if (
        len(ordered) != certificate.enumerated_worlds
        or len(ordered) != certificate.compatible_space_size
        or len({world.world_id for world in ordered}) != len(ordered)
    ):
        raise AmbiguityCertificateError("proof world denominator is incomplete")
    _channel_partition(
        certificate.permitted_channels,
        certificate.available_channels,
        certificate.unavailable_channels,
        certificate.exhausted_channels,
    )
    expected_classes = tuple(
        sorted(
            {world.authorization for world in ordered},
            key=lambda item: item.value,
        )
    )
    if certificate.compatible_classes != expected_classes:
        raise AmbiguityCertificateError("compatible authorization classes do not match proof")
    for authorization in expected_classes:
        candidates = [
            world
            for world in ordered
            if world.authorization is authorization
        ]
        if not any(
            witness.authorization is authorization
            and witness.world_id == world.world_id
            and witness.facts_hash == world.facts_hash
            for witness in certificate.witnesses
            for world in candidates
        ):
            raise AmbiguityCertificateError("a compatible class lacks a valid witness")
    if len(certificate.witnesses) != len(expected_classes):
        raise AmbiguityCertificateError("certificate must contain one witness per class")
    recomputed_hash = canonical_hash(
        _proof_payload(
            certificate.case_id,
            certificate.visible_state_hash,
            certificate.projection_hash,
            certificate.proof_method,
            certificate.solver_name,
            certificate.solver_version,
            certificate.solver_configuration,
            certificate.compatible_space_size,
            ordered,
        )
    )
    if recomputed_hash != certificate.proof_hash:
        raise AmbiguityCertificateError("proof hash does not match proof worlds")
    if len(expected_classes) == 1:
        expected_conclusion = "resolvable_unique"
        if certificate.unique_class_proof is None:
            raise AmbiguityCertificateError("unique conclusion lacks its proof statement")
        if certificate.irreducible_no_channel_reason is not None:
            raise AmbiguityCertificateError("unique conclusion has an irreducibility claim")
    elif certificate.available_channels:
        expected_conclusion = "ambiguity_resolution_available"
        if (
            certificate.unique_class_proof is not None
            or certificate.irreducible_no_channel_reason is not None
        ):
            raise AmbiguityCertificateError("reducible ambiguity has a terminal claim")
    else:
        expected_conclusion = "irreducibly_ambiguous_escalate"
        if certificate.irreducible_no_channel_reason is None:
            raise AmbiguityCertificateError("irreducibility lacks a no-channel reason")
        if certificate.unique_class_proof is not None:
            raise AmbiguityCertificateError("irreducibility has a uniqueness claim")
    if certificate.conclusion != expected_conclusion:
        raise AmbiguityCertificateError("certificate conclusion is inconsistent")
    expected_identity = canonical_hash(
        {
            "case_id": certificate.case_id,
            "visible_state_hash": certificate.visible_state_hash,
            "projection_hash": certificate.projection_hash,
            "proof_hash": certificate.proof_hash,
            "conclusion": certificate.conclusion,
        }
    )
    if certificate.certificate_id != f"ambiguity_{expected_identity}":
        raise AmbiguityCertificateError("certificate identity is not content-derived")
    return True
