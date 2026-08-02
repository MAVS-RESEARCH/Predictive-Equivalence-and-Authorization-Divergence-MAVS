"""Construct and verify the final signed Phase 11 method freeze."""

from __future__ import annotations

import base64
import hashlib
import json
import platform
import sys
from importlib.metadata import distributions
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization

from pead.config.console import ResearchConsole
from pead.custody.contract import canonical_bytes, sha256_file
from pead.custody.consumer import phase11_preflight
from pead.custody.events import read_event_log, verify_event_log
from pead.phase11.contracts import atomic_json, inventory_rows, verify_file_inventory, verify_signed_mapping


PHASE11_CODE = (
    "src/pead/phase11/__init__.py",
    "src/pead/phase11/contracts.py",
    "src/pead/phase11/freeze.py",
    "src/pead/phase11/materialize.py",
    "src/pead/phase11/audit.py",
    "src/pead/phase11/test_runner.py",
    "scripts/freeze_phase11.py",
    "scripts/materialize_phase11.py",
    "scripts/audit_phase11.py",
    "scripts/run_phase11_tests.py",
    "scripts/run_phase11.py",
    "scripts/correct_phase11_freeze_candidate.py",
    "scripts/record_phase11_failed_attempt.py",
    "tests/unit/test_phase11_freeze.py",
    "tests/integration/test_phase11_materialization.py",
    "tests/stress/test_phase11_stress.py",
)


def _candidate_mapping(candidate: dict[str, Any]) -> dict[str, str]:
    entries = candidate.get("claim_relevant_files")
    if not isinstance(entries, dict) or not entries:
        raise ValueError("Phase 10 freeze-candidate inventory has an unexpected representation")
    return {str(path): str(digest) for path, digest in entries.items()}


def _is_transient(relative: str) -> bool:
    path = Path(relative)
    return relative.endswith(".pyc") or "__pycache__" in path.parts or ".pytest_cache" in path.parts or "tmp" in path.parts


def _environment() -> dict[str, Any]:
    packages = sorted(
        ({"name": (item.metadata.get("Name") or "unknown").lower(), "version": item.version} for item in distributions()),
        key=lambda row: (row["name"], row["version"]),
    )
    return {
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "installed_packages": packages,
    }


