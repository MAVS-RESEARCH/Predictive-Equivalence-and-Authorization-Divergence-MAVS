"""Paired causal contrasts over immutable evaluation units."""

from __future__ import annotations

from collections.abc import Mapping


def paired_effect(treated: Mapping[str, float], control: Mapping[str, float]) -> dict[str, object]:
    if set(treated) != set(control) or not treated:
        raise ValueError("paired causal effect requires identical nonempty unit identities")
    effects = {unit: float(treated[unit] - control[unit]) for unit in sorted(treated)}
    return {"unit_effects": effects, "mean_effect": sum(effects.values()) / len(effects), "units": len(effects)}


def pair_sequence_effects(
    pair_treated: Mapping[str, float], pair_control: Mapping[str, float],
    sequence_treated: Mapping[str, float], sequence_control: Mapping[str, float],
) -> dict[str, object]:
    return {"pairs": paired_effect(pair_treated, pair_control), "sequences": paired_effect(sequence_treated, sequence_control)}
