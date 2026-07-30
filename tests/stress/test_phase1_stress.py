from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.core.ids import derive_content_id
from pead.core.traces import AppendOnlyTraceWriter, validate_trace_file
from tests.unit.test_traces import valid_trace


class Phase1StressTests(unittest.TestCase):
    def test_one_hundred_thousand_content_ids_have_no_collision(self) -> None:
        observed = {
            derive_content_id(
                "world",
                {"seed": index, "mechanism": f"M{index % 12 + 1:02d}"},
            )
            for index in range(100_000)
        }
        self.assertEqual(len(observed), 100_000)

    def test_ten_thousand_trace_records_finalize_without_loss(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "stress.jsonl"
            writer = AppendOnlyTraceWriter(
                path, console=ResearchConsole("1", stream=io.StringIO())
            )
            for index in range(10_000):
                writer.append(
                    valid_trace(
                        world_id=f"world:{index:064x}",
                        decision_hash=f"{index:064x}",
                        label_hash=f"{index + 1:064x}",
                    )
                )
            manifest = writer.finalize()
            audit = validate_trace_file(path)
            self.assertEqual(manifest["record_count"], 10_000)
            self.assertEqual(audit["record_count"], 10_000)
            self.assertEqual(
                manifest["terminal_chain_hash"], audit["terminal_chain_hash"]
            )


if __name__ == "__main__":
    unittest.main()
