"""Deterministic non-claim-bearing producer-consumer custody rehearsal."""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pead.config.console import ResearchConsole
from pead.custody.consumer import phase11_preflight
from pead.custody.contract import (
    COMMITMENT_FIELDS,
    PACKAGE_FIELDS,
    CustodyContractError,
    canonical_bytes,
    sha256_bytes,
    validate_commitment,
    validate_index,
)
from pead.custody.events import read_event_log, verify_event_log
from pead.custody.invariance import FRESH_IDENTITIES, assert_identity_freshness
from pead.custody.materializer import materialize_once
from pead.custody.producer import produce_preseal


def _synthetic_counts() -> dict[str, Any]:
    return {
        "total_records": 12,
        "per_bank": {"structural": 4, "domains": 4, "final_blind": 4},
        "per_track": {"exact": 3, "near": 3, "reversal": 2, "scope": 2, "evidence": 2},
        "per_bank_track": {
            "structural": {"exact": 1, "near": 1, "reversal": 0, "scope": 1, "evidence": 1},
            "domains": {"exact": 1, "near": 1, "reversal": 1, "scope": 0, "evidence": 1},
            "final_blind": {"exact": 1, "near": 1, "reversal": 1, "scope": 1, "evidence": 0},
        },
    }


def _expect_rejection(mutation_id: str, operation: Callable[[], Any]) -> dict[str, Any]:
    try:
        operation()
    except Exception as exc:
        return {"mutation_id": mutation_id, "expected": "reject", "observed": "reject", "status": "pass", "error_type": type(exc).__name__}
    return {"mutation_id": mutation_id, "expected": "reject", "observed": "accept", "status": "fail", "error_type": None}


def _mutated_commitment_check(commitment: dict[str, Any], mutate: Callable[[dict[str, Any]], None]) -> None:
    value = copy.deepcopy(commitment)
    mutate(value)
    validate_commitment(value, expected_study="synthetic-study-v3", expected_preseal="synthetic-preseal-v3")


def _mutated_index_check(index: dict[str, Any], mutate: Callable[[dict[str, Any]], None]) -> None:
    value = copy.deepcopy(index)
    mutate(value)
    validate_index(value, expected_study="synthetic-study-v3", expected_preseal="synthetic-preseal-v3")


