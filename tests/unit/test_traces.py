from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.core.traces import (
    AppendOnlyTraceWriter,
    DecisionTrace,
    TraceValidationError,
    validate_trace_file,
)


def valid_trace(**overrides: object) -> DecisionTrace:
    values: dict[str, object] = {
        "schema_version": "1.0",
        "study_id": "PEAD-MAIN-v1",
        "run_id": "run:" + "a" * 64,
        "config_hash": "b" * 64,
        "commit_hash": "c" * 40,
        "environment_hash": "d" * 64,
        "world_id": "world:" + "e" * 64,
        "atomic_group_id": "group-1",
        "split_id": "development_fit",
        "method_id": "P01-LOGREG-v1",
        "budget_id": "low-v1",
        "projection_hash": "f" * 64,
        "decision_hash": "1" * 64,
        "decision_commit_time": "2026-07-30T12:00:00+00:00",
        "label_hash": "2" * 64,
        "label_reveal_time": "2026-07-30T12:00:00.000001+00:00",
        "resource_usage": {"latency_ms": 1.25, "calls": 1},
    }
    values.update(overrides)
    return DecisionTrace(**values)  # type: ignore[arg-type]


class TraceContractTests(unittest.TestCase):
    def test_append_finalize_validate_and_parquet_row(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace.jsonl"
            console = ResearchConsole("1", stream=io.StringIO())
            writer = AppendOnlyTraceWriter(path, console=console)
            writer.append(valid_trace())
            manifest = writer.finalize()
            audit = validate_trace_file(path)
            self.assertEqual(manifest["record_count"], 1)
            self.assertEqual(audit["record_count"], 1)
            row = valid_trace().parquet_row()
            self.assertIsInstance(row["resource_usage"], str)
            self.assertEqual(set(row), set(valid_trace().__dataclass_fields__))

    def test_existing_output_and_post_finalize_append_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace.jsonl"
            writer = AppendOnlyTraceWriter(
                path, console=ResearchConsole("1", stream=io.StringIO())
            )
            writer.append(valid_trace())
            writer.finalize()
            with self.assertRaises(TraceValidationError):
                writer.append(valid_trace())
            with self.assertRaises(FileExistsError):
                AppendOnlyTraceWriter(
                    path, console=ResearchConsole("1", stream=io.StringIO())
                )

    def test_malformed_incomplete_and_out_of_order_traces_are_rejected(self) -> None:
        raw = {key: getattr(valid_trace(), key) for key in valid_trace().__dataclass_fields__}
        raw.pop("budget_id")
        with self.assertRaises(TraceValidationError):
            DecisionTrace.from_mapping(raw)
        with self.assertRaises(TraceValidationError):
            valid_trace(
                decision_commit_time="2026-07-30T12:00:01+00:00",
                label_reveal_time="2026-07-30T12:00:00+00:00",
            )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.jsonl"
            path.write_text("{not-json}\n", encoding="utf-8")
            with self.assertRaises(TraceValidationError):
                validate_trace_file(path)

    def test_tampering_breaks_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace.jsonl"
            writer = AppendOnlyTraceWriter(
                path, console=ResearchConsole("1", stream=io.StringIO())
            )
            writer.append(valid_trace())
            writer.finalize()
            envelope = json.loads(path.read_text(encoding="utf-8"))
            envelope["trace_hash"] = "0" * 64
            path.write_text(json.dumps(envelope) + "\n", encoding="utf-8")
            with self.assertRaises(TraceValidationError):
                validate_trace_file(path)


if __name__ == "__main__":
    unittest.main()
