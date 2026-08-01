from __future__ import annotations

import copy
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pead.custody.contract import CustodyContractError, canonical_bytes, sha256_bytes, sign_mapping, verify_signature
from pead.custody.events import ZERO_HASH, create_signed_event, verify_event_log


class CustodyContractV3Tests(unittest.TestCase):
    def test_signature_round_trip_and_unknown_envelope_field_rejection(self) -> None:
        key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
        identity = sha256_bytes(key.public_key().public_bytes_raw())
        signed = sign_mapping({"value": 7}, key, identity)
        self.assertEqual(verify_signature(signed, expected_signer=identity), identity)
        invalid = copy.deepcopy(signed)
        invalid["signature"]["unknown"] = True
        with self.assertRaises(CustodyContractError):
            verify_signature(invalid, expected_signer=identity)

    def test_event_sequence_is_signed_from_genesis_and_reorder_fails(self) -> None:
        key = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32))))
        identity = sha256_bytes(key.public_key().public_bytes_raw())
        first = create_signed_event(
            study_version="study", preseal_id="preseal", sequence=1, event_id="e1", action="genesis", verdict="record",
            details={"x": 1}, previous_event_sha256=ZERO_HASH, private_key=key, signer_identity=identity,
            timestamp_utc="2026-01-01T00:00:01Z",
        )
        second = create_signed_event(
            study_version="study", preseal_id="preseal", sequence=2, event_id="e2", action="append", verdict="record",
            details={"x": 2}, previous_event_sha256=first["event_sha256"], private_key=key, signer_identity=identity,
            timestamp_utc="2026-01-01T00:00:02Z",
        )
        self.assertEqual(verify_event_log([first, second], study_version="study", preseal_id="preseal", expected_signer_identity=identity)["unsigned_events"], 0)
        with self.assertRaises(CustodyContractError):
            verify_event_log([second, first], study_version="study", preseal_id="preseal", expected_signer_identity=identity)

    def test_canonicalization_is_deterministic(self) -> None:
        self.assertEqual(canonical_bytes({"b": 1, "a": 2}), b'{"a":2,"b":1}')
