"""Shared three-outcome adapter and registry-facing baseline contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash
from pead.core.types import AuthorizationAction, MethodDecision
from pead.projections.firewall import SealedMethodInput

ACTIONS = ("Accept", "Reject", "Escalate")


class BaselineContractError(ValueError):
    """Raised when a comparator violates its access or execution contract."""


@dataclass(frozen=True)
class MethodContract:
    method_id: str
    family: str
    access_profile: str
    representation_id: str
    training_status: str
    reporting_role: str


class BaselineAdapter(ABC):
    """One interface for every P-only, Raw-G, and Oracle-G comparator."""

    def __init__(
        self,
        contract: MethodContract,
        *,
        console: ResearchConsole,
        operating_point_id: str = "unselected",
    ) -> None:
        self.contract = contract
        self.console = console
        self.operating_point_id = operating_point_id
        self._fitted = contract.training_status in {"fixed", "fixed-model", "fixed-sampling-contract"}

    def validate_input(self, method_input: SealedMethodInput) -> None:
        if method_input.access_profile != self.contract.access_profile:
            raise BaselineContractError(
                f"{self.contract.method_id} requires {self.contract.access_profile}"
            )
        if method_input.representation_id != self.contract.representation_id:
            raise BaselineContractError(
                f"{self.contract.method_id} requires {self.contract.representation_id}"
            )

    @abstractmethod
    def score(self, method_input: SealedMethodInput) -> Mapping[str, float]:
        """Return finite three-outcome scores from visible projection content only."""

    def decide(
        self,
        method_input: SealedMethodInput,
        *,
        commit_time: str | None = None,
        execution_mode: str = "production",
    ) -> MethodDecision:
        self.validate_input(method_input)
        if execution_mode == "production" and not self._fitted:
            raise BaselineContractError(
                f"{self.contract.method_id} has no selected Phase 10 checkpoint"
            )
        if execution_mode not in {"production", "contract_probe"}:
            raise BaselineContractError("unknown execution mode")
        # STEP LOG P7-BASELINE-001: Execute one registered comparator against only its sealed visible projection.
        self.console.log(
            "P7-BASELINE-001",
            "Executing registered baseline adapter.",
            details={
                "execution_mode": execution_mode,
                "method_id": self.contract.method_id,
                "projection_hash": method_input.projection_hash,
            },
        )
        raw_scores = dict(self.score(method_input))
        if set(raw_scores) != set(ACTIONS):
            raise BaselineContractError("baseline must return exactly three decision scores")
        if any(not isinstance(value, (float, int)) for value in raw_scores.values()):
            raise BaselineContractError("decision scores must be numeric")
        total = sum(max(0.0, float(value)) for value in raw_scores.values())
        if total <= 0.0:
            raise BaselineContractError("decision scores must have positive mass")
        scores = {action: max(0.0, float(raw_scores[action])) / total for action in ACTIONS}
        decision_name = max(ACTIONS, key=lambda action: (scores[action], -ACTIONS.index(action)))
        timestamp = commit_time or datetime.now(timezone.utc).isoformat(timespec="microseconds")
        decision = MethodDecision(
            schema_version="1.0",
            decision=AuthorizationAction(decision_name),
            decision_scores=scores,
            operating_point_id=self.operating_point_id,
            rationale="Highest normalized score under the registered three-outcome policy.",
            diagnostic_trace={
                "method_id": self.contract.method_id,
                "execution_mode": execution_mode,
                "scientific_result": execution_mode == "production",
                "score_hash": canonical_hash(scores),
            },
            resource_usage={"calls": 0, "tokens": 0, "execution_mode": execution_mode},
            visible_projection_hash=method_input.projection_hash,
            commit_time=timestamp,
        )
        # STEP LOG P7-BASELINE-002: Commit a normalized three-outcome MethodDecision with explicit execution provenance.
        self.console.log(
            "P7-BASELINE-002",
            "Three-outcome baseline decision constructed.",
            details={"decision": decision_name, "method_id": self.contract.method_id},
        )
        return decision


class ContractProbeAdapter(BaselineAdapter):
    """Non-scientific deterministic probe used to verify every registered interface."""

    def score(self, method_input: SealedMethodInput) -> Mapping[str, float]:
        digest = bytes.fromhex(method_input.semantic_fact_hash)
        values = tuple(1.0 + digest[index] for index in range(3))
        return dict(zip(ACTIONS, values, strict=True))


def contract_from_inventory(record: Mapping[str, Any]) -> MethodContract:
    """Create the runtime contract without changing frozen inventory identity."""

    family = str(record["family"])
    representation = "canonical-tabular-v1"
    if "sequence" in family.lower() or "judge" in family.lower() or "self-consistency" in family.lower():
        representation = "canonical-sequence-v1"
    elif "graph" in family.lower():
        representation = "canonical-graph-v1"
    return MethodContract(
        method_id=str(record["method_id"]),
        family=family,
        access_profile=str(record["access_profile"]),
        representation_id=representation,
        training_status=str(record["training_status"]),
        reporting_role=str(record["reporting_role"]),
    )
