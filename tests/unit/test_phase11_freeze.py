"""Unit tests for Phase 11 signatures, inventories, and lineage controls."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pead.custody.contract import canonical_bytes
from pead.phase11.contracts import Phase11ContractError, assert_lineage, inventory_rows, verify_file_inventory, verify_signed_mapping
from pead.phase11.materialize import _module


class Phase11FreezeTests(unittest.TestCase):
    def _signed(self) -> dict[str, object]:
        private = Ed25519PrivateKey.generate()
        public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        signer = hashlib.sha256(public).hexdigest()
        value: dict[str, object] = {"study_version": "pead-study-v3", "preseal_id": "phase9a-preseal-v3", "signer_identity": signer}
        value["signature"] = {"algorithm": "Ed25519", "public_key_b64": base64.b64encode(public).decode(), "signature_b64": base64.b64encode(private.sign(canonical_bytes(value))).decode(), "signer_identity": signer}
        return value

    def test_signature_and_lineage(self) -> None:
        value = self._signed()
        verify_signed_mapping(value)
        assert_lineage(value)
        tampered = copy.deepcopy(value)
        tampered["study_version"] = "pead-study-v2"
        with self.assertRaises(Phase11ContractError):
            verify_signed_mapping(tampered)

    def test_inventory_is_size_and_hash_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "frozen.txt"
            path.write_text("registered\n", encoding="utf-8")
            rows = inventory_rows({"frozen.txt": hashlib.sha256(path.read_bytes()).hexdigest()}, root)
            verify_file_inventory(root, rows)
            path.write_text("changed\n", encoding="utf-8")
            with self.assertRaises(Phase11ContractError):
                verify_file_inventory(root, rows)

    def test_authoritative_freeze_when_present(self) -> None:
        root = Path(__file__).resolve().parents[2]
        path = root / "manifests/freeze_manifest.json"
        if not path.is_file():
            self.skipTest("authoritative freeze is created after the pre-freeze test stage")
        value = json.loads(path.read_text(encoding="utf-8"))
        verify_signed_mapping(value)
        verify_file_inventory(root, value["frozen_file_inventory"])

    def test_custody_module_registration_supports_dataclasses(self) -> None:
        module = _module("phase11_dataclass_contract_probe", b"from dataclasses import dataclass\n@dataclass\nclass Probe:\n    value: int\n", "<custody>/probe.py")
        self.assertEqual(module.Probe(7).value, 7)


if __name__ == "__main__":
    unittest.main()
