"""Exact predictive-equivalence twin allocation, construction, and lower bounds."""

from __future__ import annotations

import copy
import json
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

from pead.core.hashing import canonical_bytes, canonical_hash
from pead.core.types import AuthorizationAction
from pead.labels.ambiguity import (
    AmbiguityCertificate,
    CompatibleWorld,
    build_exact_certificate,
    verify_certificate,
)
from pead.labels.evaluator_dsl import evaluate_policy
from pead.labels.evaluator_reference import evaluate_reference
from pead.labels.parser import load_policy
from pead.labels.reasons import LabelEvaluation, quarantine_disagreement
from pead.phase3.allocation import load_validation_manifest
from pead.world.generator_primary import generate_world
from pead.world.generator_reference import generate_world_reference
from pead.world.interventions import LatentVariant, apply_intervention
from pead.world.mechanisms import MECHANISM_BY_ID
from pead.world.nuisance import nuisance_assignment
from pead.world.schema import (
    GeneratedWorld,
    InterventionProof,
    WorldRequest,
    WorldSchemaError,
)


class ExactTrackError(ValueError):
    """Raised when an exact allocation or pair violates a hard release gate."""


@dataclass(frozen=True)
class ExactAllocation:
    domain_id: str
    domain_pair_index: int
    subbank: str
    mechanism_id: str
    orientation: str
    left_expected: AuthorizationAction
    right_expected: AuthorizationAction
    complexity: str
    interacting_facts: int
    template_family_id: str
    latent_family_id: str
    sequence_lineage_id: str
    intervention_lineage_id: str
    provenance_lineage_id: str
    atomic_group_id: str
    split_id: str


@dataclass(frozen=True)
class ExactTwinPair:
    schema_version: str
    pair_id: str
    allocation: ExactAllocation
    left: GeneratedWorld
    right: GeneratedWorld
    left_evaluation: LabelEvaluation
    right_evaluation: LabelEvaluation
    intervention_proof: InterventionProof
    ambiguity_certificates: tuple[AmbiguityCertificate, ...]
    predictive_field_equal: bool
    predictive_byte_equal: bool
    primary_reference_generation_agreement: bool

    @property
    def predictive_equivalence_index(self) -> int:
        return int(self.predictive_field_equal and self.predictive_byte_equal)

    @property
    def authorization_divergence_index(self) -> int:
        return int(self.left_evaluation.label is not self.right_evaluation.label)


@dataclass(frozen=True)
class LowerBoundResult:
    evaluator: str
    pair_count: int
    expected_terminal_errors: float
    pair_error_rate: float
    coverage: float


@lru_cache(maxsize=4)
def _load_deploy_policy(policy_path: str):
    return load_policy(Path(policy_path))


def base_predictive_parents() -> dict[str, Any]:
    return {
        "shared_representation": [0.25, -0.5, 0.75, 0.125],
        "specialist_outputs": [0.8, 0.8, 0.8],
        "signed_support": [1.0, 1.0, 1.0],
        "predicted_label": "stable-task-class",
        "confidence": 0.8,
        "uncertainty": 0.2,
        "agreement": ["specialist-a", "specialist-b", "specialist-c"],
        "calibration": {
            "nodes": [{"id": "calibration-root"}, {"id": "calibration-leaf"}],
            "edges": [
                {
                    "source": "calibration-root",
                    "target": "calibration-leaf",
                    "edge_type": "calibrates",
                }
            ],
        },
        "candidate_action": {
            "type": "deploy_patch",
            "environment": "production",
            "artifact_id": "patch-stable",
        },
    }


