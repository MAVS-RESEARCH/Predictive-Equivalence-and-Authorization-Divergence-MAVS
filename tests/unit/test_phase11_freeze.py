from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pead.phase11.contracts import Phase11ContractError, canonical_bytes, verify_signed_mapping


class Phase11FreezeTests(unittest.TestCase):
    def _signed(self) -> dict[str, object]:
        private = Ed25519PrivateKey.generate()
        public = private.public_key().public_bytes_raw()
        value: dict[str, object] = {"freeze_id": "fixture", "files": 3}
        value["signature"] = {
            "algorithm": "Ed25519",
            "public_key_b64": base64.b64encode(public).decode("ascii"),
            "signature_b64": base64.b64encode(private.sign(canonical_bytes(value))).decode("ascii"),
        }
        return value

    def test_valid_signature_passes(self) -> None:
        verify_signed_mapping(self._signed())

    def test_tampered_freeze_fails(self) -> None:
        value = self._signed()
        value["files"] = 4
        with self.assertRaises(Phase11ContractError):
            verify_signed_mapping(value)

    def test_private_key_is_not_required_for_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "freeze.json"
            self.assertFalse(path.exists())
            verify_signed_mapping(self._signed())
