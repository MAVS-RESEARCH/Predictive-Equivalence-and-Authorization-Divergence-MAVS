"""Execute the complete Phase 11 compliance audit."""

import argparse
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase11.audit import run_audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--custody-workspace", type=Path, required=True)
    args = parser.parse_args()
    console = ResearchConsole("11")
    # STEP LOG P11-AUDIT-SCRIPT-001: Start the final Phase 11 clause and evidence audit.
    console.log("P11-AUDIT-SCRIPT-001", "Starting complete Phase 11 compliance audit.")
    report = run_audit(Path(__file__).parents[1].resolve(), args.custody_workspace.resolve(), console)
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
