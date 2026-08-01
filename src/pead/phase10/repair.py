"""Repair and prove isolation of the Phase 10 Oracle representation defect."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from pead.config.console import ResearchConsole
from pead.phase10.banks import ROLE_ROOTS, generate_open_banks, iter_role_arrays
from pead.phase10.training import RUN_ID


def _update_array(digest: Any, value: np.ndarray) -> None:
    contiguous = np.ascontiguousarray(value)
    digest.update(str(contiguous.dtype).encode("ascii"))
    digest.update(json.dumps(contiguous.shape).encode("ascii"))
    digest.update(contiguous.tobytes())


def _projection_digest(root: Path, end: int) -> str:
    digest = hashlib.sha256()
    for role in ROLE_ROOTS:
        digest.update(role.encode("utf-8"))
        for shard in iter_role_arrays(root, role):
            for field in ("case_id", "world_id", "atomic_group_id", "label"):
                _update_array(digest, shard[field])
            _update_array(digest, shard["features"][:, :end])
    return digest.hexdigest()


def repair_oracle_representation(root: Path, console: ResearchConsole) -> dict[str, Any]:
    # STEP LOG P10-REPAIR-001: Hash every P-only and Raw-G identity, label, and feature byte before regenerating the Oracle-only representation.
    console.log("P10-REPAIR-001", "Hashing unaffected projections before Oracle repair.")
    before = {"P-only": _projection_digest(root, 8), "Raw-G": _projection_digest(root, 16)}
    old_manifest = hashlib.sha256((root / "results/manifests/phase10/open_bank_manifest.json").read_bytes()).hexdigest()
    # STEP LOG P10-REPAIR-002: Regenerate every open-bank container with lossless Oracle labels and no change to P-only or Raw-G projections.
    console.log("P10-REPAIR-002", "Regenerating open banks with lossless Oracle representation.")
    generate_open_banks(root, console)
    after = {"P-only": _projection_digest(root, 8), "Raw-G": _projection_digest(root, 16)}
    if before != after:
        raise ValueError("Oracle repair changed a P-only or Raw-G projection, identity, or label")
    reconstructed = total = 0
    for role in ROLE_ROOTS:
        for shard in iter_role_arrays(root, role):
            labels = shard["features"][:, 23].astype(np.uint8)
            reconstructed += int(np.count_nonzero(labels == shard["label"])); total += len(labels)
    if reconstructed != total:
        raise ValueError("Oracle reconstruction is not lossless")
    report = {
        "schema_version": "1.0", "phase": 10, "run_id": RUN_ID, "status": "pass",
        "defect": "Oracle projection omitted the exact-control authorization override",
        "classification": "interface_only_infrastructure_defect",
        "invalidation_scope": "Oracle-profile validation, processed reports, audit, and freeze candidate",
        "retained_training_scope": "P-only and Raw-G checkpoints only after byte-level projection proof",
        "old_open_bank_manifest_sha256": old_manifest,
        "new_open_bank_manifest_sha256": hashlib.sha256((root / "results/manifests/phase10/open_bank_manifest.json").read_bytes()).hexdigest(),
        "projection_digests_before": before, "projection_digests_after": after,
        "unchanged_projection_proof": before == after,
        "oracle_reconstruction_correct": reconstructed, "oracle_reconstruction_total": total,
        "oracle_rule_accuracy": reconstructed / total,
        "invalidated_artifact_archive": "C:/Users/Saif malik/OneDrive/Documents/Desktop/Documents/PEAD_INVALIDATED_PHASE10_ORACLE_VALIDATION",
    }
    path = root / f"results/audits/{RUN_ID}/oracle_repair.json"; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P10-REPAIR-003: Retain the byte-equivalence and full Oracle reconstruction proof before downstream reruns.
    console.log("P10-REPAIR-003", "Oracle repair isolation proof retained.", status="pass", details={"cases": total, "oracle_rule_accuracy": 1.0})
    return report
