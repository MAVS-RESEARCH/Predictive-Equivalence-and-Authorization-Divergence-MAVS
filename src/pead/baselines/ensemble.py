"""Registered grouped out-of-fold Raw-G stacking contract."""

from __future__ import annotations

from collections.abc import Iterable

BASE_CONSTITUENTS = ("G01-LOGREG", "G03-GBDT", "G04-MLP", "G05-SEQUENCE", "G06-GRAPH")
META_GRID = tuple({"C": value} for value in (0.01, 0.1, 1.0, 10.0))
GROUPED_FOLDS = 5
GROUP_SEEDS = (101, 211, 307)


def grouped_fold_assignments(group_ids: Iterable[str], *, folds: int = GROUPED_FOLDS) -> dict[str, int]:
    groups = sorted(set(group_ids))
    if len(groups) < folds:
        raise ValueError("stacking requires at least one atomic group per fold")
    return {group_id: index % folds for index, group_id in enumerate(groups)}


def assert_out_of_fold(rows: Iterable[tuple[str, int, int]]) -> None:
    """Reject meta-features made by a base model trained on the same group fold."""

    for group_id, training_fold, prediction_fold in rows:
        if training_fold == prediction_fold:
            raise ValueError(f"in-fold ensemble prediction for group {group_id}")
