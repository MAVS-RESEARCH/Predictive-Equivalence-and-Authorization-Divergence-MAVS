"""D6 open adapter for a bounded financial-approval proxy."""

from pathlib import Path

from pead.domains.base import DomainAdapter


class FinancialApprovalProxyAdapter(DomainAdapter):
    CONFIG_FILE = "finance.yaml"
    EXPECTED_DOMAIN_ID = "D6"


def load_adapter(repo_root: Path) -> FinancialApprovalProxyAdapter:
    return FinancialApprovalProxyAdapter(repo_root)
