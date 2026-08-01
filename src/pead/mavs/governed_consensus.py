"""Frozen governed-consensus severity, weighting, mitigation, veto, and policy."""

from __future__ import annotations

from pead.config.console import ResearchConsole
from pead.core.types import AuthorizationAction
from pead.mavs.ds_cf import DSCFVector
from pead.mavs.profiles import MAVSProfile
from pead.mavs.traces import MAVSTrace


class GovernedConsensusError(ValueError):
    """Raised when a MAVS structural invariant is violated."""


def _contextual_weights(supports: tuple[float, ...], vector: DSCFVector, enabled: bool) -> tuple[float, ...]:
    if not supports:
        raise GovernedConsensusError("all-speak support vector cannot be empty")
    if not enabled:
        return tuple(1.0 / len(supports) for _ in supports)
    floor = 1e-6
    raw = tuple(floor + max(0.0, 1.0 - vector.z_c * (index / max(1, len(supports) - 1))) for index in range(len(supports)))
    total = sum(raw)
    return tuple(value / total for value in raw)


def hard_veto(vector: DSCFVector, profile: MAVSProfile) -> bool:
    if not profile.hard_veto:
        return False
    thresholds = profile.thresholds
    return (
        vector.z_h >= thresholds["tau_h"]
        and vector.z_s < thresholds["tau_s"]
        and (
            vector.z_f >= thresholds["tau_f"]
            or vector.z_m >= thresholds["tau_m"]
            or vector.z_p >= thresholds["tau_p"]
        )
    )


def govern(
    *,
    profile: MAVSProfile,
    method_id: str,
    projection_hash: str,
    supports: tuple[float, ...],
    vector: DSCFVector,
    console: ResearchConsole,
    ablation_changes: tuple[str, ...] = (),
    scalar_value: float | None = None,
) -> MAVSTrace:
    """Apply the frozen two-path governed authorization equations."""

    values = vector.values()
    severity = sum(profile.severity_weights.get(name, 0.0) * values[name] for name in values if name in profile.enabled_diagnostics)
    mitigation = min(profile.mitigation_bound, vector.z_s) if "mitigation" in profile.enabled_diagnostics else 0.0
    weights = _contextual_weights(supports, vector, profile.contextual_weights)
    consensus = sum(weight * support for weight, support in zip(weights, supports, strict=True))
    threshold = profile.base_threshold + profile.severity_multiplier * severity - profile.mitigation_multiplier * mitigation
    veto = hard_veto(vector, profile)
    if vector.z_c >= 1.0 and vector.z_h == 0.0 and veto:
        raise GovernedConsensusError("raw correlation alone cannot hard-veto")
    ambiguity = profile.escalation and not veto and (
        vector.z_m >= profile.thresholds["ambiguity"]
        or (profile.thresholds["soft_h_low"] <= vector.z_h < profile.thresholds["tau_h"])
    )
    if profile.scalarization in {"fixed_scalar", "learned_scalar", "flat_raw_g"}:
        scalar = severity if scalar_value is None else min(1.0, max(0.0, scalar_value))
        veto = False
        ambiguity = profile.escalation and profile.thresholds["scalar_accept"] < scalar < profile.thresholds["scalar_reject"]
        if scalar >= profile.thresholds["scalar_reject"]:
            decision = AuthorizationAction.REJECT
        elif scalar <= profile.thresholds["scalar_accept"]:
            decision = AuthorizationAction.ACCEPT
        else:
            decision = AuthorizationAction.ESCALATE if profile.escalation else AuthorizationAction.REJECT
    elif veto:
        decision = AuthorizationAction.REJECT
    elif ambiguity:
        decision = AuthorizationAction.ESCALATE
    elif consensus >= threshold:
        decision = AuthorizationAction.ACCEPT
    else:
        decision = AuthorizationAction.REJECT
    trace = MAVSTrace(
        schema_version="1.0", profile_id=profile.profile_id, method_id=method_id,
        access_profile=profile.access_profile, visible_projection_hash=projection_hash,
        supports=supports, diagnostic_vector=values,
        diagnostic_definition_hashes=vector.definition_hashes, severity=severity,
        contextual_weights=weights, mitigation=mitigation, threshold=threshold,
        veto=veto, ambiguity=ambiguity, consensus=consensus,
        terminal_decision=decision,
        enabled_components=tuple(sorted(profile.enabled_diagnostics)),
        ablation_changes=ablation_changes, scope_enforced=profile.scope_enforced,
    )
    # STEP LOG P8-GOVERN-001: Apply severity, contextual weights, bounded mitigation, threshold, veto, ambiguity, and terminal authorization in order.
    console.log(
        "P8-GOVERN-001",
        "Governed consensus decision completed.",
        details={"decision": decision.value, "method_id": method_id, "profile_id": profile.profile_id, "veto": veto},
    )
    return trace
