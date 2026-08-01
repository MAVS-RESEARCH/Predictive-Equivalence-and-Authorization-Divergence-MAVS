"""Audit one retained usage record against a registered resource ceiling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pead.config.console import ResearchConsole


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("usage", type=Path)
    parser.add_argument("ceiling", type=Path)
    args = parser.parse_args()
    console = ResearchConsole("7")
    # STEP LOG P7-BUDGET-SCRIPT-001: Load immutable usage and ceiling records for independent comparison.
    console.log("P7-BUDGET-SCRIPT-001", "Loading resource usage and ceiling records.")
    usage = json.loads(args.usage.read_text(encoding="utf-8"))
    ceiling = json.loads(args.ceiling.read_text(encoding="utf-8"))
    keys = ("wall_time_seconds", "peak_memory_bytes", "calls", "tokens")
    exceeded = {key: usage.get(key, 0) for key in keys if usage.get(key, 0) > ceiling.get(key, float("inf"))}
    if exceeded:
        raise SystemExit(f"registered budget exceeded: {exceeded}")
    # STEP LOG P7-BUDGET-SCRIPT-002: Report budget parity only when all measured resources remain under their registered ceilings.
    console.log("P7-BUDGET-SCRIPT-002", "Resource usage is within the registered ceiling.", status="pass", details={"checked": list(keys)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
