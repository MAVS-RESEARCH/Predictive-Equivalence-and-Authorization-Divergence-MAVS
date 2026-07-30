"""Static and runtime audits for Phase 6 visibility boundaries."""

from __future__ import annotations

import ast
import dataclasses
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import yaml

from pead.core.hashing import canonical_hash
from pead.core.types import WorldState
from pead.projections.firewall import AccessProfile, SealedMethodInput
from pead.projections.oracle import ORACLE_FIELD_ACCESSORS
from pead.projections.predictive import PREDICTIVE_FIELD_ACCESSORS
from pead.projections.raw_governance import GOVERNANCE_FIELD_ACCESSORS

FORBIDDEN_METHOD_IMPORT_PREFIXES = (
    "pead.audits",
    "pead.labels",
    "pead.world",
    "pead.projections.oracle",
)
FORBIDDEN_METHOD_SYMBOLS = {
    "AuthorizationLabel",
    "GeneratedWorld",
    "OracleState",
    "WorldState",
    "evaluate_policy",
    "evaluate_reference",
}
FORBIDDEN_METHOD_ATTRIBUTES = {
    "authorization_label",
    "generator_lineage",
    "hidden_label",
    "hidden_mechanism",
    "latent_facts",
    "latent_governance_truth",
    "nuisance_state",
    "oracle_state",
    "split_id",
    "task_truth",
    "world_state",
}


def _profile_field_sets() -> dict[str, tuple[str, ...]]:
    predictive = tuple(PREDICTIVE_FIELD_ACCESSORS)
    governance = tuple(GOVERNANCE_FIELD_ACCESSORS)
    oracle = tuple(ORACLE_FIELD_ACCESSORS)
    return {
        AccessProfile.P_ONLY.value: tuple(sorted(predictive)),
        AccessProfile.RAW_G.value: tuple(sorted((*predictive, *governance))),
        AccessProfile.ORACLE_G.value: tuple(
            sorted((*predictive, *governance, *oracle))
        ),
    }


def validate_access_configs(repo_root: Path) -> dict[str, Any]:
    """Verify access configs implement exactly the frozen dictionary fields."""

    profile_paths = {
        "P-only": repo_root / "configs/access/p_only.yaml",
        "Raw-G": repo_root / "configs/access/raw_g.yaml",
        "Oracle-G": repo_root / "configs/access/oracle_g.yaml",
    }
    expected = _profile_field_sets()
    profiles: dict[str, Any] = {}
    for profile_id, path in profile_paths.items():
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if value.get("profile_id") != profile_id:
            raise ValueError(f"access profile identity mismatch: {path}")
        if tuple(sorted(value.get("visible_field_ids", []))) != expected[profile_id]:
            raise ValueError(f"access field mask differs from frozen IDs: {profile_id}")
        if value.get("truncation_allowed") is not False:
            raise ValueError(f"truncation must be disabled: {profile_id}")
        if value.get("lossy_transformations") != []:
            raise ValueError(f"lossy transformations must be empty: {profile_id}")
        if value.get("back_reference_allowed") is not False:
            raise ValueError(f"WorldState back-reference is not prohibited: {profile_id}")
        renderings = value.get("canonical_renderings")
        if set(renderings or ()) != {
            "canonical-tabular-v1",
            "canonical-sequence-v1",
            "canonical-graph-v1",
        }:
            raise ValueError(f"canonical rendering registry incomplete: {profile_id}")
        profiles[profile_id] = {
            "config": path.relative_to(repo_root).as_posix(),
            "field_count": len(expected[profile_id]),
            "field_mask_sha256": canonical_hash(expected[profile_id]),
            "headline_eligible": value.get("headline_eligible"),
            "lossy_transformations": 0,
            "truncation_allowed": False,
        }
    if profiles["Oracle-G"]["headline_eligible"] is not False:
        raise ValueError("Oracle-G must be excluded from headline comparisons")
    return {
        "status": "pass",
        "profiles": profiles,
        "frozen_predictive_fields": len(PREDICTIVE_FIELD_ACCESSORS),
        "frozen_governance_fields": len(GOVERNANCE_FIELD_ACCESSORS),
        "declared_oracle_fields": len(ORACLE_FIELD_ACCESSORS),
    }


