"""Governance-reversal sequences with known change and restoration times."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pead.core.hashing import canonical_bytes, canonical_hash
from pead.core.types import AuthorizationAction, SequenceRecord
from pead.labels.ambiguity import AmbiguityCertificate
from pead.labels.evaluator_dsl import evaluate_policy
from pead.labels.evaluator_reference import evaluate_reference
from pead.labels.reasons import LabelEvaluation, quarantine_disagreement
from pead.phase4.allocation import load_phase4_manifest
from pead.tracks.exact import (
    _certificate,
    _generation_paths_agree,
    _load_deploy_policy,
    base_latent_facts,
    base_predictive_parents,
    predictive_governance_tokens,
    serialize_latent_facts,
)
from pead.world.generator_primary import generate_world
from pead.world.generator_reference import generate_world_reference
from pead.world.interventions import LatentVariant, apply_intervention
from pead.world.schema import GeneratedWorld, WorldRequest


class ReversalTrackError(ValueError):
    """Raised when a reversal sequence violates chronology or fidelity."""


@dataclass(frozen=True)
class ReversalFamily:
    family_id: str
    mechanism_id: str
    changed_parent: str
    adverse_action: AuthorizationAction


@dataclass(frozen=True)
class ReversalAllocation:
    domain_id: str
    domain_sequence_index: int
    family: ReversalFamily
    length: int
    change_index: int
    restoration_index: int
    atomic_group_id: str
    split_id: str
    sequence_lineage_id: str


@dataclass(frozen=True)
class ReversalStep:
    step_index: int
    timestamp: str
    phase: str
    world: GeneratedWorld
    evaluation: LabelEvaluation
    ambiguity_certificate: AmbiguityCertificate | None


@dataclass(frozen=True)
class GovernanceReversalSequence:
    schema_version: str
    allocation: ReversalAllocation
    record: SequenceRecord
    steps: tuple[ReversalStep, ...]
    change_timestamp: str
    restoration_timestamp: str
    stale_authorization_opportunities: tuple[int, ...]
    false_reversal_control_indices: tuple[int, ...]
    predictive_byte_stable: bool
    dual_label_agreement: bool
    primary_reference_generation_agreement: bool


@dataclass(frozen=True)
class ReversalControl:
    schema_version: str
    control_id: str
    domain_id: str
    kind: str
    truth_hash_before: str
    truth_hash_after: str
    expected_authorization_before: AuthorizationAction
    expected_authorization_after: AuthorizationAction
    signal_change_index: int
    atomic_group_id: str
    split_id: str


def _split(group_id: str) -> str:
    roles = (
        "development_fit",
        "development_selection",
        "calibration_fit",
        "calibration_policy",
        "public_validation",
    )
    return roles[int(group_id.removeprefix("group_")[:8], 16) % len(roles)]


def _length_and_timing(index: int) -> tuple[int, int, int]:
    if index < 100:
        return 4, 1, 3
    if index < 400:
        return 6, 2, 4
    return 8, 2, 6


def iter_reversal_allocations(
    manifest: Mapping[str, Any],
) -> Iterator[ReversalAllocation]:
    if manifest["reversal"]["canonical_sequences"] != 4_000:
        raise ReversalTrackError("reversal manifest denominator is invalid")
    families = tuple(
        ReversalFamily(
            family_id=str(item["family_id"]),
            mechanism_id=str(item["mechanism_id"]),
            changed_parent=str(item["changed_parent"]),
            adverse_action=AuthorizationAction(item["adverse_action"]),
        )
        for item in manifest["reversal"]["families"]
    )
    if len(families) != 6:
        raise ReversalTrackError("exactly six reversal families are required")
    for domain_id in manifest["domains"]:
        for sequence_index in range(500):
            length, change_index, restoration_index = _length_and_timing(
                sequence_index
            )
            family = families[sequence_index % len(families)]
            if family.family_id == "evidence_restoration":
                restoration_index = change_index
            sequence_lineage = (
                f"{domain_id}-{family.family_id}-sequence-{sequence_index:04d}"
            )
            group = f"group_{canonical_hash({
                'domain': domain_id,
                'sequence': sequence_lineage,
                'family': family.family_id,
            })}"
            yield ReversalAllocation(
                domain_id=domain_id,
                domain_sequence_index=sequence_index,
                family=family,
                length=length,
                change_index=change_index,
                restoration_index=restoration_index,
                atomic_group_id=group,
                split_id=_split(group),
                sequence_lineage_id=sequence_lineage,
            )


def iter_reversal_controls(
    manifest: Mapping[str, Any],
) -> Iterator[ReversalControl]:
    control_counts = manifest["reversal"]["controls"]
    kinds = tuple(control_counts)
    if control_counts != {
        "false_reversal": 25,
        "nuisance": 25,
        "prior_shift": 25,
        "label_permutation": 25,
    }:
        raise ReversalTrackError("signed reversal control allocation changed")
    truth_hash = canonical_hash(base_latent_facts())
    for domain_id in manifest["domains"]:
        for index in range(100):
            kind = kinds[index // 25]
            identity = {
                "domain": domain_id,
                "kind": kind,
                "index": index,
            }
            group = f"group_{canonical_hash(identity)}"
            yield ReversalControl(
                schema_version="1.0",
                control_id=f"reversal_control_{canonical_hash(identity)}",
                domain_id=domain_id,
                kind=kind,
                truth_hash_before=truth_hash,
                truth_hash_after=truth_hash,
                expected_authorization_before=AuthorizationAction.ACCEPT,
                expected_authorization_after=AuthorizationAction.ACCEPT,
                signal_change_index=2,
                atomic_group_id=group,
                split_id=_split(group),
            )


def _variant_for_step(
    allocation: ReversalAllocation,
    step_index: int,
) -> tuple[LatentVariant, str]:
    if allocation.family.family_id == "evidence_restoration":
        if step_index < allocation.change_index:
            return LatentVariant.UNRESOLVED, "pre_restoration_unresolved"
        return LatentVariant.PERMITTED, "restored"
    if allocation.change_index <= step_index < allocation.restoration_index:
        return LatentVariant.BLOCKED, "adverse"
    if step_index < allocation.change_index:
        return LatentVariant.PERMITTED, "baseline"
    return LatentVariant.PERMITTED, "recovered"


def _expected_label(
    allocation: ReversalAllocation,
    step_index: int,
) -> AuthorizationAction:
    if allocation.family.family_id == "evidence_restoration":
        return (
            AuthorizationAction.ESCALATE
            if step_index < allocation.change_index
            else AuthorizationAction.ACCEPT
        )
    if allocation.change_index <= step_index < allocation.restoration_index:
        return allocation.family.adverse_action
    return AuthorizationAction.ACCEPT


def build_reversal_sequence(
    allocation: ReversalAllocation,
    repo_root: Path,
) -> GovernanceReversalSequence:
    predictive = base_predictive_parents()
    policy = _load_deploy_policy(
        str(repo_root / "configs/policies/deploy_authorized_v1.yaml")
    )
    start = datetime(
        2026,
        6,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    ) + timedelta(days=allocation.domain_sequence_index)
    steps: list[ReversalStep] = []
    dual_agreement = True
    generator_agreement = True
    for step_index in range(allocation.length):
        variant, phase = _variant_for_step(allocation, step_index)
        facts, proof = apply_intervention(
            mechanism_id=allocation.family.mechanism_id,
            variant=variant,
            latent_facts=base_latent_facts(),
            predictive_parents=predictive,
            intervention_id=(
                f"{allocation.sequence_lineage_id}-step-{step_index:02d}"
            ),
        )
        if not proof.predictive_parents_byte_equal:
            raise ReversalTrackError("reversal changed predictive parents")
        request = WorldRequest(
            schema_version="1.0",
            request_id=f"{allocation.sequence_lineage_id}-step-{step_index:02d}",
            domain_id=allocation.domain_id,
            mechanism_id=allocation.family.mechanism_id,
            template_family_id=f"{allocation.domain_id}-reversal-template",
            latent_family_id=f"{allocation.sequence_lineage_id}-latent",
            sequence_lineage_id=allocation.sequence_lineage_id,
            intervention_lineage_id=(
                f"{allocation.sequence_lineage_id}-intervention"
            ),
            provenance_lineage_id=(
                f"{allocation.sequence_lineage_id}-provenance"
            ),
            predictive_parents=predictive,
            latent_facts=facts,
            nuisance_state={"variant": "canonical"},
        )
        world = generate_world(request)
        reference_world = generate_world_reference(request)
        generator_agreement = generator_agreement and _generation_paths_agree(
            world,
            reference_world,
        )
        if predictive_governance_tokens(world):
            raise ReversalTrackError(
                "reversal predictive state reveals governance"
            )
        payload = serialize_latent_facts(world.latent_facts)
        evaluation = evaluate_policy(policy, payload)
        reference = evaluate_reference(policy.policy_id, payload)
        disagreement = quarantine_disagreement(
            case_id=request.request_id,
            policy_id=policy.policy_id,
            dsl_result=evaluation,
            reference_result=reference,
            invalidation_scope=(
                allocation.domain_id,
                allocation.family.family_id,
                "reversal_bank",
            ),
        )
        dual_agreement = dual_agreement and disagreement is None
        expected = _expected_label(allocation, step_index)
        if evaluation.label is not expected:
            raise ReversalTrackError(
                f"unexpected reversal label at step {step_index}: "
                f"{evaluation.label.value} != {expected.value}"
            )
        timestamp = (
            start + timedelta(seconds=60 * step_index)
        ).isoformat()
        certificate = (
            _certificate(world, request.request_id)
            if evaluation.label is AuthorizationAction.ESCALATE
            else None
        )
        steps.append(
            ReversalStep(
                step_index=step_index,
                timestamp=timestamp,
                phase=phase,
                world=world,
                evaluation=evaluation,
                ambiguity_certificate=certificate,
            )
        )
    predictive_byte_stable = len(
        {canonical_bytes(step.world.predictive_state) for step in steps}
    ) == 1
    if not predictive_byte_stable or not dual_agreement or not generator_agreement:
        raise ReversalTrackError(
            "reversal generation, labels, or predictive stability failed"
        )
    reversal_indices = (
        (allocation.change_index,)
        if allocation.family.family_id == "evidence_restoration"
        else (allocation.change_index, allocation.restoration_index)
    )
    record = SequenceRecord.create(
        world_ids=tuple(step.world.world_state.world_id for step in steps),
        timestamps=tuple(step.timestamp for step in steps),
        authorization_labels=tuple(
            step.evaluation.label for step in steps
        ),
        reversal_indices=reversal_indices,
        lineage={
            "domain_id": allocation.domain_id,
            "family_id": allocation.family.family_id,
            "sequence_lineage_id": allocation.sequence_lineage_id,
            "atomic_group_id": allocation.atomic_group_id,
        },
        split_id=allocation.split_id,
    )
    stale = (
        tuple()
        if allocation.family.family_id == "evidence_restoration"
        else tuple(range(allocation.change_index, allocation.restoration_index))
    )
    return GovernanceReversalSequence(
        schema_version="1.0",
        allocation=allocation,
        record=record,
        steps=tuple(steps),
        change_timestamp=steps[allocation.change_index].timestamp,
        restoration_timestamp=steps[allocation.restoration_index].timestamp,
        stale_authorization_opportunities=stale,
        false_reversal_control_indices=(),
        predictive_byte_stable=predictive_byte_stable,
        dual_label_agreement=dual_agreement,
        primary_reference_generation_agreement=generator_agreement,
    )


def load_reversal_allocations(
    repo_root: Path,
) -> tuple[ReversalAllocation, ...]:
    manifest = load_phase4_manifest(
        repo_root / "results/manifests/phase4/phase4_validation_manifest_v1.json"
    )
    return tuple(iter_reversal_allocations(manifest))


def load_reversal_controls(repo_root: Path) -> tuple[ReversalControl, ...]:
    manifest = load_phase4_manifest(
        repo_root / "results/manifests/phase4/phase4_validation_manifest_v1.json"
    )
    return tuple(iter_reversal_controls(manifest))


def reversal_allocation_counts(
    allocations: Sequence[ReversalAllocation],
    controls: Sequence[ReversalControl],
) -> dict[str, Any]:
    return {
        "canonical_sequences": len(allocations),
        "canonical_steps": sum(item.length for item in allocations),
        "domains": Counter(item.domain_id for item in allocations),
        "lengths": Counter(item.length for item in allocations),
        "families": Counter(
            item.family.family_id for item in allocations
        ),
        "additional_controls": len(controls),
        "control_kinds": Counter(item.kind for item in controls),
        "atomic_groups": len(
            {
                *(item.atomic_group_id for item in allocations),
                *(item.atomic_group_id for item in controls),
            }
        ),
    }
