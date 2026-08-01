"""Fixed and learned one-scalar Raw-G reduction comparators."""

from __future__ import annotations

from dataclasses import dataclass

from pead.baselines.neural import MLP_GRID

SCALAR_GRID = tuple(
    {**configuration, "monotonic_penalty": penalty}
    for configuration in MLP_GRID
    for penalty in (0.0, 0.1)
)


@dataclass(frozen=True)
class ScalarOperatingPoint:
    reject_below: float
    accept_above: float

    def decide(self, value: float) -> str:
        if value <= self.reject_below:
            return "Reject"
        if value >= self.accept_above:
            return "Accept"
        return "Escalate"


def fixed_scalar(components: tuple[float, ...]) -> float:
    if not components:
        raise ValueError("fixed scalar requires visible governance components")
    return sum(components) / len(components)
