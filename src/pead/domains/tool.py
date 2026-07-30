"""D1 open adapter for governed tool execution."""

from pathlib import Path

from pead.domains.base import DomainAdapter


class ToolExecutionAdapter(DomainAdapter):
    CONFIG_FILE = "tool.yaml"
    EXPECTED_DOMAIN_ID = "D1"


def load_adapter(repo_root: Path) -> ToolExecutionAdapter:
    return ToolExecutionAdapter(repo_root)