def run_synthetic_rehearsal(output_path: Path, console: ResearchConsole) -> dict[str, Any]:
    temp_root = Path(tempfile.mkdtemp(prefix="pead-v3-synthetic-"))
    repo_root = temp_root / "development"
    custody_root = temp_root / "custody"
    repo_root.mkdir()
    custody_root.mkdir()
    signing_key = Ed25519PrivateKey.from_private_bytes(sha256_bytes(b"pead-v3-synthetic-ed25519").encode("ascii")[:32])
    encryption_key = bytes.fromhex(sha256_bytes(b"pead-v3-synthetic-aes256"))
    signer_identity = sha256_bytes(signing_key.public_key().public_bytes_raw())
    allocation_sha256 = sha256_bytes(canonical_bytes({"allocation": "synthetic-only-v3", "records": 12}))
    role_records = {
        "content": [
            {"case_id": f"SYN-{index:03d}", "bank": ("structural", "domains", "final_blind")[index % 3], "track": ("exact", "near", "reversal", "scope", "evidence")[index % 5], "visible": {"x": index}, "evaluator_hidden_fact": index * 7}
            for index in range(12)
        ],
        "labels": [{"case_id": f"SYN-{index:03d}", "label": ("Accept", "Reject", "Escalate")[index % 3]} for index in range(12)],
        "seeds": [{"seed_family": family, "values": [ordinal * 101 + offset for offset in range(4)]} for ordinal, family in enumerate(("structural", "domain", "cross_product"), start=1)],
    }
    state_path = custody_root / "one_shot_state.json"
    state_path.write_bytes(canonical_bytes({"schema_version": "3.0", "study_version": "synthetic-study-v3", "preseal_id": "synthetic-preseal-v3", "consumed": False, "materialization_count": 0}) + b"\n")
    clock_counter = iter(range(1, 20))
    clock = lambda: f"2026-01-01T00:00:{next(clock_counter):02d}Z"
    artifact_dir = repo_root / "artifacts" / "synthetic"
    index_path = repo_root / "manifests" / "synthetic.index.json"
    commitment_path = repo_root / "manifests" / "synthetic.commitment.json"
    event_path = custody_root / "events.jsonl"
    # STEP LOG P9A-V3-SYN-001: Produce deterministic non-claim-bearing content, label, and seed packages with the production Phase 9A contract.
    console.log("P9A-V3-SYN-001", "Producing the isolated synthetic custody packages.")
    produced = produce_preseal(
        repo_root=repo_root,
        custody_root=custody_root,
        study_version="synthetic-study-v3",
        preseal_id="synthetic-preseal-v3",
        phase9_anchor_sha="a" * 64,
        allocation_sha256=allocation_sha256,
        bank_counts=_synthetic_counts(),
        role_records=role_records,
        encryption_key=encryption_key,
        private_key=signing_key,
        signer_identity=signer_identity,
        design_commitment_sha256=sha256_bytes(b"synthetic-design"),
        artifact_directory=artifact_dir,
        index_path=index_path,
        commitment_path=commitment_path,
        event_log_path=event_path,
        nonce_by_role={"content": b"C" * 12, "labels": b"L" * 12, "seeds": b"S" * 12},
        clock=clock,
    )
    # STEP LOG P9A-V3-SYN-002: Run the exact future Phase 11 preflight against the synthetic Phase 9A producer output.
    console.log("P9A-V3-SYN-002", "Running the shared Phase 11 preflight against synthetic output.")
    preflight = phase11_preflight(
        repo_root=repo_root,
        commitment_path=commitment_path,
        index_path=index_path,
        event_log_path=event_path,
        one_shot_state_path=state_path,
        expected_study="synthetic-study-v3",
        expected_preseal="synthetic-preseal-v3",
    )
    # STEP LOG P9A-V3-SYN-003: Perform exactly one authenticated synthetic materialization through the production one-shot materializer.
    console.log("P9A-V3-SYN-003", "Executing the single permitted synthetic materialization.")
    materialized = materialize_once(
        repo_root=repo_root,
        commitment_path=commitment_path,
        index_path=index_path,
        event_log_path=event_path,
        one_shot_state_path=state_path,
        output_root=custody_root / "materialized",
        encryption_key=encryption_key,
        expected_study="synthetic-study-v3",
        expected_preseal="synthetic-preseal-v3",
    )
    if materialized["method_projection_fields"] != ["case_id", "visible"]:
        raise CustodyContractError("method projection contains hidden fields or labels")
    # STEP LOG P9A-V3-SYN-004: Verify that a repeated synthetic unlock or materialization is rejected by consumed one-shot state.
    console.log("P9A-V3-SYN-004", "Testing fail-closed repeat materialization rejection.")
    repeat = _expect_rejection(
        "SYN-SECOND-MATERIALIZATION",
        lambda: materialize_once(
            repo_root=repo_root,
            commitment_path=commitment_path,
            index_path=index_path,
            event_log_path=event_path,
            one_shot_state_path=state_path,
            output_root=custody_root / "materialized-second",
            encryption_key=encryption_key,
            expected_study="synthetic-study-v3",
            expected_preseal="synthetic-preseal-v3",
        ),
    )
    commitment = produced["commitment"]
    index = produced["index"]
    events = read_event_log(event_path)
    mutations: list[dict[str, Any]] = [repeat]
    for field in sorted(COMMITMENT_FIELDS):
        mutations.append(_expect_rejection(f"TOP-MISSING-{field}", lambda field=field: _mutated_commitment_check(commitment, lambda value: value.pop(field))))
    mutations.append(_expect_rejection("TOP-UNKNOWN-FIELD", lambda: _mutated_commitment_check(commitment, lambda value: value.update({"unexpected": True}))))
    for role_index, role in enumerate(("content", "labels", "seeds")):
        for field in sorted(PACKAGE_FIELDS):
            mutations.append(
                _expect_rejection(
                    f"PACKAGE-{role.upper()}-MISSING-{field}",
                    lambda role_index=role_index, field=field: _mutated_commitment_check(commitment, lambda value: value["packages"][role_index].pop(field)),
                )
            )
    mutations.extend(
        [
            _expect_rejection("PACKAGE-UNKNOWN-FIELD", lambda: _mutated_commitment_check(commitment, lambda value: value["packages"][0].update({"unexpected": True}))),
            _expect_rejection("PLAINTEXT-HASH", lambda: _mutated_commitment_check(commitment, lambda value: value.update({"content_plaintext_sha256": "0" * 64}))),
            _expect_rejection("CIPHERTEXT-HASH", lambda: _mutated_commitment_check(commitment, lambda value: value["packages"][0].update({"ciphertext_sha256": "0" * 64}))),
            _expect_rejection("RECORD-COUNT-ZERO", lambda: _mutated_commitment_check(commitment, lambda value: value["packages"][0].update({"record_count": 0}))),
            _expect_rejection("RECORD-COUNT-NEGATIVE", lambda: _mutated_commitment_check(commitment, lambda value: value["packages"][0].update({"record_count": -1}))),
            _expect_rejection("RECORD-COUNT-DISAGREEMENT", lambda: _mutated_commitment_check(commitment, lambda value: value["packages"][1].update({"record_count": 11}))),
            _expect_rejection("BANK-COUNT-ZERO-TOTAL", lambda: _mutated_commitment_check(commitment, lambda value: value["bank_counts"].update({"total_records": 0}))),
            _expect_rejection("BANK-COUNT-NEGATIVE", lambda: _mutated_commitment_check(commitment, lambda value: value["bank_counts"]["per_bank"].update({"structural": -1}))),
            _expect_rejection("BANK-COUNT-DISAGREEMENT", lambda: _mutated_commitment_check(commitment, lambda value: value["bank_counts"]["per_track"].update({"exact": 4}))),
            _expect_rejection("ALLOCATION-BINDING", lambda: _mutated_commitment_check(commitment, lambda value: value["packages"][0].update({"allocation_sha256": "0" * 64}))),
            _expect_rejection("PACKAGE-ROLE-SUBSTITUTION", lambda: _mutated_commitment_check(commitment, lambda value: value["packages"][0].update({"role": "labels"}))),
            _expect_rejection("UNSUPPORTED-ENCRYPTION", lambda: _mutated_commitment_check(commitment, lambda value: value["packages"][0].update({"encryption_algorithm": "AES-CBC"}))),
            _expect_rejection("NONCE-REUSE", lambda: _mutated_commitment_check(commitment, lambda value: value["packages"][1].update({"nonce_b64": value["packages"][0]["nonce_b64"]}))),
            _expect_rejection("PATH-TRAVERSAL", lambda: _mutated_commitment_check(commitment, lambda value: value["packages"][0].update({"path": "../escape.aesgcm"}))),
            _expect_rejection("COMMITMENT-SIGNATURE", lambda: _mutated_commitment_check(commitment, lambda value: value["signature"].update({"signature_b64": "A" * 88}))),
            _expect_rejection("INDEX-SIGNATURE", lambda: _mutated_index_check(index, lambda value: value["signature"].update({"signature_b64": "A" * 88}))),
            _expect_rejection("PUBLIC-KEY-SUBSTITUTION", lambda: _mutated_commitment_check(commitment, lambda value: value["signature"].update({"public_key_b64": "A" * 44}))),
            _expect_rejection("OLD-STUDY-IDENTITY", lambda: _mutated_commitment_check(commitment, lambda value: value.update({"study_version": "pead-study-v2"}))),
        ]
    )
    def event_mutation(mutation: Callable[[list[dict[str, Any]]], None]) -> None:
        changed = copy.deepcopy(events)
        mutation(changed)
        verify_event_log(changed, study_version="synthetic-study-v3", preseal_id="synthetic-preseal-v3", expected_signer_identity=signer_identity)
    mutations.extend(
        [
            _expect_rejection("EVENT-HASH", lambda: event_mutation(lambda rows: rows[1].update({"event_sha256": "0" * 64}))),
            _expect_rejection("EVENT-SIGNATURE", lambda: event_mutation(lambda rows: rows[1]["signature"].update({"signature_b64": "A" * 88}))),
            _expect_rejection("EVENT-PREVIOUS-HASH", lambda: event_mutation(lambda rows: rows[2].update({"previous_event_sha256": "0" * 64}))),
            _expect_rejection("EVENT-SEQUENCE", lambda: event_mutation(lambda rows: rows[2].update({"sequence": 99}))),
            _expect_rejection("EVENT-REORDER", lambda: event_mutation(lambda rows: rows.__setitem__(slice(1, 3), [rows[2], rows[1]]))),
            _expect_rejection("EVENT-OMISSION", lambda: event_mutation(lambda rows: rows.pop(2))),
            _expect_rejection("EVENT-DUPLICATION", lambda: event_mutation(lambda rows: rows.insert(2, copy.deepcopy(rows[1])))),
            _expect_rejection("EVENT-DUPLICATE-IDENTITY", lambda: event_mutation(lambda rows: rows[2].update({"event_id": rows[1]["event_id"]}))),
            _expect_rejection("EVENT-UNSIGNED", lambda: event_mutation(lambda rows: rows[1].pop("signature"))),
            _expect_rejection("EVENT-MIXED-STUDY", lambda: event_mutation(lambda rows: rows[1].update({"study_version": "pead-study-v2"}))),
        ]
    )
    fake_new = {field: sha256_bytes(f"new:{field}".encode()) for field in FRESH_IDENTITIES}
    mutations.append(_expect_rejection("REUSED-KEY-IDENTITY", lambda: assert_identity_freshness(fake_new, {"v2": {"old": next(iter(fake_new.values()))}})))
    mutations.append(_expect_rejection("REUSED-HIDDEN-SEED-IDENTITY", lambda: assert_identity_freshness(fake_new, {"v2": {"old": fake_new["structural_seed_selection_sha256"]}})))
    ciphertext_path = repo_root / produced["packages"][0]["path"]
    original_ciphertext = ciphertext_path.read_bytes()
    def mutate_ciphertext_byte() -> None:
        changed = bytearray(original_ciphertext)
        changed[0] ^= 1
        ciphertext_path.write_bytes(bytes(changed))
        try:
            phase11_preflight(
                repo_root=repo_root,
                commitment_path=commitment_path,
                index_path=index_path,
                event_log_path=event_path,
                one_shot_state_path=custody_root / "fresh_state.json",
                expected_study="synthetic-study-v3",
                expected_preseal="synthetic-preseal-v3",
            )
        finally:
            ciphertext_path.write_bytes(original_ciphertext)
    (custody_root / "fresh_state.json").write_bytes(canonical_bytes({"schema_version": "3.0", "study_version": "synthetic-study-v3", "preseal_id": "synthetic-preseal-v3", "consumed": False, "materialization_count": 0}) + b"\n")
    mutations.append(_expect_rejection("CIPHERTEXT-BYTE", mutate_ciphertext_byte))
    # STEP LOG P9A-V3-SYN-005: Execute the complete field, cryptographic, chain, identity, substitution, and one-shot mutation program.
    console.log("P9A-V3-SYN-005", "Completed the synthetic fail-closed mutation program.", details={"mutations": len(mutations)})
    failures = [item for item in mutations if item["status"] != "pass"]
    result = {
        "schema_version": "1.0",
        "study_version": "synthetic-study-v3",
        "claim_bearing": False,
        "status": "pass" if not failures else "fail",
        "producer_consumer_preflight": preflight,
        "producer_values_required": sorted(COMMITMENT_FIELDS),
        "consumer_invented_values": preflight["consumer_invented_values"],
        "missing_commitments": preflight["missing_commitments"],
        "custody_events": produced["event_receipt"],
        "valid_materializations_accepted": 1,
        "repeat_materializations_accepted": 0 if repeat["status"] == "pass" else 1,
        "materialization": materialized,
        "mutation_denominator": len(mutations),
        "accepted_invalid_mutations": len(failures),
        "mutations": mutations,
        "real_bank_touched": False,
        "artifact_hashes": {
            "commitment_sha256": sha256_bytes(commitment_path.read_bytes()),
            "index_sha256": sha256_bytes(index_path.read_bytes()),
            "event_log_sha256": sha256_bytes(event_path.read_bytes()),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P9A-V3-SYN-006: Retain machine-readable rehearsal denominators, mutation verdicts, and non-claim-bearing artifact hashes.
    console.log("P9A-V3-SYN-006", "Wrote the synthetic rehearsal evidence.", status=result["status"], details={"mutation_denominator": len(mutations), "accepted_invalid_mutations": len(failures)})
    shutil.rmtree(temp_root)
    if failures:
        raise CustodyContractError(f"synthetic rehearsal accepted {len(failures)} invalid mutation(s)")
    return result
