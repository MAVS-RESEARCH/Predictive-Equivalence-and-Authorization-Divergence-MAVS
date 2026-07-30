"""Shared deterministic access to the released Phase 2 fixtures."""

from __future__ import annotations

from pathlib import Path

from pead.labels.parser import load_policy
from pead.phase2.fixtures import AuthorizationFixture, load_fixtures

REPO_ROOT = Path(__file__).parents[1]


def released_fixtures() -> tuple[AuthorizationFixture, ...]:
    return load_fixtures(REPO_ROOT)


def policy_for(fixture: AuthorizationFixture):
    return load_policy(REPO_ROOT / fixture.policy_file)
