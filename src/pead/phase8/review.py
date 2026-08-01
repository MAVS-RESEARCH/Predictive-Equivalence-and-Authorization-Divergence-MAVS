"""Independent non-vacuous Phase 8 MAVS rule and ablation stress review."""

from __future__ import annotations

import ast
import hashlib
import itertools
from pathlib import Path
from typing import Any

import json

from pead.config.console import ResearchConsole
from pead.core.diagnostic_registry import load_diagnostic_definitions
from pead.core.types import AuthorizationAction
from pead.mavs.adapter import MAVSAdapter
from pead.mavs.ablations import load_ablation_registry
from pead.mavs.ds_cf import DSCFVector, SIGNAL_TO_DIAGNOSTIC
from pead.mavs.governed_consensus import govern, hard_veto
from pead.mavs.profiles import load_profiles
from pead.mavs.scalarization import ScalarCompressionCase, audit_scalar_compression
from pead.phase8.fixtures import sealed_p_only, sealed_raw_g


class DigestingLogStream:
    """Bounded evidence sink retaining count, size, and SHA-256 of all events."""

    def __init__(self) -> None:
        self._hash = hashlib.sha256()
        self._events = 0
        self._characters = 0

    def write(self, value: str) -> int:
        self._hash.update(value.encode("utf-8"))
        self._events += value.count("\n")
        self._characters += len(value)
        return len(value)

    def flush(self) -> None:
        return None

    def report(self) -> dict[str, Any]:
        return {"event_lines": self._events, "characters": self._characters, "sha256": self._hash.hexdigest()}


def _vector(values: tuple[float, ...], hashes: dict[str, str]) -> DSCFVector:
    return DSCFVector(
        **dict(zip(SIGNAL_TO_DIAGNOSTIC, values, strict=True)),
        definition_hashes=hashes,
        evidence_fields={name: () for name in SIGNAL_TO_DIAGNOSTIC},
    )


def audit_semantic_registry(root: Path) -> dict[str, Any]:
    manifest = json.loads((root / "results/manifests/phase4/phase4_validation_manifest_v1.json").read_text(encoding="utf-8"))
    definitions = load_diagnostic_definitions(root).entries
    current = {diagnostic_id: definition.definition_hash for diagnostic_id, definition in definitions.items()}
    if current != manifest["diagnostic_definition_hashes"]:
        raise ValueError("DS-CF semantics differ from the signed pre-Phase-4 registry")
    expected = {
        "z_c": ("correlation_presence", "observation-only"),
        "z_h": ("harmful_correlation", "conjunctive-veto-input"),
        "z_s": ("safe_consistency", "bounded-mitigation"),
        "z_m": ("missing_evidence", "conjunctive-veto-input"),
        "z_p": ("policy_conflict", "conjunctive-veto-input"),
        "z_o": ("overconfidence", "soft-evidence"),
        "z_f": ("counterfactual_fragility", "conjunctive-veto-input"),
    }
    contracts = {}
    all_ids = set(definitions)
    for signal, diagnostic_id in SIGNAL_TO_DIAGNOSTIC.items():
        definition = definitions[diagnostic_id]
        semantic_name, authority = expected[signal]
        gates = {
            "semantic_name": definition.semantic_name == semantic_name,
            "version": definition.version == "1.0.0",
            "status": definition.status == "frozen",
            "authority": definition.maximum_authority == authority,
            "scope_generators": set(definition.generators) == {
                "positive", "matched_negative", "boundary", "adversarial_out_of_scope",
            },
            "interactions": set(definition.interaction_partners) == all_ids - {diagnostic_id},
            "monotonicity": bool(definition.monotonicity_contract.strip()),
            "influence_paths": bool(definition.permitted_influence_paths) and bool(definition.prohibited_influence_paths),
        }
        if not all(gates.values()):
            raise ValueError(f"DS-CF semantic contract mismatch for {signal}: {gates}")
        contracts[signal] = {
            "diagnostic_id": diagnostic_id,
            "semantic_name": definition.semantic_name,
            "version": definition.version,
            "maximum_authority": definition.maximum_authority,
            "scope_generators": sorted(definition.generators),
            "interaction_partners": sorted(definition.interaction_partners),
            "monotonicity_contract": definition.monotonicity_contract,
            "gates": gates,
        }
    return {
        "status": "pass", "signals": len(current), "definition_hashes": current,
        "contracts": contracts,
        "phase4_registry_sha256": manifest["diagnostic_registry_sha256"],
        "semantic_changes": 0, "reopen_phases_on_change": [0, 4, 8, "all-dependent-banks"],
    }


