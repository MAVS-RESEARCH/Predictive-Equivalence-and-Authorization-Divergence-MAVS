"""Load and audit the frozen method inventory without mutating its identities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pead.baselines.base import ContractProbeAdapter, contract_from_inventory
from pead.config.console import ResearchConsole

P_ONLY_IDS = {
    "P01-CONF", "P02-UNC", "P03-DIS", "P04-SC", "P05-CONF-STATIC",
    "P06-CONF-ADAPT", "P07-REJECT", "P08-TABULAR", "P09-SEQUENCE",
}
RAW_G_IDS = {
    "G01-LOGREG", "G02-TREE", "G03-GBDT", "G04-MLP", "G05-SEQUENCE",
    "G06-GRAPH", "G07-BAYES", "G08-POLICY", "G09-VALIDATOR", "G10-JUDGE",
    "G11-SCALAR", "G12-ENSEMBLE",
}
ORACLE_IDS = {"O01-ORACLE-RULE", "O02-ORACLE-MLP"}
MAVS_IDS = {f"MAVS-A{index:02d}" for index in range(16)}


def load_inventory(repo_root: Path) -> tuple[dict[str, Any], ...]:
    payload = yaml.safe_load(
        (repo_root / "configs/methods/method_inventory_v1.yaml").read_text(encoding="utf-8")
    )
    methods = tuple(payload["methods"])
    identifiers = [record["method_id"] for record in methods]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("method inventory contains duplicate IDs")
    actual = set(identifiers)
    expected = P_ONLY_IDS | RAW_G_IDS | ORACLE_IDS | MAVS_IDS
    if actual != expected:
        raise ValueError(f"method inventory mismatch: missing={sorted(expected-actual)}, extra={sorted(actual-expected)}")
    return methods


def comparator_probes(repo_root: Path, console: ResearchConsole) -> dict[str, ContractProbeAdapter]:
    """Instantiate the 23 Phase 7 comparator contracts for interface-only tests."""

    records = load_inventory(repo_root)
    return {
        record["method_id"]: ContractProbeAdapter(contract_from_inventory(record), console=console)
        for record in records
        if record["method_id"] in P_ONLY_IDS | RAW_G_IDS | ORACLE_IDS
    }
