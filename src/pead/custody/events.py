"""Append-only, individually signed custody events from sequence one."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from pead.custody.contract import (
    CustodyContractError,
    canonical_bytes,
    sha256_bytes,
    sign_mapping,
    verify_signature,
)


EVENT_FIELDS = frozenset(
    {
        "schema_version",
        "study_version",
        "preseal_id",
        "sequence",
        "event_id",
        "timestamp_utc",
        "action",
        "verdict",
        "details_sha256",
        "previous_event_sha256",
        "signer_identity",
        "signature",
        "event_sha256",
    }
)
ZERO_HASH = "0" * 64


def _unsigned_event(event: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(event)
    value.pop("event_sha256", None)
    return value


def event_hash(event: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(_unsigned_event(event)))


def create_signed_event(
    *,
    study_version: str,
    preseal_id: str,
    sequence: int,
    event_id: str,
    action: str,
    verdict: str,
    details: Mapping[str, Any],
    previous_event_sha256: str,
    private_key: Any,
    signer_identity: str,
    timestamp_utc: str | None = None,
) -> dict[str, Any]:
    if sequence <= 0 or not event_id or not action or verdict not in {"allow", "deny", "record"}:
        raise CustodyContractError("custody event identity, sequence, action, or verdict is invalid")
    timestamp = timestamp_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    unsigned = {
        "schema_version": "3.0",
        "study_version": study_version,
        "preseal_id": preseal_id,
        "sequence": sequence,
        "event_id": event_id,
        "timestamp_utc": timestamp,
        "action": action,
        "verdict": verdict,
        "details_sha256": sha256_bytes(canonical_bytes(details)),
        "previous_event_sha256": previous_event_sha256,
        "signer_identity": signer_identity,
    }
    signed = sign_mapping(unsigned, private_key, signer_identity)
    signed["event_sha256"] = event_hash(signed)
    verify_event(signed, study_version=study_version, preseal_id=preseal_id, expected_sequence=sequence, expected_previous=previous_event_sha256)
    return signed


def verify_event(
    event: Mapping[str, Any],
    *,
    study_version: str,
    preseal_id: str,
    expected_sequence: int,
    expected_previous: str,
) -> None:
    if set(event) != EVENT_FIELDS:
        raise CustodyContractError("custody event has absent or unknown fields")
    if event["schema_version"] != "3.0" or event["study_version"] != study_version or event["preseal_id"] != preseal_id:
        raise CustodyContractError("custody event schema, study, or preseal mismatch")
    if event["sequence"] != expected_sequence or event["previous_event_sha256"] != expected_previous:
        raise CustodyContractError("custody event sequence or hash-chain pointer mismatch")
    if not isinstance(event["event_id"], str) or not event["event_id"]:
        raise CustodyContractError("custody event identity is absent")
    if not isinstance(event["timestamp_utc"], str) or not event["timestamp_utc"].endswith("Z"):
        raise CustodyContractError("custody event timestamp is not canonical UTC")
    if not isinstance(event["details_sha256"], str) or len(event["details_sha256"]) != 64:
        raise CustodyContractError("custody event details identity is malformed")
    if event["signer_identity"] != event["signature"].get("signer_identity"):
        raise CustodyContractError("custody event signer identities differ")
    verify_signature(_unsigned_event(event), expected_signer=str(event["signer_identity"]))
    if event_hash(event) != event["event_sha256"]:
        raise CustodyContractError("custody event hash is invalid")


def verify_event_log(
    events: Sequence[Mapping[str, Any]],
    *,
    study_version: str,
    preseal_id: str,
    expected_signer_identity: str | None = None,
) -> dict[str, Any]:
    if not events:
        raise CustodyContractError("custody event log is empty")
    previous = ZERO_HASH
    identities: set[str] = set()
    for sequence, event in enumerate(events, start=1):
        verify_event(event, study_version=study_version, preseal_id=preseal_id, expected_sequence=sequence, expected_previous=previous)
        if event["event_id"] in identities:
            raise CustodyContractError("duplicate custody event identity")
        identities.add(str(event["event_id"]))
        if expected_signer_identity is not None and event["signer_identity"] != expected_signer_identity:
            raise CustodyContractError("mixed custody event signers are prohibited")
        previous = str(event["event_sha256"])
    return {
        "status": "pass",
        "event_count": len(events),
        "genesis_sha256": events[0]["event_sha256"],
        "head_sha256": events[-1]["event_sha256"],
        "all_events_signed": True,
        "unsigned_events": 0,
    }


def read_event_log(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise CustodyContractError("custody event log is absent")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            raise CustodyContractError(f"blank custody event at line {line_number}")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise CustodyContractError(f"custody event at line {line_number} is not a mapping")
        rows.append(value)
    return rows


class SignedEventLog:
    """Append events only after full-log verification and immediate signature verification."""

    def __init__(
        self,
        path: Path,
        *,
        study_version: str,
        preseal_id: str,
        private_key: Any,
        signer_identity: str,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self.path = path
        self.study_version = study_version
        self.preseal_id = preseal_id
        self.private_key = private_key
        self.signer_identity = signer_identity
        self.clock = clock

    def append(self, event_id: str, action: str, verdict: str, details: Mapping[str, Any]) -> dict[str, Any]:
        events = read_event_log(self.path) if self.path.exists() else []
        if events:
            verify_event_log(events, study_version=self.study_version, preseal_id=self.preseal_id, expected_signer_identity=self.signer_identity)
        if any(row["event_id"] == event_id for row in events):
            raise CustodyContractError("refusing duplicate custody event identity")
        previous = str(events[-1]["event_sha256"]) if events else ZERO_HASH
        timestamp = self.clock() if self.clock is not None else None
        event = create_signed_event(
            study_version=self.study_version,
            preseal_id=self.preseal_id,
            sequence=len(events) + 1,
            event_id=event_id,
            action=action,
            verdict=verdict,
            details=details,
            previous_event_sha256=previous,
            private_key=self.private_key,
            signer_identity=self.signer_identity,
            timestamp_utc=timestamp,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(canonical_bytes(event).decode("utf-8") + "\n")
            stream.flush()
        retained = read_event_log(self.path)
        verify_event_log(retained, study_version=self.study_version, preseal_id=self.preseal_id, expected_signer_identity=self.signer_identity)
        return event
