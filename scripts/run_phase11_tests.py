"""Execute the complete Phase 11 regression program."""

from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase11.test_runner import run_tests


def main() -> int:
    console = ResearchConsole("11")
    # STEP LOG P11-TEST-SCRIPT-001: Start the full repository regression from the canonical Phase 11 entrypoint.
    console.log("P11-TEST-SCRIPT-001", "Starting complete Phase 11 regression program.")
    report = run_tests(Path(__file__).parents[1].resolve(), console)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
