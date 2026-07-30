"""Frozen-epsilon near-equivalence allocation and pair construction."""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pead.core.hashing import canonical_hash
from pead.core.types import AuthorizationAction
from pead.labels.ambiguity import AmbiguityCertificate
from pead.labels.evaluator_dsl import evaluate_policy
from pead.labels.evaluator_reference import evaluate_reference
from pead.labels.reasons import LabelEvaluation, quarantine_disagreement
from pead.phase3.allocation import load_validation_manifest
from pead.tracks.distances import (
    DistanceResult,
    load_distance_registry,
    predictive_distance,
)
from pead.tracks.exact import (
    _certificate,
    _generation_paths_agree,
    _load_deploy_policy,
    _request,
    _variant,
    base_latent_facts,
    base_predictive_parents,
    predictive_governance_tokens,
    serialize_latent_facts,
)
from pead.world.generator_primary import generate_world
from pead.world.generator_reference import generate_world_reference
from pead.world.interventions import LatentVariant, apply_intervention
from pead.world.mechanisms import MECHANISM_BY_ID
from pead.world.nuisance import nuisance_assignment
from pead.world.schema import GeneratedWorld, InterventionProof


class NearTrackError(ValueError):
    """Raised when a near allocation, distance, or proof violates the registry."""


@dataclass(frozen=True)
class NearAllocation:
    domain_id: str
    epsilon_index: int
    epsilon: float
    cell_pair_index: int
    subbank: str
    mechanism_id: str
    orientation: str
    left_expected: AuthorizationAction
    right_expected: AuthorizationAction
    rotation: int
    template_family_id: str
    latent_family_id: str
    sequence_lineage_id: str
    intervention_lineage_id: str
    provenance_lineage_id: str
    atomic_group_id: str
    split_id: str

    @property
    def domain_pair_index(self) -> int:
        return self.epsilon_index * 125 + self.cell_pair_index


@dataclass(frozen=True)
class NearTwinPair:
    schema_version: str
    pair_id: str
    allocation: NearAllocation
    left: GeneratedWorld
    right: GeneratedWorld
    left_evaluation: LabelEvaluation
    right_evaluation: LabelEvaluation
    intervention_proof: InterventionProof
    ambiguity_certificates: tuple[AmbiguityCertificate, ...]
    distance: DistanceResult
    governance_intervention_visible_in_predictive: bool
    primary_reference_generation_agreement: bool


def _split(atomic_group_id: str) -> str:
    roles = (
        "development_fit",
        "development_selection",
        "calibration_fit",
        "calibration_policy",
        "public_validation",
    )
    return roles[int(atomic_group_id[-8:], 16) % len(roles)]


def _cell_labels(
    subbank: str,
    position: int,
    rotation: int,
) -> tuple[str, AuthorizationAction, AuthorizationAction]:
    if subbank == "I-N":
        allocations = (
            (17, 17, 16),
            (17, 16, 17),
            (16, 17, 17),
        )[rotation]
        same = [
            label
            for label, count in zip(
                (
                    AuthorizationAction.ACCEPT,
                    AuthorizationAction.REJECT,
                    AuthorizationAction.ESCALATE,
                ),
                allocations,
            )
            for _ in range(count)
        ]
        return "same", same[position], same[position]
    left, right = {
        "I-A": (AuthorizationAction.ACCEPT, AuthorizationAction.REJECT),
        "I-B": (AuthorizationAction.ACCEPT, AuthorizationAction.ESCALATE),
        "I-C": (AuthorizationAction.REJECT, AuthorizationAction.ESCALATE),
    }[subbank]
    if position % 2:
        return "reverse", right, left
    return "forward", left, right


