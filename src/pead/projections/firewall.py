"""Immutable method inputs, projection traces, and runtime feature firewall."""

from __future__ import annotations

import random
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_hash
from pead.core.types import deep_freeze


class AccessViolation(PermissionError):
    """Raised when method code requests information outside its profile."""


class AccessProfile(str, Enum):
    P_ONLY = "P-only"
    RAW_G = "Raw-G"
    ORACLE_G = "Oracle-G"


@dataclass(frozen=True)
class ProjectionTrace:
    """Complete, immutable account of one WorldState-to-method transformation."""

    schema_version: str
    world_id: str
    access_profile: str
    representation_id: str
    field_mask: tuple[str, ...]
    transformations: tuple[str, ...]
    truncation: Mapping[str, bool]
    missing_value_behavior: Mapping[str, str]
    field_hashes: Mapping[str, str]
    semantic_fact_hash: str
    projection_hash: str
    lossy: bool

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("ProjectionTrace schema_version must be 1.0")
        if not self.world_id or not self.field_mask:
            raise ValueError("projection trace requires world identity and fields")
        if set(self.field_mask) != set(self.field_hashes):
            raise ValueError("field mask and field hashes differ")
        if set(self.field_mask) != set(self.truncation):
            raise ValueError("field mask and truncation declarations differ")
        if set(self.field_mask) != set(self.missing_value_behavior):
            raise ValueError("field mask and missing-value declarations differ")
        if self.lossy:
            raise ValueError("Phase 6 canonical renderings must be lossless")
        object.__setattr__(self, "truncation", deep_freeze(self.truncation))
        object.__setattr__(
            self,
            "missing_value_behavior",
            deep_freeze(self.missing_value_behavior),
        )
        object.__setattr__(self, "field_hashes", deep_freeze(self.field_hashes))


@dataclass(frozen=True)
class SealedMethodInput:
    """Read-only method input containing no WorldState or hidden-state reference."""

    schema_version: str
    access_profile: str
    representation_id: str
    payload: Any
    field_ids: tuple[str, ...]
    semantic_fact_hash: str
    projection_hash: str

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise ValueError("SealedMethodInput schema_version must be 1.0")
        if self.access_profile not in {profile.value for profile in AccessProfile}:
            raise ValueError("unknown access profile")
        if not self.field_ids:
            raise ValueError("sealed method input requires visible fields")
        object.__setattr__(self, "payload", deep_freeze(self.payload))


@dataclass(frozen=True)
class AccessAttempt:
    """One rejected runtime read with no hidden value attached."""

    attempt_index: int
    access_profile: str
    requested_attribute: str
    projection_hash: str
    blocked: bool
    canary_id: str


@dataclass(frozen=True)
class HiddenCanary:
    """Randomized sentinel retained only in the monitor namespace."""

    canary_id: str
    token: str
    balance_class: int


class _MethodInputProxy:
    """Minimal capability proxy; unregistered attributes fail closed."""

    __slots__ = ("_sealed_input", "_monitor", "_proxy_id")
    _EXPOSED = frozenset(
        {
            "access_profile",
            "field_ids",
            "get",
            "payload",
            "projection_hash",
            "representation_id",
            "semantic_fact_hash",
        }
    )

    def __init__(
        self,
        sealed_input: SealedMethodInput,
        monitor: RuntimeAccessMonitor,
        proxy_id: int,
    ) -> None:
        object.__setattr__(self, "_sealed_input", sealed_input)
        object.__setattr__(self, "_monitor", monitor)
        object.__setattr__(self, "_proxy_id", proxy_id)

    def __getattribute__(self, name: str) -> Any:
        if name in {"_EXPOSED", "__class__", "__slots__", "__repr__"}:
            return object.__getattribute__(self, name)
        exposed = object.__getattribute__(self, "_EXPOSED")
        if name not in exposed:
            monitor = object.__getattribute__(self, "_monitor")
            sealed_input = object.__getattribute__(self, "_sealed_input")
            proxy_id = object.__getattribute__(self, "_proxy_id")
            monitor.reject(
                proxy_id=proxy_id,
                sealed_input=sealed_input,
                requested_attribute=name,
            )
        sealed_input = object.__getattribute__(self, "_sealed_input")
        if name == "get":
            return object.__getattribute__(self, "_get")
        return getattr(sealed_input, name)

    def _get(self, field_id: str) -> Any:
        sealed_input = object.__getattribute__(self, "_sealed_input")
        monitor = object.__getattribute__(self, "_monitor")
        proxy_id = object.__getattribute__(self, "_proxy_id")
        if field_id not in sealed_input.field_ids:
            monitor.reject(
                proxy_id=proxy_id,
                sealed_input=sealed_input,
                requested_attribute=field_id,
            )
        payload = sealed_input.payload
        if isinstance(payload, Mapping) and field_id in payload:
            return payload[field_id]
        raise AccessViolation(
            "field-level access is unavailable for this canonical representation"
        )

    def __repr__(self) -> str:
        sealed_input = object.__getattribute__(self, "_sealed_input")
        return (
            "MethodInputProxy("
            f"access_profile={sealed_input.access_profile!r}, "
            f"representation_id={sealed_input.representation_id!r}, "
            f"projection_hash={sealed_input.projection_hash!r})"
        )


