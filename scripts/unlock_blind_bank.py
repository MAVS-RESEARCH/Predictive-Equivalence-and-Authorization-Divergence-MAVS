"""Run the fail-closed Phase 11 unlock preflight and retain its receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.phase11.unlock import blocked_receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--custody-workspace", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[1])
    args = parser.parse_args()
    console = ResearchConsole("11")
    # STEP LOG P11-UNLOCK-SCRIPT-001: Validate that the separately controlled custody workspace exists without reading its hidden content.
    console.log("P11-UNLOCK-SCRIPT-001", "Validating external custody workspace presence.")
    if not args.custody_workspace.is_dir():
        raise FileNotFoundError("external custody workspace is absent")
    receipt = blocked_receipt(args.repo_root.resolve(), args.freeze_manifest.resolve(), args.custody_workspace.resolve(), console)
    freeze = json.loads(args.freeze_manifest.read_text(encoding="utf-8"))
    target = args.repo_root / "results/audits" / freeze["freeze_id"] / "custody_unlock.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if receipt["status"] == "eligible" else 2


if __name__ == "__main__":
    raise SystemExit(main())
