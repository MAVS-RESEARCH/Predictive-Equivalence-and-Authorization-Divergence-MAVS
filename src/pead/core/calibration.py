"""Partition-isolated calibration and terminal policy selection."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash


class CalibrationContractError(ValueError):
    """Raised when calibration chronology or probability inputs are invalid."""


@dataclass(frozen=True)
class CalibrationArtifact:
    method: str
    parameters: tuple[float, ...]
    fit_partition: str
    artifact_hash: str


@dataclass(frozen=True)
class OperatingPoint:
    operating_point_id: str
    accept_threshold: float
    reject_threshold: float
    policy_partition: str
    objective: tuple[float, ...]


def fit_temperature(
    logits: Iterable[tuple[float, float, float]],
    labels: Iterable[int],
    *,
    partition: str,
    console: ResearchConsole,
) -> CalibrationArtifact:
    """Fit one deterministic grid-searched temperature on calibration_fit only."""

    if partition != "calibration_fit":
        raise CalibrationContractError("calibrator fitting requires calibration_fit")
    rows = tuple(logits)
    targets = tuple(labels)
    if not rows or len(rows) != len(targets):
        raise CalibrationContractError("calibration logits and labels must align")
    # STEP LOG P7-CALIBRATION-001: Fit the registered calibration transform on calibration_fit only.
    console.log(
        "P7-CALIBRATION-001",
        "Fitting temperature transform on calibration_fit.",
        details={"rows": len(rows)},
    )
    candidates = tuple(0.25 + index * 0.05 for index in range(76))
    def loss(temperature: float) -> float:
        total = 0.0
        for row, target in zip(rows, targets, strict=True):
            scaled = tuple(value / temperature for value in row)
            maximum = max(scaled)
            denominator = sum(math.exp(value - maximum) for value in scaled)
            probability = math.exp(scaled[target] - maximum) / denominator
            total -= math.log(max(probability, 1e-15))
        return total / len(rows)
    temperature = min(candidates, key=lambda value: (loss(value), value))
    payload = {"method": "temperature", "parameters": [temperature], "partition": partition}
    return CalibrationArtifact(
        method="temperature",
        parameters=(temperature,),
        fit_partition=partition,
        artifact_hash=canonical_hash(payload),
    )


def choose_probability_calibrator(class_counts: Iterable[int]) -> str:
    """Use isotonic only when every class has at least 1,000 opportunities."""

    counts = tuple(class_counts)
    if len(counts) != 3 or any(count < 1 for count in counts):
        raise CalibrationContractError("three positive class counts are required")
    return "isotonic" if min(counts) >= 1000 else "Platt"


def fit_binary_calibrator(
    scores: Iterable[float],
    labels: Iterable[int],
    *,
    method: str,
    partition: str,
) -> Any:
    """Fit exact sklearn isotonic or Platt calibration on calibration_fit."""

    if partition != "calibration_fit":
        raise CalibrationContractError("binary calibrator fitting requires calibration_fit")
    x = tuple(float(value) for value in scores)
    y = tuple(int(value) for value in labels)
    if not x or len(x) != len(y):
        raise CalibrationContractError("calibration scores and labels must align")
    if method == "isotonic":
        from sklearn.isotonic import IsotonicRegression
        return IsotonicRegression(out_of_bounds="clip").fit(x, y)
    if method == "Platt":
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression(solver="lbfgs", random_state=0).fit([[value] for value in x], y)
    raise CalibrationContractError("unregistered probability calibrator")


def select_operating_point(
    candidates: Iterable[OperatingPoint],
    *,
    partition: str,
    console: ResearchConsole,
) -> OperatingPoint:
    """Select by frozen lexicographic objective on calibration_policy only."""

    if partition != "calibration_policy":
        raise CalibrationContractError("terminal policy selection requires calibration_policy")
    options = tuple(candidates)
    if not options or any(option.policy_partition != partition for option in options):
        raise CalibrationContractError("operating-point candidates are incomplete")
    # STEP LOG P7-CALIBRATION-002: Select the headline threshold by the registered calibration_policy lexicographic objective.
    console.log(
        "P7-CALIBRATION-002",
        "Selecting terminal operating point on calibration_policy.",
        details={"candidates": len(options)},
    )
    return max(
        options,
        key=lambda item: (item.objective, -item.accept_threshold, item.operating_point_id),
    )


def report_threshold_sweep(
    options: Iterable[OperatingPoint], headline_id: str
) -> dict[str, object]:
    """Retain sensitivity options without replacing the selected headline."""

    rows = tuple(options)
    if headline_id not in {row.operating_point_id for row in rows}:
        raise CalibrationContractError("headline operating point is absent from sweep")
    return {
        "headline_operating_point_id": headline_id,
        "headline_replaced_by_sweep": False,
        "sweep": [row.__dict__ for row in rows],
    }
