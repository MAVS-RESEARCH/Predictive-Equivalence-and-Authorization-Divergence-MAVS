"""Deterministic, disjoint seed lineage."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pead.core.hashing import canonical_bytes

SEED_NAMESPACES: dict[str, tuple[int, int]] = {
    "development": (1_000_000, 1_999_999),
    "calibration": (2_000_000, 2_499_999),
    "public_validation": (3_000_000, 3_499_999),
    "structural_holdout": (7_000_000, 7_999_999),
    "domain_holdout": (8_000_000, 8_999_999),
    "final_blind": (9_000_000, 9_999_999),
}


@dataclass(frozen=True)
class SeedLineage:
    schema_version: str
    namespace: str
    root_seed: int
    component: str
    index: int
    derived_seed: int
    derivation_digest: str


def derive_seed(
    *,
    namespace: str,
    root_seed: int,
    component: str,
    index: int = 0,
) -> SeedLineage:
    """Derive a stable in-namespace seed without global random state."""

    if namespace not in SEED_NAMESPACES:
        raise ValueError(f"unknown seed namespace: {namespace}")
    if not isinstance(root_seed, int) or root_seed < 0:
        raise ValueError("root_seed must be a non-negative integer")
    if not component or not isinstance(component, str):
        raise ValueError("component must be non-empty")
    if not isinstance(index, int) or index < 0:
        raise ValueError("index must be a non-negative integer")
    payload = {
        "schema_version": "1.0",
        "namespace": namespace,
        "root_seed": root_seed,
        "component": component,
        "index": index,
    }
    digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    lower, upper = SEED_NAMESPACES[namespace]
    derived = lower + (int(digest, 16) % (upper - lower + 1))
    return SeedLineage(
        schema_version="1.0",
        namespace=namespace,
        root_seed=root_seed,
        component=component,
        index=index,
        derived_seed=derived,
        derivation_digest=digest,
    )
