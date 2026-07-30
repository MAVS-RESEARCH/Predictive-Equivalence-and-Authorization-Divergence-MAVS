"""D3 open adapter for governed multi-agent operations."""

from pathlib import Path

from pead.domains.base import DomainAdapter


class MultiAgentOperationsAdapter(DomainAdapter):
    CONFIG_FILE = "multi_agent.yaml"
    EXPECTED_DOMAIN_ID = "D3"


def load_adapter(repo_root: Path) -> MultiAgentOperationsAdapter:
    return MultiAgentOperationsAdapter(repo_root)
