"""Scientific invariance and lineage-freshness guards."""

from __future__ import annotations

from typing import Mapping

from pead.custody.contract import CustodyContractError


FRESH_IDENTITIES = frozenset(
    {
        "structural_seed_selection_sha256",
        "domain_seed_selection_sha256",
        "cross_product_seed_selection_sha256",
        "encryption_key_sha256",
        "custody_signing_private_key_sha256",
        "custody_signing_public_key_sha256",
        "one_shot_state_genesis_sha256",
        "custody_log_genesis_sha256",
    }
)


def assert_identity_freshness(new: Mapping[str, str], predecessor_sets: Mapping[str, Mapping[str, str]]) -> None:
    if set(new) != FRESH_IDENTITIES:
        raise CustodyContractError("freshness identity fields differ from the registered contract")
    if any(not isinstance(value, str) or len(value) != 64 for value in new.values()):
        raise CustodyContractError("freshness identities must be SHA-256 values")
    for lineage, predecessor in predecessor_sets.items():
        overlap = sorted(set(new.values()) & set(predecessor.values()))
        if overlap:
            raise CustodyContractError(f"custody identity reuse detected against {lineage}: {len(overlap)} identity value(s)")


def assert_semantic_invariance(reference: Mapping[str, str], candidate: Mapping[str, str]) -> None:
    if set(reference) != set(candidate):
        raise CustodyContractError("scientific semantic artifact sets differ")
    mismatches = sorted(path for path in reference if reference[path] != candidate[path])
    if mismatches:
        raise CustodyContractError(f"scientific semantic identities differ: {mismatches}")
