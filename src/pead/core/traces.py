"""Strict append-only decision traces with atomic finalization."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_bytes, canonical_hash, restore_canonical_object
from pead.core.types import deep_freeze

TRACE_SCHEMA_VERSION = "1.0"
REQUIRED_TRACE_FIELDS = (
    "schema_version",
    "study_id",
    "run_id",
    "config_hash",
    "commit_hash",
    "environment_hash",
    "world_id",
    "atomic_group_id",
    "split_id",
    "method_id",
    "budget_id",
    "projection_hash",
    "decision_hash",
    "decision_commit_time",
    "label_hash",
    "label_reveal_time",
    "resource_usage",
)


class TraceValidationError(ValueError):
    """Raised when a trace is incomplete, malformed, or out of order."""


def _parse_time(value: str, field_name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise TraceValidationError(f"{field_name} must be non-empty")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TraceValidationError(f"{field_name} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise TraceValidationError(f"{field_name} must include an offset")
    return parsed


@dataclass(frozen=True)
class DecisionTrace:
    schema_version: str
    study_id: str
    run_id: str
    config_hash: str
    commit_hash: str
    environment_hash: str
    world_id: str
    atomic_group_id: str
    split_id: str
    method_id: str
    budget_id: str
    projection_hash: str
    decision_hash: str
    decision_commit_time: str
    label_hash: str
    label_reveal_time: str
    resource_usage: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.schema_version != TRACE_SCHEMA_VERSION:
            raise TraceValidationError("trace schema_version must be 1.0")
        for name in REQUIRED_TRACE_FIELDS[1:-1]:
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise TraceValidationError(f"{name} must be non-empty")
        commit_time = _parse_time(self.decision_commit_time, "decision_commit_time")
        reveal_time = _parse_time(self.label_reveal_time, "label_reveal_time")
        if reveal_time < commit_time:
            raise TraceValidationError("hidden label was revealed before decision commit")
        if not isinstance(self.resource_usage, Mapping):
            raise TraceValidationError("resource_usage must be a mapping")
        object.__setattr__(self, "resource_usage", deep_freeze(self.resource_usage))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DecisionTrace":
        if set(value) != set(REQUIRED_TRACE_FIELDS):
            missing = sorted(set(REQUIRED_TRACE_FIELDS) - set(value))
            extra = sorted(set(value) - set(REQUIRED_TRACE_FIELDS))
            raise TraceValidationError(
                f"trace fields mismatch; missing={missing}; extra={extra}"
            )
        return cls(**value)

    def parquet_row(self) -> dict[str, Any]:
        """Return scalar columns compatible with a future Parquet writer."""

        row = {
            field.name: getattr(self, field.name)
            for field in dataclasses.fields(self)
        }
        row["resource_usage"] = json.dumps(
            dict(row["resource_usage"]),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return row


class AppendOnlyTraceWriter:
    """Write a hash-chained JSONL stream and atomically publish it once."""

    def __init__(self, final_path: Path, *, console: ResearchConsole) -> None:
        if final_path.suffix != ".jsonl":
            raise TraceValidationError("final trace path must have .jsonl suffix")
        self.final_path = final_path
        self.partial_path = final_path.with_suffix(".jsonl.partial")
        if self.final_path.exists() or self.partial_path.exists():
            raise FileExistsError("trace output cannot overwrite an existing artifact")
        self.final_path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.partial_path.open("xb")
        self._console = console
        self._count = 0
        self._previous_hash = "0" * 64
        self._finalized = False
        # STEP LOG P1-TRACE-001: Create a new exclusive append-only partial trace.
        self._console.log(
            "P1-TRACE-001",
            "Exclusive partial trace created.",
            details={"path": self.partial_path.as_posix()},
        )

    def append(self, trace: DecisionTrace) -> str:
        if self._finalized or self._stream.closed:
            raise TraceValidationError("cannot append after trace finalization")
        trace_hash = canonical_hash(trace)
        envelope = {
            "schema_version": TRACE_SCHEMA_VERSION,
            "record_index": self._count,
            "previous_record_hash": self._previous_hash,
            "trace_hash": trace_hash,
            "trace": trace,
        }
        self._stream.write(canonical_bytes(envelope) + b"\n")
        self._stream.flush()
        os.fsync(self._stream.fileno())
        self._count += 1
        self._previous_hash = canonical_hash(envelope)
        # STEP LOG P1-TRACE-002: Append and synchronize one validated hash-chained record.
        self._console.log(
            "P1-TRACE-002",
            "Validated trace record appended.",
            details={"record_index": self._count - 1, "trace_hash": trace_hash},
        )
        return trace_hash

    def finalize(self) -> dict[str, Any]:
        if self._finalized:
            raise TraceValidationError("trace already finalized")
        if self._count == 0:
            self._stream.close()
            raise TraceValidationError("an empty trace cannot be finalized")
        self._stream.flush()
        os.fsync(self._stream.fileno())
        self._stream.close()
        os.replace(self.partial_path, self.final_path)
        self._finalized = True
        manifest = {
            "schema_version": TRACE_SCHEMA_VERSION,
            "trace_path": self.final_path.as_posix(),
            "record_count": self._count,
            "terminal_chain_hash": self._previous_hash,
            "artifact_sha256": hashlib.sha256(self.final_path.read_bytes()).hexdigest(),
            "parquet_compatibility": {
                "representation": "scalar-columns-with-resource-usage-json",
                "columns": list(REQUIRED_TRACE_FIELDS),
            },
        }
        # STEP LOG P1-TRACE-003: Atomically publish the complete nonempty trace.
        self._console.log(
            "P1-TRACE-003",
            "Trace atomically finalized.",
            details={"path": self.final_path.as_posix(), "record_count": self._count},
        )
        return manifest


def validate_trace_file(path: Path) -> dict[str, Any]:
    """Recompute every record and hash-chain link in a finalized JSONL trace."""

    if path.suffix != ".jsonl" or not path.is_file():
        raise TraceValidationError("finalized trace must be a JSONL file")
    previous = "0" * 64
    count = 0
    for line in path.read_bytes().splitlines():
        try:
            envelope = json.loads(line.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise TraceValidationError("trace contains malformed UTF-8 JSON") from exc
        if set(envelope) != {
            "schema_version",
            "record_index",
            "previous_record_hash",
            "trace_hash",
            "trace",
        }:
            raise TraceValidationError("trace envelope fields are incomplete")
        if envelope["schema_version"] != TRACE_SCHEMA_VERSION:
            raise TraceValidationError("trace envelope schema_version is invalid")
        if envelope["record_index"] != count:
            raise TraceValidationError("trace record index is discontinuous")
        if envelope["previous_record_hash"] != previous:
            raise TraceValidationError("trace hash chain is broken")
        restored_trace = restore_canonical_object(envelope["trace"])
        trace = DecisionTrace.from_mapping(restored_trace)
        if envelope["trace_hash"] != canonical_hash(trace):
            raise TraceValidationError("trace record hash mismatch")
        previous = canonical_hash(
            {
                "schema_version": envelope["schema_version"],
                "record_index": envelope["record_index"],
                "previous_record_hash": envelope["previous_record_hash"],
                "trace_hash": envelope["trace_hash"],
                "trace": trace,
            }
        )
        count += 1
    if count == 0:
        raise TraceValidationError("trace file is empty")
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "record_count": count,
        "terminal_chain_hash": previous,
    }
