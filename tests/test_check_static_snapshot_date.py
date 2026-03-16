import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_static_snapshot_date.py"


class CheckStaticSnapshotDateTest(unittest.TestCase):
    def test_ok_when_snapshot_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "artifact.json"
            path.write_text(json.dumps({"meta": {"snapshot_date": "2026-02-12"}}), encoding="utf-8")
            proc = subprocess.run(
                ["python3", str(SCRIPT), "--path", str(path), "--snapshot-date", "2026-02-12"],
                capture_output=True,
                text=True,
                check=False,
                cwd=REPO_ROOT,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn("OK", proc.stdout)

    def test_mismatch_when_snapshot_differs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "artifact.json"
            path.write_text(json.dumps({"meta": {"snapshot_date": "2026-02-11"}}), encoding="utf-8")
            proc = subprocess.run(
                ["python3", str(SCRIPT), "--path", str(path), "--snapshot-date", "2026-02-12"],
                capture_output=True,
                text=True,
                check=False,
                cwd=REPO_ROOT,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("MISMATCH", proc.stdout)
