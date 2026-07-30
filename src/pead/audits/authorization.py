"""Authorization quota, certificate, and exact lower-bound audits."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from pead.core.types import AuthorizationAction
from pead.labels.ambiguity import CompatibleWorld, verify_certificate
from pead.tracks.exact import (
    ExactTwinPair,
    deterministic_terminal_lower_bound,
    escalate_both_lower_bound,
    pair_error_coverage_frontier,
    randomized_terminal_lower_bound,
)
from pead.tracks.near import NearTwinPair


class AuthorizationAuditError(ValueError):
    """Raised when authorization evidence violates a frozen bank gate."""


@dataclass
class AuthorizationAccumulator:
    exact_labels: Counter[str] = field(default_factory=Counter)
    near_labels: Counter[str] = field(default_factory=Counter)
    exact_subbanks: Counter[str] = field(default_factory=Counter)
    exact_domain_subbanks: Counter[tuple[str, str]] = field(default_factory=Counter)
    exact_domain_mechanisms: Counter[tuple[str, str]] = field(
        default_factory=Counter
    )
    exact_orientations: Counter[tuple[str, str, str]] = field(
        default_factory=Counter
    )
    exact_complexity: Counter[str] = field(default_factory=Counter)
    exact_three_factor: int = 0
    near_cells: Counter[tuple[str, int, str]] = field(default_factory=Counter)
    certificates: int = 0
    certificate_failures: int = 0
    exact_pairs_for_bounds: list[ExactTwinPair] = field(default_factory=list)

    def _observe_certificates(self, pair: ExactTwinPair | NearTwinPair) -> None:
        for certificate in pair.ambiguity_certificates:
            worlds = tuple(
                CompatibleWorld(
                    world_id=witness.world_id,
                    facts_hash=witness.facts_hash,
                    authorization=witness.authorization,
                )
                for witness in certificate.witnesses
            )
            self.certificates += 1
            self.certificate_failures += int(
                not verify_certificate(certificate, worlds)
            )

    def observe_exact(self, pair: ExactTwinPair) -> None:
        allocation = pair.allocation
        self.exact_pairs_for_bounds.append(pair)
        self.exact_subbanks[allocation.subbank] += 1
        self.exact_domain_subbanks[(allocation.domain_id, allocation.subbank)] += 1
        self.exact_domain_mechanisms[
            (allocation.domain_id, allocation.mechanism_id)
        ] += 1
        self.exact_orientations[
            (allocation.domain_id, allocation.subbank, allocation.orientation)
        ] += 1
        self.exact_complexity[allocation.complexity] += 1
        self.exact_three_factor += int(allocation.interacting_facts >= 3)
        for evaluation in (pair.left_evaluation, pair.right_evaluation):
            self.exact_labels[evaluation.label.value] += 1
        self._observe_certificates(pair)

    def observe_near(self, pair: NearTwinPair) -> None:
        allocation = pair.allocation
        self.near_cells[
            (allocation.domain_id, allocation.epsilon_index, allocation.subbank)
        ] += 1
        for evaluation in (pair.left_evaluation, pair.right_evaluation):
            self.near_labels[evaluation.label.value] += 1
        self._observe_certificates(pair)

    def finalize(self) -> dict[str, Any]:
        expected_mechanisms = {
            **{f"M{index:02d}": 167 for index in range(1, 9)},
            **{f"M{index:02d}": 166 for index in range(9, 13)},
        }
        quota_errors: list[str] = []
        for domain_index in range(1, 9):
            domain = f"D{domain_index}"
            for subbank, expected in (
                ("I-A", 800),
                ("I-B", 400),
                ("I-C", 400),
                ("I-N", 400),
            ):
                if self.exact_domain_subbanks[(domain, subbank)] != expected:
                    quota_errors.append(f"{domain}:{subbank}")
            for mechanism, expected in expected_mechanisms.items():
                if self.exact_domain_mechanisms[(domain, mechanism)] != expected:
                    quota_errors.append(f"{domain}:{mechanism}")
            for subbank, expected in (("I-A", 400), ("I-B", 200), ("I-C", 200)):
                for orientation in ("forward", "reverse"):
                    if (
                        self.exact_orientations[(domain, subbank, orientation)]
                        != expected
                    ):
                        quota_errors.append(
                            f"{domain}:{subbank}:{orientation}"
                        )
        for domain_index in range(1, 9):
            domain = f"D{domain_index}"
            for epsilon_index in range(8):
                for subbank, expected in (
                    ("I-A", 25),
                    ("I-B", 25),
                    ("I-C", 25),
                    ("I-N", 50),
                ):
                    if self.near_cells[(domain, epsilon_index, subbank)] != expected:
                        quota_errors.append(
                            f"{domain}:epsilon-{epsilon_index}:{subbank}"
                        )
        exact_expected = {"Accept": 10_666, "Reject": 10_666, "Escalate": 10_668}
        near_expected = {"Accept": 5_334, "Reject": 5_334, "Escalate": 5_332}
        if dict(self.exact_labels) != exact_expected:
            quota_errors.append("exact-global-labels")
        if dict(self.near_labels) != near_expected:
            quota_errors.append("near-global-labels")
        if self.exact_complexity != Counter({"compositional": 11_200, "simple": 4_800}):
            quota_errors.append("exact-complexity")
        if self.exact_three_factor != 6_400:
            quota_errors.append("exact-three-factor")
        deterministic = {
            action.value: deterministic_terminal_lower_bound(
                self.exact_pairs_for_bounds,
                action,
            )
            for action in (
                AuthorizationAction.ACCEPT,
                AuthorizationAction.REJECT,
            )
        }
        randomized = randomized_terminal_lower_bound(
            self.exact_pairs_for_bounds,
            {
                AuthorizationAction.ACCEPT: 0.5,
                AuthorizationAction.REJECT: 0.5,
            },
        )
        escalate_both = escalate_both_lower_bound(self.exact_pairs_for_bounds)
        frontier = pair_error_coverage_frontier(self.exact_pairs_for_bounds)
        if quota_errors or self.certificate_failures:
            raise AuthorizationAuditError(
                "authorization gates failed: "
                f"quota_errors={quota_errors}; "
                f"certificate_failures={self.certificate_failures}"
            )
        return {
            "schema_version": "1.0",
            "status": "pass",
            "exact_world_labels": dict(self.exact_labels),
            "near_world_labels": dict(self.near_labels),
            "exact_subbanks": dict(self.exact_subbanks),
            "exact_complexity": dict(self.exact_complexity),
            "exact_three_or_more_fact_pairs": self.exact_three_factor,
            "dual_engine_agreement": "verified_during_pair_construction",
            "ambiguity_certificates": {
                "verified": self.certificates,
                "failures": self.certificate_failures,
            },
            "predictive_only_lower_bounds": {
                "deterministic_terminal": deterministic,
                "randomized_terminal": randomized,
                "escalate_both": escalate_both,
                "pair_error_coverage_frontier": frontier,
            },
            "quota_errors": quota_errors,
        }
