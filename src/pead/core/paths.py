"""Immutable run layout and manifest-guarded result cleanup."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pead.config.console import ResearchConsole
from pead.core.hashing import canonical_bytes, canonical_hash
from pead.core.ids import ContentId


class PathSafetyError(ValueError):
    """Raised when a result path or cleanup target violates containment."""


@dataclass(frozen=True)
class RunLayout:
    schema_version: str
    run_id: str
    raw: Path
    processed: Path
    audits: Path
    reports: Path
    manifests: Path


@dataclass(frozen=True)
class CleanupTarget:
    relative_path: str
    sha256: str
    absolute_path: Path


@dataclass(frozen=True)
class CleanupPlan:
    schema_version: str
    manifest_path: Path
    manifest_sha256: str
    scope: str
    run_id: str | None
    targets: tuple[CleanupTarget, ...]


class RepositoryPaths:
    """Resolve all mutable artifacts against one verified repository root."""

    def __init__(self, repository_root: Path) -> None:
        root = repository_root.resolve(strict=True)
        if not (root / ".git").exists():
            raise PathSafetyError("repository root must contain .git")
        results = (root / "results").resolve(strict=True)
        if results == root or root not in results.parents:
            raise PathSafetyError("results root is not contained by repository root")
        self._root = root
        self._results = results

    @property
    def root(self) -> Path:
        return self._root

    @property
    def results(self) -> Path:
        return self._results

    def run_layout(self, run_id: str, *, create: bool = False) -> RunLayout:
        ContentId.parse(run_id, expected_kind="run")
        layout = RunLayout(
            schema_version="1.0",
            run_id=run_id,
            raw=self.results / "raw" / run_id,
            processed=self.results / "processed" / run_id,
            audits=self.results / "audits" / run_id,
            reports=self.results / "reports" / run_id,
            manifests=self.results / "manifests" / run_id,
        )
        paths = (layout.raw, layout.processed, layout.audits, layout.reports, layout.manifests)
        if any(path.exists() for path in paths):
            raise FileExistsError(f"immutable run layout already exists: {run_id}")
        if create:
            created: list[Path] = []
            try:
                for path in paths:
                    path.mkdir(parents=True, exist_ok=False)
                    created.append(path)
            except OSError:
                for path in reversed(created):
                    path.rmdir()
                raise
        return layout

    def _guard_target(self, relative_path: str) -> Path:
        candidate = Path(relative_path)
        if candidate.is_absolute() or not relative_path.strip():
            raise PathSafetyError("cleanup target must be a non-empty relative path")
        resolved = (self.results / candidate).resolve(strict=True)
        if resolved in {self.root, self.results}:
            raise PathSafetyError("repository and results roots cannot be cleanup targets")
        if self.results not in resolved.parents:
            raise PathSafetyError("cleanup target escapes results root")
        if not resolved.is_file():
            raise PathSafetyError("cleanup targets must be regular files")
        return resolved

    def load_cleanup_plan(
        self,
        manifest_path: Path,
        *,
        scope: str | None,
        run_id: str | None,
    ) -> CleanupPlan:
        if bool(scope) == bool(run_id):
            raise PathSafetyError("provide exactly one explicit scope or run_id")
        if run_id is not None:
            ContentId.parse(run_id, expected_kind="run")
        resolved_manifest = manifest_path.resolve(strict=True)
        manifest_root = (self.results / "manifests").resolve(strict=True)
        if resolved_manifest == manifest_root or manifest_root not in resolved_manifest.parents:
            raise PathSafetyError("cleanup manifest must be below results/manifests")
        try:
            raw = json.loads(resolved_manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PathSafetyError("cleanup manifest is unreadable") from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != "1.0":
            raise PathSafetyError("cleanup manifest requires schema_version 1.0")
        expected_scope = scope if scope is not None else "run"
        if raw.get("scope") != expected_scope or raw.get("run_id") != run_id:
            raise PathSafetyError("cleanup manifest does not match the explicit selector")
        entries = raw.get("entries")
        if not isinstance(entries, list):
            raise PathSafetyError("cleanup manifest entries must be a list")
        targets: list[CleanupTarget] = []
        observed: set[Path] = set()
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
                raise PathSafetyError("cleanup entry requires only path and sha256")
            target = self._guard_target(str(entry["path"]))
            if target in observed:
                raise PathSafetyError("cleanup manifest contains a duplicate target")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if digest != entry["sha256"]:
                raise PathSafetyError(f"cleanup target hash mismatch: {entry['path']}")
            observed.add(target)
            targets.append(
                CleanupTarget(
                    relative_path=target.relative_to(self.results).as_posix(),
                    sha256=digest,
                    absolute_path=target,
                )
            )
        return CleanupPlan(
            schema_version="1.0",
            manifest_path=resolved_manifest,
            manifest_sha256=hashlib.sha256(resolved_manifest.read_bytes()).hexdigest(),
            scope=expected_scope,
            run_id=run_id,
            targets=tuple(targets),
        )

    def execute_cleanup(
        self,
        plan: CleanupPlan,
        *,
        confirm: bool,
        console: ResearchConsole,
    ) -> Path:
        # STEP LOG P1-CLEANUP-004: Revalidate every manifest member immediately before action.
        console.log(
            "P1-CLEANUP-004",
            "Revalidating manifest-bound cleanup targets.",
            details={"target_count": len(plan.targets)},
        )
        for target in plan.targets:
            resolved = self._guard_target(target.relative_path)
            digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
            if resolved != target.absolute_path or digest != target.sha256:
                raise PathSafetyError("cleanup target changed after plan construction")
        deleted: list[str] = []
        if confirm:
            # STEP LOG P1-CLEANUP-005: Delete only revalidated files listed in the manifest.
            console.log(
                "P1-CLEANUP-005",
                "Deleting revalidated manifest members.",
                details={"target_count": len(plan.targets)},
            )
            for target in plan.targets:
                target.absolute_path.unlink()
                deleted.append(target.relative_path)
        else:
            # STEP LOG P1-CLEANUP-006: Preserve every target during the dry run.
            console.log(
                "P1-CLEANUP-006",
                "Dry run completed without deleting targets.",
                details={"target_count": len(plan.targets)},
            )
        receipt_payload: dict[str, Any] = {
            "schema_version": "1.0",
            "scope": plan.scope,
            "run_id": plan.run_id,
            "manifest_path": plan.manifest_path.relative_to(self.root).as_posix(),
            "manifest_sha256": plan.manifest_sha256,
            "mode": "confirm" if confirm else "dry-run",
            "target_count": len(plan.targets),
            "targets": [target.relative_path for target in plan.targets],
            "deleted": deleted,
        }
        receipt_id = canonical_hash(receipt_payload)
        receipt_dir = self.results / "audits" / "cleanup"
        receipt_dir.mkdir(parents=True, exist_ok=True)
        receipt_path = receipt_dir / f"cleanup_{receipt_id}.json"
        if receipt_path.exists():
            if receipt_path.read_bytes() != canonical_bytes(receipt_payload) + b"\n":
                raise PathSafetyError("cleanup receipt identity collision")
        else:
            temporary = receipt_path.with_suffix(".json.partial")
            with temporary.open("xb") as stream:
                stream.write(canonical_bytes(receipt_payload) + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, receipt_path)
        # STEP LOG P1-CLEANUP-007: Retain the cleanup receipt as referenced evidence.
        console.log(
            "P1-CLEANUP-007",
            "Cleanup receipt retained.",
            details={"receipt": receipt_path.relative_to(self.root).as_posix()},
        )
        return receipt_path
