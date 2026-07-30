from __future__ import annotations

import io
import unittest

from pead.config.console import ResearchConsole
from pead.core.runner import (
    RunnerContractError,
    SealedProjection,
    run_committed_case,
)
from pead.core.types import WorldState
from tests.phase1_fixtures import (
    authorization_label,
    method_decision,
    predictive_state,
    world_state,
)


class CommitBeforeRevealTests(unittest.TestCase):
    def test_runner_commits_before_reveal_and_is_deterministic_with_frozen_clock(self) -> None:
        projection = SealedProjection.create(
            access_profile="P-only", payload=predictive_state()
        )
        events: list[str] = []

        def method(sealed: SealedProjection):
            events.append("method")
            return method_decision(sealed.projection_hash)

        def reveal(decision_hash: str):
            self.assertEqual(len(decision_hash), 64)
            events.append("reveal")
            return authorization_label()

        kwargs = {
            "projection": projection,
            "method": method,
            "reveal_label": reveal,
            "trace_context": {
                "study_id": "PEAD-MAIN-v1",
                "run_id": "run:" + "a" * 64,
                "config_hash": "b" * 64,
                "commit_hash": "c" * 40,
                "environment_hash": "d" * 64,
                "world_id": world_state().world_id,
                "atomic_group_id": "group-1",
                "split_id": "development_fit",
                "method_id": "P01-LOGREG-v1",
                "budget_id": "low-v1",
            },
            "console": ResearchConsole("1", stream=io.StringIO()),
            "clock": lambda: "2026-07-30T12:00:00.000001+00:00",
        }
        first = run_committed_case(**kwargs)
        second = run_committed_case(**kwargs)
        self.assertEqual(first, second)
        self.assertEqual(events, ["method", "reveal", "method", "reveal"])

    def test_world_state_cannot_be_sealed_or_passed_to_method(self) -> None:
        with self.assertRaises(RunnerContractError):
            SealedProjection.create(
                access_profile="P-only",
                payload=world_state(),  # type: ignore[arg-type]
            )
        with self.assertRaises(RunnerContractError):
            SealedProjection.create(
                access_profile="Raw-G",
                payload=predictive_state(),  # type: ignore[arg-type]
            )

    def test_projection_hash_mismatch_is_rejected_before_reveal(self) -> None:
        projection = SealedProjection.create(
            access_profile="P-only", payload=predictive_state()
        )
        revealed = False

        def reveal(_: str):
            nonlocal revealed
            revealed = True
            return authorization_label()

        with self.assertRaises(RunnerContractError):
            run_committed_case(
                projection=projection,
                method=lambda _: method_decision("0" * 64),
                reveal_label=reveal,
                trace_context={
                    "study_id": "PEAD-MAIN-v1",
                    "run_id": "run:" + "a" * 64,
                    "config_hash": "b" * 64,
                    "commit_hash": "c" * 40,
                    "environment_hash": "d" * 64,
                    "world_id": world_state().world_id,
                    "atomic_group_id": "group-1",
                    "split_id": "development_fit",
                    "method_id": "P01-LOGREG-v1",
                    "budget_id": "low-v1",
                },
                console=ResearchConsole("1", stream=io.StringIO()),
            )
        self.assertFalse(revealed)


if __name__ == "__main__":
    unittest.main()