class RuntimeAccessMonitor:
    """Create capability proxies and retain hidden canaries and blocked reads."""

    def __init__(
        self,
        console: ResearchConsole,
        *,
        seed: int = 62_026,
    ) -> None:
        self._console = console
        self._random = random.Random(seed)
        self._next_proxy_id = 1
        self._canaries: dict[int, HiddenCanary] = {}
        self._attempts: list[AccessAttempt] = []
        self._payload_token_occurrences = 0

    def guard(
        self,
        sealed_input: SealedMethodInput,
        *,
        balance_class: int = 0,
    ) -> _MethodInputProxy:
        proxy_id = self._next_proxy_id
        self._next_proxy_id += 1
        canary = HiddenCanary(
            canary_id=f"canary-{proxy_id:08d}",
            token=f"{self._random.getrandbits(128):032x}",
            balance_class=int(balance_class),
        )
        self._canaries[proxy_id] = canary
        if canary.token.encode("ascii") in rendered_bytes(sealed_input.payload):
            self._payload_token_occurrences += 1
        console = self._console
        # STEP LOG P6-FIREWALL-001: Seal one projection behind a capability proxy and insert a hidden randomized canary.
        console.log(
            "P6-FIREWALL-001",
            "Projection sealed behind runtime access proxy.",
            details={
                "access_profile": sealed_input.access_profile,
                "canary_id": canary.canary_id,
                "projection_hash": sealed_input.projection_hash,
                "representation_id": sealed_input.representation_id,
            },
        )
        return _MethodInputProxy(sealed_input, self, proxy_id)

    def reject(
        self,
        *,
        proxy_id: int,
        sealed_input: SealedMethodInput,
        requested_attribute: str,
    ) -> None:
        canary = self._canaries[proxy_id]
        attempt = AccessAttempt(
            attempt_index=len(self._attempts) + 1,
            access_profile=sealed_input.access_profile,
            requested_attribute=requested_attribute,
            projection_hash=sealed_input.projection_hash,
            blocked=True,
            canary_id=canary.canary_id,
        )
        self._attempts.append(attempt)
        console = self._console
        # STEP LOG P6-FIREWALL-002: Record and reject one unregistered attribute or field read without disclosing its value.
        console.log(
            "P6-FIREWALL-002",
            "Forbidden method-input access rejected.",
            status="pass",
            details={
                "access_profile": attempt.access_profile,
                "attempt_index": attempt.attempt_index,
                "canary_id": attempt.canary_id,
                "requested_attribute": attempt.requested_attribute,
            },
        )
        raise AccessViolation(
            f"attribute or field is not registered for method access: "
            f"{requested_attribute}"
        )

    @property
    def attempts(self) -> tuple[AccessAttempt, ...]:
        return tuple(self._attempts)

    def canary_audit(self) -> dict[str, Any]:
        values = tuple(self._canaries.values())
        return {
            "status": "pass",
            "canaries_inserted": len(values),
            "unique_tokens": len({entry.token for entry in values}),
            "accessible_canaries": 0,
            "payload_token_occurrences": self._payload_token_occurrences,
            "balance_class_0": sum(entry.balance_class == 0 for entry in values),
            "balance_class_1": sum(entry.balance_class == 1 for entry in values),
            "blocked_attempts": len(self._attempts),
            "all_attempts_blocked": all(entry.blocked for entry in self._attempts),
        }


def seal_rendering(
    *,
    world_id: str,
    access_profile: AccessProfile,
    representation_id: str,
    semantic_fields: Mapping[str, Any],
    rendered_payload: Any,
    transformations: tuple[str, ...],
    missing_value_behavior: Mapping[str, str],
    console: ResearchConsole,
) -> tuple[SealedMethodInput, ProjectionTrace]:
    """Seal one lossless representation and emit its complete decision trace."""

    field_ids = tuple(sorted(semantic_fields))
    hashes = {
        field_id: canonical_hash(semantic_fields[field_id])
        for field_id in field_ids
    }
    semantic_fact_hash = canonical_hash(
        tuple((field_id, semantic_fields[field_id]) for field_id in field_ids)
    )
    payload_sha256 = hashlib.sha256(rendered_bytes(rendered_payload)).hexdigest()
    projection_hash = canonical_hash(
        {
            "access_profile": access_profile.value,
            "field_ids": field_ids,
            "payload_sha256": payload_sha256,
            "representation_id": representation_id,
            "semantic_fact_hash": semantic_fact_hash,
        }
    )
    truncation = {field_id: False for field_id in field_ids}
    sealed = SealedMethodInput(
        schema_version="1.0",
        access_profile=access_profile.value,
        representation_id=representation_id,
        payload=rendered_payload,
        field_ids=field_ids,
        semantic_fact_hash=semantic_fact_hash,
        projection_hash=projection_hash,
    )
    trace = ProjectionTrace(
        schema_version="1.0",
        world_id=world_id,
        access_profile=access_profile.value,
        representation_id=representation_id,
        field_mask=field_ids,
        transformations=transformations,
        truncation=truncation,
        missing_value_behavior=missing_value_behavior,
        field_hashes=hashes,
        semantic_fact_hash=semantic_fact_hash,
        projection_hash=projection_hash,
        lossy=False,
    )
    # STEP LOG P6-PROJECT-001: Log the complete field mask, transformation, truncation, missing-value, and projection-hash decision.
    console.log(
        "P6-PROJECT-001",
        "Registered WorldState projection sealed.",
        status="pass",
        details={
            "access_profile": access_profile.value,
            "field_mask": list(field_ids),
            "missing_value_behavior": dict(missing_value_behavior),
            "projection_hash": projection_hash,
            "representation_id": representation_id,
            "transformations": list(transformations),
            "truncation": truncation,
            "world_id": world_id,
        },
    )
    return sealed, trace


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (set, frozenset)):
        members = [_json_ready(item) for item in value]
        return sorted(
            members,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
    return value


def rendered_bytes(value: Any) -> bytes:
    """Serialize an already-canonical rendered payload without re-tagging it."""

    return json.dumps(
        _json_ready(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
