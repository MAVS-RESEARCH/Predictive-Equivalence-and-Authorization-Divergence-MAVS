"""D5 open adapter for governed software deployment."""

from pathlib import Path

from pead.domains.base import DomainAdapter


class SoftwareDeploymentAdapter(DomainAdapter):
    CONFIG_FILE = "software.yaml"
    EXPECTED_DOMAIN_ID = "D5"


def load_adapter(repo_root: Path) -> SoftwareDeploymentAdapter:
    return SoftwareDeploymentAdapter(repo_root)
