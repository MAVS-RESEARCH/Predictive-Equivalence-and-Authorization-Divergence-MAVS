"""Canonical FailureCard generation and exact qualifying-event bijection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from pead.core.hashing import canonical_hash
from pead.reports.failure_card_schema import FailureCard

QUALIFYING_TYPES = {
    "protected error", "scope anomaly", "label disagreement", "access violation",
    "quarantine", "invalidation", "reproduction mismatch",
}


@dataclass(frozen=True)
class QualifyingEvent:
    event_id: str
    event_type: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.event_id or self.event_type not in QUALIFYING_TYPES:
            raise ValueError("invalid qualifying failure event")


def build_failure_card(event: QualifyingEvent) -> FailureCard:
    payload = dict(event.payload)
    payload["failure_card_id"] = f"FC-{canonical_hash({'event_id': event.event_id, 'event_type': event.event_type})[:24]}"
    payload["protected_error_type"] = event.event_type
    return FailureCard.from_mapping(payload)


def audit_failure_card_bijection(events: tuple[QualifyingEvent, ...], cards: tuple[FailureCard, ...]) -> dict[str, Any]:
    event_ids = [event.event_id for event in events]
    card_groups = [card.case_or_group_id for card in cards]
    duplicate_events = sorted({value for value in event_ids if event_ids.count(value) > 1})
    duplicate_cards = sorted({value for value in card_groups if card_groups.count(value) > 1})
    missing = sorted(set(event_ids) - set(card_groups))
    orphaned = sorted(set(card_groups) - set(event_ids))
    invalid_ids = sorted(card.failure_card_id for card in cards if not card.content_hash())
    if duplicate_events or duplicate_cards or missing or orphaned or invalid_ids:
        raise ValueError(f"FailureCard bijection failed: missing={missing}; duplicate_events={duplicate_events}; duplicate_cards={duplicate_cards}; orphaned={orphaned}; invalid={invalid_ids}")
    return {"status": "pass", "events": len(events), "cards": len(cards), "missing": [], "duplicates": [], "orphaned": [], "schema_invalid": []}
