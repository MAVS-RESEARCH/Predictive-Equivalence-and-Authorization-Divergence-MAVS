"""Strict loader for the released Phase 2 authorization fixture registry."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from pead.core.types import AuthorizationAction


class FixtureRegistryError(ValueError):
    """Raised when released fixtures are incomplete or malformed."""


REQUIRED_FIXTURE_CLASSES = {
    "positive",
    "negative",
    "boundary",
    "contradictory",
    "temporal",
}
REQUIRED_BENCHMARK_STRATA = {
    "exact",
    "near",
    "reversal",
    "scope",
    "evidence",
    "structural",
    "domain",
}


@dataclass(frozen=True)
class AuthorizationFixture:
    case_id: str
    policy_file: Path
    fixture_class: str
    benchmark_strata: tuple[str, ...]
    expected: AuthorizationAction
    facts: Mapping[str, Any]

    @property
    def serialized_facts(self) -> bytes:
        return json.dumps(
            self.facts,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")


def _set_path(target: dict[str, Any], path: str, value: Any) -> None:
    components = path.split(".")
    current = target
    for component in components[:-1]:
        child = current.get(component)
        if not isinstance(child, dict):
            raise FixtureRegistryError(f"override path does not exist: {path}")
        current = child
    if components[-1] not in current:
        raise FixtureRegistryError(f"override leaf does not exist: {path}")
    current[components[-1]] = copy.deepcopy(value)


def load_fixtures(repo_root: Path) -> tuple[AuthorizationFixture, ...]:
    registry_path = repo_root / "configs/policies/fixtures_v1.yaml"
    try:
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise FixtureRegistryError("cannot load Phase 2 fixture registry") from exc
    if not isinstance(raw, Mapping) or set(raw) != {
        "schema_version",
        "fixture_registry_id",
        "families",
    }:
        raise FixtureRegistryError("fixture registry envelope is invalid")
    if raw["schema_version"] != "1.0" or not isinstance(raw["families"], list):
        raise FixtureRegistryError("fixture registry version or families are invalid")
    fixtures: list[AuthorizationFixture] = []
    seen_cases: set[str] = set()
    family_classes: dict[str, set[str]] = {}
    for family in raw["families"]:
        if not isinstance(family, Mapping) or set(family) != {
            "policy_file",
            "base_facts",
            "cases",
        }:
            raise FixtureRegistryError("fixture family shape is invalid")
        policy_file = Path(str(family["policy_file"]))
        base = family["base_facts"]
        cases = family["cases"]
        if not isinstance(base, Mapping) or not isinstance(cases, list):
            raise FixtureRegistryError("fixture base_facts or cases are invalid")
        classes: set[str] = set()
        for case in cases:
            if not isinstance(case, Mapping) or set(case) != {
                "case_id",
                "fixture_class",
                "benchmark_strata",
                "expected",
                "overrides",
            }:
                raise FixtureRegistryError("fixture case shape is invalid")
            case_id = case["case_id"]
            fixture_class = case["fixture_class"]
            strata = case["benchmark_strata"]
            overrides = case["overrides"]
            if not isinstance(case_id, str) or not case_id or case_id in seen_cases:
                raise FixtureRegistryError("fixture case identities must be unique")
            if fixture_class not in REQUIRED_FIXTURE_CLASSES:
                raise FixtureRegistryError(f"unknown fixture class: {fixture_class}")
            if (
                not isinstance(strata, list)
                or not strata
                or not set(strata) <= REQUIRED_BENCHMARK_STRATA
            ):
                raise FixtureRegistryError(f"invalid benchmark strata: {case_id}")
            if not isinstance(overrides, Mapping):
                raise FixtureRegistryError(f"fixture overrides must be a mapping: {case_id}")
            facts = copy.deepcopy(dict(base))
            for override_path, override_value in overrides.items():
                if not isinstance(override_path, str):
                    raise FixtureRegistryError("override paths must be strings")
                _set_path(facts, override_path, override_value)
            try:
                expected = AuthorizationAction(case["expected"])
            except (ValueError, TypeError) as exc:
                raise FixtureRegistryError(
                    f"invalid expected authorization: {case_id}"
                ) from exc
            fixtures.append(
                AuthorizationFixture(
                    case_id=case_id,
                    policy_file=policy_file,
                    fixture_class=fixture_class,
                    benchmark_strata=tuple(strata),
                    expected=expected,
                    facts=facts,
                )
            )
            seen_cases.add(case_id)
            classes.add(fixture_class)
        family_classes[policy_file.as_posix()] = classes
    if any(classes != REQUIRED_FIXTURE_CLASSES for classes in family_classes.values()):
        raise FixtureRegistryError(
            "every rule family requires positive, negative, boundary, contradictory, "
            "and temporal fixtures"
        )
    observed_strata = {
        stratum for fixture in fixtures for stratum in fixture.benchmark_strata
    }
    if observed_strata != REQUIRED_BENCHMARK_STRATA:
        raise FixtureRegistryError("released fixture strata are incomplete")
    return tuple(fixtures)
