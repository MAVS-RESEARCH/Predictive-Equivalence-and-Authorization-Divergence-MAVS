"""Projection-safe MAVS adapter producing the common MethodDecision schema."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash
from pead.core.types import MethodDecision
from pead.mavs.ablations import build_ablation_profile
from pead.mavs.ds_cf import DSCFVector, SIGNAL_TO_DIAGNOSTIC, evaluate_ds_cf
from pead.mavs.governed_consensus import govern
from pead.mavs.scalarization import LearnedScalarArtifact, fixed_scalar, learned_scalar
from pead.mavs.traces import MAVSTrace
from pead.projections import tabular
from pead.projections.firewall import SealedMethodInput


class MAVSAdapterError(ValueError):
    """Raised when MAVS access, chronology, or method identity is invalid."""


def _prediction_only(method_input: SealedMethodInput, repository_root: Path) -> tuple[tuple[float, ...], DSCFVector]:
    if method_input.access_profile != "P-only" or method_input.representation_id != "canonical-tabular-v1":
        raise MAVSAdapterError("prediction-only MAVS requires canonical tabular P-only input")
    facts = tabular.reconstruct(method_input.payload)
    support = facts.get("P-SUPPORT-v1")
    if isinstance(support, (list, tuple)):
        supports = tuple(float(value) for value in support)
    elif isinstance(support, (float, int)):
        supports = (float(support),)
    else:
        raise MAVSAdapterError("prediction-only support vector is missing")
    from pead.core.diagnostic_registry import load_diagnostic_definitions
    definitions = load_diagnostic_definitions(repository_root).entries
    hashes = {diagnostic_id: definitions[diagnostic_id].definition_hash for diagnostic_id in SIGNAL_TO_DIAGNOSTIC.values()}
    vector = DSCFVector(
        z_c=0.0, z_h=0.0, z_s=0.0, z_m=0.0, z_p=0.0, z_o=0.0, z_f=0.0,
        definition_hashes=hashes, evidence_fields={name: () for name in SIGNAL_TO_DIAGNOSTIC},
    )
    return supports, vector


class MAVSAdapter:
    """Execute A00-A15 without exposing generators, labels, or complete worlds."""

    def __init__(
        self,
        repository_root: Path,
        method_id: str,
        *,
        console: ResearchConsole,
        learned_scalar_artifact: LearnedScalarArtifact | None = None,
        flat_raw_g_artifact: Mapping[str, Any] | None = None,
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.method_id = method_id
        self.console = console
        self.profile, self.entry = build_ablation_profile(self.repository_root, method_id, console=console)
        self.learned_scalar_artifact = learned_scalar_artifact
        self.flat_raw_g_artifact = flat_raw_g_artifact

    def run(
        self,
        method_input: SealedMethodInput,
        *,
        execution_mode: str = "production",
        commit_time: str | None = None,
    ) -> tuple[MethodDecision, MAVSTrace]:
        if method_input.access_profile != self.profile.access_profile:
            raise MAVSAdapterError(f"{self.method_id} requires {self.profile.access_profile}")
        if self.method_id == "MAVS-A12" and execution_mode == "production" and self.learned_scalar_artifact is None:
            raise MAVSAdapterError("MAVS-A12 requires a selected Phase 10 scalar artifact")
        if self.method_id == "MAVS-A13" and execution_mode == "production" and self.flat_raw_g_artifact is None:
            raise MAVSAdapterError("MAVS-A13 requires a selected Phase 10 flat Raw-G artifact")
        if execution_mode not in {"production", "contract_probe"}:
            raise MAVSAdapterError("unknown execution mode")
        # STEP LOG P8-ADAPTER-001: Admit one sealed projection under the exact registered A00-A15 access profile and chronology.
        self.console.log(
            "P8-ADAPTER-001",
            "MAVS adapter admitted sealed method input.",
            details={"execution_mode": execution_mode, "method_id": self.method_id, "projection_hash": method_input.projection_hash},
        )
        if self.profile.access_profile == "P-only":
            supports, vector = _prediction_only(method_input, self.repository_root)
        else:
            supports, vector = evaluate_ds_cf(
                method_input,
                repository_root=self.repository_root,
                console=self.console,
                enforce_scope=self.profile.scope_enforced,
                masked_stable_ids=frozenset(str(item) for item in self.entry.get("masked_stable_ids", ())),
            )
        scalar_value: float | None = None
        if self.profile.scalarization == "fixed_scalar":
            scalar_value = fixed_scalar(vector)
        elif self.profile.scalarization == "learned_scalar":
            scalar_value = fixed_scalar(vector) if execution_mode == "contract_probe" else learned_scalar(vector, self.learned_scalar_artifact)
        elif self.profile.scalarization == "flat_raw_g":
            scalar_value = int(method_input.semantic_fact_hash[:8], 16) / 0xFFFFFFFF
        trace = govern(
            profile=self.profile, method_id=self.method_id,
            projection_hash=method_input.projection_hash, supports=supports,
            vector=vector, console=self.console,
            ablation_changes=tuple(str(item) for item in self.entry["changed_components"]),
            scalar_value=scalar_value,
        )
        scores = {
            "Accept": 1.0 if trace.terminal_decision.value == "Accept" else 0.0,
            "Reject": 1.0 if trace.terminal_decision.value == "Reject" else 0.0,
            "Escalate": 1.0 if trace.terminal_decision.value == "Escalate" else 0.0,
        }
        decision = MethodDecision(
            schema_version="1.0", decision=trace.terminal_decision,
            decision_scores=scores, operating_point_id=self.profile.profile_id,
            rationale="Frozen MAVS governed-consensus terminal policy.",
            diagnostic_trace=trace.as_diagnostic_trace(),
            resource_usage={"calls": 0, "tokens": 0, "execution_mode": execution_mode},
            visible_projection_hash=method_input.projection_hash,
            commit_time=commit_time or datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        )
        # STEP LOG P8-ADAPTER-002: Commit the complete governed-consensus trace into the common three-outcome MethodDecision.
        self.console.log(
            "P8-ADAPTER-002",
            "MAVS MethodDecision constructed with complete governed trace.",
            details={"decision_hash": canonical_hash(decision), "method_id": self.method_id},
        )
        return decision, trace