def base_latent_facts() -> dict[str, Any]:
    return {
        "action": {
            "type": "deploy_patch",
            "environment": "production",
            "rollback_available": True,
        },
        "actor": {"permissions": ["production.deploy"]},
        "policy": {
            "change_control": {
                "active": True,
                "prohibited": False,
                "validity": {
                    "valid_from": "2026-01-01T00:00:00+00:00",
                    "valid_until": "2026-12-31T23:59:59+00:00",
                },
            }
        },
        "provenance": {
            "compromised": False,
            "sources": [
                {"source_id": "source-a", "independent": True},
                {"source_id": "source-b", "independent": True},
            ],
        },
        "consequence": {"impact_tier": 3},
        "evidence": {
            "provenance_status": "verified",
            "resolution_available": True,
        },
        "decision_time": "2026-06-01T12:00:00+00:00",
        "dependency_graph": {
            "nodes": [{"id": "source-a"}, {"id": "source-b"}],
            "edges": [
                {
                    "source": "source-a",
                    "target": "source-b",
                    "edge_type": "independent",
                }
            ],
        },
        "counterfactual_views": {"fragility": "stable", "permitted": True},
        "nuisance": {
            "scope_probe": "inside_registered_scope",
            "variant": "canonical",
            "nonce": "baseline",
        },
    }


def _same_label_counts(domain_index: int) -> dict[AuthorizationAction, int]:
    if domain_index < 3:
        counts = (66, 67, 267)
    elif domain_index < 6:
        counts = (67, 66, 267)
    else:
        counts = (67, 67, 266)
    return dict(
        zip(
            (
                AuthorizationAction.ACCEPT,
                AuthorizationAction.REJECT,
                AuthorizationAction.ESCALATE,
            ),
            counts,
        )
    )


def _mechanism_assignments() -> dict[str, list[str]]:
    capacities = {"I-A": 800, "I-B": 400, "I-C": 400, "I-N": 400}
    remaining = {
        **{f"M{index:02d}": 167 for index in range(1, 9)},
        **{f"M{index:02d}": 166 for index in range(9, 13)},
    }
    result = {subbank: [] for subbank in capacities}
    result["I-N"].extend(["M11"] * remaining["M11"])
    remaining["M11"] = 0
    for subbank in ("I-A", "I-B", "I-C", "I-N"):
        required = capacities[subbank] - len(result[subbank])
        for position in range(required):
            candidates = [
                mechanism_id
                for mechanism_id, quota in remaining.items()
                if quota > 0
                and subbank
                in MECHANISM_BY_ID[mechanism_id].permitted_subbanks
            ]
            if not candidates:
                raise ExactTrackError("mechanism allocation exhausted prematurely")
            rotation = position % len(candidates)
            ordered = sorted(candidates)
            mechanism_id = max(
                ordered,
                key=lambda item: (
                    remaining[item],
                    -((ordered.index(item) - rotation) % len(ordered)),
                ),
            )
            result[subbank].append(mechanism_id)
            remaining[mechanism_id] -= 1
    if any(remaining.values()):
        raise ExactTrackError(f"mechanism allocation has remainder: {remaining}")
    return result


def _divergent_labels(
    subbank: str,
    position: int,
) -> tuple[str, AuthorizationAction, AuthorizationAction]:
    forward = position % 2 == 0
    pairs = {
        "I-A": (AuthorizationAction.ACCEPT, AuthorizationAction.REJECT),
        "I-B": (AuthorizationAction.ACCEPT, AuthorizationAction.ESCALATE),
        "I-C": (AuthorizationAction.REJECT, AuthorizationAction.ESCALATE),
    }
    left, right = pairs[subbank]
    return (
        "forward" if forward else "reverse",
        left if forward else right,
        right if forward else left,
    )


def _split_for_group(atomic_group_id: str) -> str:
    roles = (
        "development_fit",
        "development_selection",
        "calibration_fit",
        "calibration_policy",
        "public_validation",
    )
    return roles[int(atomic_group_id.removeprefix("group_")[:8], 16) % len(roles)]


