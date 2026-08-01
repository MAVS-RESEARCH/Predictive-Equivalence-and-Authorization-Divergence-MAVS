"""Validate a Phase 10 training manifest against the frozen Phase 7 chronology."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.core.training import TrainingRow, assert_projection_alignment, audit_role_isolation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if not args.validate_only:
        raise SystemExit("Phase 7 may validate training manifests only; fitting begins in Phase 10")
    console = ResearchConsole("7")
    # STEP LOG P7-TRAIN-SCRIPT-001: Load an explicit training manifest without admitting any holdout content.
    console.log("P7-TRAIN-SCRIPT-001", "Loading training manifest for validation only.")
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    profiles = {
        profile: tuple(TrainingRow(**row) for row in rows)
        for profile, rows in payload["profiles"].items()
    }
    for rows in profiles.values():
        audit_role_isolation(rows)
    alignment = assert_projection_alignment(profiles)
    # STEP LOG P7-TRAIN-SCRIPT-002: Close manifest validation only after role isolation and equal-identity projection parity pass.
    console.log("P7-TRAIN-SCRIPT-002", "Training manifest passed chronology controls.", status="pass", details=alignment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
