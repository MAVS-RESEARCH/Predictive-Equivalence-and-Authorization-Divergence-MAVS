"""Validate and submit a Phase 11 custody unlock request without exposing hidden content."""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from pead.config.console import ResearchConsole
from pead.holdouts.commitment_verifier import verify_preseal
from pead.phase11.contracts import (
    Phase11ContractError,
    sha256_file,
    verify_file_inventory,
    verify_materialization_precommit,
    verify_signed_mapping,
)


def verify_custody_design_hashes(custody_workspace: Path, commitment: dict[str, Any]) -> dict[str, Any]:
    verified = []
    root = custody_workspace.resolve()
    for artifact in commitment["design_artifacts"]:
        path = (root / artifact["artifact_id"]).resolve()
        if root not in path.parents or not path.is_file():
            raise Phase11ContractError(f"custody design artifact is absent or escapes custody: {artifact['artifact_id']}")
        if sha256_file(path) != artifact["sha256"] or path.stat().st_size != artifact["bytes"]:
            raise Phase11ContractError(f"custody design artifact identity mismatch: {artifact['artifact_id']}")
        verified.append(artifact["artifact_id"])
    return {"status": "pass", "verified_artifacts": len(verified), "mismatches": 0}


def _run_custody_verifier(repo_root: Path, custody_workspace: Path, freeze: dict[str, Any]) -> dict[str, Any]:
    operator = custody_workspace / "phase11_verify.py"
    expected = freeze["custody_operator"]
    if not operator.is_file() or sha256_file(operator) != expected["sha256"] or operator.stat().st_size != expected["bytes"]:
        raise Phase11ContractError("custody verification operator differs from the signed freeze")
    completed = subprocess.run(
        [sys.executable, str(operator), "--custody-root", str(custody_workspace), "--commitment", str(repo_root / "manifests/custody/holdout_design_commitment.json"), "--freeze-id", freeze["freeze_id"]],
        check=False,
        capture_output=True,
        text=True,
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if completed.returncode or not lines:
        raise Phase11ContractError("custody design verifier failed without a valid receipt")
    receipt = json.loads(lines[-1])
    if receipt.get("status") != "pass" or not receipt.get("custody_event_signed"):
        raise Phase11ContractError("custody design verification or signed access logging failed")
    event = receipt.get("custody_event")
    if not isinstance(event, dict):
        raise Phase11ContractError("custody verifier omitted the signed access event")
    hashed = dict(event)
    observed_event_hash = hashed.pop("event_sha256", None)
    if hashlib.sha256(json.dumps(hashed, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest() != observed_event_hash:
        raise Phase11ContractError("custody event hash verification failed")
    signed = dict(event)
    signed.pop("event_sha256", None)
    signature = signed.pop("signature", None)
    commitment = json.loads((repo_root / "manifests/custody/holdout_design_commitment.json").read_text(encoding="utf-8"))
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(commitment["signature"]["public_key_b64"], validate=True)).verify(
            base64.b64decode(signature["signature_b64"], validate=True),
            json.dumps(signed, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        )
    except (InvalidSignature, ValueError, TypeError, KeyError) as exc:
        raise Phase11ContractError("custody access-event signature verification failed") from exc
    return receipt


def preflight_unlock(repo_root: Path, freeze_manifest: Path, custody_workspace: Path, console: ResearchConsole) -> dict[str, Any]:
    # STEP LOG P11-UNLOCK-001: Verify the signed freeze and all frozen artifacts before any custody request.
    console.log("P11-UNLOCK-001", "Verifying the signed method freeze before custody submission.")
    freeze = json.loads(freeze_manifest.read_text(encoding="utf-8"))
    verify_signed_mapping(freeze)
    verify_file_inventory(repo_root, freeze["frozen_file_inventory"])
    # STEP LOG P11-UNLOCK-002: Reverify the Phase 9A signature, public hashes, and ciphertext identities at the unlock boundary.
    console.log("P11-UNLOCK-002", "Reverifying Phase 9A identities at the custody boundary.")
    receipt = verify_preseal(repo_root)
    if receipt.preseal_id != freeze["phase9a_preseal_id"]:
        raise Phase11ContractError("freeze and custody preseal identities differ")
    commitment_path = repo_root / "manifests/custody/holdout_design_commitment.json"
    index_path = repo_root / "manifests/custody/encrypted_blind_package.index.json"
    if sha256_file(commitment_path) != freeze["phase9a_commitment_sha256"]:
        raise Phase11ContractError("Phase 9A design commitment changed after freeze")
    if sha256_file(index_path) != freeze["encrypted_package_index_sha256"]:
        raise Phase11ContractError("encrypted package index changed after freeze")
    commitment = json.loads(commitment_path.read_text(encoding="utf-8"))
    # STEP LOG P11-UNLOCK-002A: Rehash every committed custody-only design artifact without exposing its bytes or scientific content.
    console.log("P11-UNLOCK-002A", "Verifying custody-only design artifact identities in place.", details={"artifacts": len(commitment["design_artifacts"])})
    custody_design = _run_custody_verifier(repo_root, custody_workspace, freeze)
    # STEP LOG P11-UNLOCK-003: Require signed plaintext identities, counts, bank allocations, and allocation binding before decryption.
    console.log("P11-UNLOCK-003", "Validating that Phase 9A precommitted every materialization cross-check.")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    allocation_path = repo_root / "manifests/allocations/final_claim_bank_v1.json"
    preflight_errors = []
    readiness = None
    try:
        readiness = verify_materialization_precommit(index, sha256_file(allocation_path))
    except Phase11ContractError as exc:
        preflight_errors.append(str(exc))
    prior_log = custody_design["prior_log_audit"]
    if prior_log["unsigned_events"]:
        preflight_errors.append(f"custody access log contains {prior_log['unsigned_events']} unsigned pre-Phase11 events")
    if prior_log["hash_chain_status"] != "pass":
        preflight_errors.append("custody access log hash chain is invalid")
    if preflight_errors:
        error = Phase11ContractError("; ".join(preflight_errors))
        error.custody_design = custody_design  # type: ignore[attr-defined]
        raise error
    # STEP LOG P11-UNLOCK-004: Authorize exactly one custody submission only after every fail-closed precondition passes.
    console.log("P11-UNLOCK-004", "Custody unlock request is eligible for one-shot submission.", status="pass", details={"freeze_id": freeze["freeze_id"]})
    return {"status": "eligible", "unlock_attempted": False, "freeze_id": freeze["freeze_id"], "readiness": readiness, "custody_design": custody_design}


def blocked_receipt(repo_root: Path, freeze_manifest: Path, custody_workspace: Path, console: ResearchConsole) -> dict[str, Any]:
    try:
        return preflight_unlock(repo_root, freeze_manifest, custody_workspace, console)
    except Exception as exc:
        # STEP LOG P11-UNLOCK-BLOCK: Record the exact pre-unlock failure while preserving ciphertext, keys, and one-shot custody state.
        console.log("P11-UNLOCK-BLOCK", "Custody unlock blocked before decryption or materialization.", status="blocked", details={"error": str(exc), "error_type": type(exc).__name__})
        freeze = json.loads(freeze_manifest.read_text(encoding="utf-8"))
        custody_design = getattr(exc, "custody_design", {"status": "not-reached", "verified_artifacts": 0, "mismatches": 0})
        return {
            "schema_version": "1.0",
            "phase": 11,
            "freeze_id": freeze.get("freeze_id", "unknown"),
            "status": "blocked",
            "unlock_attempted": False,
            "decryption_attempted": False,
            "materialization_attempted": False,
            "one_shot_state_consumed": False,
            "custody_design": custody_design,
            "reason": str(exc),
            "required_resolution": "new-study-version-repeat-phase9a-before-retraining-and-refreeze",
        }
