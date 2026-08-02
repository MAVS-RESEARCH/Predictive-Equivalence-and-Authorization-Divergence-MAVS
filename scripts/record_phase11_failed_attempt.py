"""Record the failed pre-materialization v3 custody access as a signed event."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from pead.config.console import ResearchConsole
from pead.custody.contract import sha256_file
from pead.custody.events import SignedEventLog, read_event_log, verify_event_log
from pead.phase11.contracts import atomic_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--custody-root", type=Path, required=True)
    args = parser.parse_args()
    console = ResearchConsole("11")
    state_path = args.custody_root / "state/one_shot_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state["consumed"] or state["materialization_count"] != 0:
        raise ValueError("failed-attempt receipt is valid only before materialization")
    private = serialization.load_pem_private_key((args.custody_root / "keys/phase9a_v3_ed25519_private.pem").read_bytes(), password=None)
    signer = hashlib.sha256(private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).hexdigest()
    event_log = SignedEventLog(args.custody_root / "logs/events.jsonl", study_version="pead-study-v3", preseal_id="phase9a-preseal-v3", private_key=private, signer_identity=signer)
    # STEP LOG P11-INCIDENT-001: Append an individually signed event for the failed source-bundle access before any retry.
    console.log("P11-INCIDENT-001", "Recording the failed pre-materialization custody access in the signed event chain.")
    event = event_log.append(
        "phase11-freeze-v3-755c6311c6f71d9afd7c-failed-attempt-001",
        "authenticated-package-decryption-failed-before-materialization",
        "record",
        {"freeze_id": "phase11-freeze-v3-755c6311c6f71d9afd7c", "failure_class": "custody-consumer-dynamic-module-registration", "design_hashes_verified": 15, "case_generation_started": False, "materialization_started": False, "one_shot_state_consumed": False, "blind_label_revealed": False, "method_executed": False},
    )
    receipt = verify_event_log(read_event_log(args.custody_root / "logs/events.jsonl"), study_version="pead-study-v3", preseal_id="phase9a-preseal-v3", expected_signer_identity=signer)
    value = {
        "schema_version": "1.0",
        "phase": 11,
        "study_version": "pead-study-v3",
        "preseal_id": "phase9a-preseal-v3",
        "failed_freeze_id": "phase11-freeze-v3-755c6311c6f71d9afd7c",
        "status": "failed-closed-before-generation-or-materialization",
        "failure_class": "custody-consumer-dynamic-module-registration",
        "event_sha256": event["event_sha256"],
        "event_sequence": event["sequence"],
        "event_log_head_sha256": receipt["head_sha256"],
        "freeze_manifest_sha256": sha256_file(args.repo_root / "manifests/freeze_manifest.json"),
        "design_artifacts_verified": 15,
        "decryption_attempted": True,
        "case_generation_started": False,
        "materialization_attempted": False,
        "one_shot_state_consumed": False,
        "blind_label_revealed": False,
        "method_executed": False,
        "scientific_design_changed": False,
        "method_or_report_changed": False,
        "required_resolution": "correct-custody-consumer-register-module-run-full-regression-and-issue-superseding-signed-freeze",
    }
    atomic_json(args.repo_root / "results/audits/phase11-prefreeze/failed_attempt_001.json", value)
    # STEP LOG P11-INCIDENT-002: Verify the failure receipt, pristine one-shot state, and signed continuation head.
    console.log("P11-INCIDENT-002", "Failed custody access retained with an unconsumed one-shot state.", status="pass", details={"event_sequence": event["sequence"], "materialization_count": 0})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

