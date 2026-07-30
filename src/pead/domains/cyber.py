"""D2 open adapter for governed cyber response."""

from pathlib import Path

from pead.domains.base import DomainAdapter


class CyberResponseAdapter(DomainAdapter):
    CONFIG_FILE = "cyber.yaml"
    EXPECTED_DOMAIN_ID = "D2"


def load_adapter(repo_root: Path) -> CyberResponseAdapter:
    return CyberResponseAdapter(repo_root)
