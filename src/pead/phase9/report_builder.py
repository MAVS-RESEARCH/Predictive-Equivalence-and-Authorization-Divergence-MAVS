"""Build the non-scientific Phase 9 report-contract artifact."""

from __future__ import annotations

import argparse
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase2.audit import write_json
from pead.phase9.review import failure_and_report_review


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    parser.add_argument("--output", type=Path, default=Path("results/reports/phase9_contract/report_contract.json"))
    args = parser.parse_args()
    root = args.repo_root.resolve()
    console = ResearchConsole("9")
    # STEP LOG P9-REPORT-001: Build strict failure-card, unsuppressed-method, figure-point, provenance, and claim fixtures.
    console.log("P9-REPORT-001", "Building Phase 9 report contract.")
    report = failure_and_report_review(root)
    # STEP LOG P9-REPORT-002: Retain the report contract only when every method, event, provenance edge, and claim gate is represented.
    console.log("P9-REPORT-002", "Validating report completeness before publication.")
    if report["status"] != "pass" or not report["table"]["failed_methods_visible"] or report["claim_ledger"]["claims"]:
        raise ValueError("Phase 9 report contract is incomplete or emitted a scientific claim")
    output = args.output if args.output.is_absolute() else root / args.output
    write_json(output, {"schema_version": "1.0", "phase": 9, "report_type": "implementation-contract-only", **report})
    # STEP LOG P9-REPORT-003: Publish the non-scientific report-builder proof with zero eligible scientific claims.
    console.log("P9-REPORT-003", "Phase 9 report contract published.", status="pass", details={"claims": 0, "methods": report["table"]["methods"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
