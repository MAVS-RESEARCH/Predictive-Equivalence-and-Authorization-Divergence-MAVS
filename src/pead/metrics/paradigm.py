"""Paradigm-level paired information and architecture metrics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def lower_bound_gap(observed_p_only_terminal_error: float, theoretical_lower_bound: float) -> float:
    """LBG: observed P-only terminal error minus its matched-coverage lower bound."""

    return float(observed_p_only_terminal_error - theoretical_lower_bound)


def governance_information_gain(best_raw_g_utility: float, best_p_only_utility: float) -> float:
    """GIG: protected utility gained by adding registered Raw-G information."""

    return float(best_raw_g_utility - best_p_only_utility)


def governance_architecture_gain(mavs_utility: float, best_flat_raw_g_utility: float) -> float:
    """GAG: equal-information utility gained by structured MAVS governance."""

    return float(mavs_utility - best_flat_raw_g_utility)


def authorization_flip_accuracy(
    expected_pairs: Mapping[str, tuple[str, str]],
    observed_pairs: Mapping[str, tuple[str, str]],
) -> dict[str, float | int]:
    """AFA over pairs whose ground-truth authorization changes."""

    if set(expected_pairs) != set(observed_pairs):
        raise ValueError("AFA requires identical pair identities")
    eligible = [pair_id for pair_id, actions in expected_pairs.items() if actions[0] != actions[1]]
    if not eligible:
        raise ValueError("AFA denominator is empty")
    correct = sum(
        observed_pairs[pair_id][0] != observed_pairs[pair_id][1]
        and observed_pairs[pair_id] == expected_pairs[pair_id]
        for pair_id in eligible
    )
    return {"numerator": correct, "denominator": len(eligible), "value": correct / len(eligible)}


def paired_paradigm_metrics(
    *, p_only_error: float, lower_bound: float, raw_g_utility: float,
    p_only_utility: float, mavs_utility: float, flat_raw_g_utility: float,
    expected_pairs: Mapping[str, tuple[str, str]], observed_pairs: Mapping[str, tuple[str, str]],
) -> dict[str, object]:
    return {
        "LBG": lower_bound_gap(p_only_error, lower_bound),
        "GIG": governance_information_gain(raw_g_utility, p_only_utility),
        "GAG": governance_architecture_gain(mavs_utility, flat_raw_g_utility),
        "AFA": authorization_flip_accuracy(expected_pairs, observed_pairs),
        "paired_units": len(expected_pairs),
    }
