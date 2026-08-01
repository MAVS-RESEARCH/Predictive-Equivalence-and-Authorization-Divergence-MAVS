"""Unit coverage for complete Phase 10 bank materialization contracts."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from pead.phase10.banks import ROLE_DIRECTORY, ROLES, load_open_bank

ROOT = Path(__file__).parents[2]


class Phase10BankTests(unittest.TestCase):
    def test_phase10_roles_are_complete_and_atomic(self) -> None:
        case_sets = []
        group_sets = []
        for role in ROLES:
            bank = load_open_bank(ROOT, role)
            manifest = json.loads((ROOT / ROLE_DIRECTORY[role] / "bank_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(bank.labels), manifest["case_rows"])
            self.assertEqual(len(set(int(value) for value in bank.group_ids)), manifest["atomic_groups"])
            case_sets.append(set(int(value) for value in bank.case_ids))
            group_sets.append(set(int(value) for value in bank.group_ids))
        self.assertTrue(all(not case_sets[left] & case_sets[right] for left in range(len(ROLES)) for right in range(left + 1, len(ROLES))))
        self.assertTrue(all(not group_sets[left] & group_sets[right] for left in range(len(ROLES)) for right in range(left + 1, len(ROLES))))

    def test_exact_pairs_preserve_predictive_bytes(self) -> None:
        for role in ROLES:
            bank = load_open_bank(ROOT, role)
            groups = {}
            for index in np.flatnonzero(bank.tracks == 0):
                groups.setdefault(int(bank.group_ids[index]), []).append(int(index))
            self.assertTrue(groups)
            self.assertTrue(all(len(rows) == 2 and np.array_equal(bank.p_features[rows[0]], bank.p_features[rows[1]]) for rows in groups.values()))
