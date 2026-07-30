"""Property checks for complete, proof-bearing ambiguity certificates."""

from __future__ import annotations

import unittest
from dataclasses import replace

from pead.core.hashing import canonical_hash
from pead.core.types import AuthorizationAction
from pead.labels.ambiguity import (
    AmbiguityCertificateError,
    CompatibleWorld,
    build_exact_certificate,
    build_nonclaim_unresolved,
    verify_certificate,
)


def worlds(*labels: AuthorizationAction) -> tuple[CompatibleWorld, ...]:
    return tuple(
        CompatibleWorld(
            world_id=f"world-{index:03d}",
            facts_hash=canonical_hash({"world": index, "label": label}),
            authorization=label,
        )
        for index, label in enumerate(labels)
    )


class AmbiguityCertificatePropertyTests(unittest.TestCase):
    def test_complete_unique_certificate_is_independently_verified(self) -> None:
        proof = worlds(
            AuthorizationAction.ACCEPT,
            AuthorizationAction.ACCEPT,
            AuthorizationAction.ACCEPT,
        )
        certificate = build_exact_certificate(
            case_id="unique",
            visible_state_hash=canonical_hash({"visible": 1}),
            projection_hash=canonical_hash({"schema": 1}),
            worlds=proof,
            compatible_space_size=3,
        )
        self.assertEqual(certificate.conclusion, "resolvable_unique")
        self.assertTrue(certificate.unique_class_proof)
        self.assertTrue(verify_certificate(certificate, proof))

    def test_complete_irreducibility_requires_witnesses_and_exhausted_channels(self) -> None:
        proof = worlds(
            AuthorizationAction.ACCEPT,
            AuthorizationAction.REJECT,
            AuthorizationAction.ESCALATE,
        )
        certificate = build_exact_certificate(
            case_id="irreducible",
            visible_state_hash=canonical_hash({"visible": 2}),
            projection_hash=canonical_hash({"schema": 1}),
            worlds=proof,
            compatible_space_size=3,
            permitted_channels=("authority", "provenance"),
            unavailable_channels=("provenance",),
            exhausted_channels=("authority",),
        )
        self.assertEqual(
            certificate.conclusion,
            "irreducibly_ambiguous_escalate",
        )
        self.assertEqual(len(certificate.witnesses), 3)
        self.assertTrue(verify_certificate(certificate, proof))

    def test_available_resolution_channel_prevents_irreducibility_claim(self) -> None:
        proof = worlds(AuthorizationAction.ACCEPT, AuthorizationAction.REJECT)
        certificate = build_exact_certificate(
            case_id="reducible",
            visible_state_hash=canonical_hash({"visible": 3}),
            projection_hash=canonical_hash({"schema": 1}),
            worlds=proof,
            compatible_space_size=2,
            permitted_channels=("authority",),
            available_channels=("authority",),
        )
        self.assertEqual(
            certificate.conclusion,
            "ambiguity_resolution_available",
        )
        self.assertIsNone(certificate.irreducible_no_channel_reason)
        self.assertTrue(verify_certificate(certificate, proof))

    def test_sampling_timeout_and_unknown_cannot_be_claim_bearing(self) -> None:
        proof = worlds(AuthorizationAction.ACCEPT)
        with self.assertRaises(AmbiguityCertificateError):
            build_exact_certificate(
                case_id="sample",
                visible_state_hash="v",
                projection_hash="s",
                worlds=proof,
                compatible_space_size=1,
                proof_method="sampling",
            )
        nonclaim = build_nonclaim_unresolved(
            case_id="timeout",
            visible_state_hash="v",
            projection_hash="s",
            worlds_examined=9,
            compatible_space_size=10,
            termination_status="timeout",
        )
        self.assertFalse(nonclaim.claim_bearing)
        self.assertTrue(verify_certificate(nonclaim, ()))

    def test_tampered_certificate_and_incomplete_denominator_are_rejected(self) -> None:
        proof = worlds(AuthorizationAction.ACCEPT, AuthorizationAction.REJECT)
        with self.assertRaises(AmbiguityCertificateError):
            build_exact_certificate(
                case_id="incomplete",
                visible_state_hash="v",
                projection_hash="s",
                worlds=proof[:1],
                compatible_space_size=2,
            )
        certificate = build_exact_certificate(
            case_id="tamper",
            visible_state_hash="v",
            projection_hash="s",
            worlds=proof,
            compatible_space_size=2,
        )
        with self.assertRaises(AmbiguityCertificateError):
            verify_certificate(replace(certificate, proof_hash="0" * 64), proof)


if __name__ == "__main__":
    unittest.main()
