"""Complete immutable traces for governed consensus decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from pead.core.types import AuthorizationAction, deep_freeze


class MAVSTraceError(ValueError):
    """Raised when a governed-consensus trace is incomplete or inconsistent."""


@dataclass(frozen=True)
class MAVSTrace:
    schema_version: str
    profile_id: str
    method_id: str
    access_profile: str
    visible_projection_hash: str
    supports: tuple[float, ...]
    diagnostic_vector: Mapping[str, float]
    diagnostic_definition_hashes: Mapping[str, str]
    severity: float
    contextual_weights: tuple[float, ...]
    mitigation: float
    threshold: float
    veto: bool
    ambiguity: bool
    consensus: float
    terminal_decision: AuthorizationAction
    enabled_components: tuple[str, ...]
    ablation_changes: tuple[str, ...]
    scope_enforced: bool
    trace_complete: bool = True

    def __post_init__(self) -> None:
        if self.schema_version != "1.0" or not self.profile_id or not self.method_id:
            raise MAVSTraceError("trace identity is incomplete")
        if not self.supports or len(self.supports) != len(self.contextual_weights):
            raise MAVSTraceError("supports and contextual weights must be aligned")
        if any(weight < 0.0 for weight in self.contextual_weights):
            raise MAVSTraceError("contextual weights cannot be negative")
        if abs(sum(self.contextual_weights) - 1.0) > 1e-12:
            raise MAVSTraceError("contextual weights must sum to one")
        if set(self.diagnostic_vector) != {"z_c", "z_h", "z_s", "z_m", "z_p", "z_o", "z_f"}:
            raise MAVSTraceError("trace requires the complete seven-signal DS-CF vector")
        if any(not 0.0 <= value <= 1.0 for value in self.diagnostic_vector.values()):
            raise MAVSTraceError("diagnostic values must be in [0,1]")
        if not 0.0 <= self.mitigation <= 1.0:
            raise MAVSTraceError("mitigation must be bounded in [0,1]")
        if self.veto and self.terminal_decision is not AuthorizationAction.REJECT:
            raise MAVSTraceError("hard veto must dominate the terminal decision")
        if not self.trace_complete:
            raise MAVSTraceError("incomplete governed-consensus trace is prohibited")
        object.__setattr__(self, "diagnostic_vector", deep_freeze(self.diagnostic_vector))
        object.__setattr__(self, "diagnostic_definition_hashes", deep_freeze(self.diagnostic_definition_hashes))

    def as_diagnostic_trace(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "method_id": self.method_id,
            "access_profile": self.access_profile,
            "supports": self.supports,
            "diagnostic_vector": dict(self.diagnostic_vector),
            "diagnostic_definition_hashes": dict(self.diagnostic_definition_hashes),
            "severity": self.severity,
            "contextual_weights": self.contextual_weights,
            "mitigation": self.mitigation,
            "threshold": self.threshold,
            "veto": self.veto,
            "ambiguity": self.ambiguity,
            "consensus": self.consensus,
            "terminal_decision": self.terminal_decision.value,
            "enabled_components": self.enabled_components,
            "ablation_changes": self.ablation_changes,
            "scope_enforced": self.scope_enforced,
            "trace_complete": self.trace_complete,
        }
