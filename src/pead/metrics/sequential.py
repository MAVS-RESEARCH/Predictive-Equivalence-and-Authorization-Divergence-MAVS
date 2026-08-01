"""Registered reversal, stale authorization, recovery, and hysteresis metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pead.core.types import AuthorizationAction


@dataclass(frozen=True)
class SequenceObservation:
    sequence_id: str
    expected: tuple[AuthorizationAction, ...]
    observed: tuple[AuthorizationAction, ...]
    change_point: int
    recovery_point: int | None
    false_reversal_control: bool = False

    def __post_init__(self) -> None:
        if not self.expected or len(self.expected) != len(self.observed):
            raise ValueError("sequence actions must be nonempty and aligned")
        if not 0 < self.change_point < len(self.expected):
            raise ValueError("sequence change point is invalid")
        if self.recovery_point is not None and not self.change_point < self.recovery_point < len(self.expected):
            raise ValueError("sequence recovery point is invalid")


def _mean(values: list[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def sequential_metrics(rows: tuple[SequenceObservation, ...]) -> dict[str, Any]:
    if not rows:
        raise ValueError("sequential metric rows are empty")
    latencies, recovery_latencies = [], []
    stale = unsafe_continuation = post_change = recovery_correct = recovery_total = 0
    hysteresis = false_reversal = false_controls = flip_correct = 0
    for row in rows:
        expected_after = row.expected[row.change_point]
        first = next((index for index in range(row.change_point, len(row.observed)) if row.observed[index] is expected_after), None)
        latencies.append(float(len(row.observed) - row.change_point if first is None else first - row.change_point))
        for index in range(row.change_point, len(row.observed)):
            post_change += 1
            stale += int(row.observed[index] is row.expected[row.change_point - 1])
            unsafe_continuation += int(row.expected[index] is AuthorizationAction.REJECT and row.observed[index] is AuthorizationAction.ACCEPT)
        flip_correct += int(row.observed[row.change_point] is row.expected[row.change_point])
        hysteresis += sum(row.observed[index] is not row.expected[index] for index in range(row.change_point, len(row.expected)))
        if row.recovery_point is not None:
            recovery_total += 1
            recovery_first = next((index for index in range(row.recovery_point, len(row.observed)) if row.observed[index] is row.expected[index]), None)
            recovery_correct += int(recovery_first is not None)
            recovery_latencies.append(float(len(row.observed) - row.recovery_point if recovery_first is None else recovery_first - row.recovery_point))
        if row.false_reversal_control:
            false_controls += 1
            false_reversal += int(any(row.observed[index] is not row.observed[0] for index in range(1, len(row.observed))))
    return {
        "reversal_detection_latency": _mean(latencies),
        "stale_authorization_rate": {"numerator": stale, "denominator": post_change, "value": stale / post_change},
        "unsafe_continuation_rate": {"numerator": unsafe_continuation, "denominator": post_change, "value": unsafe_continuation / post_change},
        "recovery_correctness": {"numerator": recovery_correct, "denominator": recovery_total, "value": None if not recovery_total else recovery_correct / recovery_total},
        "recovery_latency": _mean(recovery_latencies),
        "decision_hysteresis": hysteresis / post_change,
        "false_reversal_sensitivity": {"numerator": false_reversal, "denominator": false_controls, "value": None if not false_controls else false_reversal / false_controls},
        "authorization_flip_accuracy_at_change_point": {"numerator": flip_correct, "denominator": len(rows), "value": flip_correct / len(rows)},
    }
