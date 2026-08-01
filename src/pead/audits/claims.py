"""Frozen claim-predicate, dependency, and wording audit."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

FORBIDDEN = (
    "universal prediction insufficiency", "universal mavs optimality",
    "deployment certification", "zero risk", "escalation alone is safety",
    "official external benchmark execution",
)


def audit_claims(
    eligibility: Mapping[str, bool], emitted_claims: Sequence[str], narrative: str,
    required_evidence: Mapping[str, Sequence[str]], available_evidence: Sequence[str],
) -> dict[str, Any]:
    unknown = sorted(set(emitted_claims) - set(eligibility))
    ineligible = sorted(claim for claim in emitted_claims if not eligibility.get(claim, False))
    evidence = set(available_evidence)
    missing = {claim: sorted(set(required_evidence.get(claim, ())) - evidence) for claim in emitted_claims}
    missing = {claim: values for claim, values in missing.items() if values}
    wording = sorted(phrase for phrase in FORBIDDEN if phrase in narrative.lower())
    if unknown or ineligible or missing or wording:
        raise ValueError(f"claim gate failed: unknown={unknown}; ineligible={ineligible}; missing={missing}; wording={wording}")
    return {"status": "pass", "emitted_claims": list(emitted_claims), "ineligible": [], "missing_evidence": {}, "forbidden_wording": []}