def iter_exact_allocations(
    validation_manifest: Mapping[str, Any],
) -> Iterator[ExactAllocation]:
    if validation_manifest["exact"]["global_pairs"] != 16_000:
        raise ExactTrackError("validation manifest exact denominator is invalid")
    mechanisms = _mechanism_assignments()
    for domain_index, domain_id in enumerate(validation_manifest["domains"]):
        same_labels = [
            label
            for label, count in _same_label_counts(domain_index).items()
            for _ in range(count)
        ]
        domain_position = 0
        for subbank in ("I-A", "I-B", "I-C", "I-N"):
            for position, mechanism_id in enumerate(mechanisms[subbank]):
                if subbank == "I-N":
                    left_expected = right_expected = same_labels[position]
                    orientation = "same"
                else:
                    orientation, left_expected, right_expected = _divergent_labels(
                        subbank, position
                    )
                complexity = "simple" if domain_position < 600 else "compositional"
                interacting_facts = (
                    1
                    if complexity == "simple"
                    else 3
                    if domain_position < 1_400
                    else 2
                )
                template_family = f"{domain_id}-template-{domain_position:04d}"
                latent_family = f"{domain_id}-latent-{domain_position:04d}"
                sequence_lineage = (
                    f"{domain_id}-exact-singleton-sequence-{domain_position:04d}"
                )
                intervention_lineage = (
                    f"{domain_id}-{mechanism_id}-intervention-{domain_position:04d}"
                )
                provenance_lineage = (
                    f"{domain_id}-provenance-{domain_position:04d}"
                )
                group_payload = {
                    "domain_id": domain_id,
                    "pair": domain_position,
                    "latent_family": latent_family,
                    "template_family": template_family,
                    "sequence_lineage": sequence_lineage,
                    "intervention_lineage": intervention_lineage,
                    "provenance_lineage": provenance_lineage,
                }
                atomic_group_id = f"group_{canonical_hash(group_payload)}"
                yield ExactAllocation(
                    domain_id=domain_id,
                    domain_pair_index=domain_position,
                    subbank=subbank,
                    mechanism_id=mechanism_id,
                    orientation=orientation,
                    left_expected=left_expected,
                    right_expected=right_expected,
                    complexity=complexity,
                    interacting_facts=interacting_facts,
                    template_family_id=template_family,
                    latent_family_id=latent_family,
                    sequence_lineage_id=sequence_lineage,
                    intervention_lineage_id=intervention_lineage,
                    provenance_lineage_id=provenance_lineage,
                    atomic_group_id=atomic_group_id,
                    split_id=_split_for_group(atomic_group_id),
                )
                domain_position += 1


def _variant(label: AuthorizationAction) -> LatentVariant:
    return {
        AuthorizationAction.ACCEPT: LatentVariant.PERMITTED,
        AuthorizationAction.REJECT: LatentVariant.BLOCKED,
        AuthorizationAction.ESCALATE: LatentVariant.UNRESOLVED,
    }[label]


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted((_plain(item) for item in value), key=repr)
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def serialize_latent_facts(facts: Mapping[str, Any]) -> bytes:
    return json.dumps(
        _plain(facts),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def predictive_governance_tokens(world: GeneratedWorld) -> set[str]:
    serialized = canonical_bytes(world.predictive_state).decode("utf-8").lower()
    forbidden = {
        "provenance",
        "permission",
        "policy",
        "consequence",
        "evidence",
        "authority",
        "mechanism",
        *(f"m{index:02d}" for index in range(1, 13)),
    }
    return {token for token in forbidden if token in serialized}


def _request(
    allocation: ExactAllocation,
    side: str,
    facts: Mapping[str, Any],
    predictive_parents: Mapping[str, Any],
    nuisance_variant: str,
) -> WorldRequest:
    return WorldRequest(
        schema_version="1.0",
        request_id=(
            f"{allocation.domain_id}-{allocation.domain_pair_index:04d}-{side}"
        ),
        domain_id=allocation.domain_id,
        mechanism_id=allocation.mechanism_id,
        template_family_id=allocation.template_family_id,
        latent_family_id=allocation.latent_family_id,
        sequence_lineage_id=allocation.sequence_lineage_id,
        intervention_lineage_id=allocation.intervention_lineage_id,
        provenance_lineage_id=allocation.provenance_lineage_id,
        predictive_parents=predictive_parents,
        latent_facts=facts,
        nuisance_state={"variant": nuisance_variant},
    )


def _generation_paths_agree(
    primary: GeneratedWorld,
    reference: GeneratedWorld,
) -> bool:
    return all(
        canonical_hash(left) == canonical_hash(right)
        for left, right in (
            (primary.predictive_state, reference.predictive_state),
            (primary.governance_state, reference.governance_state),
            (primary.oracle_state, reference.oracle_state),
            (primary.latent_facts, reference.latent_facts),
            (primary.surface, reference.surface),
        )
    )


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, (Mapping, MappingProxyType)):
        result: dict[str, Any] = {}
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(item, Mapping):
                result.update(_flatten(item, path))
            else:
                result[path] = item
        return result
    return {prefix: value}


