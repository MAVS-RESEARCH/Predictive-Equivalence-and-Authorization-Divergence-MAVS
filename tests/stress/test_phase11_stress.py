from __future__ import annotations

import copy
import unittest

from pead.phase11.contracts import Phase11ContractError, verify_materialization_precommit


class Phase11StressTests(unittest.TestCase):
    def _complete(self) -> dict[str, object]:
        allocation = "a" * 64
        return {
            "allocation_sha256": allocation,
            "bank_counts": {"structural": 100, "domains": 100, "final_blind": 100},
            "content_plaintext_sha256": "b" * 64,
            "label_plaintext_sha256": "c" * 64,
            "seed_selection_sha256": "d" * 64,
            "packages": [
                {"role": role, "plaintext_sha256": str(index) * 64, "record_count": 300, "allocation_sha256": allocation}
                for index, role in enumerate(("content", "labels", "seeds"), start=1)
            ],
        }

    def test_every_materialization_field_fails_closed_when_removed(self) -> None:
        required = ("allocation_sha256", "bank_counts", "content_plaintext_sha256", "label_plaintext_sha256", "seed_selection_sha256")
        for field in required:
            with self.subTest(field=field):
                value = self._complete()
                del value[field]
                with self.assertRaises(Phase11ContractError):
                    verify_materialization_precommit(value, "a" * 64)

    def test_every_package_field_fails_closed_when_removed(self) -> None:
        for package_index in range(3):
            for field in ("plaintext_sha256", "record_count", "allocation_sha256"):
                with self.subTest(package_index=package_index, field=field):
                    value = copy.deepcopy(self._complete())
                    del value["packages"][package_index][field]
                    with self.assertRaises(Phase11ContractError):
                        verify_materialization_precommit(value, "a" * 64)

    def test_zero_and_negative_counts_fail_closed(self) -> None:
        for count in (0, -1):
            value = self._complete()
            value["packages"][0]["record_count"] = count
            with self.assertRaises(Phase11ContractError):
                verify_materialization_precommit(value, "a" * 64)
