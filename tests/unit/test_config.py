from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pead.core.config import CoreConfigError, load_config


class ImmutableConfigTests(unittest.TestCase):
    def test_repository_config_is_loaded_with_stable_identity(self) -> None:
        root = Path(__file__).parents[2]
        first = load_config(root, Path("configs/study/pead_main_v1.yaml"))
        second = load_config(root, Path("configs/study/pead_main_v1.yaml"))
        self.assertEqual(first.config_id, second.config_id)
        self.assertEqual(first.canonical_payload, second.canonical_payload)
        with self.assertRaises(TypeError):
            first.data["schema_version"] = "changed"  # type: ignore[index]

    def test_absolute_outside_and_repository_root_are_rejected(self) -> None:
        root = Path(__file__).parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            outside = Path(temporary) / "outside.yaml"
            outside.write_text("schema_version: '1.0'\n", encoding="utf-8")
            with self.assertRaises(CoreConfigError):
                load_config(root, outside)
        with self.assertRaises(CoreConfigError):
            load_config(root, root)

    def test_unversioned_config_is_rejected(self) -> None:
        root = Path(__file__).parents[2]
        path = root / "tmp" / "phase1_unversioned.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("name: test\n", encoding="utf-8")
        try:
            with self.assertRaises(CoreConfigError):
                load_config(root, path)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
