"""Fail-closed Phase 9A compliance audit over nonrevealing repository evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from pead.config.console import ResearchConsole
from pead.holdouts.commitment_verifier import verify_preseal, verify_signed_mapping


PRESEAL_ID = "phase9a-preseal-v2"
REQUIRED_CUSTODY_AUDITS = ("holdout_design", "allocation", "custody", "human_review")
FORBIDDEN_REPOSITORY_PATTERNS = (
    r"exact_hidden_seeds_v1", r"phase9a_aes256\.key", r"phase9a_ed25519_private",
    r"def generate_case\(", r"template_families: \[eligibility", r"template_families: \[access",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _allocation_semantics(yaml_value: dict[str, Any], json_value: dict[str, Any]) -> bool:
    candidate = dict(json_value)
    candidate.pop("signature", None); candidate.pop("normative_yaml_sha256", None); candidate.pop("canonicalization", None)
    candidate["normative_status"] = "human_authored_pending_phase_9a_signature"
    candidate["final_signature"] = {"phase": "9A", "status": "pending", "required_output": "manifests/allocations/final_claim_bank_v1.json"}
    return candidate == yaml_value


def _inventory_logs(paths: list[Path], root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            match = re.search(r'console\.log\("(P9A-[A-Z0-9-]+)"', line)
            if match:
                prior = lines[index - 1].strip() if index else ""
                if not prior.startswith(f"# STEP LOG {match.group(1)}:"):
                    raise ValueError(f"missing adjacent identifying comment: {path}:{index + 1}")
                rows.append({"file": str(path.relative_to(root)).replace("\\", "/"), "comment_line": index, "console_log_line": index + 1, "event_id": match.group(1), "comment": prior[2:]})
    return rows


def run_audit(root: Path, console: ResearchConsole) -> dict[str, Any]:
    audit_root = root / f"results/audits/{PRESEAL_ID}"
    # STEP LOG P9A-AUDIT-001: Verify all public signatures, ciphertext hashes, and separated package roles.
    console.log("P9A-AUDIT-001", "Verifying public signatures and encrypted package identities.")
    receipt = verify_preseal(root)
    allocation_path = root / "manifests/allocations/final_claim_bank_v1.json"
    allocation = json.loads(allocation_path.read_text(encoding="utf-8"))
    normative_path = root / "configs/allocations/final_claim_bank_v1.yaml"
    normative = yaml.safe_load(normative_path.read_text(encoding="utf-8"))
    # STEP LOG P9A-AUDIT-002: Prove normative YAML hash identity and YAML-to-signed-JSON semantic equality.
    console.log("P9A-AUDIT-002", "Auditing allocation canonicalization and exact registered quotas.")
    if allocation["normative_yaml_sha256"] != sha256_file(normative_path) or not _allocation_semantics(normative, allocation):
        raise ValueError("normative allocation YAML and signed JSON are not semantically identical")
    if sum(allocation["exact"]["subbanks"].values()) != 2000 or sum(allocation["exact"]["mechanism_pairs_per_domain"].values()) != 2000:
        raise ValueError("exact allocation totals changed")
    if sum(allocation["near"]["per_cell"].values()) != 125 or len(allocation["near"]["epsilons"]) != 8:
        raise ValueError("near allocation totals changed")
    # STEP LOG P9A-AUDIT-003: Require custody test evidence for allocation, groups, distance, ambiguity, separation, and access denial.
    console.log("P9A-AUDIT-003", "Validating sealed-workspace test and read-audit receipts.")
    custody_audits = {name: json.loads((audit_root / f"{name}.json").read_text(encoding="utf-8")) for name in REQUIRED_CUSTODY_AUDITS}
    if any(value.get("status") != "pass" or value.get("preseal_id") != PRESEAL_ID for value in custody_audits.values()):
        raise ValueError("custody audit evidence is missing or failed")
    required_gates = {
        "allocation", "atomic_groups", "typed_distance", "ambiguity_certificate",
        "generator_label_separation", "signed_json_only", "development_access_denial",
        "append_only_log", "d7_d8_vocabularies", "surface_distributions",
        "feature_mappings", "nuisance_transforms", "concrete_example_schemas",
    }
    observed_gates = {gate for value in custody_audits.values() for gate, status in value.get("gates", {}).items() if status == "pass"}
    if not required_gates.issubset(observed_gates):
        raise ValueError(f"custody gates absent: {sorted(required_gates - observed_gates)}")
    # STEP LOG P9A-AUDIT-004: Scan tracked development files for private keys, exact seeds, D7/D8 implementations, and generators.
    console.log("P9A-AUDIT-004", "Scanning development repository for prohibited custody content.")
    allowed_suffixes = {".py", ".yaml", ".yml", ".json", ".md", ".toml"}
    scan_paths = [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in allowed_suffixes and ".git" not in path.parts and ".venv" not in path.parts and "tmp" not in path.parts]
    violations = []
    for path in scan_paths:
        relative = str(path.relative_to(root)).replace("\\", "/")
        if relative in {"WorkPlan.md", "docs/blind_custody_protocol.md", "Path.md", "src/pead/phase9a/audit.py"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        violations.extend(f"{relative}:{pattern}" for pattern in FORBIDDEN_REPOSITORY_PATTERNS if re.search(pattern, text))
    if violations:
        raise ValueError(f"custody content exposed in development: {violations}")
    # STEP LOG P9A-AUDIT-005: Prove commitment chronology predates all Phase 10 training, calibration, and public-validation artifacts.
    console.log("P9A-AUDIT-005", "Checking the signed Phase 9A chronology receipt.")
    phase10_paths = [root / "banks/development", root / "banks/calibration", root / "banks/public_validation", root / "manifests/freeze_candidate_v1.json"]
    phase10_artifacts = sum(1 for path in phase10_paths if path.exists())
    commitment = json.loads((root / "manifests/custody/holdout_design_commitment.json").read_text(encoding="utf-8"))
    verify_signed_mapping(commitment)
    if not commitment["chronology"]["phase9a_precedes_phase10"] or commitment["chronology"]["phase10_artifact_count_at_seal"] != 0:
        raise ValueError("Phase 9A chronology gate failed")
    # STEP LOG P9A-AUDIT-006: Inventory every repository Phase 9A console.log and its immediately adjacent identifying comment.
    console.log("P9A-AUDIT-006", "Inventorying Phase 9A line instrumentation.")
    code_paths = list((root / "src/pead/holdouts").glob("*.py")) + list((root / "src/pead/phase9a").glob("*.py"))
    inventory = _inventory_logs(code_paths, root)
    inventory_path = audit_root / "console_inventory.json"
    inventory_path.write_text(json.dumps({"schema_version": "1.0", "phase": "9A", "status": "pass", "entries": inventory}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = {
        "schema_version": "1.0", "phase": "9A", "preseal_id": PRESEAL_ID, "status": "pass",
        "verified_ciphertexts": list(receipt.verified_ciphertexts), "design_artifacts_signed": commitment["design_artifact_count"],
        "allocation_semantic_equality": "pass", "custody_gates": sorted(required_gates),
        "repository_scan_files": len(scan_paths), "repository_scan_violations": [],
        "phase10_artifact_count_at_audit": phase10_artifacts,
        "phase10_artifact_count_at_seal": commitment["chronology"]["phase10_artifact_count_at_seal"],
        "console_log_sites": len(inventory), "change_policy": commitment["change_policy"], "compliance_gaps": [],
    }
    # STEP LOG P9A-AUDIT-007: Emit the zero-gap verdict only after every Phase 9A completion gate passes.
    console.log("P9A-AUDIT-007", "Phase 9A compliance audit passed.", status="pass", details={"compliance_gaps": 0, "design_artifacts": commitment["design_artifact_count"], "ciphertexts": len(receipt.verified_ciphertexts)})
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    parser.add_argument("--report", type=Path, default=Path(f"results/audits/{PRESEAL_ID}/phase9a_compliance.json"))
    args = parser.parse_args(); root = args.repo_root.resolve(); console = ResearchConsole("9A")
    try:
        report = run_audit(root, console)
    except Exception as exc:
        # STEP LOG P9A-AUDIT-FAIL: Retain the exact release-blocking Phase 9A compliance failure.
        console.log("P9A-AUDIT-FAIL", "Phase 9A compliance audit failed.", status="fail", details={"error": str(exc)})
        report = {"schema_version": "1.0", "phase": "9A", "status": "fail", "error": str(exc), "compliance_gaps": [str(exc)]}
    path = args.report if args.report.is_absolute() else root / args.report; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__": raise SystemExit(main())
