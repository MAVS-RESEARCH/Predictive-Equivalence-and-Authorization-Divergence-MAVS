"""Verify retained Phase 6 equal-information representation evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pead.config.console import ResearchConsole


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    args = parser.parse_args()
    root = args.repo_root.resolve()
    console = ResearchConsole("6")
    # STEP LOG P6-PARITY-001: Load the retained field-by-method and representation-oracle evidence.
    console.log("P6-PARITY-001", "Loading retained representation parity evidence.")
    path = root / "results/audits/phase6/representation_parity_report.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    matrix = report["raw_g_field_method_matrix"]
    oracle = report["representation_oracle"]
    valid = (
        report.get("status") == "pass"
        and matrix.get("status") == "pass"
        and matrix.get("mismatches") == []
        and matrix.get("case_count") == 3_600
        and oracle.get("status") == "pass"
        and oracle.get("mismatches") == 0
        and report["lossy_transformations"].get("count") == 0
    )
    # STEP LOG P6-PARITY-002: Emit the independent retained-evidence parity verdict.
    console.log(
        "P6-PARITY-002",
        "Representation parity evidence verified." if valid else "Representation parity evidence failed.",
        status="pass" if valid else "fail",
        details={
            "cases": matrix.get("case_count"),
            "matrix_cells": matrix.get("matrix_cells"),
            "mismatches": len(matrix.get("mismatches", [])),
        },
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
