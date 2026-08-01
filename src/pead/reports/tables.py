"""Unsuppressible tabular reports with cell-level provenance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ProvenanceCell:
    cell_id: str
    value: Any
    processed_data_id: str
    raw_trace_ids: tuple[str, ...]
    config_id: str
    audit_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all((self.cell_id, self.processed_data_id, self.raw_trace_ids, self.config_id, self.audit_ids)):
            raise ValueError("report cell provenance is incomplete")


def build_method_table(
    expected_method_ids: tuple[str, ...], rows: Mapping[str, Mapping[str, ProvenanceCell]], statuses: Mapping[str, str],
) -> dict[str, Any]:
    if set(expected_method_ids) != set(rows) or set(expected_method_ids) != set(statuses):
        raise ValueError("report builder cannot suppress or add methods")
    return {
        "method_order": list(expected_method_ids),
        "rows": {method: {name: cell for name, cell in sorted(rows[method].items())} for method in expected_method_ids},
        "statuses": {method: statuses[method] for method in expected_method_ids},
        "failed_methods_visible": all(method in rows for method, status in statuses.items() if status != "pass"),
    }


def audit_table_provenance(table: Mapping[str, Any]) -> dict[str, Any]:
    cells = [cell for row in table["rows"].values() for cell in row.values()]
    if not cells or not all(isinstance(cell, ProvenanceCell) for cell in cells):
        raise ValueError("table contains untyped or absent cells")
    return {"status": "pass", "cells": len(cells), "complete": len(cells)}
