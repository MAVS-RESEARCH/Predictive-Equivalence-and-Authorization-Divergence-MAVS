"""Content-derived identifier contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, ClassVar

from pead.core.hashing import canonical_hash

_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, order=True)
class ContentId:
    """A typed, full-digest content identifier."""

    kind: str
    digest: str
    schema_version: ClassVar[str] = "1.0"

    def __post_init__(self) -> None:
        if not _KIND_PATTERN.fullmatch(self.kind):
            raise ValueError("content ID kind is invalid")
        if not _DIGEST_PATTERN.fullmatch(self.digest):
            raise ValueError("content ID digest must be a lowercase SHA-256")

    def __str__(self) -> str:
        return f"{self.kind}_{self.digest}"

    @classmethod
    def parse(cls, value: str, expected_kind: str | None = None) -> "ContentId":
        try:
            kind, digest = value.rsplit("_", 1)
        except ValueError as exc:
            raise ValueError("content ID must contain one kind separator") from exc
        identifier = cls(kind=kind, digest=digest)
        if expected_kind is not None and identifier.kind != expected_kind:
            raise ValueError(
                f"expected {expected_kind!r} content ID, received {identifier.kind!r}"
            )
        return identifier


def derive_content_id(kind: str, payload: Any) -> str:
    """Create a full SHA-256 content ID with an explicit object kind."""

    return str(ContentId(kind=kind, digest=canonical_hash(payload)))


def world_id(payload: Any) -> str:
    return derive_content_id("world", payload)


def pair_id(payload: Any) -> str:
    return derive_content_id("pair", payload)


def sequence_id(payload: Any) -> str:
    return derive_content_id("sequence", payload)


def run_id(payload: Any) -> str:
    return derive_content_id("run", payload)


def artifact_id(payload: Any) -> str:
    return derive_content_id("artifact", payload)
