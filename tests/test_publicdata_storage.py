from __future__ import annotations

import contextlib
import io
import tempfile
import sys
import unittest
from pathlib import Path
from unittest import mock

from publicdata_core import storage
from publicdata_core.storage import clone_or_copy, prune_browser_profile
from scripts.dedupe_local_storage import find_duplicate_groups, main as dedupe_main


class CloneOrCopyTest(unittest.TestCase):
    def test_destination_is_independent_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "a.bin", Path(tmp) / "b.bin"
            src.write_bytes(b"x" * 10_000)
            clone_or_copy(src, dst)
            self.assertEqual(dst.read_bytes(), src.read_bytes())
            dst.write_bytes(b"changed")
            self.assertEqual(src.read_bytes(), b"x" * 10_000)

    def test_refuses_existing_destination_unless_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "a.bin", Path(tmp) / "b.bin"
            src.write_bytes(b"new")
            dst.write_bytes(b"old")
            with self.assertRaises(FileExistsError):
                clone_or_copy(src, dst)
            self.assertEqual(dst.read_bytes(), b"old")
            clone_or_copy(src, dst, replace=True)
            self.assertEqual(dst.read_bytes(), b"new")

    @unittest.skipUnless(hasattr(__import__("os"), "O_EXCL") and sys.platform != "win32", "needs fcntl")
    def test_linux_reflink_path_never_deletes_existing_destination(self) -> None:
        # Regression: FileExistsError was swallowed as a clone failure and the existing file unlinked.
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / "a.bin", Path(tmp) / "b.bin"
            src.write_bytes(b"new")
            dst.write_bytes(b"old")
            with mock.patch.object(storage, "_clonefile", None), mock.patch.object(sys, "platform", "linux"):
                with self.assertRaises(FileExistsError):
                    clone_or_copy(src, dst)
                self.assertEqual(dst.read_bytes(), b"old")
                fresh = Path(tmp) / "c.bin"
                clone_or_copy(src, fresh)
                self.assertEqual(fresh.read_bytes(), b"new")


class PruneBrowserProfileTest(unittest.TestCase):
    def test_removes_caches_and_keeps_session_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            (profile / "optimization_guide_model_store" / "43").mkdir(parents=True)
            (profile / "optimization_guide_model_store" / "43" / "model.tflite").write_bytes(b"m" * 500)
            (profile / "Default" / "Cache").mkdir(parents=True)
            (profile / "Default" / "Cache" / "data_0").write_bytes(b"c" * 100)
            (profile / "Default" / "Cookies").write_bytes(b"cookie-db")
            (profile / "BrowserMetrics-spare.pma").write_bytes(b"p" * 50)

            freed = prune_browser_profile(profile)

            self.assertEqual(freed, 650)
            self.assertFalse((profile / "optimization_guide_model_store").exists())
            self.assertFalse((profile / "Default" / "Cache").exists())
            self.assertFalse((profile / "BrowserMetrics-spare.pma").exists())
            self.assertEqual((profile / "Default" / "Cookies").read_bytes(), b"cookie-db")

    def test_missing_profile_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(prune_browser_profile(Path(tmp) / "absent"), 0)


class DedupeLocalStorageTest(unittest.TestCase):
    def test_groups_identical_files_and_apply_keeps_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = b"official-document" * 5000
            for rel in ("raw/a.pdf", "origin/sha256/ab/a", "derived/copy.pdf"):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_bytes(payload)
            (root / "raw/other.pdf").write_bytes(b"different" * 9000)

            groups = find_duplicate_groups([root], min_bytes=1024)
            self.assertEqual(len(groups), 1)
            self.assertEqual(len(groups[0]), 3)

            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dedupe_main([str(root), "--min-bytes", "1024", "--apply"]), 0)
            for rel in ("raw/a.pdf", "origin/sha256/ab/a", "derived/copy.pdf"):
                self.assertEqual((root / rel).read_bytes(), payload)
            self.assertEqual(sorted(p.name for p in root.rglob(".*.clone")), [])


if __name__ == "__main__":
    unittest.main()
