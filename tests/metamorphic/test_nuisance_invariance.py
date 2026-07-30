"""Metamorphic tests for irrelevant and surface nuisance interventions."""

from __future__ import annotations

import unittest
from pathlib import Path

from pead.core.hashing import canonical_hash
from pead.labels.evaluator_dsl import evaluate_policy
from pead.labels.parser import load_policy
from pead.tracks.exact import (
    base_latent_facts,
    base_predictive_parents,
    serialize_latent_facts,
)
from pead.world.generator_primary import generate_world
from pead.world.interventions import LatentVariant, apply_intervention
from pead.world.nuisance import NUISANCE_VARIANTS
from pead.world.schema import WorldRequest


REPO_ROOT = Path(__file__).resolve().parents[2]


class NuisanceInvarianceTests(unittest.TestCase):
    def test_all_nuisance_variants_preserve_predictive_state_and_label(self) -> None:
        predictive = base_predictive_parents()
        facts, _ = apply_intervention(
            mechanism_id="M01",
            variant=LatentVariant.PERMITTED,
            latent_facts=base_latent_facts(),
            predictive_parents=predictive,
            intervention_id="metamorphic-M01",
        )
        policy = load_policy(
            REPO_ROOT / "configs/policies/deploy_authorized_v1.yaml"
        )
        predictive_hashes: set[str] = set()
        labels = set()
        surface_hashes: set[str] = set()
        for variant in NUISANCE_VARIANTS:
            request = WorldRequest(
                schema_version="1.0",
                request_id=f"nuisance-{variant}",
                domain_id="D1",
                mechanism_id="M01",
                template_family_id="nuisance-template",
                latent_family_id="nuisance-latent",
                sequence_lineage_id="nuisance-singleton-sequence",
                intervention_lineage_id="nuisance-intervention",
                provenance_lineage_id="nuisance-provenance",
                predictive_parents=predictive,
                latent_facts=facts,
                nuisance_state={"variant": variant},
            )
            world = generate_world(request)
            predictive_hashes.add(world.predictive_hash)
            labels.add(
                evaluate_policy(
                    policy,
                    serialize_latent_facts(world.latent_facts),
                ).label
            )
            surface_hashes.add(canonical_hash(world.surface))
        self.assertEqual(len(predictive_hashes), 1)
        self.assertEqual(len(labels), 1)
        self.assertGreaterEqual(len(surface_hashes), 5)


if __name__ == "__main__":
    unittest.main()
