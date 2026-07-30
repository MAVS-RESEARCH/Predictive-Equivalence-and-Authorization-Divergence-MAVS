"""D4 open adapter for governed retrieval and provenance."""

from pathlib import Path

from pead.domains.base import DomainAdapter


class RetrievalProvenanceAdapter(DomainAdapter):
    CONFIG_FILE = "retrieval.yaml"
    EXPECTED_DOMAIN_ID = "D4"


def load_adapter(repo_root: Path) -> RetrievalProvenanceAdapter:
    return RetrievalProvenanceAdapter(repo_root)
