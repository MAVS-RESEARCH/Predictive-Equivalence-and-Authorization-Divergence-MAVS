"""Future Phase 11-compatible public and custody-side preflight consumer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pead.custody.contract import CustodyContractError, verify_public_precommit
from pead.custody.events import read_event_log, verify_event_log


def phase11_preflight(
    *,
    repo_root: Path,
    commitment_path: Path,
    index_path: Path,
    event_log_path: Path,
    one_shot_state_path: Path,
    expected_study: str,
    expected_preseal: str,
) -> dict[str, Any]:
    public = verify_public_precommit(
        repo_root,
        commitment_path,
        index_path,
        expected_study=expected_study,
        expected_preseal=expected_preseal,
    )
    commitment = json.loads(commitment_path.read_text(encoding="utf-8"))
    events = read_event_log(event_log_path)
    event_receipt = verify_event_log(
        events,
        study_version=expected_study,
        preseal_id=expected_preseal,
        expected_signer_identity=commitment["custody_public_key_identity"],
    )
    if event_receipt["genesis_sha256"] != commitment["custody_log_genesis_sha256"]:
        raise CustodyContractError("custody log genesis differs from commitment")
    if event_receipt["head_sha256"] != commitment["custody_log_head_sha256"]:
        raise CustodyContractError("custody log head differs from commitment")
    if event_receipt["event_count"] != commitment["custody_event_count"]:
        raise CustodyContractError("custody event count differs from commitment")
    if not one_shot_state_path.is_file():
        raise CustodyContractError("one-shot state is absent")
    state = json.loads(one_shot_state_path.read_text(encoding="utf-8"))
    if set(state) != {"schema_version", "study_version", "preseal_id", "consumed", "materialization_count"}:
        raise CustodyContractError("one-shot state fields differ from contract")
    if state["study_version"] != expected_study or state["preseal_id"] != expected_preseal:
        raise CustodyContractError("one-shot state study or preseal mismatch")
    if state["consumed"] is not False or state["materialization_count"] != 0:
        raise CustodyContractError("one-shot state has already been consumed")
    return {
        **public,
        "event_verification": event_receipt,
        "one_shot_state_consumed": False,
        "unlock_attempted": False,
        "decryption_attempted": False,
        "materialization_attempted": False,
    }