def _pair_proof(
    allocation: ExactAllocation,
    left: GeneratedWorld,
    right: GeneratedWorld,
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
    changed_authorization = tuple(sorted(changed & registered))
    unauthorized = sorted(
        path
        for path in changed
        if path not in registered and not path.startswith("nuisance.")
    )
    if unauthorized:
        raise ExactTrackError(
            f"pair changes unregistered latent parents: {unauthorized}"
        )
    nuisance_only = allocation.subbank == "I-N"
    proof = InterventionProof(
        schema_version="1.0",
        mechanism_id=allocation.mechanism_id,
        intervention_id=allocation.intervention_lineage_id,
        changed_authorization_parents=changed_authorization,
        unchanged_predictive_parent_hash_before=left.predictive_hash,
        unchanged_predictive_parent_hash_after=right.predictive_hash,
        predictive_parents_byte_equal=(
            canonical_bytes(left.predictive_state)
            == canonical_bytes(right.predictive_state)
        ),
        nuisance_only=nuisance_only,
        construction_only=False,
    )
    if nuisance_only and changed_authorization:
        raise ExactTrackError("same-label control changed an authorization parent")
    return proof


def _certificate(world: GeneratedWorld, case_id: str) -> AmbiguityCertificate:
    proof_worlds = (
        CompatibleWorld(
            world_id=f"{case_id}-compatible-0",
            facts_hash=canonical_hash({"case": case_id, "state": 0}),
            authorization=AuthorizationAction.ACCEPT,
        ),
        CompatibleWorld(
            world_id=f"{case_id}-compatible-1",
            facts_hash=canonical_hash({"case": case_id, "state": 1}),
            authorization=AuthorizationAction.REJECT,
        ),
    )
    certificate = build_exact_certificate(
        case_id=case_id,
        visible_state_hash=world.predictive_hash,
        projection_hash=canonical_hash(
            {"schema": "PredictiveState-v1", "visible": world.predictive_hash}
        ),
        worlds=proof_worlds,
        compatible_space_size=2,
        permitted_channels=("registered_resolution",),
        exhausted_channels=("registered_resolution",),
    )
    if not verify_certificate(certificate, proof_worlds):
        raise ExactTrackError("ambiguity certificate verification failed")
    return certificate


def build_exact_pair(
    allocation: ExactAllocation,
    repo_root: Path,
) -> ExactTwinPair:
    predictive_parents = base_predictive_parents()
    left_base = base_latent_facts()
    right_base = base_latent_facts()
    left_variant = _variant(allocation.left_expected)
    right_variant = _variant(allocation.right_expected)
    if allocation.subbank == "I-N" and allocation.mechanism_id == "M11":
        left_base, _ = apply_intervention(
            mechanism_id="M01",
            variant=left_variant,
            latent_facts=left_base,
            predictive_parents=predictive_parents,
            intervention_id=f"{allocation.intervention_lineage_id}-background-left",
        )
        right_base, _ = apply_intervention(
            mechanism_id="M01",
            variant=right_variant,
            latent_facts=right_base,
            predictive_parents=predictive_parents,
            intervention_id=f"{allocation.intervention_lineage_id}-background-right",
        )
        left_variant = right_variant = LatentVariant.INVARIANT
    left_facts, _ = apply_intervention(
        mechanism_id=allocation.mechanism_id,
        variant=left_variant,
        latent_facts=left_base,
        predictive_parents=predictive_parents,
        intervention_id=f"{allocation.intervention_lineage_id}-left",
    )
    right_facts, _ = apply_intervention(
        mechanism_id=allocation.mechanism_id,
        variant=right_variant,
        latent_facts=right_base,
        predictive_parents=predictive_parents,
        intervention_id=f"{allocation.intervention_lineage_id}-right",
    )
    nuisance_left = nuisance_assignment(allocation.domain_pair_index * 2)
    nuisance_right = nuisance_assignment(allocation.domain_pair_index * 2 + 1)
    left_request = _request(
        allocation,
        "left",
        left_facts,
        predictive_parents,
        nuisance_left,
    )
    right_request = _request(
        allocation,
        "right",
        right_facts,
        predictive_parents,
        nuisance_right,
    )
    left = generate_world(left_request)
    right = generate_world(right_request)
    left_reference = generate_world_reference(left_request)
    right_reference = generate_world_reference(right_request)
    generation_agreement = _generation_paths_agree(
        left, left_reference
    ) and _generation_paths_agree(right, right_reference)
    if not generation_agreement:
        raise ExactTrackError("primary/reference generation paths disagree")
    policy = _load_deploy_policy(
        str(repo_root / "configs/policies/deploy_authorized_v1.yaml")
    )
    left_payload = serialize_latent_facts(left.latent_facts)
    right_payload = serialize_latent_facts(right.latent_facts)
    left_evaluation = evaluate_policy(policy, left_payload)
    right_evaluation = evaluate_policy(policy, right_payload)
    left_reference_evaluation = evaluate_reference(policy.policy_id, left_payload)
    right_reference_evaluation = evaluate_reference(policy.policy_id, right_payload)
    for side, dsl, reference in (
        ("left", left_evaluation, left_reference_evaluation),
        ("right", right_evaluation, right_reference_evaluation),
    ):
        disagreement = quarantine_disagreement(
            case_id=f"{allocation.atomic_group_id}-{side}",
            policy_id=policy.policy_id,
            dsl_result=dsl,
            reference_result=reference,
            invalidation_scope=(allocation.domain_id, allocation.subbank, "exact_bank"),
        )
        if disagreement is not None:
            raise ExactTrackError(f"dual-label disagreement on {side} world")
    if (
        left_evaluation.label is not allocation.left_expected
        or right_evaluation.label is not allocation.right_expected
    ):
        raise ExactTrackError("generated labels do not match allocation")
    field_equal = left.predictive_state == right.predictive_state
    byte_equal = canonical_bytes(left.predictive_state) == canonical_bytes(
        right.predictive_state
    )
    if not field_equal or not byte_equal:
        raise ExactTrackError("exact twins are not predictively equivalent")
    leakage_tokens = predictive_governance_tokens(
        left
    ) | predictive_governance_tokens(right)
    if leakage_tokens:
        raise ExactTrackError(
            f"exact predictive state reveals governance tokens: "
            f"{sorted(leakage_tokens)}"
        )
    if allocation.subbank != "I-N" and (
        left_evaluation.label is right_evaluation.label
    ):
        raise ExactTrackError("divergent exact subbank has invariant authorization")
    if allocation.subbank == "I-N" and (
        left_evaluation.label is not right_evaluation.label
    ):
        raise ExactTrackError("same-label exact control diverged")
    certificates = tuple(
        _certificate(world, f"{allocation.atomic_group_id}-{side}")
        for side, world, evaluation in (
            ("left", left, left_evaluation),
            ("right", right, right_evaluation),
        )
        if evaluation.label is AuthorizationAction.ESCALATE
    )
    proof = _pair_proof(allocation, left, right)
    pair_payload = {
        "allocation": allocation,
        "left_world": left.world_state.world_id,
        "right_world": right.world_state.world_id,
        "left_label_hash": left_evaluation.evaluation_hash,
        "right_label_hash": right_evaluation.evaluation_hash,
        "proof": proof,
    }
    return ExactTwinPair(
        schema_version="1.0",
        pair_id=f"pair_{canonical_hash(pair_payload)}",
        allocation=allocation,
        left=left,
        right=right,
        left_evaluation=left_evaluation,
        right_evaluation=right_evaluation,
        intervention_proof=proof,
        ambiguity_certificates=certificates,
        predictive_field_equal=field_equal,
        predictive_byte_equal=byte_equal,
        primary_reference_generation_agreement=generation_agreement,
    )


def deterministic_terminal_lower_bound(
    pairs: Sequence[ExactTwinPair],
    decision: AuthorizationAction,
) -> LowerBoundResult:
    if decision is AuthorizationAction.ESCALATE:
        raise ExactTrackError("terminal lower bound requires a covered decision")
    errors = sum(
        int(pair.left_evaluation.label is not decision)
        + int(pair.right_evaluation.label is not decision)
        for pair in pairs
    )
    return LowerBoundResult(
        evaluator=f"deterministic_{decision.value.lower()}",
        pair_count=len(pairs),
        expected_terminal_errors=float(errors),
        pair_error_rate=errors / max(2 * len(pairs), 1),
        coverage=1.0,
    )


def randomized_terminal_lower_bound(
    pairs: Sequence[ExactTwinPair],
    probabilities: Mapping[AuthorizationAction, float],
) -> LowerBoundResult:
    if set(probabilities) != {
        AuthorizationAction.ACCEPT,
        AuthorizationAction.REJECT,
    }:
        raise ExactTrackError("randomized terminal rule requires two covered classes")
    if abs(sum(probabilities.values()) - 1.0) > 1e-12:
        raise ExactTrackError("randomized terminal probabilities must sum to one")
    errors = sum(
        1.0 - probabilities.get(pair.left_evaluation.label, 0.0)
        + 1.0 - probabilities.get(pair.right_evaluation.label, 0.0)
        for pair in pairs
    )
    return LowerBoundResult(
        evaluator="randomized_terminal",
        pair_count=len(pairs),
        expected_terminal_errors=errors,
        pair_error_rate=errors / max(2 * len(pairs), 1),
        coverage=1.0,
    )


def escalate_both_lower_bound(pairs: Sequence[ExactTwinPair]) -> LowerBoundResult:
    return LowerBoundResult(
        evaluator="escalate_both",
        pair_count=len(pairs),
        expected_terminal_errors=0.0,
        pair_error_rate=0.0,
        coverage=0.0,
    )


def pair_error_coverage_frontier(
    pairs: Sequence[ExactTwinPair],
) -> tuple[LowerBoundResult, ...]:
    return (
        escalate_both_lower_bound(pairs),
        deterministic_terminal_lower_bound(pairs, AuthorizationAction.ACCEPT),
        deterministic_terminal_lower_bound(pairs, AuthorizationAction.REJECT),
        randomized_terminal_lower_bound(
            pairs,
            {
                AuthorizationAction.ACCEPT: 0.5,
                AuthorizationAction.REJECT: 0.5,
            },
        ),
    )


def allocation_counts(
    allocations: Sequence[ExactAllocation],
) -> dict[str, Any]:
    return {
        "pairs": len(allocations),
        "domains": Counter(item.domain_id for item in allocations),
        "subbanks": Counter(item.subbank for item in allocations),
        "mechanisms": {
            domain: Counter(
                item.mechanism_id
                for item in allocations
                if item.domain_id == domain
            )
            for domain in sorted({item.domain_id for item in allocations})
        },
        "orientations": Counter(
            (item.subbank, item.orientation)
            for item in allocations
            if item.subbank != "I-N"
        ),
        "complexity": Counter(item.complexity for item in allocations),
        "three_or_more_facts": sum(
            item.interacting_facts >= 3 for item in allocations
        ),
        "world_labels": Counter(
            label.value
            for item in allocations
            for label in (item.left_expected, item.right_expected)
        ),
        "splits": Counter(item.split_id for item in allocations),
        "atomic_groups": len({item.atomic_group_id for item in allocations}),
    }


def load_exact_allocations(repo_root: Path) -> tuple[ExactAllocation, ...]:
    manifest = load_validation_manifest(
        repo_root
        / "results/manifests/phase3/allocation_validation_manifest_v1.json"
    )
    return tuple(iter_exact_allocations(manifest))
