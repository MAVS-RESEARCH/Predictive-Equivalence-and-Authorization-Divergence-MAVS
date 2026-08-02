"""Remove transient runtime caches from the Phase 10 candidate before final freeze."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.custody.contract import sha256_file
from pead.phase11.contracts import atomic_json


def _transient(path: str) -> bool:
    parts = Path(path).parts
    return path.endswith(".pyc") or "__pycache__" in parts or ".pytest_cache" in parts or "tmp" in parts


def correct(root: Path, console: ResearchConsole) -> dict[str, object]:
    candidate_path = root / "manifests/freeze_candidate_v1.json"
    receipt_path = root / "results/audits/phase11-prefreeze/phase10_candidate_correction.json"
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if sha256_file(candidate_path) != receipt["corrected_candidate_sha256"]:
            raise ValueError("corrected Phase 10 candidate no longer matches its retained receipt")
        return receipt
    candidate_bytes = candidate_path.read_bytes()
    candidate = json.loads(candidate_bytes.decode("utf-8"))
    files = candidate["claim_relevant_files"]
    transient = {path: digest for path, digest in files.items() if _transient(path)}
    if not transient:
        raise ValueError("Phase 10 candidate contains no transient entries to correct")
    # STEP LOG P11-CANDIDATE-001: Verify every nontransient Phase 10 candidate identity before removing runtime caches.
    console.log("P11-CANDIDATE-001", "Verifying all nontransient Phase 10 candidate identities before correction.", details={"candidate_entries": len(files), "transient_entries": len(transient)})
    nontransient = {path: digest for path, digest in files.items() if path not in transient}
    mismatches = [path for path, digest in nontransient.items() if not (root / path).is_file() or sha256_file(root / path) != digest]
    if mismatches:
        raise ValueError(f"nontransient Phase 10 candidate identities changed: {mismatches[:10]}")
    original_hash = hashlib.sha256(candidate_bytes).hexdigest()
    original_content_hash = candidate["manifest_content_sha256"]
    candidate["claim_relevant_files"] = nontransient
    candidate["claim_relevant_file_count"] = len(nontransient)
    candidate.pop("manifest_content_sha256")
    candidate["manifest_content_sha256"] = hashlib.sha256(json.dumps(candidate, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    # STEP LOG P11-CANDIDATE-002: Rewrite only the generated candidate inventory while preserving every scientific, method, checkpoint, operating-point, metric, audit, and report hash.
    console.log("P11-CANDIDATE-002", "Removing transient bytecode entries from the generated freeze candidate.", details={"retained_entries": len(nontransient)})
    atomic_json(candidate_path, candidate)
    receipt: dict[str, object] = {
        "schema_version": "1.0",
        "phase": 11,
        "study_version": "pead-study-v3",
        "preseal_id": "phase9a-preseal-v3",
        "status": "corrected-before-final-freeze-before-unlock",
        "original_candidate_sha256": original_hash,
        "original_manifest_content_sha256": original_content_hash,
        "original_entry_count": len(files),
        "removed_transient_entries": transient,
        "removed_transient_count": len(transient),
        "corrected_entry_count": len(nontransient),
        "corrected_candidate_sha256": sha256_file(candidate_path),
        "corrected_manifest_content_sha256": candidate["manifest_content_sha256"],
        "nontransient_mismatches": [],
        "scientific_files_changed": 0,
        "method_files_changed": 0,
        "checkpoint_files_changed": 0,
        "operating_point_files_changed": 0,
        "metric_audit_report_files_changed": 0,
        "blind_access_occurred": False,
    }
    atomic_json(receipt_path, receipt)
    # STEP LOG P11-CANDIDATE-003: Verify the corrected candidate and retain the complete removed-entry custody receipt.
    console.log("P11-CANDIDATE-003", "Verified the source-based Phase 10 candidate correction.", status="pass", details={"removed_transient_entries": len(transient), "scientific_files_changed": 0})
    return receipt


def main() -> int:
    root = Path.cwd().resolve()
    correct(root, ResearchConsole("11"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

