"""Balanced surface and irrelevant-intervention nuisance controls."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pead.core.hashing import canonical_hash


NUISANCE_VARIANTS = (
    "canonical",
    "identifier_swap",
    "order_reverse",
    "style_compact",
    "label_swap_surface",
    "prior_shift_surface",
)


def _thaw(value: Any) -> Any:
    """Convert recursively frozen world data into independently mutable data."""
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_thaw(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_thaw(item) for item in value), key=repr)
    return value


def nuisance_assignment(index: int) -> str:
    return NUISANCE_VARIANTS[index % len(NUISANCE_VARIANTS)]


def apply_nuisance(
    *,
    surface: Mapping[str, Any],
    latent_facts: Mapping[str, Any],
    variant: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if variant not in NUISANCE_VARIANTS:
        raise ValueError(f"unknown nuisance variant: {variant}")
    transformed_surface = _thaw(surface)
    transformed_facts = _thaw(latent_facts)
    transformed_facts["nuisance"]["variant"] = variant
    transformed_facts["nuisance"]["nonce"] = canonical_hash(
        {"variant": variant, "surface": surface}
    )[:16]
    if variant == "identifier_swap":
        transformed_surface["display_id"] = "candidate-beta"
    elif variant == "order_reverse":
        transformed_surface["token_order"] = ["support", "candidate", "task"]
    elif variant == "style_compact":
        transformed_surface["style"] = "compact"
    elif variant == "label_swap_surface":
        transformed_surface["template_id"] = "surface-swapped"
    elif variant == "prior_shift_surface":
        transformed_surface["context_frequency"] = "rare"
    return transformed_surface, transformed_facts