def scan_method_source(path: Path) -> list[dict[str, Any]]:
    """Return fail-closed dependency and hidden-symbol violations."""

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    violations: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
            for name in names:
                if name.startswith(FORBIDDEN_METHOD_IMPORT_PREFIXES):
                    violations.append(
                        {
                            "kind": "forbidden_import",
                            "line": node.lineno,
                            "value": name,
                        }
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(FORBIDDEN_METHOD_IMPORT_PREFIXES):
                violations.append(
                    {
                        "kind": "forbidden_import",
                        "line": node.lineno,
                        "value": module,
                    }
                )
            for alias in node.names:
                if alias.name in FORBIDDEN_METHOD_SYMBOLS:
                    violations.append(
                        {
                            "kind": "forbidden_symbol_import",
                            "line": node.lineno,
                            "value": alias.name,
                        }
                    )
        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_METHOD_ATTRIBUTES:
                violations.append(
                    {
                        "kind": "forbidden_attribute",
                        "line": node.lineno,
                        "value": node.attr,
                    }
                )
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_METHOD_SYMBOLS:
                violations.append(
                    {
                        "kind": "forbidden_symbol",
                        "line": node.lineno,
                        "value": node.id,
                    }
                )
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {
                "eval",
                "exec",
                "globals",
                "locals",
                "vars",
            }:
                violations.append(
                    {
                        "kind": "reflection_bypass",
                        "line": node.lineno,
                        "value": node.func.id,
                    }
                )
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "object"
                and node.func.attr == "__getattribute__"
            ):
                violations.append(
                    {
                        "kind": "reflection_bypass",
                        "line": node.lineno,
                        "value": "object.__getattribute__",
                    }
                )
    return sorted(
        violations,
        key=lambda item: (item["line"], item["kind"], item["value"]),
    )


def scan_method_dependencies(repo_root: Path) -> dict[str, Any]:
    """Scan every present method implementation root."""

    roots = (
        repo_root / "src/pead/baselines",
        repo_root / "src/pead/mavs",
    )
    files = sorted(
        path
        for root in roots
        if root.exists()
        for path in root.rglob("*.py")
    )
    violations = {
        path.relative_to(repo_root).as_posix(): found
        for path in files
        if (found := scan_method_source(path))
    }
    return {
        "status": "pass" if not violations else "fail",
        "files_scanned": len(files),
        "roots": [
            root.relative_to(repo_root).as_posix()
            for root in roots
            if root.exists()
        ],
        "violations": violations,
    }


def assert_no_hidden_back_reference(value: Any) -> None:
    """Reject hidden world/truth objects anywhere in a sealed method input."""

    visited: set[int] = set()

    def visit(item: Any) -> None:
        identity = id(item)
        if identity in visited:
            return
        visited.add(identity)
        if isinstance(item, WorldState):
            raise ValueError("sealed method input retains a WorldState back-reference")
        if dataclasses.is_dataclass(item):
            if type(item) is not SealedMethodInput:
                raise ValueError(
                    f"sealed method input retains dataclass {type(item).__name__}"
                )
            for field in dataclasses.fields(item):
                visit(getattr(item, field.name))
            return
        if isinstance(item, Mapping):
            for key, member in item.items():
                visit(key)
                visit(member)
            return
        if isinstance(item, (tuple, list, set, frozenset)):
            for member in item:
                visit(member)

    visit(value)


def field_method_matrix(
    traces_by_method: Mapping[str, Iterable[Any]],
) -> dict[str, Any]:
    """Prove every Raw-G method/representation receives identical facts."""

    normalized = {
        method_id: tuple(traces)
        for method_id, traces in traces_by_method.items()
    }
    if not normalized:
        raise ValueError("field-method matrix requires methods")
    methods = tuple(sorted(normalized))
    denominators = {method: len(normalized[method]) for method in methods}
    if len(set(denominators.values())) != 1:
        raise ValueError("field-method matrix case denominators differ")
    case_count = next(iter(denominators.values()))
    if case_count == 0:
        raise ValueError("field-method matrix may not be vacuous")
    reference = normalized[methods[0]]
    field_ids = reference[0].field_mask
    mismatches: list[dict[str, Any]] = []
    cells: dict[str, dict[str, str]] = {}
    for field_id in field_ids:
        cells[field_id] = {}
        for method in methods:
            digest = canonical_hash(
                tuple(trace.field_hashes[field_id] for trace in normalized[method])
            )
            cells[field_id][method] = digest
        if len(set(cells[field_id].values())) != 1:
            mismatches.append(
                {"field_id": field_id, "method_hashes": cells[field_id]}
            )
    for case_index in range(case_count):
        hashes = {
            normalized[method][case_index].semantic_fact_hash
            for method in methods
        }
        if len(hashes) != 1:
            mismatches.append(
                {"case_index": case_index, "semantic_fact_hashes": sorted(hashes)}
            )
    return {
        "status": "pass" if not mismatches else "fail",
        "methods": list(methods),
        "fields": list(field_ids),
        "case_count": case_count,
        "matrix_cells": len(field_ids) * len(methods),
        "field_method_hashes": cells,
        "mismatches": mismatches,
    }
