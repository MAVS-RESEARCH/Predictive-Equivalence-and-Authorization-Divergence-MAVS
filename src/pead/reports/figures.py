"""Traceable figure specifications without selective point suppression."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pead.reports.tables import ProvenanceCell


def build_figure_spec(expected_point_ids: tuple[str, ...], points: Mapping[str, ProvenanceCell]) -> dict[str, Any]:
    if set(expected_point_ids) != set(points):
        raise ValueError("figure builder cannot suppress or add registered points")
    return {"point_order": list(expected_point_ids), "points": {point: points[point] for point in expected_point_ids}, "provenance_complete": True}
