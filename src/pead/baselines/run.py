"""Common execution path for all registered baseline families."""

from __future__ import annotations

from pead.baselines.base import BaselineAdapter
from pead.core.types import MethodDecision
from pead.projections.firewall import SealedMethodInput


def run_adapter_case(
    adapter: BaselineAdapter,
    method_input: SealedMethodInput,
    *,
    execution_mode: str,
    commit_time: str,
) -> MethodDecision:
    """Run one adapter; production and contract probes share this exact path."""

    return adapter.decide(
        method_input,
        execution_mode=execution_mode,
        commit_time=commit_time,
    )
