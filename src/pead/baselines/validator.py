"""Fixed layered Raw-G validator comparator."""

from __future__ import annotations

from collections.abc import Mapping

from pead.baselines.base import BaselineAdapter
from pead.projections.firewall import SealedMethodInput


class ValidatorStack(BaselineAdapter):
    """Expose provenance, policy, authority, and evidence validation stages."""

    STAGES = ("schema", "provenance", "authority", "policy", "temporal", "evidence")

    def score(self, method_input: SealedMethodInput) -> Mapping[str, float]:
        payload = repr(method_input.payload).lower()
        failures = sum(token in payload for token in ("invalid", "revoked", "conflict", "expired"))
        unresolved = sum(token in payload for token in ("unknown", "masked", "missing"))
        return {
            "Accept": 1.0 / (1.0 + failures + unresolved),
            "Reject": float(failures),
            "Escalate": float(unresolved),
        }
