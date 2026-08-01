"""Build and verify the signed final method-freeze manifest."""

from __future__ import annotations

import base64
import hashlib
import json
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pead.config.console import ResearchConsole
from pead.holdouts.commitment_verifier import verify_preseal
from pead.phase11.contracts import canonical_bytes, sha256_file, verify_file_inventory, verify_signed_mapping


PHASE11_SOURCE_PATHS = (
    "src/pead/phase11/__init__.py",
    "src/pead/phase11/contracts.py",
    "src/pead/phase11/freeze.py",
    "src/pead/phase11/unlock.py",
    "src/pead/phase11/audit.py",
    "src/pead/phase11/test_runner.py",
    "scripts/freeze_study.py",
    "scripts/unlock_blind_bank.py",
    "scripts/audit_phase11.py",
    "scripts/run_phase11_tests.py",
    "tests/unit/test_phase11_freeze.py",
    "tests/integration/test_phase11_unlock_contract.py",
    "tests/stress/test_phase11_stress.py",
    "banks/sealed/structural/STATUS.json",
    "banks/sealed/domains/STATUS.json",
    "banks/sealed/final_blind/STATUS.json",
)


def _load_or_create_key(authority_root: Path) -> Ed25519PrivateKey:
    authority_root.mkdir(parents=True, exist_ok=True)
    path = authority_root / "phase11_ed25519_private.pem"
    if path.exists():
        return serialization.load_pem_private_key(path.read_bytes(), password=None)
    private = Ed25519PrivateKey.generate()
    path.write_bytes(
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return private


def _environment() -> dict[str, Any]:
    packages: dict[str, str] = {}
    for name in ("cryptography", "numpy", "pgmpy", "psutil", "PyYAML", "scikit-learn", "torch", "transformers"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = "not-installed"
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": packages,
    }


def build_freeze(repo_root: Path, authority_root: Path, custody_operator: Path, console: ResearchConsole) -> dict[str, Any]:
    # STEP LOG P11-FREEZE-001: Verify the complete signed Phase 9A public commitment before constructing the method freeze.
    console.log("P11-FREEZE-001", "Verifying signed Phase 9A commitments and ciphertext identities.")
    receipt = verify_preseal(repo_root)
    candidate_path = repo_root / "manifests/freeze_candidate_v1.json"
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidate_entries = candidate["claim_relevant_files"]
    # STEP LOG P11-FREEZE-002: Prove every Phase 10 candidate file remains byte-identical before adding Phase 11 control code.
    console.log("P11-FREEZE-002", "Verifying the Phase 10 freeze-candidate inventory.", details={"files": len(candidate_entries)})
    verify_file_inventory(repo_root, candidate_entries)
    extras = []
    for relative in PHASE11_SOURCE_PATHS:
        path = repo_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"required Phase 11 freeze file is absent: {relative}")
        extras.append({"path": relative, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    merged = {entry["path"]: dict(entry) for entry in candidate_entries}
    merged.update({entry["path"]: entry for entry in extras})
    commitment_path = repo_root / "manifests/custody/holdout_design_commitment.json"
    index_path = repo_root / "manifests/custody/encrypted_blind_package.index.json"
    body: dict[str, Any] = {
        "schema_version": "1.0",
        "phase": 11,
        "status": "method-freeze-signed",
        "study_version": "pead-study-v2",
        "phase9a_preseal_id": receipt.preseal_id,
        "phase9a_commitment_sha256": sha256_file(commitment_path),
        "encrypted_package_index_sha256": sha256_file(index_path),
        "phase10_candidate_content_sha256": candidate["content_sha256"],
        "frozen_file_inventory": [merged[key] for key in sorted(merged)],
        "environment": _environment(),
        "frozen_surfaces": {
            "code": True,
            "configs": True,
            "environment": True,
            "truth_engines": True,
            "projections": True,
            "metrics": True,
            "audits": True,
            "methods": True,
            "checkpoints": True,
            "hyperparameters": True,
            "prompts": True,
            "operating_points": True,
            "report_templates": True,
        },
        "post_freeze_change_policy": "new-study-version-and-complete-dependent-regeneration",
        "custody_operator": {
            "interface_version": "phase11-custody-verifier-v1",
            "sha256": sha256_file(custody_operator),
            "bytes": custody_operator.stat().st_size,
        },
    }
    body_hash = hashlib.sha256(canonical_bytes(body)).hexdigest()
    body["freeze_id"] = f"freeze-{body_hash[:20]}"
    private = _load_or_create_key(authority_root)
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    body["signature"] = {
        "algorithm": "Ed25519",
        "public_key_b64": base64.b64encode(public).decode("ascii"),
        "signature_b64": base64.b64encode(private.sign(canonical_bytes(body))).decode("ascii"),
    }
    manifest_path = repo_root / "manifests/freeze_manifest.json"
    manifest_path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P11-FREEZE-003: Verify the final signature and every frozen file after writing the authoritative manifest.
    console.log("P11-FREEZE-003", "Verifying the signed final freeze manifest.", details={"freeze_id": body["freeze_id"], "files": len(body["frozen_file_inventory"])})
    verify_signed_mapping(body)
    verify_file_inventory(repo_root, body["frozen_file_inventory"])
    # STEP LOG P11-FREEZE-004: Retain the final method-freeze identity without authorizing a scientifically incomplete unlock.
    console.log("P11-FREEZE-004", "Final method freeze signed; custody materialization preflight remains mandatory.", status="pass", details={"freeze_id": body["freeze_id"]})
    return body
