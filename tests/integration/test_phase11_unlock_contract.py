from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from pead.phase11.contracts import Phase11ContractError, sha256_file, verify_materialization_precommit
from pead.phase11.unlock import verify_custody_design_hashes


class Phase11UnlockContractTests(unittest.TestCase):
    def test_current_style_ciphertext_only_index_is_rejected(self) -> None:
        index = {"packages": [{"role": role, "sha256": role * 8} for role in ("content", "labels", "seeds")]}
        with self.assertRaisesRegex(Phase11ContractError, "lacks signed case-materialization commitments"):
            verify_materialization_precommit(index, "a" * 64)

    def test_complete_synthetic_precommit_passes(self) -> None:
        allocation_hash = "a" * 64
        packages = [
            {"role": role, "plaintext_sha256": chr(98 + index) * 64, "record_count": 10, "allocation_sha256": allocation_hash}
            for index, role in enumerate(("content", "labels", "seeds"))
        ]
        value = {
            "allocation_sha256": allocation_hash,
            "bank_counts": {"structural": 4, "domains": 2, "final_blind": 4},
            "content_plaintext_sha256": "e" * 64,
            "label_plaintext_sha256": "f" * 64,
            "seed_selection_sha256": "1" * 64,
            "packages": packages,
        }
        self.assertEqual(verify_materialization_precommit(value, allocation_hash)["status"], "pass")

    def test_allocation_substitution_is_rejected(self) -> None:
        value = {
            "allocation_sha256": "b" * 64,
            "bank_counts": {"structural": 1},
            "content_plaintext_sha256": "c" * 64,
            "label_plaintext_sha256": "d" * 64,
            "seed_selection_sha256": "e" * 64,
            "packages": [
                {"role": role, "plaintext_sha256": "f" * 64, "record_count": 1, "allocation_sha256": "b" * 64}
                for role in ("content", "labels", "seeds")
            ],
        }
        with self.assertRaisesRegex(Phase11ContractError, "allocation binding"):
            verify_materialization_precommit(value, "a" * 64)

    def test_custody_design_byte_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "design.bin"
            path.write_bytes(b"committed")
            commitment = {"design_artifacts": [{"artifact_id": "design.bin", "sha256": sha256_file(path), "bytes": path.stat().st_size}]}
            self.assertEqual(verify_custody_design_hashes(root, commitment)["verified_artifacts"], 1)
            path.write_bytes(b"mutated")
            with self.assertRaisesRegex(Phase11ContractError, "identity mismatch"):
                verify_custody_design_hashes(root, commitment)
