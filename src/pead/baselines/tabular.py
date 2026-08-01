"""Exact registered scikit-learn tabular estimator factories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LOGISTIC_GRID = tuple(
    {"penalty": penalty, "C": value}
    for penalty in ("l1", "l2")
    for value in (1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0, 100.0)
)
TREE_GRID = tuple(
    {"max_depth": depth, "min_samples_leaf": leaf}
    for depth in (4, 8, 16, None)
    for leaf in (1, 10, 50)
)
GBDT_GRID = tuple(
    {"learning_rate": lr, "max_iter": iterations, "max_leaf_nodes": leaves, "l2_regularization": l2}
    for lr in (0.03, 0.1)
    for iterations in (200, 500)
    for leaves in (15, 31)
    for l2 in (0.0, 1.0)
)


@dataclass(frozen=True)
class TabularPreprocessingContract:
    numeric_imputation: str = "development_fit_median"
    missing_indicators: bool = True
    numeric_scaling: str = "development_fit_standardization"
    categorical_encoding: str = "development_fit_one_hot"
    unknown_category: str = "explicit_unknown"


def build_preprocessor(*, numeric_columns: list[str], categorical_columns: list[str]) -> Any:
    """Build the fit-only median/missing/scale/one-hot pipeline."""

    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    numeric = Pipeline(
        (
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
        )
    )
    categorical = Pipeline(
        (
            ("impute", SimpleImputer(strategy="constant", fill_value="__UNKNOWN__")),
            ("one_hot", OneHotEncoder(handle_unknown="ignore")),
        )
    )
    return ColumnTransformer(
        (("numeric", numeric, numeric_columns), ("categorical", categorical, categorical_columns)),
        remainder="drop",
    )


def build_logistic(*, penalty: str, C: float, seed: int) -> Any:
    from sklearn.linear_model import LogisticRegression
    return LogisticRegression(
        multi_class="multinomial",
        solver="saga",
        penalty=penalty,
        C=C,
        max_iter=5000,
        random_state=seed,
    )


def build_tree(*, max_depth: int | None, min_samples_leaf: int, seed: int) -> Any:
    from sklearn.tree import DecisionTreeClassifier
    return DecisionTreeClassifier(
        criterion="gini",
        splitter="best",
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        ccp_alpha=0.0,
        random_state=seed,
    )


def build_gbdt(*, learning_rate: float, max_iter: int, max_leaf_nodes: int, l2_regularization: float, seed: int, categorical_features: tuple[int, ...] | None = None) -> tuple[Any, Any, Any]:
    from sklearn.ensemble import HistGradientBoostingClassifier
    return tuple(
        HistGradientBoostingClassifier(
            learning_rate=learning_rate,
            max_iter=max_iter,
            max_leaf_nodes=max_leaf_nodes,
            l2_regularization=l2_regularization,
            early_stopping=False,
            categorical_features=categorical_features,
            random_state=seed + class_index,
        )
        for class_index in range(3)
    )


def select_pruning_alpha(candidates: list[tuple[float, float]]) -> float:
    """Select cost-complexity alpha by utility, then the smaller tree alpha."""

    if not candidates:
        raise ValueError("pruning candidates are required")
    return max(candidates, key=lambda item: (item[1], -item[0]))[0]