def exhaustive_rule_fidelity(root: Path) -> dict[str, Any]:
    profile = load_profiles(root)["MAVS-GC-DSCF-v1"]
    semantic = audit_semantic_registry(root)
    levels = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    vectors = 0
    active = 0
    violations = 0
    raw_correlation_vetoes = 0
    safe_consistency_overrides = 0
    for values in itertools.product(levels, repeat=7):
        vector = _vector(values, semantic["definition_hashes"])
        veto = hard_veto(vector, profile)
        vectors += 1
        active += int(veto)
        valid = (
            vector.z_h >= profile.thresholds["tau_h"]
            and vector.z_s < profile.thresholds["tau_s"]
            and max(vector.z_f, vector.z_m, vector.z_p) >= 0.5
        )
        violations += int(veto != valid)
        raw_correlation_vetoes += int(veto and vector.z_h == vector.z_m == vector.z_p == vector.z_f == 0.0)
        safe_consistency_overrides += int(veto and vector.z_s >= profile.thresholds["tau_s"])
    if vectors != 279_936 or active != 27_216 or violations or raw_correlation_vetoes or safe_consistency_overrides:
        raise ValueError("exhaustive DS-CF rule-fidelity gate failed")
    return {
        "status": "pass", "vectors": vectors, "active_veto_combinations": active,
        "veto_violations": violations, "raw_correlation_only_vetoes": raw_correlation_vetoes,
        "safe_consistency_veto_overrides": safe_consistency_overrides,
    }


def stress_ablations(root: Path, *, scenarios: int = 256) -> dict[str, Any]:
    stream = DigestingLogStream()
    console = ResearchConsole("8-stress", stream=stream)
    adapters = {f"MAVS-A{index:02d}": MAVSAdapter(root, f"MAVS-A{index:02d}", console=console) for index in range(16)}
    decisions = 0
    complete_traces = 0
    raw_g_projection_mismatches = 0
    mitigation_violations = 0
    veto_dominance_violations = 0
    for index in range(scenarios):
        raw = sealed_raw_g(
            supports=(0.4 + (index % 6) * 0.1, 0.5 + (index % 5) * 0.1, 0.6),
            correlation=(index % 11) / 10,
            independent_support=((index * 3) % 11) / 10,
            policy_conflict=1.0 if index % 7 == 0 else 0.0,
            missing_evidence=1.0 if index % 13 == 0 else 0.0,
            fragility=1.0 if index % 17 == 0 else 0.0,
            confidence=0.5 + (index % 6) * 0.1,
            agreement=(index % 11) / 10,
            authority_invalid=index % 19 == 0,
        )
        predictive = sealed_p_only(supports=(0.7, 0.8, 0.9))
        raw_hashes = set()
        for method_id, adapter in adapters.items():
            decision, trace = adapter.run(
                predictive if method_id == "MAVS-A00" else raw,
                execution_mode="contract_probe",
                commit_time="2026-08-01T00:00:00+00:00",
            )
            decisions += 1
            complete_traces += int(trace.trace_complete and len(trace.supports) == len(trace.contextual_weights))
            mitigation_violations += int(not 0.0 <= trace.mitigation <= adapter.profile.mitigation_bound)
            veto_dominance_violations += int(trace.veto and decision.decision is not AuthorizationAction.REJECT)
            if method_id != "MAVS-A00":
                raw_hashes.add(decision.visible_projection_hash)
        raw_g_projection_mismatches += int(raw_hashes != {raw.projection_hash})
    if complete_traces != decisions or raw_g_projection_mismatches or mitigation_violations or veto_dominance_violations:
        raise ValueError("MAVS ablation stress gate failed")
    return {
        "status": "pass", "scenarios": scenarios, "decisions": decisions,
        "complete_traces": complete_traces, "raw_g_projection_mismatches": raw_g_projection_mismatches,
        "mitigation_violations": mitigation_violations, "veto_dominance_violations": veto_dominance_violations,
        "operational_log": stream.report(),
    }


