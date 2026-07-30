"""Predictive-equivalence, intervention, lineage, and split audits."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from pead.tracks.exact import ExactTwinPair
from pead.tracks.near import NearTwinPair


class EquivalenceAuditError(ValueError):
    """Raised when generated pairs violate equivalence or grouping gates."""


@dataclass
class EquivalenceAccumulator:
    exact_pairs: int = 0
    exact_pei_one: int = 0
    exact_divergent_adi_one: int = 0
    exact_same_label_adi_zero: int = 0
    near_pairs: int = 0
    near_within_epsilon: int = 0
    near_governance_leaks: int = 0
    generation_disagreements: int = 0
    atomic_groups: set[str] = field(default_factory=set)
    lineage_to_splits: dict[tuple[str, str], set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    split_pairs: Counter[str] = field(default_factory=Counter)

    def _record_group(self, allocation: Any) -> None:
        group = allocation.atomic_group_id
        if group in self.atomic_groups:
            raise EquivalenceAuditError(f"duplicate atomic group: {group}")
        self.atomic_groups.add(group)
        self.split_pairs[allocation.split_id] += 1
        for kind, lineage in (
            ("template", allocation.template_family_id),
            ("latent", allocation.latent_family_id),
            ("sequence", allocation.sequence_lineage_id),
            ("intervention", allocation.intervention_lineage_id),
            ("provenance", allocation.provenance_lineage_id),
        ):
            self.lineage_to_splits[(kind, lineage)].add(allocation.split_id)

    def observe_exact(self, pair: ExactTwinPair) -> None:
        self._record_group(pair.allocation)
        self.exact_pairs += 1
        self.exact_pei_one += pair.predictive_equivalence_index
        if pair.allocation.subbank == "I-N":
            self.exact_same_label_adi_zero += int(
                pair.authorization_divergence_index == 0
            )
        else:
            self.exact_divergent_adi_one += pair.authorization_divergence_index
        self.generation_disagreements += int(
            not pair.primary_reference_generation_agreement
        )
        if not pair.intervention_proof.predictive_parents_byte_equal:
            raise EquivalenceAuditError("exact intervention changed predictive parents")

    def observe_near(self, pair: NearTwinPair) -> None:
        self._record_group(pair.allocation)
        self.near_pairs += 1
        self.near_within_epsilon += int(
            abs(pair.distance.aggregate - pair.allocation.epsilon) <= 1e-12
        )
        self.near_governance_leaks += int(
            pair.governance_intervention_visible_in_predictive
        )
        self.generation_disagreements += int(
            not pair.primary_reference_generation_agreement
        )

    def finalize(self) -> dict[str, Any]:
        lineage_overlap = {
            f"{kind}:{lineage}": sorted(splits)
            for (kind, lineage), splits in self.lineage_to_splits.items()
            if len(splits) > 1
        }
        expected_exact_divergent = 12_800
        expected_exact_same = 3_200
        gates = {
            "exact_pairs": self.exact_pairs == 16_000,
            "exact_pei_one": self.exact_pei_one == 16_000,
            "exact_divergent_adi_one": (
                self.exact_divergent_adi_one == expected_exact_divergent
            ),
            "exact_same_label_adi_zero": (
                self.exact_same_label_adi_zero == expected_exact_same
            ),
            "near_pairs": self.near_pairs == 8_000,
            "near_within_epsilon": self.near_within_epsilon == 8_000,
            "near_governance_leaks": self.near_governance_leaks == 0,
            "generation_path_agreement": self.generation_disagreements == 0,
            "atomic_groups_unique": len(self.atomic_groups) == 24_000,
            "lineage_split_overlap_zero": not lineage_overlap,
        }
        if not all(gates.values()):
            failed = sorted(key for key, passed in gates.items() if not passed)
            raise EquivalenceAuditError(f"equivalence gates failed: {failed}")
        return {
            "schema_version": "1.0",
            "status": "pass",
            "gates": gates,
            "exact": {
                "pairs": self.exact_pairs,
                "pei_one": self.exact_pei_one,
                "divergent_adi_one": self.exact_divergent_adi_one,
                "same_label_adi_zero": self.exact_same_label_adi_zero,
            },
            "near": {
                "pairs": self.near_pairs,
                "within_frozen_epsilon": self.near_within_epsilon,
                "governance_intervention_visible_in_predictive": (
                    self.near_governance_leaks
                ),
            },
            "grouping": {
                "atomic_groups": len(self.atomic_groups),
                "split_pair_counts": dict(sorted(self.split_pairs.items())),
                "lineage_split_overlaps": lineage_overlap,
            },
            "primary_reference_generation_disagreements": (
                self.generation_disagreements
            ),
        }