def iter_near_allocations(
    validation_manifest: Mapping[str, Any],
) -> Iterator[NearAllocation]:
    if validation_manifest["near"]["global_pairs"] != 8_000:
        raise NearTrackError("validation manifest near denominator is invalid")
    epsilons = tuple(float(item) for item in validation_manifest["near"]["epsilons"])
    for domain_index, domain_id in enumerate(validation_manifest["domains"]):
        for epsilon_index, epsilon in enumerate(epsilons):
            rotation = (domain_index * len(epsilons) + epsilon_index) % 3
            cell_position = 0
            for subbank, count in (
                ("I-A", 25),
                ("I-B", 25),
                ("I-C", 25),
                ("I-N", 50),
            ):
                for position in range(count):
                    mechanism_number = (
                        domain_index * 1_000
                        + epsilon_index * 125
                        + cell_position
                    ) % 12 + 1
                    mechanism_id = f"M{mechanism_number:02d}"
                    if subbank != "I-N" and mechanism_id == "M11":
                        mechanism_id = "M12"
                    orientation, left_expected, right_expected = _cell_labels(
                        subbank,
                        position,
                        rotation,
                    )
                    template = (
                        f"{domain_id}-near-template-"
                        f"{epsilon_index:02d}-{cell_position:03d}"
                    )
                    latent = (
                        f"{domain_id}-near-latent-"
                        f"{epsilon_index:02d}-{cell_position:03d}"
                    )
                    sequence = (
                        f"{domain_id}-near-singleton-sequence-"
                        f"{epsilon_index:02d}-{cell_position:03d}"
                    )
                    intervention = (
                        f"{domain_id}-{mechanism_id}-near-"
                        f"{epsilon_index:02d}-{cell_position:03d}"
                    )
                    provenance = (
                        f"{domain_id}-near-provenance-"
                        f"{epsilon_index:02d}-{cell_position:03d}"
                    )
                    group = f"group_{canonical_hash({
                        'domain': domain_id,
                        'epsilon': epsilon_index,
                        'cell_pair': cell_position,
                        'latent': latent,
                        'template': template,
                        'sequence': sequence,
                        'intervention': intervention,
                        'provenance': provenance,
                    })}"
                    yield NearAllocation(
                        domain_id=domain_id,
                        epsilon_index=epsilon_index,
                        epsilon=epsilon,
                        cell_pair_index=cell_position,
                        subbank=subbank,
                        mechanism_id=mechanism_id,
                        orientation=orientation,
                        left_expected=left_expected,
                        right_expected=right_expected,
                        rotation=rotation,
                        template_family_id=template,
                        latent_family_id=latent,
                        sequence_lineage_id=sequence,
                        intervention_lineage_id=intervention,
                        provenance_lineage_id=provenance,
                        atomic_group_id=group,
                        split_id=_split(group),
                    )
                    cell_position += 1


def _near_predictive_parents(epsilon: float) -> tuple[dict[str, Any], dict[str, Any]]:
    left = base_predictive_parents()
    right = copy.deepcopy(left)
    right["uncertainty"] = float(left["uncertainty"]) + epsilon
    return left, right


def _facts_for_side(
    allocation: NearAllocation,
    expected: AuthorizationAction,
    predictive: Mapping[str, Any],
    side: str,
) -> dict[str, Any]:
    base = base_latent_facts()
    variant = _variant(expected)
    if allocation.subbank == "I-N" and allocation.mechanism_id == "M11":
        base, _ = apply_intervention(
            mechanism_id="M01",
            variant=variant,
            latent_facts=base,
            predictive_parents=predictive,
            intervention_id=f"{allocation.intervention_lineage_id}-background-{side}",
        )
        variant = LatentVariant.INVARIANT
    facts, _ = apply_intervention(
        mechanism_id=allocation.mechanism_id,
        variant=variant,
        latent_facts=base,
        predictive_parents=predictive,
        intervention_id=f"{allocation.intervention_lineage_id}-{side}",
    )
    return facts


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(item, Mapping):
                result.update(_flatten(item, path))
            else:
                result[path] = item
        return result
    return {prefix: value}


def _proof(
    allocation: NearAllocation,
    left: GeneratedWorld,
    right: GeneratedWorld,
    base_predictive_hash: str,
) -> InterventionProof:
    left_flat = _flatten(left.latent_facts)
    right_flat = _flatten(right.latent_facts)
    changed = {
        path
        for path in left_flat.keys() | right_flat.keys()
        if canonical_hash(left_flat.get(path)) != canonical_hash(right_flat.get(path))
    }
    registered = set(
        MECHANISM_BY_ID[allocation.mechanism_id].authorization_parent_paths
    )
    authorization_changes = tuple(sorted(changed & registered))
    unauthorized = sorted(
        path
        for path in changed
        if path not in registered and not path.startswith("nuisance.")
    )
    if unauthorized:
        raise NearTrackError(
            f"near pair changes unregistered governance parents: {unauthorized}"
        )
    nuisance_only = allocation.subbank == "I-N"
    proof = InterventionProof(
        schema_version="1.0",
        mechanism_id=allocation.mechanism_id,
        intervention_id=allocation.intervention_lineage_id,
        changed_authorization_parents=authorization_changes,
        unchanged_predictive_parent_hash_before=base_predictive_hash,
        unchanged_predictive_parent_hash_after=base_predictive_hash,
        predictive_parents_byte_equal=True,
        nuisance_only=nuisance_only,
        construction_only=False,
    )
    if nuisance_only and authorization_changes:
        raise NearTrackError("near same-label control changed an authorization parent")
    return proof


