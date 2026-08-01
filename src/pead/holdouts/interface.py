"""Typed public interfaces that expose no hidden holdout facts or labels."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SealedHoldoutPaths:
    """Public paths required by the shared Phase 9A/Phase 11 contract."""

    commitment: Path
    ciphertext_index: Path
    signed_event_log: Path
    one_shot_state: Path


@dataclass(frozen=True)
class PublicPreflightReceipt:
    study_version: str
    preseal_id: str
    allocation_sha256: str
    event_count: int
    missing_commitments: tuple[str, ...]
    consumer_invented_values: tuple[str, ...]
