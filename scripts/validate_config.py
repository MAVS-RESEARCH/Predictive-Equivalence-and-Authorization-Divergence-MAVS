"""Validate the frozen study configuration and Phase 1 typed registries."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pead.config.console import ResearchConsole
from pead.config.validator import main as phase0_main
from pead.core.config import load_config
from pead.core.diagnostic_registry import load_diagnostic_registry
from pead.core.registry import RegistryValidationError
from pead.core.requirement_registry import load_requirement_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--study",
        type=Path,
        default=Path("configs/study/pead_main_v1.yaml"),
    )
    return parser


def main() -> int:
    args, remaining = build_parser().parse_known_args()
    original_argv = sys.argv
    try:
        sys.argv = [original_argv[0], *remaining]
        result = phase0_main()
    finally:
        sys.argv = original_argv
    if result != 0:
        return result
    console = ResearchConsole("1")
    try:
        # STEP LOG P1-VALIDATE-001: Load the explicit immutable study configuration.
        console.log(
            "P1-VALIDATE-001",
            "Loading explicit study configuration.",
            details={"study": args.study.as_posix()},
        )
        study = load_config(REPO_ROOT, args.study)
        # STEP LOG P1-VALIDATE-002: Construct and validate the typed diagnostic registry.
        console.log("P1-VALIDATE-002", "Validating typed diagnostic registry.")
        diagnostics = load_diagnostic_registry(REPO_ROOT)
        # STEP LOG P1-VALIDATE-003: Construct and validate the clause-level requirement registry.
        console.log("P1-VALIDATE-003", "Validating typed requirement registry.")
        requirements = load_requirement_registry(REPO_ROOT)
        # STEP LOG P1-VALIDATE-004: Report all immutable configuration and registry identities.
        console.log(
            "P1-VALIDATE-004",
            "Phase 1 configuration and registries validated.",
            status="pass",
            details={
                "diagnostics": diagnostics.manifest().entry_count,
                "requirements": requirements.manifest().entry_count,
                "study_config_id": study.config_id,
            },
        )
        return 0
    except (OSError, ValueError, RegistryValidationError) as error:
        # STEP LOG P1-VALIDATE-005: Report typed registry or configuration rejection.
        console.log(
            "P1-VALIDATE-005",
            "Phase 1 configuration validation failed.",
            status="fail",
            details={"error": str(error)},
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
