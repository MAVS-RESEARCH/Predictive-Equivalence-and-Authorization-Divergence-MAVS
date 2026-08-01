"""Common Phase 7 comparator contract-probe suite."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pead.baselines.registry import ORACLE_IDS, P_ONLY_IDS, RAW_G_IDS, comparator_probes
from pead.baselines.run import run_adapter_case
from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash
from pead.phase7.fixtures import probe_input


def execute_contract_suite(
    repo_root: Path,
    console: ResearchConsole,
    *,
    repetitions: int = 1,
) -> dict[str, Any]:
    """Run every Phase 7 comparator through one non-scientific runner path."""

    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    adapters = comparator_probes(repo_root, console)
    expected = P_ONLY_IDS | RAW_G_IDS | ORACLE_IDS
    if set(adapters) != expected:
        raise ValueError("comparator adapter registry is incomplete")
    # STEP LOG P7-SUITE-001: Admit the exact nine P-only, twelve Raw-G, and two Oracle diagnostic comparator contracts.
    console.log(
        "P7-SUITE-001",
        "Comparator contract registry admitted.",
        details={"comparators": len(adapters), "repetitions": repetitions},
    )
    decisions = []
    for repetition in range(repetitions):
        for method_id in sorted(adapters):
            adapter = adapters[method_id]
            method_input = probe_input(
                adapter.contract.access_profile,
                adapter.contract.representation_id,
                index=repetition,
            )
            decisions.append(
                run_adapter_case(
                    adapter,
                    method_input,
                    execution_mode="contract_probe",
                    commit_time="2026-08-01T00:00:00+00:00",
                )
            )
    if any(decision.diagnostic_trace["scientific_result"] for decision in decisions):
        raise ValueError("contract probes cannot be scientific results")
    # STEP LOG P7-SUITE-002: Close the common-runner proof only after every comparator returns the frozen MethodDecision schema.
    console.log(
        "P7-SUITE-002",
        "All comparator contracts passed through the common runner.",
        status="pass",
        details={"decisions": len(decisions)},
    )
    return {
        "status": "pass",
        "comparators": len(adapters),
        "p_only_families": len(P_ONLY_IDS),
        "raw_g_families": len(RAW_G_IDS),
        "oracle_diagnostics": len(ORACLE_IDS),
        "decisions": len(decisions),
        "decision_hash": canonical_hash(decisions),
        "execution_mode": "contract_probe",
        "scientific_results": 0,
    }
