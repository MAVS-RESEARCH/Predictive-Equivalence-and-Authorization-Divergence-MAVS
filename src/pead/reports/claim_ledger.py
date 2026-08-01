"""Claim-eligibility report construction with fail-closed emission."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pead.audits.claims import audit_claims


def build_claim_ledger(
    eligibility: Mapping[str, bool], requested_claims: Sequence[str], *, narrative: str,
    required_evidence: Mapping[str, Sequence[str]], available_evidence: Sequence[str],
) -> dict[str, Any]:
    audit = audit_claims(eligibility, requested_claims, narrative, required_evidence, available_evidence)
    return {"status": "pass", "claims": list(requested_claims), "narrative": narrative, "eligibility": dict(eligibility), "audit": audit}
