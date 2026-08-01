"""Fail-closed compute and inference budget accounting."""

from __future__ import annotations

import platform
import time
from dataclasses import dataclass, field
from importlib import metadata
from typing import Any

from pead.config.console import ResearchConsole


class BudgetExceeded(RuntimeError):
    """Raised when a registered resource ceiling is exceeded."""


@dataclass(frozen=True)
class BudgetCeiling:
    budget_id: str
    wall_time_seconds: float
    memory_gib: float
    accelerator_hours: float = 0.0
    calls_per_case: int = 0
    tokens_per_case: int = 0


@dataclass
class ResourceAccountant:
    """Measure one run and enforce its immutable registered ceiling."""

    ceiling: BudgetCeiling
    console: ResearchConsole
    started_at: float = field(default_factory=time.perf_counter)
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def record_call(self, *, input_tokens: int, output_tokens: int) -> None:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("token counts cannot be negative")
        self.calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        # STEP LOG P7-BUDGET-001: Record one external-model call before enforcing its per-case call and token ceilings.
        self.console.log(
            "P7-BUDGET-001",
            "External-model resource call recorded.",
            details={"calls": self.calls, "tokens": self.input_tokens + self.output_tokens},
        )
        self.assert_within_ceiling()

    def snapshot(self) -> dict[str, Any]:
        elapsed = time.perf_counter() - self.started_at
        try:
            import psutil
            peak_bytes = int(psutil.Process().memory_info().rss)
        except ImportError:
            peak_bytes = 0
        return {
            "budget_id": self.ceiling.budget_id,
            "wall_time_seconds": elapsed,
            "peak_memory_bytes": peak_bytes,
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }

    def assert_within_ceiling(self) -> None:
        usage = self.snapshot()
        failures: list[str] = []
        if usage["wall_time_seconds"] > self.ceiling.wall_time_seconds:
            failures.append("wall_time_seconds")
        if usage["peak_memory_bytes"] > self.ceiling.memory_gib * 1024**3:
            failures.append("peak_memory_bytes")
        if self.ceiling.calls_per_case and self.calls > self.ceiling.calls_per_case:
            failures.append("calls_per_case")
        if self.ceiling.tokens_per_case and self.input_tokens + self.output_tokens > self.ceiling.tokens_per_case:
            failures.append("tokens_per_case")
        if failures:
            raise BudgetExceeded(f"budget {self.ceiling.budget_id} exceeded: {failures}")

    def close(self) -> dict[str, Any]:
        self.assert_within_ceiling()
        usage = self.snapshot()
        # STEP LOG P7-BUDGET-002: Close one resource account only after every registered ceiling passes.
        self.console.log(
            "P7-BUDGET-002",
            "Resource account closed within registered ceilings.",
            status="pass",
            details=usage,
        )
        return usage


def package_environment(package_names: tuple[str, ...]) -> dict[str, Any]:
    """Capture exact packages, Python, platform, and processor identity."""

    packages: dict[str, str] = {}
    for package in package_names:
        try:
            packages[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            packages[package] = "not-installed"
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or "undisclosed",
        "packages": packages,
    }
