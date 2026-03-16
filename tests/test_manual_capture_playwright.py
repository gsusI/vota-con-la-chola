from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from scripts import manual_capture_playwright as target


class ManualCapturePlaywrightRuntimeTests(unittest.TestCase):
    def test_runtime_fallback_sets_system_node_when_driver_unhealthy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_node = tmp_path / "node"
            fake_node.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_node.chmod(fake_node.stat().st_mode | stat.S_IXUSR)

            pkg_dir = tmp_path / "playwright_pkg"
            driver_cli = pkg_dir / "driver" / "package" / "cli.js"
            driver_cli.parent.mkdir(parents=True, exist_ok=True)
            driver_cli.write_text("// fake cli\n", encoding="utf-8")

            old_path = os.environ.get("PATH")
            old_node = os.environ.get("PLAYWRIGHT_NODEJS_PATH")
            try:
                os.environ["PATH"] = f"{tmp}:{old_path}" if old_path else tmp
                os.environ.pop("PLAYWRIGHT_NODEJS_PATH", None)
                meta = target._ensure_playwright_nodejs_runtime(pkg_dir)
                self.assertTrue(meta["fallback_applied"])
                self.assertEqual(os.environ.get("PLAYWRIGHT_NODEJS_PATH"), str(fake_node))
            finally:
                if old_path is None:
                    os.environ.pop("PATH", None)
                else:
                    os.environ["PATH"] = old_path
                if old_node is None:
                    os.environ.pop("PLAYWRIGHT_NODEJS_PATH", None)
                else:
                    os.environ["PLAYWRIGHT_NODEJS_PATH"] = old_node

    def test_runtime_fallback_respects_existing_env_override(self) -> None:
        old_node = os.environ.get("PLAYWRIGHT_NODEJS_PATH")
        try:
            os.environ["PLAYWRIGHT_NODEJS_PATH"] = "/tmp/custom-node"
            meta = target._ensure_playwright_nodejs_runtime(Path("/tmp/unused"))
            self.assertFalse(meta["fallback_applied"])
            self.assertEqual(meta["effective_nodejs_path"], "/tmp/custom-node")
        finally:
            if old_node is None:
                os.environ.pop("PLAYWRIGHT_NODEJS_PATH", None)
            else:
                os.environ["PLAYWRIGHT_NODEJS_PATH"] = old_node


if __name__ == "__main__":
    unittest.main()
