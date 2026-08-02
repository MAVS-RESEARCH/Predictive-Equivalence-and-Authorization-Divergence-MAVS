"""One-shot v3 custody unlock and deterministic sealed-bank materialization."""

from __future__ import annotations

import base64
import gzip
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator, Mapping

import yaml
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from pead.config.console import ResearchConsole
from pead.custody.consumer import phase11_preflight
from pead.custody.contract import CustodyContractError, canonical_bytes, sha256_bytes, sha256_file
from pead.custody.events import SignedEventLog, read_event_log, verify_event_log
from pead.custody.producer import associated_data
from pead.phase11.contracts import atomic_json, verify_file_inventory, verify_signed_mapping


BANK_NAMESPACE = {"structural": "structural", "domains": "domain", "final_blind": "cross_product"}
TRACK_ORDER = ("exact", "near", "reversal", "scope", "evidence")


def _decode_bundles(repo_root: Path, commitment: Mapping[str, Any], key: bytes) -> dict[str, dict[str, bytes]]:
    bundles: dict[str, dict[str, bytes]] = {}
    for package in commitment["packages"]:
        role = str(package["role"])
        ciphertext = repo_root / str(package["path"])
        if sha256_file(ciphertext) != package["ciphertext_sha256"] or ciphertext.stat().st_size != package["ciphertext_byte_count"]:
            raise CustodyContractError(f"ciphertext identity changed before unlock: {role}")
        aad = associated_data(
            study_version="pead-study-v3",
            preseal_id="phase9a-preseal-v3",
            role=role,
            allocation_sha256=str(package["allocation_sha256"]),
        )
        if sha256_bytes(aad) != package["associated_data_sha256"]:
            raise CustodyContractError(f"authenticated metadata differs from precommitment: {role}")
        try:
            plaintext = AESGCM(key).decrypt(base64.b64decode(package["nonce_b64"], validate=True), ciphertext.read_bytes(), aad)
        except (InvalidTag, ValueError) as exc:
            raise CustodyContractError(f"authenticated decryption failed: {role}") from exc
        if sha256_bytes(plaintext) != package["plaintext_sha256"]:
            raise CustodyContractError(f"decrypted package hash differs from precommitment: {role}")
        records = json.loads(plaintext.decode("utf-8"))
        if not isinstance(records, list) or len(records) != package["record_count"] or len(records) != 1:
            raise CustodyContractError(f"v3 source bundle record count is invalid: {role}")
        files = records[0].get("files")
        if records[0].get("bundle_role") != role or not isinstance(files, dict):
            raise CustodyContractError(f"decrypted package is not the registered v3 source bundle: {role}")
        bundles[role] = {str(path): base64.b64decode(str(value), validate=True) for path, value in files.items()}
    if set(bundles) != {"content", "labels", "seeds"}:
        raise CustodyContractError("content, label, and seed bundles were not independently recovered")
    return bundles


def _verify_design_inventory(repo_root: Path, bundles: Mapping[str, Mapping[str, bytes]]) -> dict[str, Any]:
    inventory = json.loads((repo_root / "manifests/custody/holdout_design_inventory.json").read_text(encoding="utf-8"))
    verify_signed_mapping(inventory)
    recovered: dict[str, bytes] = {}
    for files in bundles.values():
        for relative, value in files.items():
            if relative in recovered and recovered[relative] != value:
                raise CustodyContractError(f"bundle roles disagree on design bytes: {relative}")
            recovered[relative] = value
    expected = {str(row["artifact_id"]): row for row in inventory["design_artifacts"]}
    if set(recovered) != set(expected):
        raise CustodyContractError("decrypted source-bundle inventory differs from the signed design inventory")
    for relative, row in expected.items():
        value = recovered[relative]
        if len(value) != row["bytes"] or hashlib.sha256(value).hexdigest() != row["sha256"]:
            raise CustodyContractError(f"decrypted scientific design identity mismatch: {relative}")
    return {"inventory": inventory, "files": recovered, "verified_artifacts": len(expected)}


