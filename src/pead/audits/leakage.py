"""Static and empirical predictive-only authorization leakage audits."""

from __future__ import annotations

import ast
import math
import random
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pead.core.hashing import canonical_hash
from pead.core.types import AuthorizationAction, PredictiveState


class LeakageAuditError(ValueError):
    """Raised when source or empirical leakage exceeds a frozen gate."""


LABEL_ORDER = (
    AuthorizationAction.ACCEPT,
    AuthorizationAction.REJECT,
    AuthorizationAction.ESCALATE,
)


@dataclass(frozen=True)
class LeakageSample:
    features: tuple[float, ...]
    sequence_signature: str
    graph_signature: str
    label: AuthorizationAction
    atomic_group_id: str
    split_id: str


def sample_from_predictive(
    state: PredictiveState,
    label: AuthorizationAction,
    atomic_group_id: str,
    split_id: str,
) -> LeakageSample:
    features = (
        *tuple(float(value) for value in state.shared_representation),
        *tuple(float(value) for value in state.specialist_outputs),
        *tuple(float(value) for value in state.signed_support),
        float(state.confidence),
        float(state.uncertainty),
    )
    return LeakageSample(
        features=features,
        sequence_signature=canonical_hash(
            {
                "predicted_label": state.predicted_label,
                "agreement": state.agreement,
                "candidate_action": state.candidate_action,
            }
        ),
        graph_signature=canonical_hash(state.calibration),
        label=label,
        atomic_group_id=atomic_group_id,
        split_id=split_id,
    )


