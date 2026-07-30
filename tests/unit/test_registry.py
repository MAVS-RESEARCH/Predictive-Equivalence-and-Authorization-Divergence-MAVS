from __future__ import annotations

import copy
import unittest
from pathlib import Path

import yaml

from pead.core.diagnostic_registry import (
    load_diagnostic_registry,
    scope_contract_from_mapping,
)
from pead.core.registry import FrozenRegistry, RegistryValidationError
from pead.core.requirement_registry import (
    load_requirement_registry,
    requirement_entry_from_mapping,
)


class TypedRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parents[2]

    def test_committed_registries_are_complete_and_versioned(self) -> None:
        diagnostics = load_diagnostic_registry(self.root)
        requirements = load_requirement_registry(self.root)
        self.assertEqual(diagnostics.manifest().entry_count, 7)
        self.assertEqual(requirements.manifest().entry_count, 789)
        self.assertTrue(all(entry.version for entry in diagnostics.entries.values()))
        self.assertTrue(
            all(entry.files and entry.tests for entry in requirements.entries.values())
        )

    def test_duplicate_registry_identity_is_rejected(self) -> None:
        entry = next(iter(load_diagnostic_registry(self.root).entries.values()))
        with self.assertRaises(RegistryValidationError):
            FrozenRegistry(
                registry_id="duplicate-test",
                entries=(entry, entry),
                identity=lambda value: value.diagnostic_id,
            )

    def test_missing_scope_authority_version_or_generator_is_rejected(self) -> None:
        data = yaml.safe_load(
            (self.root / "configs" / "diagnostics" / "ds_cf_zc.yaml").read_text(
                encoding="utf-8"
            )
        )
        mutations = (
            ("applicable_context",),
            ("maximum_authority",),
            ("version",),
            ("generators", "boundary"),
        )
        for path in mutations:
            mutated = copy.deepcopy(data)
            if len(path) == 1:
                mutated.pop(path[0])
            else:
                mutated[path[0]].pop(path[1])
            with self.subTest(path=path):
                with self.assertRaises(RegistryValidationError):
                    scope_contract_from_mapping(mutated)
        for key, value in (
            ("schema_version", "2.0"),
            ("maximum_authority", "unregistered-authority"),
        ):
            mutated = copy.deepcopy(data)
            mutated[key] = value
            with self.subTest(key=key, value=value):
                with self.assertRaises(RegistryValidationError):
                    scope_contract_from_mapping(mutated)

    def test_requirement_missing_traceability_is_rejected(self) -> None:
        data = yaml.safe_load(
            (
                self.root
                / "configs"
                / "requirements"
                / "pead_v1_requirements.yaml"
            ).read_text(encoding="utf-8")
        )["requirements"][0]
        for key in (
            "phases",
            "files",
            "tests",
            "produced_artifact",
            "release_failure_condition",
            "affected_claims",
        ):
            mutated = copy.deepcopy(data)
            mutated[key] = [] if isinstance(mutated[key], list) else ""
            with self.subTest(key=key):
                with self.assertRaises(RegistryValidationError):
                    requirement_entry_from_mapping(mutated)


if __name__ == "__main__":
    unittest.main()
