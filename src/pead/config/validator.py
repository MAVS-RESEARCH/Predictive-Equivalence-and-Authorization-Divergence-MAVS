"""Phase 0 configuration validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

import yaml

from pead.config.console import ResearchConsole
from pead.config.models import (
    ConfigValidationError,
    MethodEntry,
    RequirementEntry,
    StateField,
    require_keys,
    require_mapping,
    require_sequence,
    require_string,
    require_unique,
)


PREDICTIVE_IDS = {
    "P-SHARED-v1",
    "P-SPECIALISTS-v1",
    "P-SUPPORT-v1",
    "P-LABEL-v1",
    "P-CONFIDENCE-v1",
    "P-UNCERTAINTY-v1",
    "P-AGREEMENT-v1",
    "P-CALIBRATION-v1",
    "P-ACTION-v1",
}
GOVERNANCE_IDS = {
    "G-PROVENANCE-v1",
    "G-AUTHORITY-v1",
    "G-POLICY-v1",
    "G-TEMPORAL-v1",
    "G-REVERSIBILITY-v1",
    "G-CONSEQUENCE-v1",
    "G-EVIDENCE-v1",
    "G-DEPENDENCY-v1",
    "G-CFVIEW-v1",
}
DIAGNOSTIC_IDS = {
    "DSCF-ZC-v1",
    "DSCF-ZH-v1",
    "DSCF-ZS-v1",
    "DSCF-ZM-v1",
    "DSCF-ZP-v1",
    "DSCF-ZO-v1",
    "DSCF-ZF-v1",
}
DATA_ROLES = {
    "development_fit",
    "development_selection",
    "calibration_fit",
    "calibration_policy",
}
SOURCE_FILES = {
    "PEAD_Benchmark_Implementation_Specification_v1.0.docx",
    "MAVS-Diagnostic Sciences.pdf",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_yaml(path: Path) -> Mapping[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ConfigValidationError(f"Cannot load YAML {path}: {error}") from error
    return require_mapping(data, str(path))


class Phase0Validator:
    """Validate every artifact frozen by WorkPlan Phase 0."""

    def __init__(
        self,
        repo_root: Path,
        *,
        console: ResearchConsole | None = None,
        source_root: Path | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.console = console or ResearchConsole("0")
        self.source_root = source_root
        self.counts: dict[str, int] = {}

    def validate(self, *, verify_sources: bool = False) -> dict[str, Any]:
        # STEP LOG P0-VALIDATE-001: Begin the complete Phase 0 validation sequence.
        self.console.log(
            "P0-VALIDATE-001",
            "Phase 0 validation started.",
            details={"repo_root": str(self.repo_root), "verify_sources": verify_sources},
        )
        # STEP LOG P0-VALIDATE-002: Validate the study charter and source identities.
        self.console.log("P0-VALIDATE-002", "Validating study charter and source identities.")
        self._validate_study(verify_sources=verify_sources)
        # STEP LOG P0-VALIDATE-003: Validate PredictiveState and GovernanceState dictionaries.
        self.console.log("P0-VALIDATE-003", "Validating frozen state dictionaries.")
        self._validate_state_dictionaries()
        # STEP LOG P0-VALIDATE-004: Validate the Diagnostic Sciences registry.
        self.console.log("P0-VALIDATE-004", "Validating Diagnostic Sciences registry.")
        self._validate_diagnostics()
        # STEP LOG P0-VALIDATE-005: Validate the frozen method inventory.
        self.console.log("P0-VALIDATE-005", "Validating frozen method inventory.")
        self._validate_methods()
        # STEP LOG P0-VALIDATE-006: Validate holdout custody and single-unlock controls.
        self.console.log("P0-VALIDATE-006", "Validating holdout custody registry.")
        self._validate_holdouts()
        # STEP LOG P0-VALIDATE-007: Validate the protected operating-point objective.
        self.console.log("P0-VALIDATE-007", "Validating protected operating-point objective.")
        self._validate_protected_objective()
        # STEP LOG P0-VALIDATE-008: Validate the strict FailureCard contract.
        self.console.log("P0-VALIDATE-008", "Validating strict FailureCard schema.")
        self._validate_failure_card_schema()
        # STEP LOG P0-VALIDATE-009: Validate the clause-level requirements registry.
        self.console.log("P0-VALIDATE-009", "Validating clause-level requirements registry.")
        self._validate_requirements()
        # STEP LOG P0-VALIDATE-010: Validate the human-readable claim ledger.
        self.console.log("P0-VALIDATE-010", "Validating claim ledger boundaries.")
        self._validate_claims()
        report = {
            "phase": 0,
            "status": "pass",
            "counts": dict(sorted(self.counts.items())),
            "verified_sources": verify_sources,
        }
        # STEP LOG P0-VALIDATE-011: Report successful completion and audited counts.
        self.console.log(
            "P0-VALIDATE-011",
            "Phase 0 validation passed.",
            status="pass",
            details=report["counts"],
        )
        return report

    def _validate_study(self, *, verify_sources: bool) -> None:
        path = self.repo_root / "configs/study/pead_main_v1.yaml"
        data = load_yaml(path)
        require_keys(
            data,
            (
                "schema_version",
                "study",
                "source_documents",
                "hypotheses",
                "claims",
                "data_roles",
                "data_role_constraints",
                "access_profiles",
                "cross_profile_identity",
                "integrity_gates",
                "negative_result_policy",
                "outcome_tiers",
                "stop_conditions",
                "versioning",
            ),
            str(path),
        )
        hypotheses = require_mapping(data["hypotheses"], f"{path}.hypotheses")
        if set(hypotheses) != {"H1", "H2", "H3"}:
            raise ConfigValidationError("Study hypotheses must be exactly H1, H2, and H3")
        if hypotheses["H1"] is hypotheses["H2"] or hypotheses["H1"] == hypotheses["H2"]:
            raise ConfigValidationError("H1 and H2 must remain distinct")
        for hypothesis_id in ("H1", "H2"):
            hypothesis = require_mapping(
                hypotheses[hypothesis_id], f"{path}.hypotheses.{hypothesis_id}"
            )
            if hypothesis.get("independently_reportable") is not True:
                raise ConfigValidationError(
                    f"{hypothesis_id} must be independently reportable"
                )
        claims = require_mapping(data["claims"], f"{path}.claims")
        if set(require_sequence(claims["ids"], f"{path}.claims.ids")) != {
            "C1",
            "C2",
            "C3",
            "C4",
            "C5",
            "C6",
        }:
            raise ConfigValidationError("Claim IDs must be exactly C1-C6")
        roles = require_sequence(data["data_roles"], f"{path}.data_roles")
        role_ids = {
            require_string(require_mapping(item, "data role")["id"], "data role id")
            for item in roles
        }
        if role_ids != DATA_ROLES:
            raise ConfigValidationError(f"Data roles must be exactly {sorted(DATA_ROLES)}")
        if any(
            require_mapping(item, "data role").get("group_atomic") is not True
            for item in roles
        ):
            raise ConfigValidationError("Every open-data role must be group-atomic")
        constraints = require_mapping(
            data["data_role_constraints"], f"{path}.data_role_constraints"
        )
        if constraints.get("mutually_disjoint") is not True:
            raise ConfigValidationError("Data roles must be mutually disjoint")
        if constraints.get("public_validation") != "inspection-only":
            raise ConfigValidationError("Public validation must be inspection-only")
        profiles = require_mapping(data["access_profiles"], f"{path}.access_profiles")
        if set(profiles) != {"P-only", "Raw-G", "Oracle-G"}:
            raise ConfigValidationError("Access profiles must be P-only, Raw-G, Oracle-G")
        cross_profile = require_mapping(
            data["cross_profile_identity"], f"{path}.cross_profile_identity"
        )
        required_ids = {
            "world_id",
            "pair_id",
            "sequence_id",
            "atomic_group_id",
            "partition_id",
        }
        if set(cross_profile.get("identical_ids", [])) != required_ids:
            raise ConfigValidationError("Cross-profile identity fields are incomplete")
        if cross_profile.get("only_projection_may_differ") is not True:
            raise ConfigValidationError("Only the projection may differ across profiles")
        negative = require_mapping(
            data["negative_result_policy"], f"{path}.negative_result_policy"
        )
        if negative.get("publish_integrity_valid_negative") is not True:
            raise ConfigValidationError("Integrity-valid negative results must be publishable")
        stop_ids = {
            require_mapping(item, "stop condition").get("id")
            for item in require_sequence(data["stop_conditions"], "stop conditions")
        }
        if stop_ids != {f"STOP-{index:02d}" for index in range(1, 8)}:
            raise ConfigValidationError("Stop conditions must be exactly STOP-01 through STOP-07")
        source_entries = require_sequence(data["source_documents"], "source documents")
        source_names = {
            require_mapping(entry, "source document").get("filename")
            for entry in source_entries
        }
        if source_names != SOURCE_FILES:
            raise ConfigValidationError("Both frozen source documents must be registered")
        for entry in source_entries:
            source = require_mapping(entry, "source document")
            if not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256", ""))):
                raise ConfigValidationError(
                    f"Source SHA-256 must be lowercase hexadecimal: {source.get('filename')}"
                )
        if verify_sources:
            if self.source_root is None:
                raise ConfigValidationError("source_root is required for source verification")
            for entry in source_entries:
                source = require_mapping(entry, "source document")
                source_path = self.source_root / str(source["filename"])
                if not source_path.is_file():
                    raise ConfigValidationError(f"Source file is missing: {source_path}")
                actual = sha256_file(source_path)
                if actual != str(source["sha256"]).lower():
                    raise ConfigValidationError(
                        f"Source hash mismatch for {source_path.name}: {actual}"
                    )
        self.counts["hypotheses"] = len(hypotheses)
        self.counts["claims"] = 6
        self.counts["data_roles"] = len(role_ids)
        self.counts["stop_conditions"] = len(stop_ids)
        self.counts["source_documents"] = len(source_entries)

    def _validate_state_dictionaries(self) -> None:
        for relative_path, expected_ids, exact_value in (
            (
                "configs/access/predictive_state_v1.yaml",
                PREDICTIVE_IDS,
                True,
            ),
            (
                "configs/access/governance_state_v1.yaml",
                GOVERNANCE_IDS,
                False,
            ),
        ):
            path = self.repo_root / relative_path
            data = load_yaml(path)
            fields = [
                StateField.from_mapping(item, f"{path}.fields[{index}]")
                for index, item in enumerate(
                    require_sequence(data.get("fields"), f"{path}.fields")
                )
            ]
            require_unique((field.stable_id for field in fields), f"{path}.fields")
            actual_ids = {field.stable_id for field in fields}
            if actual_ids != expected_ids:
                raise ConfigValidationError(
                    f"{path} IDs differ: missing={sorted(expected_ids-actual_ids)}, "
                    f"extra={sorted(actual_ids-expected_ids)}"
                )
            if any(field.exact_twin_equal is not exact_value for field in fields):
                raise ConfigValidationError(
                    f"{path} exact_twin_equal values violate the state contract"
                )
            if any(not field.prohibited_derived_information for field in fields):
                raise ConfigValidationError(
                    f"{path} contains a field without prohibited-derived-information rules"
                )
            expected_visibility = (
                {"P-only", "Raw-G", "Oracle-G"}
                if exact_value
                else {"Raw-G", "Oracle-G"}
            )
            if any(set(field.visibility) != expected_visibility for field in fields):
                raise ConfigValidationError(
                    f"{path} contains an incorrect access-profile visibility set"
                )
            self.counts[f"{data['state_type']}_fields"] = len(fields)

    def _validate_diagnostics(self) -> None:
        schema_path = self.repo_root / "configs/diagnostics/schema.yaml"
        schema = load_yaml(schema_path)
        required_fields = set(
            require_sequence(schema.get("required_fields"), f"{schema_path}.required_fields")
        )
        generator_keys = set(
            require_sequence(schema.get("generator_keys"), f"{schema_path}.generator_keys")
        )
        mandatory_metrics = set(
            require_sequence(
                schema.get("mandatory_metrics"), f"{schema_path}.mandatory_metrics"
            )
        )
        entries: dict[str, Mapping[str, Any]] = {}
        for path in sorted((self.repo_root / "configs/diagnostics").glob("ds_cf_*.yaml")):
            data = load_yaml(path)
            require_keys(data, required_fields, str(path))
            diagnostic_id = require_string(data["diagnostic_id"], f"{path}.diagnostic_id")
            if diagnostic_id in entries:
                raise ConfigValidationError(f"Duplicate diagnostic ID: {diagnostic_id}")
            generators = require_mapping(data["generators"], f"{path}.generators")
            if set(generators) != generator_keys:
                raise ConfigValidationError(
                    f"{path} generator keys must be exactly {sorted(generator_keys)}"
                )
            if set(data["metrics"]) != mandatory_metrics:
                raise ConfigValidationError(
                    f"{path} metrics must be exactly {sorted(mandatory_metrics)}"
                )
            entries[diagnostic_id] = data
        if set(entries) != DIAGNOSTIC_IDS:
            raise ConfigValidationError(
                f"Diagnostic IDs differ: missing={sorted(DIAGNOSTIC_IDS-set(entries))}, "
                f"extra={sorted(set(entries)-DIAGNOSTIC_IDS)}"
            )
        for diagnostic_id, data in entries.items():
            partners = set(data["interaction_partners"])
            if partners != DIAGNOSTIC_IDS - {diagnostic_id}:
                raise ConfigValidationError(
                    f"{diagnostic_id} must name every other diagnostic as an interaction partner"
                )
        zc = entries["DSCF-ZC-v1"]
        if zc["maximum_authority"] != "observation-only":
            raise ConfigValidationError("Raw correlation must remain observation-only")
        if "independent hard veto" not in zc["prohibited_influence_paths"]:
            raise ConfigValidationError("Raw correlation must prohibit independent hard veto")
        self.counts["diagnostics"] = len(entries)

    def _validate_methods(self) -> None:
        path = self.repo_root / "configs/methods/method_inventory_v1.yaml"
        data = load_yaml(path)
        entries = [
            MethodEntry.from_mapping(item, f"{path}.methods[{index}]")
            for index, item in enumerate(
                require_sequence(data.get("methods"), f"{path}.methods")
            )
        ]
        require_unique((entry.method_id for entry in entries), f"{path}.methods")
        p_only = {entry.method_id for entry in entries if re.fullmatch(r"P0[1-9]-.+", entry.method_id)}
        raw_g = {
            entry.method_id
            for entry in entries
            if re.fullmatch(r"G(?:0[1-9]|1[0-2])-.+", entry.method_id)
        }
        oracle = {entry.method_id for entry in entries if entry.method_id.startswith("O0")}
        mavs = {entry.method_id for entry in entries if entry.method_id.startswith("MAVS-A")}
        if len(p_only) != 9:
            raise ConfigValidationError(f"Expected 9 P-only families, found {len(p_only)}")
        if len(raw_g) != 12:
            raise ConfigValidationError(f"Expected 12 Raw-G families, found {len(raw_g)}")
        if oracle != {"O01-ORACLE-RULE", "O02-ORACLE-MLP"}:
            raise ConfigValidationError("Oracle inventory must contain O01 and O02")
        if mavs != {f"MAVS-A{index:02d}" for index in range(16)}:
            raise ConfigValidationError("MAVS inventory must contain A00-A15")
        o02 = next(entry for entry in entries if entry.method_id == "O02-ORACLE-MLP")
        if o02.reporting_role != "diagnostic-only":
            raise ConfigValidationError("Learned Oracle MLP must remain diagnostic-only")
        if any(not entry.mandatory_tracks for entry in entries):
            raise ConfigValidationError("Every method must declare mandatory tracks")
        if any(
            entry.access_profile != "P-only"
            for entry in entries
            if entry.method_id.startswith("P")
        ):
            raise ConfigValidationError("Every P01-P09 method must use P-only access")
        if any(
            entry.access_profile != "Raw-G"
            for entry in entries
            if entry.method_id.startswith("G")
        ):
            raise ConfigValidationError("Every G01-G12 method must use Raw-G access")
        self.counts["p_only_method_families"] = len(p_only)
        self.counts["raw_g_method_families"] = len(raw_g)
        self.counts["oracle_diagnostics"] = len(oracle)
        self.counts["mavs_conditions"] = len(mavs)
        self.counts["method_entries"] = len(entries)

    def _validate_holdouts(self) -> None:
        path = self.repo_root / "configs/holdouts/holdout_registry_v1.yaml"
        data = load_yaml(path)
        chronology = require_mapping(data.get("chronology"), f"{path}.chronology")
        if chronology.get("unlock_and_materialize_phase") != 11:
            raise ConfigValidationError("Phase 11 must unlock and materialize")
        if chronology.get("streamed_evaluation_phase") != 12:
            raise ConfigValidationError("Phase 12 must stream evaluation")
        if chronology.get("one_unlock_only") is not True:
            raise ConfigValidationError("The holdout lifecycle must permit one unlock only")
        holdouts = {
            require_mapping(item, "holdout").get("id"): require_mapping(item, "holdout")
            for item in require_sequence(data.get("holdouts"), f"{path}.holdouts")
        }
        if set(holdouts) != {"structural", "domain-D7", "domain-D8", "final-blind"}:
            raise ConfigValidationError("Holdout registry IDs are incomplete")
        for holdout_id in ("domain-D7", "domain-D8"):
            custody = set(holdouts[holdout_id].get("custody_only_content", []))
            required = {
                "generation logic",
                "templates",
                "vocabulary",
                "surface distribution",
                "feature mapping",
                "nuisance transforms",
                "allocation realization",
                "examples",
                "labels",
                "adapter outputs",
            }
            if custody != required:
                raise ConfigValidationError(f"{holdout_id} custody boundary is incomplete")
        self.counts["holdouts"] = len(holdouts)

    def _validate_protected_objective(self) -> None:
        path = self.repo_root / "configs/metrics/protected_objective_v1.yaml"
        data = load_yaml(path)
        if data.get("selection_partition") != "calibration_policy":
            raise ConfigValidationError("Protected objective must use calibration_policy")
        if data.get("selection_mode") != "lexicographic":
            raise ConfigValidationError("Protected objective must be lexicographic")
        objectives = require_sequence(
            data.get("ordered_objectives"), f"{path}.ordered_objectives"
        )
        metrics = [require_mapping(item, "objective").get("metric") for item in objectives]
        expected = [
            "unsafe_acceptance_rate",
            "false_rejection_rate",
            "unnecessary_escalation_rate",
            "resource_cost",
            "model_complexity",
        ]
        if metrics != expected:
            raise ConfigValidationError(
                f"Protected objective order must be {expected}, found {metrics}"
            )
        priorities = [require_mapping(item, "objective").get("priority") for item in objectives]
        if priorities != [1, 2, 3, 4, 5]:
            raise ConfigValidationError("Protected objective priorities must be 1 through 5")
        self.counts["protected_objectives"] = len(objectives)

    def _validate_failure_card_schema(self) -> None:
        path = self.repo_root / "configs/study/failure_card_schema_v1.yaml"
        data = load_yaml(path)
        required = set(require_sequence(data.get("required_fields"), f"{path}.required_fields"))
        essential = {
            "case_or_group_id",
            "run_id",
            "commit_hash",
            "environment_hash",
            "config_hash",
            "method_id",
            "projection_hash",
            "trace_hash",
            "expected_action",
            "observed_action",
            "root_cause_class",
            "case_validity_verdict",
            "affected_claim_ids",
            "reproduction_command",
            "artifact_references",
        }
        if not essential <= required:
            raise ConfigValidationError(
                f"FailureCard schema is missing essential fields: {sorted(essential-required)}"
            )
        if data.get("additional_fields_allowed") is not False:
            raise ConfigValidationError("FailureCard schema must be strict")
        self.counts["failure_card_fields"] = len(required)

    def _validate_requirements(self) -> None:
        path = self.repo_root / "configs/requirements/pead_v1_requirements.yaml"
        data = load_yaml(path)
        requirements = [
            RequirementEntry.from_mapping(item, f"{path}.requirements[{index}]")
            for index, item in enumerate(
                require_sequence(data.get("requirements"), f"{path}.requirements")
            )
        ]
        require_unique(
            (requirement.requirement_id for requirement in requirements),
            f"{path}.requirements",
        )
        if any(".." in requirement.requirement_id for requirement in requirements):
            raise ConfigValidationError("Requirement IDs must be fully expanded")
        for requirement in requirements:
            if sha256_text(requirement.exact_source_clause) != requirement.source_clause_sha256:
                raise ConfigValidationError(
                    f"Source clause hash mismatch for {requirement.requirement_id}"
                )
            if (
                not requirement.phases
                or not requirement.files
                or not requirement.tests
                or not requirement.affected_claims
            ):
                raise ConfigValidationError(
                    f"Requirement mapping is incomplete for {requirement.requirement_id}"
                )
            if not re.fullmatch(r"(DOCX-P\d{4}|DOCX-T\d{3}-R\d{3})", requirement.requirement_id):
                raise ConfigValidationError(
                    f"Unstable requirement ID format: {requirement.requirement_id}"
                )
        declared = data.get("included_clause_count")
        if declared != len(requirements):
            raise ConfigValidationError(
                f"Requirement count mismatch: declared={declared}, actual={len(requirements)}"
            )
        if len(requirements) < 500:
            raise ConfigValidationError(
                "Requirement registry is unexpectedly small for the frozen source"
            )
        registry_source = require_mapping(
            data.get("source_document"), f"{path}.source_document"
        )
        study = load_yaml(self.repo_root / "configs/study/pead_main_v1.yaml")
        source_hashes = {
            item["filename"]: item["sha256"]
            for item in require_sequence(
                study["source_documents"], "study source documents"
            )
        }
        if (
            registry_source.get("sha256")
            != source_hashes["PEAD_Benchmark_Implementation_Specification_v1.0.docx"]
        ):
            raise ConfigValidationError(
                "Requirement registry source hash differs from the study manifest"
            )
        self.counts["source_requirements"] = len(requirements)

    def _validate_claims(self) -> None:
        path = self.repo_root / "CLAIMS.md"
        text = path.read_text(encoding="utf-8")
        for required_text in (
            "H1 - Information necessity",
            "H2 - Architecture value",
            "C1 - Existence",
            "C2 - Prediction-only lower bound",
            "C3 - Governance information",
            "C4 - Structured governance",
            "C5 - Diagnostic Sciences",
            "C6 - Evidence boundary",
            "Negative-result publication policy",
            "Causal-rejection closure map",
            "Self-Learning MAVS is outside Paper 1",
        ):
            if required_text not in text:
                raise ConfigValidationError(f"CLAIMS.md is missing: {required_text}")
        closure_section = text.split("## Causal-rejection closure map", maxsplit=1)[1]
        concern_rows = [
            line
            for line in closure_section.splitlines()
            if line.startswith("| ") and not line.startswith("|---") and "Concern" not in line
        ]
        if len(concern_rows) != 13:
            raise ConfigValidationError(
                f"Causal-rejection closure map must contain 13 concerns, found {len(concern_rows)}"
            )
        for row in concern_rows:
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            if len(cells) != 5 or any(not cell for cell in cells):
                raise ConfigValidationError(
                    "Every causal-rejection row must contain a concern, control, "
                    "audit, gate, and evidence artifact"
                )
        self.counts["causal_rejection_concerns"] = len(concern_rows)


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[3])
    parser.add_argument("--source-root", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--verify-sources", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("results/audits/phase0/phase0_validation.json"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    console = ResearchConsole("0")
    try:
        validator = Phase0Validator(
            args.repo_root,
            console=console,
            source_root=args.source_root,
        )
        report = validator.validate(verify_sources=args.verify_sources)
        report_path = args.report
        if not report_path.is_absolute():
            report_path = args.repo_root / report_path
        write_report(report_path, report)
        # STEP LOG P0-VALIDATE-012: Record the retained validation evidence location.
        console.log(
            "P0-VALIDATE-012",
            "Validation evidence written.",
            status="pass",
            details={"report": str(report_path.resolve())},
        )
        return 0
    except ConfigValidationError as error:
        # STEP LOG P0-VALIDATE-013: Emit a factual validation failure before returning nonzero.
        console.log(
            "P0-VALIDATE-013",
            "Phase 0 validation failed.",
            status="fail",
            details={"error": str(error)},
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
