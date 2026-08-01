"""Fixed mechanism-level Raw-G policy engine."""

from __future__ import annotations

from collections.abc import Mapping

from pead.baselines.base import BaselineAdapter
from pead.projections.firewall import SealedMethodInput


class PolicyEngine(BaselineAdapter):
    """Apply visible authority, policy, temporal, and evidence facts conservatively."""

    def score(self, method_input: SealedMethodInput) -> Mapping[str, float]:
        text = repr(method_input.payload).lower()
        ambiguity = any(token in text for token in ("unknown", "masked", "unavailable"))
        prohibited = any(token in text for token in ("revoked", "prohibited", "conflict"))
        if ambiguity:
            return {"Accept": 0.0, "Reject": 0.2, "Escalate": 1.0}
        if prohibited:
            return {"Accept": 0.0, "Reject": 1.0, "Escalate": 0.1}
        return {"Accept": 1.0, "Reject": 0.1, "Escalate": 0.1}
