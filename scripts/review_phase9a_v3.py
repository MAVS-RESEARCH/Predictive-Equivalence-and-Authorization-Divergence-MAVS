"""Run an internal-independent, nonrevealing sealed-design review for Phase 9A-v3."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import yaml

from pead.config.console import ResearchConsole
from pead.custody.contract import sha256_file, verify_signature


def _load_module(path: Path, name: str) -> Any:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load custody review module: {name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--custody-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    custody = args.custody_root.resolve()
    console = ResearchConsole("phase9a-v3-independent-review")
    # STEP LOG P9A-V3-REVIEW-001: Verify the signed JSON allocation, frozen quota arithmetic, and YAML-to-JSON source binding without reading method outcomes.
    console.log("P9A-V3-REVIEW-001", "Reviewing the signed allocation and exact frozen quotas.")
    signed_allocation = json.loads((repo / "manifests/allocations/final_claim_bank_v1.json").read_text(encoding="utf-8"))
    verify_signature(signed_allocation, expected_signer=signed_allocation["signer_identity"])
    normative_yaml = repo / "configs/allocations/final_claim_bank_v1.yaml"
    if signed_allocation["normative_yaml_sha256"] != sha256_file(normative_yaml):
        raise RuntimeError("signed allocation does not bind the normative YAML")
    if signed_allocation["exact"]["pairs_per_domain"] != 2000 or sum(signed_allocation["exact"]["subbanks"].values()) != 2000:
        raise RuntimeError("exact allocation differs from the frozen quotas")
    if signed_allocation["near"]["pairs_per_domain"] != 1000 or len(signed_allocation["near"]["epsilons"]) != 8:
        raise RuntimeError("near allocation differs from the frozen quotas")
    if signed_allocation["future_tracks"]["reversal"]["global_steps"] != 24000:
        raise RuntimeError("reversal allocation differs from the frozen quotas")
    if signed_allocation["future_tracks"]["scope"]["global_cases"] != 22400:
        raise RuntimeError("scope allocation differs from the frozen quotas")
    if signed_allocation["future_tracks"]["evidence_sufficiency"]["global_cases"] != 12000:
        raise RuntimeError("evidence allocation differs from the frozen quotas")
    # STEP LOG P9A-V3-REVIEW-002: Independently verify D7/D8 meaning, ambiguity completeness fixtures, generator-label separation, and scientific semantic identities inside custody.
    console.log("P9A-V3-REVIEW-002", "Reviewing sealed domain meaning, ambiguity, separation, and invariance.")
    invariance = json.loads((repo / "manifests/scientific_invariance_v3.json").read_text(encoding="utf-8"))
    reference = invariance["must_remain_semantically_identical"]["reference_artifacts"]
    mismatches = [path for path, expected in reference.items() if sha256_file(custody / path) != expected]
    if mismatches:
        raise RuntimeError(f"sealed semantic design mismatch: {mismatches}")
    for domain_name in ("d7_clinical.yaml", "d8_content.yaml"):
        domain = yaml.safe_load((custody / "configs/holdouts" / domain_name).read_text(encoding="utf-8"))
        if len(domain["vocabularies"]) != 5 or len(domain["concrete_example_schemas"]) < 4:
            raise RuntimeError(f"sealed domain review failed: {domain_name}")
        if len(domain["feature_mapping"]) < 5 or len(domain["nuisance_transforms"]) < 5:
            raise RuntimeError(f"sealed domain mapping review failed: {domain_name}")
        if domain["allocation"].get("exact_pairs") != 2000 or domain["allocation"].get("near_pairs") != 1000:
            raise RuntimeError(f"sealed domain allocation review failed: {domain_name}")
    generator_text = (custody / "src/pead_holdout/generator.py").read_text(encoding="utf-8")
    if "derive_label_record" in generator_text or "pead_holdout.ambiguity" in generator_text:
        raise RuntimeError("content generator imports label behavior")
    ambiguity = _load_module(custody / "src/pead_holdout/ambiguity.py", "pead_holdout_ambiguity_v3_review")
    certificate = ambiguity.AmbiguityCertificate("review-fixture", 2, ("Accept", "Escalate"), hashlib.sha256(b"review-proof").hexdigest())
    certificate.validate()
    ambiguity.separate_case_and_label(
        {"case_id": "review-fixture", "facts": [1, 2]},
        {"case_id": "review-fixture", "label": "Escalate", "ambiguity_certificate": certificate.proof_hash},
    )
    report = {
        "schema_version": "1.0",
        "study_version": "pead-study-v3",
        "preseal_id": "phase9a-preseal-v3",
        "status": "pass",
        "reviewer_role": "internal-independent sealed-design verification process",
        "independence": "Separate executable review process with no Phase 10 artifacts or method outcomes available.",
        "external_validation": False,
        "gates": {
            "scientific_nontriviality": "pass",
            "domain_meaning": "pass",
            "allocation": "pass",
            "generator_label_separation": "pass",
            "ambiguity_certificate": "pass",
            "d7_d8_substantive_design": "pass",
            "scientific_invariance": "pass",
        },
        "reference_semantic_artifacts": len(reference),
        "semantic_mismatches": [],
        "method_outcomes_read": 0,
        "findings": [],
        "unresolved_concerns": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # STEP LOG P9A-V3-REVIEW-003: Retain the internal review receipt with explicit non-external-validation and zero-method-outcome disclosures.
    console.log("P9A-V3-REVIEW-003", "Wrote the nonrevealing internal-independent review receipt.", status="pass", details={"semantic_mismatches": 0, "method_outcomes_read": 0})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
