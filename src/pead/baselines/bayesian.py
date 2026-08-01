"""Registered pgmpy Bayesian-network contract."""

from __future__ import annotations

from typing import Any

BAYES_GRID = tuple(
    {"quantile_bins": bins, "equivalent_sample_size": ess}
    for bins in (8, 16)
    for ess in (1, 5, 10)
)
BAYES_CONTRACT = {
    "structure_search": "hill_climb_BIC",
    "maximum_indegree": 4,
    "maximum_structure_operations": 100_000,
    "parameter_estimator": "Bayesian",
    "discretization_fit_partition": "development_fit",
    "missing_state": "explicit",
    "seeds": (101, 211, 307),
}


def require_pgmpy() -> Any:
    """Load the exact backend or fail without substituting another model."""

    try:
        import pgmpy
    except ImportError as exc:
        raise RuntimeError(
            "pgmpy is required for G07-BAYES; backend substitution is prohibited"
        ) from exc
    return pgmpy
