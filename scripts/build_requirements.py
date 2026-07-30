"""Build the frozen clause-level registry from the normative PEAD DOCX."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pead.config.console import ResearchConsole
from pead.config.models import ConfigValidationError
from pead.phase0.requirements import build_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-docx",
        type=Path,
        default=Path.home()
        / "Downloads"
        / "PEAD_Benchmark_Implementation_Specification_v1.0.docx",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "configs/requirements/pead_v1_requirements.yaml",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    console = ResearchConsole("0")
    try:
        # STEP LOG P0-REQUIREMENTS-001: Establish the immutable source identity.
        console.log(
            "P0-REQUIREMENTS-001",
            "Reading the normative specification.",
            details={"source": str(args.source_docx.resolve())},
        )
        registry = build_registry(args.source_docx)
        # STEP LOG P0-REQUIREMENTS-002: Confirm complete source-block extraction counts.
        console.log(
            "P0-REQUIREMENTS-002",
            "Source clause inventory constructed.",
            details={
                "clauses": registry["included_clause_count"],
                "headings": registry["heading_count"],
                "paragraphs": registry["source_document"]["body_paragraph_count"],
                "tables": registry["source_document"]["body_table_count"],
            },
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            yaml.safe_dump(
                registry,
                allow_unicode=False,
                sort_keys=False,
                width=120,
            ),
            encoding="utf-8",
        )
        # STEP LOG P0-REQUIREMENTS-003: Retain the canonical machine registry.
        console.log(
            "P0-REQUIREMENTS-003",
            "Clause-level requirements registry written.",
            status="pass",
            details={
                "output": str(args.output.resolve()),
                "inventory_sha256": registry["clause_inventory_sha256"],
            },
        )
        return 0
    except ConfigValidationError as error:
        # STEP LOG P0-REQUIREMENTS-004: Report source extraction failure as a hard gate.
        console.log(
            "P0-REQUIREMENTS-004",
            "Clause-level requirements registry build failed.",
            status="fail",
            details={"error": str(error)},
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