def build_near_pair(
    allocation: NearAllocation,
    repo_root: Path,
) -> NearTwinPair:
    left_predictive, right_predictive = _near_predictive_parents(
        allocation.epsilon
    )
    left_facts = _facts_for_side(
        allocation,
        allocation.left_expected,
        left_predictive,
        "left",
    )
    right_facts = _facts_for_side(
        allocation,
        allocation.right_expected,
        right_predictive,
        "right",
    )
    left_request = _request(
        allocation,
        "left",
        left_facts,
        left_predictive,
        nuisance_assignment(allocation.domain_pair_index * 2),
    )
    right_request = _request(
        allocation,
        "right",
        right_facts,
        right_predictive,
        nuisance_assignment(allocation.domain_pair_index * 2 + 1),
    )
    left = generate_world(left_request)
    right = generate_world(right_request)
    left_reference = generate_world_reference(left_request)
    right_reference = generate_world_reference(right_request)
    generation_agreement = _generation_paths_agree(
        left, left_reference
    ) and _generation_paths_agree(right, right_reference)
    if not generation_agreement:
        raise NearTrackError("primary/reference near generation paths disagree")
    policy = _load_deploy_policy(
        str(repo_root / "configs/policies/deploy_authorized_v1.yaml")
    )
    left_payload = serialize_latent_facts(left.latent_facts)
    right_payload = serialize_latent_facts(right.latent_facts)
    left_evaluation = evaluate_policy(policy, left_payload)
    right_evaluation = evaluate_policy(policy, right_payload)
    references = (
        evaluate_reference(policy.policy_id, left_payload),
        evaluate_reference(policy.policy_id, right_payload),
    )
    for side, dsl, reference in (
        ("left", left_evaluation, references[0]),
        ("right", right_evaluation, references[1]),
    ):
        if quarantine_disagreement(
            case_id=f"{allocation.atomic_group_id}-{side}",
            policy_id=policy.policy_id,
            dsl_result=dsl,
            reference_result=reference,
            invalidation_scope=(allocation.domain_id, "near_bank"),
        ):
            raise NearTrackError(f"dual-label disagreement on near {side} world")
    if (
        left_evaluation.label is not allocation.left_expected
        or right_evaluation.label is not allocation.right_expected
    ):
        raise NearTrackError("near labels do not match allocation")
    registry = load_distance_registry(
        repo_root / "configs/tracks/near_distance_registry.yaml"
    )
    distance = predictive_distance(
        left.predictive_state,
        right.predictive_state,
        registry,
    )
    if abs(distance.aggregate - allocation.epsilon) > 1e-12:
        raise NearTrackError(
            f"near distance {distance.aggregate} does not equal epsilon "
            f"{allocation.epsilon}"
        )
    leakage_tokens = predictive_governance_tokens(left) | predictive_governance_tokens(
        right
    )
    certificates = tuple(
        _certificate(world, f"{allocation.atomic_group_id}-{side}")
        for side, world, evaluation in (
            ("left", left, left_evaluation),
            ("right", right, right_evaluation),
        )
        if evaluation.label is AuthorizationAction.ESCALATE
    )
    proof = _proof(
        allocation,
        left,
        right,
        canonical_hash(base_predictive_parents()),
    )
    pair_id = f"near_pair_{canonical_hash({
        'allocation': allocation,
        'left': left.world_state.world_id,
        'right': right.world_state.world_id,
        'distance': distance,
    })}"
    return NearTwinPair(
        schema_version="1.0",
        pair_id=pair_id,
        allocation=allocation,
        left=left,
        right=right,
        left_evaluation=left_evaluation,
        right_evaluation=right_evaluation,
        intervention_proof=proof,
        ambiguity_certificates=certificates,
        distance=distance,
        governance_intervention_visible_in_predictive=bool(leakage_tokens),
        primary_reference_generation_agreement=generation_agreement,
    )


def near_allocation_counts(
    allocations: tuple[NearAllocation, ...],
) -> dict[str, Any]:
    return {
        "pairs": len(allocations),
        "domains": Counter(item.domain_id for item in allocations),
        "epsilon_cells": Counter(
            (item.domain_id, item.epsilon) for item in allocations
        ),
        "cell_subbanks": Counter(
            (item.domain_id, item.epsilon, item.subbank)
            for item in allocations
        ),
        "rotations": Counter(item.rotation for item in allocations),
        "world_labels": Counter(
            label.value
            for item in allocations
            for label in (item.left_expected, item.right_expected)
        ),
        "atomic_groups": len({item.atomic_group_id for item in allocations}),
    }


def load_near_allocations(repo_root: Path) -> tuple[NearAllocation, ...]:
    manifest = load_validation_manifest(
        repo_root
        / "results/manifests/phase3/allocation_validation_manifest_v1.json"
    )
    return tuple(iter_near_allocations(manifest))
