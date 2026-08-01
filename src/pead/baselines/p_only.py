"""Prediction-only confidence, uncertainty, disagreement, conformal, and reject baselines."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pead.baselines.base import ACTIONS, BaselineAdapter, BaselineContractError
from pead.projections.firewall import SealedMethodInput


def _mapping_payload(method_input: SealedMethodInput) -> Mapping[str, Any]:
    if not isinstance(method_input.payload, Mapping):
        raise BaselineContractError("fixed P-only gates require canonical tabular input")
    return method_input.payload


def _numeric(value: Any, default: float = 0.5) -> float:
    if isinstance(value, (float, int)):
        return float(value)
    if isinstance(value, Mapping):
        for item in value.values():
            if isinstance(item, (float, int)):
                return float(item)
    return default


class PredictionGate(BaselineAdapter):
    """Frozen prediction-facing gate with explicit escalation behavior."""

    def score(self, method_input: SealedMethodInput) -> Mapping[str, float]:
        payload = _mapping_payload(method_input)
        method_id = self.contract.method_id
        confidence = _numeric(payload.get("P-CONFIDENCE-v1"))
        uncertainty = _numeric(payload.get("P-UNCERTAINTY-v1"))
        agreement = _numeric(payload.get("P-AGREEMENT-v1"))
        if method_id == "P01-CONF":
            return {"Accept": confidence, "Reject": 1.0 - confidence, "Escalate": 0.05}
        if method_id == "P02-UNC":
            return {"Accept": 1.0 - uncertainty, "Reject": uncertainty * 0.5, "Escalate": uncertainty}
        if method_id == "P03-DIS":
            return {"Accept": agreement, "Reject": (1.0 - agreement) * 0.5, "Escalate": 1.0 - agreement}
        raise BaselineContractError(f"unsupported fixed prediction gate: {method_id}")


class StaticConformal(BaselineAdapter):
    """Frozen-base conformal set mapped to Accept/Reject/Escalate."""

    def __init__(self, *args: Any, alpha: float, quantile: float, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if alpha not in {0.01, 0.025, 0.05, 0.1, 0.2}:
            raise BaselineContractError("alpha is outside the registered static grid")
        self.alpha = alpha
        self.quantile = quantile

    def score(self, method_input: SealedMethodInput) -> Mapping[str, float]:
        confidence = _numeric(_mapping_payload(method_input).get("P-CONFIDENCE-v1"))
        nonconformity = 1.0 - confidence
        if nonconformity <= self.quantile:
            return {"Accept": 1.0 - nonconformity, "Reject": nonconformity, "Escalate": self.alpha}
        return {"Accept": 0.0, "Reject": nonconformity, "Escalate": 1.0}


class AdaptiveConformal(StaticConformal):
    """Causal delayed-label conformal adapter with a registered rolling window."""

    def __init__(self, *args: Any, window: int, **kwargs: Any) -> None:
        if window not in {256, 1024}:
            raise BaselineContractError("adaptive conformal window is unregistered")
        super().__init__(*args, **kwargs)
        self.window = window
        self._past_nonconformity: list[float] = []

    def update_after_label(self, nonconformity: float) -> None:
        """Admit only delayed, already-revealed labels to future quantiles."""

        self._past_nonconformity.append(float(nonconformity))
        self._past_nonconformity = self._past_nonconformity[-self.window :]


REGISTERED_CONFORMAL_ALPHAS = (0.01, 0.025, 0.05, 0.1, 0.2)
REGISTERED_ADAPTIVE_GRID = tuple((alpha, window) for alpha in (0.025, 0.05, 0.1) for window in (256, 1024))


def finite_sample_quantile_index(sample_count: int, alpha: float) -> int:
    """Return the one-based ceil((n+1)(1-alpha)) conformal rank."""

    import math
    if sample_count < 1 or not 0.0 < alpha < 1.0:
        raise BaselineContractError("conformal rank requires n>0 and 0<alpha<1")
    return min(sample_count, math.ceil((sample_count + 1) * (1.0 - alpha)))
