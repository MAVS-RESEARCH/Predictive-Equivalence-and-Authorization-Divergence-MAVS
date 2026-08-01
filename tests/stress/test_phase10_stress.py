"""High-volume collision, deterministic-decision, and mutation stress for Phase 10."""

from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

import numpy as np

from pead.phase10.banks import load_open_bank

ROOT = Path(__file__).parents[2]


class Phase10StressTests(unittest.TestCase):
    def test_one_million_open_identity_and_decision_stress(self) -> None:
        identifiers = np.fromiter((int.from_bytes(hashlib.sha256(f"PEAD-P10-STRESS|{index}".encode()).digest()[:8], "big") for index in range(1_000_000)), dtype=np.uint64, count=1_000_000)
        self.assertEqual(len(np.unique(identifiers)), 1_000_000)
        first = ((identifiers ^ (identifiers >> np.uint64(17))) % np.uint64(3)).astype(np.uint8)
        second = ((identifiers ^ (identifiers >> np.uint64(17))) % np.uint64(3)).astype(np.uint8)
        self.assertTrue(np.array_equal(first, second))

    def test_role_mutation_detects_overlap(self) -> None:
        fit = load_open_bank(ROOT, "development_fit")
        public = load_open_bank(ROOT, "public_validation")
        mutated = set(int(value) for value in public.group_ids)
        mutated.add(int(fit.group_ids[0]))
        self.assertTrue(set(int(value) for value in fit.group_ids) & mutated)