def build_freeze(repo_root: Path, custody_root: Path, console: ResearchConsole) -> dict[str, Any]:
    """Verify the candidate, remove transient build products, and sign the final freeze."""

    repo_root = repo_root.resolve()
    candidate_path = repo_root / "manifests/freeze_candidate_v1.json"
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    mapping = _candidate_mapping(candidate)
    # STEP LOG P11-FREEZE-001: Verify every nontransient Phase 10 candidate byte before constructing the authoritative freeze.
    console.log("P11-FREEZE-001", "Verifying every nontransient Phase 10 freeze-candidate identity.", details={"candidate_entries": len(mapping)})
    transient = sorted(path for path in mapping if _is_transient(path))
    mutable_ledgers = ["manifests/lineage/pead-study-v3.json"]
    cleaned = {path: digest for path, digest in mapping.items() if path not in transient and path not in mutable_ledgers}
    verify_file_inventory(repo_root, inventory_rows(cleaned, repo_root))
    transient_state = []
    for relative in transient:
        path = repo_root / relative
        transient_state.append({"path": relative, "candidate_sha256": mapping[relative], "present": path.is_file(), "current_sha256": sha256_file(path) if path.is_file() else None, "candidate_match": path.is_file() and sha256_file(path) == mapping[relative]})
    # STEP LOG P11-FREEZE-002: Record and exclude ignored bytecode and cache products from the signed scientific freeze.
    console.log("P11-FREEZE-002", "Excluding non-source transient build products from the final freeze.", details={"excluded_files": len(transient)})
    correction = {
        "schema_version": "1.0",
        "phase": 11,
        "study_version": "pead-study-v3",
        "preseal_id": "phase9a-preseal-v3",
        "status": "corrected-before-final-freeze-and-before-unlock",
        "phase10_candidate_manifest_identity_retained": True,
        "phase10_nontransient_inventory_verified": True,
        "excluded_class": ["*.pyc", "**/__pycache__/**", ".pytest_cache", "tmp"],
        "excluded_count": len(transient),
        "excluded_paths": transient,
        "transient_state_at_final_freeze": transient_state,
        "mutable_execution_ledgers_excluded_from_method_freeze": mutable_ledgers,
        "mutable_execution_ledger_starting_hashes": {path: mapping[path] for path in mutable_ledgers},
        "scientific_files_changed": 0,
        "method_or_report_files_changed": 0,
        "blind_access_occurred": False,
    }
    correction_path = repo_root / "results/audits/phase11-prefreeze/transient_candidate_correction.json"
    candidate_correction_path = repo_root / "results/audits/phase11-prefreeze/phase10_candidate_correction.json"
    if not candidate_correction_path.is_file():
        raise FileNotFoundError("Phase 10 transient candidate correction receipt is absent")
    correction["phase10_candidate_correction_receipt_sha256"] = sha256_file(candidate_correction_path)
    atomic_json(correction_path, correction)
    cleaned[correction_path.relative_to(repo_root).as_posix()] = sha256_file(correction_path)
    cleaned[candidate_correction_path.relative_to(repo_root).as_posix()] = sha256_file(candidate_correction_path)
    for relative in PHASE11_CODE:
        path = repo_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"required Phase 11 control file is absent: {relative}")
        cleaned[relative] = sha256_file(path)
    prefreeze_tests = repo_root / "results/audits/phase11-prefreeze-tests.json"
    if not prefreeze_tests.is_file():
        raise FileNotFoundError("complete pre-freeze regression evidence is absent")
    cleaned[prefreeze_tests.relative_to(repo_root).as_posix()] = sha256_file(prefreeze_tests)
    # STEP LOG P11-FREEZE-003: Reverify Phase 9A signatures, ciphertexts, counts, allocation, and pristine one-shot state.
    console.log("P11-FREEZE-003", "Reverifying the corrected Phase 9A preseal at the final freeze boundary.")
    preflight = phase11_preflight(
        repo_root=repo_root,
        commitment_path=repo_root / "manifests/custody/holdout_design_commitment.json",
        index_path=repo_root / "manifests/custody/encrypted_blind_package.index.json",
        event_log_path=repo_root / "manifests/custody/phase9a-preseal-v3.custody-events.jsonl",
        one_shot_state_path=custody_root / "state/one_shot_state.json",
        expected_study="pead-study-v3",
        expected_preseal="phase9a-preseal-v3",
    )
    public_events = read_event_log(repo_root / "manifests/custody/phase9a-preseal-v3.custody-events.jsonl")
    external_events = read_event_log(custody_root / "logs/events.jsonl")
    if external_events[: len(public_events)] != public_events:
        raise ValueError("external custody continuation does not retain the exact Phase 9A prefix")
    continuation_receipt = verify_event_log(external_events, study_version="pead-study-v3", preseal_id="phase9a-preseal-v3")
    allowed_continuation_actions = {"authenticated-package-decryption-failed-before-materialization"}
    if not {row["action"] for row in external_events[len(public_events):]}.issubset(allowed_continuation_actions):
        raise ValueError("pre-freeze custody continuation contains an unauthorized action")
    failed_attempt_path = repo_root / "results/audits/phase11-prefreeze/failed_attempt_001.json"
    failed_freeze_path = repo_root / "results/audits/phase11-prefreeze/failed_freeze_manifest_001.json"
    if failed_attempt_path.is_file() or failed_freeze_path.is_file():
        if not (failed_attempt_path.is_file() and failed_freeze_path.is_file()):
            raise FileNotFoundError("failed-attempt evidence is incomplete")
        cleaned[failed_attempt_path.relative_to(repo_root).as_posix()] = sha256_file(failed_attempt_path)
        cleaned[failed_freeze_path.relative_to(repo_root).as_posix()] = sha256_file(failed_freeze_path)
        final_rows = inventory_rows(cleaned, repo_root)
    final_rows = inventory_rows(cleaned, repo_root)
    private = serialization.load_pem_private_key((custody_root / "keys/phase9a_v3_ed25519_private.pem").read_bytes(), password=None)
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    signer_identity = hashlib.sha256(public).hexdigest()
    body: dict[str, Any] = {
        "schema_version": "3.0",
        "phase": 11,
        "study_version": "pead-study-v3",
        "preseal_id": "phase9a-preseal-v3",
        "status": "method-freeze-signed",
        "signer_identity": signer_identity,
        "phase9_anchor_sha": "be093b5d2639deb2ff76ad96785c918b5a2a9b92",
        "phase9a_commitment_sha256": sha256_file(repo_root / "manifests/custody/holdout_design_commitment.json"),
        "phase9a_inventory_sha256": sha256_file(repo_root / "manifests/custody/holdout_design_inventory.json"),
        "phase9a_event_log_sha256": sha256_file(repo_root / "manifests/custody/phase9a-preseal-v3.custody-events.jsonl"),
        "phase10_candidate_sha256": sha256_file(candidate_path),
        "phase10_candidate_correction_sha256": sha256_file(candidate_correction_path),
        "phase10_candidate_manifest_content_sha256": candidate["manifest_content_sha256"],
        "lineage_pre_phase11_sha256": mapping["manifests/lineage/pead-study-v3.json"],
        "preflight": preflight,
        "pre_freeze_custody_continuation": continuation_receipt,
        "transient_correction_sha256": sha256_file(correction_path),
        "frozen_file_inventory": final_rows,
        "environment": _environment(),
        "frozen_surfaces": {
            "code": True,
            "configs": True,
            "environment": True,
            "truth_engines": True,
            "projections": True,
            "metrics": True,
            "audits": True,
            "methods": True,
            "checkpoints": True,
            "hyperparameters": True,
            "prompts": True,
            "operating_points": True,
            "report_templates": True,
        },
        "post_freeze_change_policy": "new-study-version-and-complete-dependent-regeneration",
    }
    body["freeze_id"] = "phase11-freeze-v3-" + hashlib.sha256(canonical_bytes(body)).hexdigest()[:20]
    body["signature"] = {
        "algorithm": "Ed25519",
        "public_key_b64": base64.b64encode(public).decode("ascii"),
        "signature_b64": base64.b64encode(private.sign(canonical_bytes(body))).decode("ascii"),
        "signer_identity": signer_identity,
    }
    freeze_path = repo_root / "manifests/freeze_manifest.json"
    atomic_json(freeze_path, body)
    # STEP LOG P11-FREEZE-004: Verify the custody signature and every final frozen byte before permitting unlock.
    console.log("P11-FREEZE-004", "Verifying the signed authoritative freeze and its complete file inventory.", details={"freeze_id": body["freeze_id"], "files": len(final_rows)})
    verify_signed_mapping(body, signer_identity)
    verify_file_inventory(repo_root, final_rows)
    # STEP LOG P11-FREEZE-005: Close the method and reporting surface under the new-study-version mutation policy.
    console.log("P11-FREEZE-005", "Authoritative Phase 11 method freeze accepted.", status="pass", details={"freeze_id": body["freeze_id"]})
    return body
