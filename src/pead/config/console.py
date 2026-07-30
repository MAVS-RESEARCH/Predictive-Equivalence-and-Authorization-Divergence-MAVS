"""Structured console output with stable event identities."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, TextIO


@dataclass(frozen=True)
class ResearchConsole:
    """Emit deterministic, machine-readable progress events to a stream."""

    phase: str
    stream: TextIO = sys.stdout

    def log(
        self,
        event_id: str,
        message: str,
        *,
        status: str = "info",
        details: dict[str, Any] | None = None,
    ) -> None:
        if not event_id or not message:
            raise ValueError("event_id and message are required")
        payload: dict[str, Any] = {
            "event_id": event_id,
            "message": message,
            "phase": self.phase,
            "status": status,
        }
        if details:
            payload["details"] = details
        print(
            json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
            file=self.stream,
            flush=True,
        )
