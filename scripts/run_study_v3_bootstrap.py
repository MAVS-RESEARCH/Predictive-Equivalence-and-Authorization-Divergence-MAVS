"""Execute and audit the study-v3 shared custody-contract bootstrap."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from pead.config.console import ResearchConsole
from pead.custody.contract import COMMITMENT_FIELDS, PACKAGE_FIELDS, sha256_file
from pead.custody.rehearsal import run_synthetic_rehearsal


ANCHOR = "be093b5d2639deb2ff76ad96785c918b5a2a9b92"
BLOCKED_V2 = "cea7ba439de271ab054d959ec7e1571d98315d80"


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(["git", *arguments], cwd=root, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def _scan_boundaries(root: Path) -> dict[str, Any]:
    tracked = _git(root, "ls-files").splitlines()
    secret_suffixes = {".pem", ".key", ".plaintext"}
    secret_paths = sorted(path for path in tracked if Path(path).suffix.lower() in secret_suffixes)
    forbidden_names = {"seeds.yaml", "seeds.json", "decrypted.json", "plaintext.json"}
    plaintext_paths = sorted(path for path in tracked if Path(path).name.lower() in forbidden_names)
    return {
        "tracked_files": len(tracked),
        "private_key_or_secret_paths": secret_paths,
        "custody_plaintext_paths": plaintext_paths,
        "status": "pass" if not secret_paths and not plaintext_paths else "fail",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.repo_root.resolve()
    console = ResearchConsole("study-v3-bootstrap")
    # STEP LOG P9A-V3-BOOT-001: Verify the recovery branch, Phase 9 ancestry, blocked-v2 tag, and immutable main topology.
    console.log("P9A-V3-BOOT-001", "Verifying recovery-lineage Git identities.")
    branch = _git(root, "branch", "--show-current")
    anchor_is_ancestor = _git(root, "merge-base", "--is-ancestor", ANCHOR, "HEAD") == ""
    blocked_tag = _git(root, "rev-parse", "pead-study-v2-blocked^{}")
    main_sha = _git(root, "rev-parse", "main")
    if branch != "pead-study-v3" or not anchor_is_ancestor or blocked_tag != BLOCKED_V2 or main_sha != BLOCKED_V2:
        raise RuntimeError("study-v3 recovery branch topology differs from the frozen lineage")
    # STEP LOG P9A-V3-BOOT-002: Verify the machine-readable scientific boundary and shared producer-consumer schema identities.
    console.log("P9A-V3-BOOT-002", "Verifying scientific-invariance and shared-schema manifests.")
    invariance_path = root / "manifests/scientific_invariance_v3.json"
    contract_path = root / "manifests/custody/materialization_contract_v3.json"
    invariance = json.loads(invariance_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if invariance["scientific_config_sha256"] != sha256_file(root / invariance["scientific_config"]):
        raise RuntimeError("scientific configuration changed after lineage binding")
    if set(contract["commitment_fields"]) != COMMITMENT_FIELDS or set(contract["package_fields"]) != PACKAGE_FIELDS:
        raise RuntimeError("machine-readable schema manifest differs from executable shared schema")
    # STEP LOG P9A-V3-BOOT-003: Execute the first complete deterministic synthetic producer-consumer rehearsal.
    console.log("P9A-V3-BOOT-003", "Executing the first synthetic compatibility rehearsal.")
    rehearsal_path = root / "results/audits/study-v3-bootstrap/synthetic_rehearsal.json"
    first = run_synthetic_rehearsal(rehearsal_path, console)
    first_bytes = rehearsal_path.read_bytes()
    # STEP LOG P9A-V3-BOOT-004: Regenerate the complete synthetic evidence and require byte-identical deterministic output.
    console.log("P9A-V3-BOOT-004", "Reexecuting the rehearsal for deterministic reproduction.")
    second = run_synthetic_rehearsal(rehearsal_path, console)
    deterministic = first_bytes == rehearsal_path.read_bytes() and first == second
    if not deterministic:
        raise RuntimeError("synthetic rehearsal is not byte-identically reproducible")
    # STEP LOG P9A-V3-BOOT-005: Scan the development tree for private keys, exact seeds, and custody plaintext boundary violations.
    console.log("P9A-V3-BOOT-005", "Scanning development-side source and artifact boundaries.")
    boundary = _scan_boundaries(root)
    if boundary["status"] != "pass":
        raise RuntimeError("development repository contains prohibited custody material")
    audit = {
        "schema_version": "1.0",
        "phase": "study-v3-bootstrap",
        "status": "pass",
        "branch": branch,
        "phase9_anchor": ANCHOR,
        "blocked_v2_head": BLOCKED_V2,
        "shared_schema": {
            "commitment_required_fields": len(COMMITMENT_FIELDS),
            "package_required_fields_per_role": len(PACKAGE_FIELDS),
            "roles": 3,
            "single_definition": contract["shared_definition"],
        },
        "synthetic_rehearsal": {
            "status": first["status"],
            "mutation_denominator": first["mutation_denominator"],
            "accepted_invalid_mutations": first["accepted_invalid_mutations"],
            "valid_materializations_accepted": first["valid_materializations_accepted"],
            "repeat_materializations_accepted": first["repeat_materializations_accepted"],
            "missing_commitments": first["missing_commitments"],
            "consumer_invented_values": first["consumer_invented_values"],
            "deterministic_reproduction": deterministic,
        },
        "boundary_scan": boundary,
        "scientific_result_generated": False,
        "real_bank_touched": False,
        "phase10_started": False,
        "compliance_gaps": [],
    }
    audit_path = root / "results/audits/study-v3-bootstrap/bootstrap_compliance.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P9A-V3-BOOT-006: Retain the bootstrap compliance verdict with zero scientific output and zero Phase 10 execution.
    console.log("P9A-V3-BOOT-006", "Wrote the study-v3 bootstrap compliance evidence.", status="pass", details={"compliance_gaps": 0, "mutations": first["mutation_denominator"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
