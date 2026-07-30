from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from pead.config.console import ResearchConsole
from pead.core.ids import run_id
from pead.core.paths import PathSafetyError, RepositoryPaths


class SafePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / ".git").mkdir()
        (self.root / "results" / "manifests" / "cleanup").mkdir(parents=True)
        self.paths = RepositoryPaths(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _manifest(
        self,
        *,
        scope: str = "test",
        run_identifier: str | None = None,
        entries: list[dict[str, str]] | None = None,
    ) -> Path:
        name = run_identifier or scope
        path = self.root / "results" / "manifests" / "cleanup" / f"{name}.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "scope": scope,
                    "run_id": run_identifier,
                    "entries": entries or [],
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return path

    def test_run_layout_is_content_addressed_and_never_reused(self) -> None:
        identifier = run_id({"study": "test", "seed": 1})
        layout = self.paths.run_layout(identifier, create=True)
        self.assertTrue(layout.raw.is_dir())
        with self.assertRaises(FileExistsError):
            self.paths.run_layout(identifier, create=True)

    def test_dry_run_retains_manifest_member_and_writes_receipt(self) -> None:
        target = self.root / "results" / "raw" / "artifact.txt"
        target.parent.mkdir(parents=True)
        target.write_text("generated", encoding="utf-8")
        manifest = self._manifest(
            entries=[
                {
                    "path": "raw/artifact.txt",
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                }
            ]
        )
        plan = self.paths.load_cleanup_plan(manifest, scope="test", run_id=None)
        receipt = self.paths.execute_cleanup(
            plan,
            confirm=False,
            console=ResearchConsole("1", stream=io.StringIO()),
        )
        self.assertTrue(target.exists())
        self.assertTrue(receipt.exists())

    def test_confirm_deletes_only_manifest_member(self) -> None:
        listed = self.root / "results" / "raw" / "listed.txt"
        retained = self.root / "results" / "raw" / "retained.txt"
        listed.parent.mkdir(parents=True)
        listed.write_text("listed", encoding="utf-8")
        retained.write_text("retained", encoding="utf-8")
        manifest = self._manifest(
            entries=[
                {
                    "path": "raw/listed.txt",
                    "sha256": hashlib.sha256(listed.read_bytes()).hexdigest(),
                }
            ]
        )
        plan = self.paths.load_cleanup_plan(manifest, scope="test", run_id=None)
        self.paths.execute_cleanup(
            plan,
            confirm=True,
            console=ResearchConsole("1", stream=io.StringIO()),
        )
        self.assertFalse(listed.exists())
        self.assertTrue(retained.exists())

    def test_root_results_root_outside_and_traversal_are_rejected(self) -> None:
        outside = self.root / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        for target in ("..", "../outside.txt", ".", str(self.root)):
            with self.subTest(target=target):
                manifest = self._manifest(
                    scope=f"bad-{abs(hash(target))}",
                    entries=[
                        {
                            "path": target,
                            "sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
                        }
                    ],
                )
                with self.assertRaises(PathSafetyError):
                    self.paths.load_cleanup_plan(
                        manifest,
                        scope=f"bad-{abs(hash(target))}",
                        run_id=None,
                    )

    def test_unlisted_or_hash_changed_target_cannot_be_deleted(self) -> None:
        target = self.root / "results" / "raw" / "changed.txt"
        target.parent.mkdir(parents=True)
        target.write_text("first", encoding="utf-8")
        manifest = self._manifest(
            entries=[
                {
                    "path": "raw/changed.txt",
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                }
            ]
        )
        target.write_text("second", encoding="utf-8")
        with self.assertRaises(PathSafetyError):
            self.paths.load_cleanup_plan(manifest, scope="test", run_id=None)


if __name__ == "__main__":
    unittest.main()
