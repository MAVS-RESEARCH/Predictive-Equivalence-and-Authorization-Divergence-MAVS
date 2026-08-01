"""Extreme-rigor WorkPlan Phase 8 compliance audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash
from pead.mavs.ablations import load_ablation_registry
from pead.mavs.profiles import load_profiles
from pead.phase0.audit import inventory_console_logs
from pead.phase2.audit import write_json
from pead.phase8.review import execute_phase8_review

EXPECTED_FILES = {
    *(f"src/pead/mavs/{name}.py" for name in ("adapter", "governed_consensus", "ds_cf", "profiles", "scalarization", "ablations", "traces")),
    *(f"configs/diagnostics/ds_cf_z{name}.yaml" for name in ("c", "h", "s", "m", "p", "o", "f")),
    "configs/methods/mavs_profiles_v1.yaml",
    "configs/methods/mavs_ablations_v1.yaml",
    "configs/methods/mavs_scalarization_v1.yaml",
    "configs/methods/mavs_adapter_v1.yaml",
    "tests/unit/test_ds_cf_invariants.py",
    "tests/integration/test_mavs_adapter.py",
    "tests/property/test_mavs_scope_and_veto.py",
}
EXPECTED_ABLATIONS = {f"MAVS-A{index:02d}" for index in range(16)}


def _audit_files(root: Path) -> dict[str, Any]:
    missing = sorted(path for path in EXPECTED_FILES if not (root / path).is_file())
    if missing:
        raise ValueError(f"Phase 8 required-file gap: {missing}")
    return {"status": "pass", "required_files": len(EXPECTED_FILES), "missing": []}


def _audit_profiles(root: Path) -> dict[str, Any]:
    profiles = load_profiles(root)
    expected = {"MAVS-PREDICTION-ONLY-v1", "MAVS-GC-ORIGINAL-v1", "MAVS-GC-DSCF-v1"}
    if set(profiles) != expected:
        raise ValueError("MAVS profile inventory is not exact")
    gates = {
        name: {
            "frozen": profile.status == "frozen",
            "versioned": profile.version == "1.0.0",
            "diagnostic_separation": profile.profile_id != "MAVS-PREDICTION-ONLY-v1" or not profile.enabled_diagnostics,
        }
        for name, profile in profiles.items()
    }
    if not all(all(values.values()) for values in gates.values()):
        raise ValueError(f"MAVS frozen-profile gate failed: {gates}")
    return {"status": "pass", "profiles": gates, "profile_hashes": {key: value.profile_hash for key, value in profiles.items()}}


def _audit_ablations_and_information(root: Path) -> dict[str, Any]:
    records = load_ablation_registry(root)
    config = yaml.safe_load((root / "configs/methods/mavs_ablations_v1.yaml").read_text(encoding="utf-8"))
    inventory = yaml.safe_load((root / "configs/methods/method_inventory_v1.yaml").read_text(encoding="utf-8"))
    inventory_ids = {row["method_id"] for row in inventory["methods"] if row["method_id"].startswith("MAVS-A")}
    equal = config["equal_information"]
    gates = {
        "exact_registry": set(records) == EXPECTED_ABLATIONS,
        "exact_inventory": inventory_ids == EXPECTED_ABLATIONS,
        "prediction_only_A00": records["MAVS-A00"]["access_profile"] == "P-only",
        "raw_g_A01_A15": all(records[f"MAVS-A{index:02d}"]["access_profile"] == "Raw-G" for index in range(1, 16)),
        "one_registered_delta": all(len(record["changed_components"]) == 1 for record in records.values()),
        "four_open_roles": equal["roles"] == ["development_fit", "development_selection", "calibration_fit", "calibration_policy"],
        "same_underlying_ids": equal["identical_underlying_ids"] == ["world_id", "pair_id", "sequence_id", "atomic_group_id", "partition_id"],
        "all_raw_g_listed": set(equal["raw_g_methods"]) == EXPECTED_ABLATIONS - {"MAVS-A00"},
        "only_registered_delta": equal["only_registered_component_delta"] is True,
    }
    if not all(gates.values()):
        raise ValueError(f"MAVS ablation/equal-information gate failed: {gates}")
    return {"status": "pass", "conditions": sorted(records), "gates": gates}


def _audit_scalarization(root: Path) -> dict[str, Any]:
    scalar = yaml.safe_load((root / "configs/methods/mavs_scalarization_v1.yaml").read_text(encoding="utf-8"))
    learned = scalar["learned"]
    gates = {
        "same_four_roles": learned["identity_roles"] == ["development_fit", "development_selection", "calibration_fit", "calibration_policy"],
        "comparable_raw_g_learner": learned["comparable_raw_g_method"] == "G11-SCALAR-trained",
        "same_budget_policy": learned["budget_policy"] == "PEAD-RAW-G-FIXED-v1.G11-SCALAR.trained",
        "phase10_artifact_required": learned["production_requires_selected_phase10_artifact"] is True,
        "structural_domain_holdouts": scalar["central_compression_test"]["required_holdouts"] == ["structural", "domain"],
        "executable": scalar["central_compression_test"]["executable"] is True,
    }
    if not all(gates.values()):
        raise ValueError(f"scalarization contract gate failed: {gates}")
    return {"status": "pass", "gates": gates}


def _audit_test_evidence(root: Path) -> dict[str, Any]:
    report = json.loads((root / "results/audits/phase8/phase8_tests.json").read_text(encoding="utf-8"))
    stress = report.get("stress_gates", {})
    rules = stress.get("rule_fidelity", {})
    ablations = stress.get("ablations", {})
    monotonicity = stress.get("monotonicity", {})
    if (
        report.get("status") != "pass" or report.get("failures") or report.get("errors")
        or report.get("tests_run", 0) < 167 or rules.get("vectors") != 279_936
        or rules.get("active_veto_combinations") != 27_216 or rules.get("veto_violations") != 0
        or ablations.get("decisions") != 4_096 or ablations.get("complete_traces") != 4_096
        or monotonicity.get("pairs") != 1_000 or monotonicity.get("violations") != 0
        or stress.get("scientific_results") != 0
    ):
        raise ValueError("Phase 8 complete-suite evidence is incomplete")
    return {"status": "pass", "tests_run": report["tests_run"], "failures": 0, "errors": 0, "stress_gates": stress}


def _audit_phase_boundary(root: Path) -> dict[str, Any]:
    forbidden = [
        path.relative_to(root).as_posix()
        for directory in (root / "results/models", root / "results/checkpoints", root / "results/processed")
        if directory.exists()
        for path in directory.rglob("*") if path.is_file() and "phase8" in path.as_posix().lower()
    ]
    if forbidden:
        raise ValueError(f"Phase 8 created scientific/training artifacts: {forbidden}")
    return {"status": "pass", "scientific_results": 0, "trained_models": 0, "released_rows": 0, "forbidden_artifacts": []}


def _write_manifest(root: Path, review: dict[str, Any]) -> dict[str, Any]:
    paths = sorted((root / "src/pead/mavs").glob("*.py")) + sorted((root / "configs/methods").glob("mavs_*.yaml")) + sorted((root / "configs/diagnostics").glob("ds_cf_*.yaml"))
    files = {path.relative_to(root).as_posix(): canonical_hash(path.read_bytes()) for path in paths}
    manifest = {
        "schema_version": "1.0", "phase": 8, "registry_id": "PEAD-MAVS-IMPLEMENTATION-v1",
        "files": files, "profile_hashes": review["profiles"],
        "diagnostic_definition_hashes": review["semantic_registry"]["definition_hashes"],
        "phase4_registry_sha256": review["semantic_registry"]["phase4_registry_sha256"],
        "ablation_ids": review["ablation_registry"], "released_rows": 0,
    }
    manifest["manifest_sha256"] = canonical_hash(manifest)
    write_json(root / "results/manifests/phase8/mavs_registry_v1.json", manifest)
    return {"status": "pass", "files": len(files), "manifest_sha256": manifest["manifest_sha256"]}


def _audit_console_inventory(root: Path) -> dict[str, Any]:
    entries = [entry for entry in inventory_console_logs(root) if entry["event_id"].startswith("P8-")]
    if not entries:
        raise ValueError("Phase 8 console inventory is empty")
    return {"status": "pass", "events": len(entries), "entries": entries}


def _write_component_reports(output: Path, **reports: dict[str, Any]) -> None:
    for name, report in reports.items():
        write_json(output / f"{name}.json", {"schema_version": "1.0", **report})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output = root / "results/audits/phase8"
    console = ResearchConsole("8")
    try:
        # STEP LOG P8-AUDIT-001: Verify every WorkPlan-named Phase 8 source, configuration, and test file exists.
        console.log("P8-AUDIT-001", "Auditing required Phase 8 files.")
        files = _audit_files(root)
        # STEP LOG P8-AUDIT-002: Prove prediction-only, original, and DS-CF profiles are exact, frozen, and versioned.
        console.log("P8-AUDIT-002", "Auditing frozen MAVS profiles.")
        profiles = _audit_profiles(root)
        # STEP LOG P8-AUDIT-003: Prove A00-A15 identity, access parity, single deltas, stable IDs, and four open-data roles.
        console.log("P8-AUDIT-003", "Auditing ablations and equal-information controls.")
        ablations = _audit_ablations_and_information(root)
        # STEP LOG P8-AUDIT-004: Verify learned scalar identity/budget parity and executable structural/domain compression holdouts.
        console.log("P8-AUDIT-004", "Auditing scalarization controls.")
        scalarization = _audit_scalarization(root)
        # STEP LOG P8-AUDIT-005: Independently execute semantic, exhaustive-veto, trace, monotonicity, scalar, and dependency reviews.
        console.log("P8-AUDIT-005", "Executing independent MAVS implementation review.")
        review = execute_phase8_review(root, console)
        # STEP LOG P8-AUDIT-006: Validate the complete repository regression and retained high-volume Phase 8 test evidence.
        console.log("P8-AUDIT-006", "Auditing complete-suite evidence.")
        tests = _audit_test_evidence(root)
        # STEP LOG P8-AUDIT-007: Prove Phase 8 produced no training, model-selection, released-bank, or scientific-result artifact.
        console.log("P8-AUDIT-007", "Auditing Phase 8 boundary.")
        boundary = _audit_phase_boundary(root)
        # STEP LOG P8-AUDIT-008: Freeze exact MAVS source, configuration, profile, diagnostic, and ablation identities.
        console.log("P8-AUDIT-008", "Writing Phase 8 implementation manifest.")
        manifest = _write_manifest(root, review)
        # STEP LOG P8-AUDIT-009: Inventory every Phase 8 console.log with its adjacent identifying STEP LOG comment and exact line.
        console.log("P8-AUDIT-009", "Auditing Phase 8 console instrumentation.")
        console_inventory = _audit_console_inventory(root)
        reports = {
            "required_files": files, "profiles": profiles, "ablations": ablations,
            "scalarization": scalarization, "implementation_review": review,
            "test_evidence": tests, "phase_boundary": boundary,
            "implementation_manifest": manifest, "console_inventory": console_inventory,
        }
        _write_component_reports(output, **reports)
        compliance = {"schema_version": "1.0", "phase": 8, "status": "pass", "compliance_gaps": [], "checks": reports}
        write_json(output / "phase8_compliance.json", compliance)
        # STEP LOG P8-AUDIT-010: Emit the zero-gap Phase 8 completion verdict only after every independent gate passes.
        console.log(
            "P8-AUDIT-010", "Phase 8 compliance audit passed.", status="pass",
            details={"compliance_gaps": 0, "tests": tests["tests_run"], "veto_vectors": review["rule_fidelity"]["vectors"]},
        )
        return 0
    except Exception as exc:
        write_json(output / "phase8_compliance.json", {"schema_version": "1.0", "phase": 8, "status": "fail", "compliance_gaps": [str(exc)]})
        # STEP LOG P8-AUDIT-FAIL: Retain the release-blocking Phase 8 compliance failure.
        console.log("P8-AUDIT-FAIL", "Phase 8 compliance audit failed.", status="fail", details={"error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