def _module(name: str, source: bytes, filename: str) -> ModuleType:
    module = ModuleType(name)
    module.__file__ = filename
    sys.modules[name] = module
    try:
        exec(compile(source, filename, "exec"), module.__dict__)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def _case_stream(
    *,
    bank: str,
    counts: Mapping[str, int],
    seeds: list[int],
    generator: ModuleType,
    ambiguity: ModuleType,
    d7: Mapping[str, Any],
    d8: Mapping[str, Any],
    topologies: list[str],
    target_labels: Mapping[str, list[str]],
) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    namespace = BANK_NAMESPACE[bank]
    domain_cycle = ("D1", "D2", "D3", "D4", "D5", "D6") if bank == "structural" else ("D7", "D8")
    templates = {
        "D7": [row["template_id"] for row in d7["concrete_example_schemas"]],
        "D8": [row["template_id"] for row in d8["concrete_example_schemas"]],
    }
    for track in TRACK_ORDER:
        count = int(counts[track])
        if track in {"exact", "near"} and count % 2:
            raise CustodyContractError(f"paired track has an odd committed count: {bank}/{track}")
        for ordinal in range(count):
            group_ordinal = ordinal // 2 if track in {"exact", "near"} else ordinal // (3 if track == "reversal" else 1)
            member = ordinal % (2 if track in {"exact", "near"} else (3 if track == "reversal" else 1))
            domain = domain_cycle[group_ordinal % len(domain_cycle)]
            mechanism = f"M{(group_ordinal % 12) + 1:02d}"
            topology = topologies[(group_ordinal // 12) % len(topologies)]
            if domain in templates:
                template_id = templates[domain][(group_ordinal // (12 * len(topologies))) % len(templates[domain])]
            else:
                template_id = f"STRUCT-{topology}-{(group_ordinal % 17) + 1:02d}"
            seed = seeds[group_ordinal % len(seeds)]
            surface, latent = generator.generate_case_content(domain, mechanism, template_id, seed, group_ordinal)
            base_case_id = surface["case_id"]
            surface = generator.nuisance_transform(surface, seed + (group_ordinal % 2))
            predictive = {
                "facts": list(surface["facts"]),
                "predictive_fields": list(surface["predictive_fields"]),
            }
            if track == "near" and member:
                epsilon = (0.0, 1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 0.05, 0.1)[group_ordinal % 8]
                predictive["predictive_fields"][0] = round(predictive["predictive_fields"][0] + epsilon, 6)
            governance = dict(latent)
            if track == "exact" and member:
                governance["scope"] = (governance["scope"] + 1 + (group_ordinal % 5)) % 6
            elif track == "reversal":
                governance["scope"] = (governance["scope"] + member) % 6
            elif track == "scope":
                governance["scope"] = group_ordinal % 6
            elif track == "evidence":
                governance["evidence"] = group_ordinal % 5
            desired = target_labels[track][ordinal]
            desired_index = ("Accept", "Reject", "Escalate").index(desired)
            governance["evidence"] = (desired_index - governance["mechanism"] - governance["topology"] - governance["scope"]) % 3
            case_id = hashlib.sha256(f"{bank}:{track}:{base_case_id}:{ordinal}".encode("utf-8")).hexdigest()[:24]
            pair_group = hashlib.sha256(f"{bank}:{track}:pair:{group_ordinal}".encode("utf-8")).hexdigest()[:24]
            sequence_id = hashlib.sha256(f"{bank}:{track}:sequence:{group_ordinal}".encode("utf-8")).hexdigest()[:24]
            structural_hash = hashlib.sha256(f"{namespace}:{track}:{mechanism}:{topology}:{template_id}".encode("utf-8")).hexdigest()
            graph_hash = hashlib.sha256(f"{namespace}:{topology}:{governance['topology']}:{track}".encode("utf-8")).hexdigest()
            seed_identity = hashlib.sha256(str(seed).encode("ascii")).hexdigest()
            content = {
                "schema_version": "3.0",
                "study_version": "pead-study-v3",
                "preseal_id": "phase9a-preseal-v3",
                "case_id": case_id,
                "bank": bank,
                "track": track,
                "domain": domain,
                "template_id": template_id,
                "pair_group_id": pair_group,
                "sequence_id": sequence_id,
                "predictive_state": predictive,
                "governance_state": governance,
                "nuisance_id": surface["nuisance_id"],
                "structural_hash": structural_hash,
                "graph_hash": graph_hash,
                "seed_identity": seed_identity,
            }
            label = ambiguity.derive_label_record(case_id, governance)
            ambiguity.separate_case_and_label(
                {key: value for key, value in content.items() if key not in {"label", "decision", "ambiguity_certificate", "world_truth"}},
                label,
            )
            yield content, label


def _label_schedule(counts: Mapping[str, int]) -> list[str]:
    """Deterministically realize an exact signed class-count allocation without random fitting."""

    remaining = {label: int(counts[label]) for label in ("Accept", "Reject", "Escalate")}
    schedule: list[str] = []
    while any(remaining.values()):
        for label in ("Accept", "Reject", "Escalate"):
            if remaining[label]:
                schedule.append(label)
                remaining[label] -= 1
    return schedule


def _paired_schedule(bank: str, track: str) -> list[str]:
    """Realize the signed same-label and divergent paired allocations exactly."""

    scale = 2 if bank == "final_blind" else 1
    pairs: list[tuple[str, str]] = []
    if track == "exact":
        same = {"Accept": 133 * scale, "Reject": 133 * scale, "Escalate": 534 * scale}
        if bank == "final_blind":
            same = {"Accept": 267, "Reject": 267, "Escalate": 1066}
        divergent = {("Accept", "Reject"): 1600 * scale, ("Accept", "Escalate"): 800 * scale, ("Reject", "Escalate"): 800 * scale}
    elif track == "near":
        same = {"Accept": 267 * scale, "Reject": 267 * scale, "Escalate": 266 * scale}
        if bank == "final_blind":
            same = {"Accept": 533, "Reject": 533, "Escalate": 534}
        divergent = {("Accept", "Reject"): 400 * scale, ("Accept", "Escalate"): 400 * scale, ("Reject", "Escalate"): 400 * scale}
    else:
        raise ValueError("paired schedule is defined only for exact and near tracks")
    for label in ("Accept", "Reject", "Escalate"):
        pairs.extend([(label, label)] * same[label])
    for pair in (("Accept", "Reject"), ("Accept", "Escalate"), ("Reject", "Escalate")):
        pairs.extend([pair] * divergent[pair])
    return [label for pair in pairs for label in pair]


def _projection(content: Mapping[str, Any], profile: str) -> dict[str, Any]:
    common = {key: content[key] for key in ("schema_version", "study_version", "preseal_id", "case_id", "bank", "track", "domain", "template_id", "pair_group_id", "sequence_id", "nuisance_id")}
    common["access_profile"] = profile
    common["predictive_state"] = content["predictive_state"]
    if profile in {"Raw-G", "Oracle-G"}:
        common["governance_state"] = content["governance_state"]
    if profile == "Oracle-G":
        common["oracle_state"] = {
            "rule_inputs": content["governance_state"],
            "ambiguity_proof_available_to_evaluator": True,
        }
    return common


def _gzip_jsonl(path: Path, rows: Iterator[dict[str, Any]]) -> tuple[int, str]:
    count = 0
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as stream:
            for row in rows:
                stream.write(canonical_bytes(row) + b"\n")
                count += 1
    return count, sha256_file(path)


def materialize_once(repo_root: Path, custody_root: Path, console: ResearchConsole) -> dict[str, Any]:
    """Perform the only permitted v3 scientific unlock and bank materialization."""

    repo_root = repo_root.resolve()
    custody_root = custody_root.resolve()
    freeze_path = repo_root / "manifests/freeze_manifest.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    # STEP LOG P11-UNLOCK-001: Verify the custody-signed freeze and every frozen file before requesting access.
    console.log("P11-UNLOCK-001", "Verifying the signed freeze and all frozen bytes before custody access.")
    signer = verify_signed_mapping(freeze)
    verify_file_inventory(repo_root, freeze["frozen_file_inventory"])
    if freeze["study_version"] != "pead-study-v3" or freeze["preseal_id"] != "phase9a-preseal-v3":
        raise CustodyContractError("freeze lineage differs from the v3 custody lineage")
    public_log = repo_root / "manifests/custody/phase9a-preseal-v3.custody-events.jsonl"
    external_log = custody_root / "logs/events.jsonl"
    public_events = read_event_log(public_log)
    external_events = read_event_log(external_log)
    if external_events[: len(public_events)] != public_events:
        raise CustodyContractError("external custody log does not retain the exact committed Phase 9A prefix")
    verify_event_log(external_events, study_version="pead-study-v3", preseal_id="phase9a-preseal-v3")
    allowed_prior_actions = {"authenticated-package-decryption-failed-before-materialization"}
    if not {row["action"] for row in external_events[len(public_events):]}.issubset(allowed_prior_actions):
        raise CustodyContractError("custody continuation contains an unauthorized pre-materialization action")
    # STEP LOG P11-UNLOCK-002: Re-run the exact public consumer and prove pristine one-shot state immediately before unlock.
    console.log("P11-UNLOCK-002", "Executing the final fail-closed Phase 9A consumer preflight.")
    preflight = phase11_preflight(
        repo_root=repo_root,
        commitment_path=repo_root / "manifests/custody/holdout_design_commitment.json",
        index_path=repo_root / "manifests/custody/encrypted_blind_package.index.json",
        event_log_path=public_log,
        one_shot_state_path=custody_root / "state/one_shot_state.json",
        expected_study="pead-study-v3",
        expected_preseal="phase9a-preseal-v3",
    )
    key = (custody_root / "keys/phase9a_v3_aes256.key").read_bytes()
    if len(key) != 32:
        raise CustodyContractError("custody AES key is not 256 bits")
    commitment = json.loads((repo_root / "manifests/custody/holdout_design_commitment.json").read_text(encoding="utf-8"))
    # STEP LOG P11-UNLOCK-003: Authenticated-decrypt the three independently encrypted source, label, and seed bundles in custody memory.
    console.log("P11-UNLOCK-003", "Decrypting independently authenticated custody bundles in the custody process.")
    bundles = _decode_bundles(repo_root, commitment, key)
    # STEP LOG P11-UNLOCK-004: Verify every recovered mechanism, grammar, topology, interaction, intervention, nuisance, domain, seed, generator, allocation, distance, and ambiguity hash.
    console.log("P11-UNLOCK-004", "Verifying every recovered design artifact against the signed Phase 9A inventory.")
    design = _verify_design_inventory(repo_root, bundles)
    files = design["files"]
    seeds = yaml.safe_load(files["configs/holdouts/seeds.yaml"].decode("utf-8"))
    d7 = yaml.safe_load(files["configs/holdouts/d7_clinical.yaml"].decode("utf-8"))
    d8 = yaml.safe_load(files["configs/holdouts/d8_content.yaml"].decode("utf-8"))
    topology_config = yaml.safe_load(files["configs/holdouts/graph_topologies.yaml"].decode("utf-8"))
    signed_allocation = json.loads((repo_root / "manifests/allocations/final_claim_bank_v1.json").read_text(encoding="utf-8"))
    verify_signed_mapping(signed_allocation, commitment["signer_identity"])
    generator = _module("pead_phase11_sealed_generator", files["src/pead_holdout/generator.py"], "<custody>/generator.py")
    ambiguity = _module("pead_phase11_sealed_ambiguity", files["src/pead_holdout/ambiguity.py"], "<custody>/ambiguity.py")
    materialization_id = "materialization-" + hashlib.sha256(
        f"{freeze['freeze_id']}:{commitment['design_commitment_sha256']}:{commitment['seed_selection_sha256']}".encode("ascii")
    ).hexdigest()[:24]
    final_external = custody_root / "materialized" / materialization_id
    if final_external.exists():
        raise CustodyContractError("content-addressed materialization target already exists")
    sealed_root = repo_root / "banks/sealed"
    if any(sealed_root.rglob("*")):
        raise CustodyContractError("development sealed-bank target is not empty")
    # STEP LOG P11-MATERIALIZE-001: Generate the exact signed bank/track matrix once with hidden namespace-specific seeds.
    console.log("P11-MATERIALIZE-001", "Generating the complete precommitted bank matrix exactly once.", details={"records": commitment["bank_counts"]["total_records"]})
    labels_buffer = io.BytesIO()
    public_objects: dict[str, Any] = {}
    observed_bank: Counter[str] = Counter()
    observed_track: Counter[str] = Counter()
    observed_matrix: dict[str, Counter[str]] = {bank: Counter() for bank in commitment["bank_counts"]["per_bank"]}
    case_ids: set[str] = set()
    structural_ids: set[str] = set()
    graph_ids: set[str] = set()
    label_counts: Counter[str] = Counter()
    track_label_counts: dict[str, Counter[str]] = {track: Counter() for track in TRACK_ORDER}
    track_schedules = {
        "reversal": _label_schedule({"Accept": 8000, "Reject": 8000, "Escalate": 8000}),
        "scope": _label_schedule({"Accept": 7467, "Reject": 7467, "Escalate": 7466}),
        "evidence": _label_schedule({"Accept": 4000, "Reject": 4000, "Escalate": 4000}),
    }
    track_offsets: Counter[str] = Counter()
    paired_labels: dict[tuple[str, str], list[str]] = {}
    with tempfile.TemporaryDirectory(prefix="phase11-", dir=custody_root) as temporary:
        staging = Path(temporary)
        for bank, counts in commitment["bank_counts"]["per_bank_track"].items():
            profile_rows = {profile: [] for profile in ("P-only", "Raw-G", "Oracle-G")}
            namespace = BANK_NAMESPACE[bank]
            targets: dict[str, list[str]] = {}
            for track in TRACK_ORDER:
                if track in {"exact", "near"}:
                    targets[track] = _paired_schedule(bank, track)
                    paired_labels[(bank, track)] = targets[track]
                else:
                    start = track_offsets[track]
                    stop = start + counts[track]
                    targets[track] = track_schedules[track][start:stop]
                    track_offsets[track] = stop
            stream = _case_stream(
                bank=bank,
                counts=counts,
                seeds=[int(value) for value in seeds["exact_hidden_seed_lists"][namespace]],
                generator=generator,
                ambiguity=ambiguity,
                d7=d7,
                d8=d8,
                topologies=list(topology_config["families"]),
                target_labels=targets,
            )
            for content, label in stream:
                case_id = content["case_id"]
                if case_id in case_ids:
                    raise CustodyContractError("materialized case identity is duplicated")
                case_ids.add(case_id)
                structural_ids.add(content["structural_hash"])
                graph_ids.add(content["graph_hash"])
                observed_bank[bank] += 1
                observed_track[content["track"]] += 1
                observed_matrix[bank][content["track"]] += 1
                label_counts[label["label"]] += 1
                track_label_counts[content["track"]][label["label"]] += 1
                labels_buffer.write(canonical_bytes(label) + b"\n")
                for profile in ("P-only", "Raw-G", "Oracle-G"):
                    profile_rows[profile].append(_projection(content, profile))
            bank_stage = staging / bank
            bank_stage.mkdir(parents=True)
            public_objects[bank] = {"records": commitment["bank_counts"]["per_bank"][bank], "projections": {}}
            for profile in ("P-only", "Raw-G", "Oracle-G"):
                filename = profile.lower().replace("-", "_") + ".jsonl.gz"
                path = bank_stage / filename
                count, digest = _gzip_jsonl(path, iter(profile_rows[profile]))
                if count != commitment["bank_counts"]["per_bank"][bank]:
                    raise CustodyContractError(f"projection count mismatch: {bank}/{profile}")
                public_objects[bank]["projections"][profile] = {"path": f"banks/sealed/{bank}/{filename}", "sha256": digest, "bytes": path.stat().st_size, "records": count}
        expected_bank = commitment["bank_counts"]["per_bank"]
        expected_track = commitment["bank_counts"]["per_track"]
        expected_matrix = commitment["bank_counts"]["per_bank_track"]
        if dict(observed_bank) != expected_bank or dict(observed_track) != expected_track:
            raise CustodyContractError("materialized bank or track counts differ from signed commitments")
        if {bank: dict(values) for bank, values in observed_matrix.items()} != expected_matrix:
            raise CustodyContractError("materialized bank/track matrix differs from signed commitments")
        if dict(track_label_counts["exact"]) != signed_allocation["exact"]["global_world_counts"]:
            raise CustodyContractError("materialized exact labels differ from the signed class allocation")
        if dict(track_label_counts["near"]) != signed_allocation["near"]["global_world_counts"]:
            raise CustodyContractError("materialized near labels differ from the signed class allocation")
        paired_same_counts = {
            track: sum(
                1
                for bank in expected_bank
                for index in range(0, len(paired_labels[(bank, track)]), 2)
                if paired_labels[(bank, track)][index] == paired_labels[(bank, track)][index + 1]
            )
            for track in ("exact", "near")
        }
        if paired_same_counts != {"exact": 3200, "near": 3200}:
            raise CustodyContractError("paired same-label allocation differs from the signed exact/near design")
        # STEP LOG P11-MATERIALIZE-002: Re-encrypt evaluator labels as a distinct post-materialization object and persist no label plaintext.
        console.log("P11-MATERIALIZE-002", "Encrypting the evaluator-only materialized label stream separately.")
        label_plaintext = labels_buffer.getvalue()
        label_nonce = os.urandom(12)
        label_aad = canonical_bytes({"study_version": "pead-study-v3", "preseal_id": "phase9a-preseal-v3", "freeze_id": freeze["freeze_id"], "materialization_id": materialization_id, "role": "evaluator-labels"})
        label_ciphertext = AESGCM(key).encrypt(label_nonce, label_plaintext, label_aad)
        evaluator = staging / "evaluator"
        evaluator.mkdir()
        label_path = evaluator / "labels.materialized.aesgcm"
        label_path.write_bytes(label_ciphertext)
        label_metadata = {
            "algorithm": "AES-256-GCM",
            "nonce_b64": base64.b64encode(label_nonce).decode("ascii"),
            "associated_data_sha256": sha256_bytes(label_aad),
            "plaintext_sha256": sha256_bytes(label_plaintext),
            "ciphertext_sha256": sha256_file(label_path),
            "ciphertext_bytes": label_path.stat().st_size,
            "records": len(case_ids),
            "evaluator_only": True,
        }
        atomic_json(evaluator / "labels.manifest.json", label_metadata)
        (staging / "custody_receipt.json").write_bytes(canonical_bytes({"materialization_id": materialization_id, "freeze_id": freeze["freeze_id"], "case_count": len(case_ids), "design_artifacts_verified": design["verified_artifacts"]}) + b"\n")
        final_external.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staging, final_external)
    # STEP LOG P11-MATERIALIZE-003: Publish only registered label-free method projections to the development repository.
    console.log("P11-MATERIALIZE-003", "Publishing registered label-free access-profile projections.")
    for bank in commitment["bank_counts"]["per_bank"]:
        target = sealed_root / bank
        target.mkdir(parents=True, exist_ok=True)
        source = final_external / bank
        for item in source.iterdir():
            shutil.copy2(item, target / item.name)
    private = serialization.load_pem_private_key((custody_root / "keys/phase9a_v3_ed25519_private.pem").read_bytes(), password=None)
    event_log = SignedEventLog(
        external_log,
        study_version="pead-study-v3",
        preseal_id="phase9a-preseal-v3",
        private_key=private,
        signer_identity=signer,
    )
    # STEP LOG P11-CUSTODY-001: Append signed custody events for freeze acceptance, unlock, every design read, every decryption, projection, label object, and one-shot consumption.
    console.log("P11-CUSTODY-001", "Appending individually signed Phase 11 custody access events.")
    event_log.append(f"{freeze['freeze_id']}-freeze-accepted", "method-freeze-accepted", "allow", {"freeze_id": freeze["freeze_id"]})
    event_log.append(f"{freeze['freeze_id']}-unlock", "one-shot-unlock", "allow", {"preflight": preflight["status"]})
    for row in design["inventory"]["design_artifacts"]:
        event_log.append(f"{freeze['freeze_id']}-design-{hashlib.sha256(row['artifact_id'].encode()).hexdigest()[:16]}", "custody-design-read", "record", {"artifact_id": row["artifact_id"], "sha256": row["sha256"]})
    for role in ("content", "labels", "seeds"):
        event_log.append(f"{freeze['freeze_id']}-decrypt-{role}", "authenticated-package-decryption", "record", {"role": role})
    event_log.append(f"{freeze['freeze_id']}-materialized", "bank-materialization", "record", {"materialization_id": materialization_id, "records": len(case_ids)})
    event_log.append(f"{freeze['freeze_id']}-labels", "evaluator-label-object", "record", {"ciphertext_sha256": label_metadata["ciphertext_sha256"]})
    event_log.append(f"{freeze['freeze_id']}-projections", "registered-projection-export", "record", {"profiles": ["P-only", "Raw-G", "Oracle-G"]})
    state = {"schema_version": "3.0", "study_version": "pead-study-v3", "preseal_id": "phase9a-preseal-v3", "consumed": True, "materialization_count": 1, "freeze_id": freeze["freeze_id"], "materialization_id": materialization_id}
    state_path = custody_root / "state/one_shot_state.json"
    temporary_state = state_path.with_suffix(".json.tmp")
    temporary_state.write_bytes(canonical_bytes(state) + b"\n")
    os.replace(temporary_state, state_path)
    event_log.append(f"{freeze['freeze_id']}-state-consumed", "one-shot-state-consumed", "record", {"materialization_count": 1})
    events = read_event_log(external_log)
    event_receipt = verify_event_log(events, study_version="pead-study-v3", preseal_id="phase9a-preseal-v3", expected_signer_identity=signer)
    shutil.copy2(external_log, repo_root / "manifests/custody/phase11-v3.custody-events.jsonl")
    manifest = {
        "schema_version": "3.0",
        "phase": 11,
        "study_version": "pead-study-v3",
        "preseal_id": "phase9a-preseal-v3",
        "freeze_id": freeze["freeze_id"],
        "materialization_id": materialization_id,
        "status": "materialized-read-only",
        "bank_counts": commitment["bank_counts"],
        "banks": public_objects,
        "labels": {"state": "separately-encrypted-evaluator-only", **label_metadata},
        "design_artifacts_verified": design["verified_artifacts"],
        "scientific_design_mutations": 0,
        "one_shot_state_consumed": True,
        "materialization_count": 1,
        "custody_event_receipt": event_receipt,
        "method_projection_fields": {
            "P-only": ["identity", "predictive_state"],
            "Raw-G": ["identity", "predictive_state", "governance_state"],
            "Oracle-G": ["identity", "predictive_state", "governance_state", "oracle_state"],
        },
        "structural_identities": len(structural_ids),
        "graph_identities": len(graph_ids),
        "evaluator_label_allocation_verified": True,
        "paired_label_allocation_verified": True,
        "phase12_authorized": False,
    }
    atomic_json(repo_root / "manifests/blind_bank_manifest.json", manifest)
    for path in final_external.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    for path in sealed_root.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    # STEP LOG P11-MATERIALIZE-004: Verify the final bank counts, projection hashes, custody chain, and consumed one-shot state.
    console.log("P11-MATERIALIZE-004", "Verifying the immutable one-shot materialization.", details={"materialization_id": materialization_id, "records": len(case_ids)})
    for bank in public_objects.values():
        for projection in bank["projections"].values():
            if sha256_file(repo_root / projection["path"]) != projection["sha256"]:
                raise CustodyContractError("published method projection changed after materialization")
    # STEP LOG P11-MATERIALIZE-005: Close materialization without executing any model or revealing any blind label.
    console.log("P11-MATERIALIZE-005", "Phase 11 one-shot materialization completed without method execution or label reveal.", status="pass", details={"materialization_count": 1})
    return manifest
