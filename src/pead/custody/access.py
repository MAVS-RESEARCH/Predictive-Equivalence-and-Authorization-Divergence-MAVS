"""Fail-closed pre-freeze access controls for the sealed custody workspace."""

from __future__ import annotations

from typing import Any, Mapping

from pead.custody.events import SignedEventLog


def deny_pre_freeze_access(
    event_log: SignedEventLog,
    *,
    event_id: str,
    actor_role: str,
    requested_action: str,
    details: Mapping[str, Any] | None = None,
) -> None:
    event_log.append(
        event_id,
        "pre-freeze-access-attempt",
        "deny",
        {"actor_role": actor_role, "requested_action": requested_action, **dict(details or {})},
    )
    raise PermissionError(f"pre-freeze access denied for {actor_role}: {requested_action}")