def audit_generator_sources(repo_root: Path) -> dict[str, Any]:
    generator_paths = (
        repo_root / "src/pead/world/generator_primary.py",
        repo_root / "src/pead/world/generator_reference.py",
    )
    violations: list[str] = []
    source_hashes: dict[str, str] = {}
    for path in generator_paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        source_hashes[path.name] = canonical_hash(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (
                (node.module or "").startswith("pead.labels")
                or (node.module or "") == "pead.world.generator_primary"
            ):
                violations.append(f"{path.name}:{node.lineno}:forbidden-import")
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in {label.value for label in LABEL_ORDER}:
                    violations.append(f"{path.name}:{node.lineno}:terminal-label")
    schema_source = (
        repo_root / "src/pead/world/schema.py"
    ).read_text(encoding="utf-8")
    schema_tree = ast.parse(schema_source)
    schema_fields = {
        target.id
        for node in ast.walk(schema_tree)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        for target in (node.target,)
    }
    prohibited_fields = sorted(
        field
        for field in schema_fields
        if "authorization_label" in field or field in {"label", "target", "outcome"}
    )
    if violations or prohibited_fields:
        raise LeakageAuditError(
            f"generator source leakage: {violations}; schema={prohibited_fields}"
        )
    return {
        "status": "pass",
        "generator_source_hashes": source_hashes,
        "forbidden_import_or_terminal_label_violations": violations,
        "prohibited_generator_schema_fields": prohibited_fields,
        "separate_primary_reference_sources": (
            source_hashes["generator_primary.py"]
            != source_hashes["generator_reference.py"]
        ),
    }


def _majority(samples: Sequence[LeakageSample]) -> AuthorizationAction:
    counts = Counter(sample.label for sample in samples)
    return max(LABEL_ORDER, key=lambda label: (counts[label], -LABEL_ORDER.index(label)))


def _nearest_centroid(
    train: Sequence[LeakageSample],
    test: Sequence[LeakageSample],
) -> list[AuthorizationAction]:
    dimensions = len(train[0].features)
    sums = {label: [0.0] * dimensions for label in LABEL_ORDER}
    counts = Counter(sample.label for sample in train)
    for sample in train:
        for index, value in enumerate(sample.features):
            sums[sample.label][index] += value
    centroids = {
        label: tuple(value / max(counts[label], 1) for value in sums[label])
        for label in LABEL_ORDER
    }
    return [
        min(
            LABEL_ORDER,
            key=lambda label: (
                sum(
                    (value - center) ** 2
                    for value, center in zip(sample.features, centroids[label])
                ),
                LABEL_ORDER.index(label),
            ),
        )
        for sample in test
    ]


def _decision_stump(
    train: Sequence[LeakageSample],
    test: Sequence[LeakageSample],
) -> list[AuthorizationAction]:
    majority = _majority(train)
    best = (0.0, 0, majority, majority)
    for feature_index in range(len(train[0].features)):
        values = sorted({sample.features[feature_index] for sample in train})
        if len(values) < 2:
            continue
        thresholds = [
            (left + right) / 2.0 for left, right in zip(values, values[1:])
        ]
        for threshold in thresholds:
            below = [
                sample for sample in train
                if sample.features[feature_index] <= threshold
            ]
            above = [
                sample for sample in train
                if sample.features[feature_index] > threshold
            ]
            left_label = _majority(below) if below else majority
            right_label = _majority(above) if above else majority
            correct = sum(
                (
                    left_label
                    if sample.features[feature_index] <= threshold
                    else right_label
                )
                is sample.label
                for sample in train
            )
            candidate = (correct / len(train), feature_index, left_label, right_label)
            if candidate[0] > best[0]:
                best = candidate
                best_threshold = threshold
    if best[0] == 0.0:
        return [majority] * len(test)
    return [
        best[2] if sample.features[best[1]] <= best_threshold else best[3]
        for sample in test
    ]


def _signature_model(
    train: Sequence[LeakageSample],
    test: Sequence[LeakageSample],
    field: str,
) -> list[AuthorizationAction]:
    majority = _majority(train)
    groups: dict[str, list[LeakageSample]] = defaultdict(list)
    for sample in train:
        groups[getattr(sample, field)].append(sample)
    lookup = {key: _majority(values) for key, values in groups.items()}
    return [lookup.get(getattr(sample, field), majority) for sample in test]


def _nearest_neighbor(
    train: Sequence[LeakageSample],
    test: Sequence[LeakageSample],
) -> list[AuthorizationAction]:
    unique: dict[tuple[float, ...], list[LeakageSample]] = defaultdict(list)
    for sample in train:
        unique[sample.features].append(sample)
    prototypes = [
        (features, _majority(group)) for features, group in sorted(unique.items())
    ]
    return [
        min(
            prototypes,
            key=lambda prototype: (
                sum(
                    (value - candidate) ** 2
                    for value, candidate in zip(sample.features, prototype[0])
                ),
                LABEL_ORDER.index(prototype[1]),
            ),
        )[1]
        for sample in test
    ]


def empirical_leakage_audit(
    samples: Sequence[LeakageSample],
    *,
    seed: int,
    permutations: int,
    frozen_upper: float,
) -> dict[str, Any]:
    train_roles = {"development_fit", "development_selection"}
    train = [sample for sample in samples if sample.split_id in train_roles]
    test = [sample for sample in samples if sample.split_id == "public_validation"]
    train_groups = {sample.atomic_group_id for sample in train}
    test_groups = {sample.atomic_group_id for sample in test}
    overlap = train_groups & test_groups
    if not train or not test or overlap:
        raise LeakageAuditError(
            f"invalid grouped leakage split; train={len(train)}; "
            f"test={len(test)}; overlap={len(overlap)}"
        )
    predictions = {
        "linear": _nearest_centroid(train, test),
        "gbdt": _decision_stump(train, test),
        "sequence": _signature_model(
            train, test, "sequence_signature"
        ),
        "graph": _signature_model(train, test, "graph_signature"),
        "nearest_neighbor": _nearest_neighbor(train, test),
    }
    actual = [sample.label for sample in test]
    accuracies = {
        name: sum(pred is truth for pred, truth in zip(values, actual)) / len(test)
        for name, values in predictions.items()
    }
    rng = random.Random(seed)
    pooled_null: list[float] = []
    shuffled = list(actual)
    for _ in range(permutations):
        rng.shuffle(shuffled)
        for values in predictions.values():
            pooled_null.append(
                sum(pred is truth for pred, truth in zip(values, shuffled))
                / len(test)
            )
    pooled_null.sort()
    permutation_p99 = pooled_null[
        min(math.ceil(0.99 * len(pooled_null)) - 1, len(pooled_null) - 1)
    ]
    failures = {
        name: accuracy
        for name, accuracy in accuracies.items()
        if accuracy > frozen_upper
    }
    if failures:
        raise LeakageAuditError(
            f"predictive-only leakage exceeds {frozen_upper}: {failures}"
        )
    return {
        "schema_version": "1.0",
        "status": "pass",
        "train_worlds": len(train),
        "test_worlds": len(test),
        "train_atomic_groups": len(train_groups),
        "test_atomic_groups": len(test_groups),
        "group_overlap": len(overlap),
        "adversary_accuracy": accuracies,
        "frozen_accuracy_upper_band": frozen_upper,
        "permutation_seed": seed,
        "permutations": permutations,
        "pooled_prediction_permutation_p99": permutation_p99,
        "failures": failures,
    }