def monotonicity_review(root: Path) -> dict[str, Any]:
    profile = load_profiles(root)["MAVS-GC-DSCF-v1"]
    semantic = audit_semantic_registry(root)
    console = ResearchConsole("8-monotonicity", stream=DigestingLogStream())
    pairs = 0
    violations = 0
    for index in range(1000):
        low_h = (index % 50) / 100
        high_h = min(1.0, low_h + 0.4)
        base = (0.5, low_h, 0.0, 0.0, 0.0, 0.0, 0.0)
        higher = (0.5, high_h, 0.0, 0.0, 0.0, 0.0, 0.0)
        low = govern(profile=profile, method_id="MAVS-A15", projection_hash="a" * 64, supports=(0.7, 0.7), vector=_vector(base, semantic["definition_hashes"]), console=console)
        high = govern(profile=profile, method_id="MAVS-A15", projection_hash="a" * 64, supports=(0.7, 0.7), vector=_vector(higher, semantic["definition_hashes"]), console=console)
        pairs += 1
        violations += int(high.threshold < low.threshold or (low.terminal_decision is AuthorizationAction.REJECT and high.terminal_decision is AuthorizationAction.ACCEPT))
    if violations:
        raise ValueError("certified severity monotonicity violation")
    return {"status": "pass", "pairs": pairs, "violations": violations}


def scalar_review() -> dict[str, Any]:
    base = {name: 0.0 for name in SIGNAL_TO_DIAGNOSTIC}
    rows = (
        ScalarCompressionCase("structural-accept", "structural", base, AuthorizationAction.ACCEPT),
        ScalarCompressionCase("structural-reject", "structural", base, AuthorizationAction.REJECT),
        ScalarCompressionCase("domain-accept", "domain", base, AuthorizationAction.ACCEPT),
        ScalarCompressionCase("domain-escalate", "domain", base, AuthorizationAction.ESCALATE),
    )
    return audit_scalar_compression(rows)


def dependency_review(root: Path) -> dict[str, Any]:
    violations = []
    for path in (root / "src/pead/mavs").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports = [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        imports += [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        for name in imports:
            if name.startswith(("pead.world", "pead.labels")):
                violations.append({"file": path.name, "import": name, "direction": "mavs-to-hidden"})
    for directory in (root / "src/pead/world", root / "src/pead/labels"):
        for path in directory.glob("*.py"):
            if "pead.mavs" in path.read_text(encoding="utf-8"):
                violations.append({"file": path.relative_to(root).as_posix(), "import": "pead.mavs", "direction": "truth-to-mavs"})
    if violations:
        raise ValueError(f"MAVS dependency firewall violations: {violations}")
    return {"status": "pass", "violations": [], "directions_checked": ["mavs-to-generators-labels", "generators-labels-to-mavs"]}


def execute_phase8_review(root: Path, console: ResearchConsole) -> dict[str, Any]:
    # STEP LOG P8-REVIEW-001: Bind the live seven-signal implementation to the signed pre-Phase-4 semantic hashes.
    console.log("P8-REVIEW-001", "Auditing signed DS-CF semantic registry.")
    semantic = audit_semantic_registry(root)
    # STEP LOG P8-REVIEW-002: Exhaust all 279,936 discretized vectors and prove exact conjunction fidelity.
    console.log("P8-REVIEW-002", "Executing exhaustive DS-CF veto review.")
    rules = exhaustive_rule_fidelity(root)
    # STEP LOG P8-REVIEW-003: Stress every A00-A15 condition on matched visible projections with complete traces.
    console.log("P8-REVIEW-003", "Executing matched-ablation stress review.")
    ablations = stress_ablations(root)
    # STEP LOG P8-REVIEW-004: Verify certified severity monotonicity over 1,000 paired interventions.
    console.log("P8-REVIEW-004", "Executing monotonicity review.")
    monotonicity = monotonicity_review(root)
    # STEP LOG P8-REVIEW-005: Execute the central scalar-compression collision test on structural and domain holdouts.
    console.log("P8-REVIEW-005", "Executing scalar-compression holdout review.")
    scalar = scalar_review()
    # STEP LOG P8-REVIEW-006: Prove bidirectional dependency isolation between MAVS and generator/label engines.
    console.log("P8-REVIEW-006", "Auditing MAVS dependency firewall.")
    dependencies = dependency_review(root)
    # STEP LOG P8-REVIEW-007: Report the complete non-scientific Phase 8 rule and architecture verdict.
    console.log(
        "P8-REVIEW-007", "Phase 8 independent implementation review passed.", status="pass",
        details={"ablation_decisions": ablations["decisions"], "rule_vectors": rules["vectors"], "semantic_changes": semantic["semantic_changes"]},
    )
    return {
        "status": "pass", "semantic_registry": semantic, "rule_fidelity": rules,
        "ablations": ablations, "monotonicity": monotonicity,
        "scalar_compression": scalar, "dependencies": dependencies,
        "profiles": {key: profile.profile_hash for key, profile in load_profiles(root).items()},
        "ablation_registry": sorted(load_ablation_registry(root)),
        "scientific_results": 0,
    }
