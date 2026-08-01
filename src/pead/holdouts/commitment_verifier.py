"""Phase 11-facing adapter to the single neutral custody contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pead.custody.consumer import phase11_preflight
from pead.holdouts.interface import PublicPreflightReceipt, SealedHoldoutPaths


def verify_preseal(
    *,
    repo_root: Path,
    custody_root: Path,
    paths: SealedHoldoutPaths,
    study_version: str,
    preseal_id: str,
) -> tuple[PublicPreflightReceipt, dict[str, Any]]:
    result = phase11_preflight(
        repo_root=repo_root,
        commitment_path=paths.commitment,
        index_path=paths.ciphertext_index,
        event_log_path=paths.signed_event_log,
        one_shot_state_path=paths.one_shot_state,
        expected_study=study_version,
        expected_preseal=preseal_id,
    )
    receipt = PublicPreflightReceipt(
        study_version=study_version,
        preseal_id=preseal_id,
        allocation_sha256=result["allocation_sha256"],
        event_count=result["event_verification"]["event_count"],
        missing_commitments=tuple(result["missing_commitments"]),
        consumer_invented_values=tuple(result["consumer_invented_values"]),
    )
    return receipt, result
