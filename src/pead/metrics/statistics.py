"""Exact intervals, paired cluster bootstrap, strata summaries, and multiplicity."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

def exact_binomial_interval(successes: int, trials: int, alpha: float = 0.05) -> tuple[float, float]:
    if trials <= 0 or not 0 <= successes <= trials or not 0.0 < alpha < 1.0:
        raise ValueError("invalid exact-binomial arguments")
    def cdf(k: int, probability: float) -> float:
        return sum(math.comb(trials, index) * probability**index * (1.0 - probability) ** (trials - index) for index in range(k + 1))
    def solve(k: int, target: float) -> float:
        low, high = 0.0, 1.0
        for _ in range(100):
            midpoint = (low + high) / 2.0
            if cdf(k, midpoint) > target:
                low = midpoint
            else:
                high = midpoint
        return (low + high) / 2.0
    lower = 0.0 if successes == 0 else solve(successes - 1, 1.0 - alpha / 2.0)
    upper = 1.0 if successes == trials else solve(successes, alpha / 2.0)
    return lower, upper


def paired_cluster_bootstrap(
    effects: Mapping[str, float], clusters: Mapping[str, str], *, repetitions: int = 2000,
    seed: int = 9107, alpha: float = 0.05,
) -> dict[str, Any]:
    if set(effects) != set(clusters) or not effects or repetitions < 100:
        raise ValueError("cluster bootstrap requires aligned units and at least 100 repetitions")
    members: dict[str, list[str]] = defaultdict(list)
    for unit, cluster in clusters.items():
        members[cluster].append(unit)
    cluster_ids = sorted(members)
    rng = random.Random(seed)
    samples = []
    for _ in range(repetitions):
        selected = [rng.choice(cluster_ids) for _ in cluster_ids]
        values = [effects[unit] for cluster in selected for unit in members[cluster]]
        samples.append(sum(values) / len(values))
    samples.sort()
    lo = samples[max(0, math.floor((alpha / 2) * repetitions))]
    hi = samples[min(repetitions - 1, math.ceil((1 - alpha / 2) * repetitions) - 1)]
    return {"estimate": sum(effects.values()) / len(effects), "lower": lo, "upper": hi, "clusters": len(cluster_ids), "units": len(effects), "repetitions": repetitions, "seed": seed}


def mechanism_domain_bootstrap(
    effects: Mapping[str, float], mechanisms: Mapping[str, str], domains: Mapping[str, str],
    *, repetitions: int = 2000, seed: int = 9107,
) -> dict[str, Any]:
    if set(effects) != set(mechanisms) or set(effects) != set(domains):
        raise ValueError("mechanism/domain bootstrap identities differ")
    clusters = {unit: f"{domains[unit]}::{mechanisms[unit]}" for unit in effects}
    return paired_cluster_bootstrap(effects, clusters, repetitions=repetitions, seed=seed)


def stratified_effects(values: Mapping[str, float], strata: Mapping[str, str]) -> dict[str, Any]:
    if set(values) != set(strata) or not values:
        raise ValueError("stratified effects require aligned nonempty identities")
    groups: dict[str, list[float]] = defaultdict(list)
    for unit, value in values.items():
        groups[strata[unit]].append(value)
    per_stratum = {name: sum(items) / len(items) for name, items in sorted(groups.items())}
    return {"per_stratum": per_stratum, "macro_average": sum(per_stratum.values()) / len(per_stratum)}


def holm_correction(p_values: Mapping[str, float], alpha: float = 0.05) -> dict[str, Any]:
    if not p_values or any(not 0.0 <= value <= 1.0 for value in p_values.values()):
        raise ValueError("Holm correction requires valid p-values")
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted, running = {}, 0.0
    for rank, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, value * (len(ordered) - rank)))
        adjusted[name] = running
    return {name: {"raw": p_values[name], "adjusted": adjusted[name], "reject": adjusted[name] <= alpha} for name in sorted(p_values)}
