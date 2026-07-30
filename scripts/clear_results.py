"""Safely inspect or remove only manifest-declared generated result files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pead.config.console import ResearchConsole
from pead.core.paths import PathSafetyError, RepositoryPaths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--scope")
    selector.add_argument("--run-id")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--confirm", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    console = ResearchConsole("1")
    try:
        # STEP LOG P1-CLEANUP-001: Resolve and verify the repository and results roots.
        console.log("P1-CLEANUP-001", "Resolving protected result roots.")
        paths = RepositoryPaths(args.repo_root)
        selector = args.scope if args.scope is not None else args.run_id
        manifest = args.manifest
        if manifest is None:
            manifest = (
                paths.results
                / "manifests"
                / "cleanup"
                / f"{selector}.json"
            )
        # STEP LOG P1-CLEANUP-002: Load the exact manifest selected by scope or run identity.
        console.log(
            "P1-CLEANUP-002",
            "Loading explicit cleanup manifest.",
            details={"manifest": str(manifest), "selector": selector},
        )
        plan = paths.load_cleanup_plan(
            manifest,
            scope=args.scope,
            run_id=args.run_id,
        )
        # STEP LOG P1-CLEANUP-003: Execute the selected dry-run or confirmed cleanup mode.
        console.log(
            "P1-CLEANUP-003",
            "Executing manifest-guarded cleanup plan.",
            details={"confirm": args.confirm, "target_count": len(plan.targets)},
        )
        paths.execute_cleanup(plan, confirm=args.confirm, console=console)
        # STEP LOG P1-CLEANUP-008: Report successful guarded cleanup completion.
        console.log(
            "P1-CLEANUP-008",
            "Manifest-guarded cleanup completed.",
            status="pass",
            details={"confirm": args.confirm, "target_count": len(plan.targets)},
        )
        return 0
    except (OSError, PathSafetyError, ValueError) as error:
        # STEP LOG P1-CLEANUP-009: Report a rejected or failed cleanup without suppressing the cause.
        console.log(
            "P1-CLEANUP-009",
            "Manifest-guarded cleanup failed.",
            status="fail",
            details={"error": str(error)},
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
