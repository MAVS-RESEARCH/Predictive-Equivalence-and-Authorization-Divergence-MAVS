"""Cross-domain contracts, anti-triviality, and held-out isolation."""

from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

from pead.domains.base import (
    OBVIOUS_AUTHORIZATION_FIELDS,
    DomainContractError,
    universal_projection_signature,
)
from pead.domains.heldout_interface import load_heldout_contract
from pead.phase5.review import (
    REVIEWER_ID,
    audit_heldout_isolation,
    load_open_adapters,
    review_adapter,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class DomainContractIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapters = load_open_adapters(REPO_ROOT)

    def test_d1_d6_and_heldout_projection_shapes_have_parity(self) -> None:
        signatures = {
            adapter.build_case(0).projection.schema_signature
            for adapter in self.adapters
        }
        signatures.add(load_heldout_contract(REPO_ROOT).projection_signature)
        self.assertEqual(signatures, {universal_projection_signature()})

    def test_every_open_domain_meets_mechanism_and_shortcut_minima(self) -> None:
        for adapter in self.adapters:
            definition = adapter.definition
            kinds = {item.kind for item in definition.mechanisms}
            self.assertGreaterEqual(len(definition.mechanisms), 6)
            self.assertIn("composition", kinds)
            self.assertIn("ambiguity", kinds)
            self.assertGreaterEqual(len(definition.label_swaps), 2)
            self.assertGreaterEqual(len(definition.surface_transforms), 4)
            self.assertFalse(
                {field.lower() for field in definition.raw_governance_fields}
                & OBVIOUS_AUTHORIZATION_FIELDS
            )

    def test_cross_domain_graph_temporal_and_policy_minima(self) -> None:
        self.assertGreaterEqual(
            sum(adapter.definition.graph_dependent for adapter in self.adapters),
            2,
        )
        self.assertGreaterEqual(
            sum(adapter.definition.temporal_reversal for adapter in self.adapters),
            2,
        )
        self.assertGreaterEqual(
            sum(
                adapter.definition.policy_grammar_composition
                for adapter in self.adapters
            ),
            2,
        )

    def test_label_swaps_and_surface_transforms_preserve_meaning(self) -> None:
        for adapter in self.adapters:
            for mechanism_index in range(len(adapter.definition.mechanisms)):
                variants = adapter.anti_shortcut_variants(mechanism_index)
                self.assertEqual(
                    len(variants),
                    len(adapter.definition.label_swaps)
                    * len(adapter.definition.surface_transforms),
                )
                self.assertEqual(
                    len({item.latent_meaning_hash for item in variants}),
                    1,
                )
                self.assertEqual(
                    len({item.surface_hash for item in variants}),
                    len(variants),
                )

    def test_independent_reviewer_is_not_any_adapter_author(self) -> None:
        for adapter in self.adapters:
            report = review_adapter(adapter)
            self.assertNotEqual(REVIEWER_ID, adapter.definition.author_id)
            self.assertFalse(report["reviewer_authorship_overlap"])
            self.assertEqual(set(report["review_dimensions"].values()), {"pass"})

    def test_obvious_raw_governance_verdict_field_is_rejected(self) -> None:
        definition = self.adapters[0].definition
        with self.assertRaises(DomainContractError):
            replace(
                definition,
                raw_governance_fields=(
                    *definition.raw_governance_fields,
                    "is_authorized",
                ),
            )

    def test_heldout_contract_cannot_instantiate_or_reveal_content(self) -> None:
        contract = load_heldout_contract(REPO_ROOT)
        self.assertEqual(contract.placeholder_ids, ("D7", "D8"))
        self.assertTrue(contract.phase10_blocked_until_custody_sealed)
        with self.assertRaises(DomainContractError):
            contract.instantiate("D7")
        isolation = audit_heldout_isolation(REPO_ROOT)
        self.assertEqual(isolation["semantic_marker_violations"], 0)
        self.assertEqual(isolation["placeholder_location_violations"], 0)
        self.assertEqual(
            isolation["repository_exposure"],
            "interface_and_placeholder_ids_only",
        )
