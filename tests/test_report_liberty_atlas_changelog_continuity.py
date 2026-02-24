from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.report_liberty_atlas_changelog_continuity import main


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class TestReportLibertyAtlasChangelogContinuity(unittest.TestCase):
    def test_main_strict_ok_with_release_crosscheck(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            changelog_path = root / "history.jsonl"
            release_json = root / "release.json"
            out_path = root / "continuity.json"

            changelog_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "entry_id": "snap-2026-02-22",
                                "snapshot_date": "2026-02-22",
                                "previous_snapshot_date": "",
                                "run_at": "2026-02-22T19:09:00+00:00",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "entry_id": "snap-2026-02-23",
                                "snapshot_date": "2026-02-23",
                                "previous_snapshot_date": "2026-02-22",
                                "run_at": "2026-02-23T19:09:00+00:00",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "entry_id": "snap-2026-02-23-rerun",
                                "snapshot_date": "2026-02-23",
                                "previous_snapshot_date": "2026-02-23",
                                "run_at": "2026-02-23T19:10:00+00:00",
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            _write_json(
                release_json,
                {
                    "status": "ok",
                    "snapshot_date": "2026-02-23",
                    "changelog": {
                        "entry_id": "snap-2026-02-23-rerun",
                        "history_latest_entry_id": "snap-2026-02-23-rerun",
                    },
                },
            )

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--changelog-jsonl",
                        str(changelog_path),
                        "--snapshot-date",
                        "2026-02-23",
                        "--release-json",
                        str(release_json),
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 0)

            payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(str(payload["status"]), "ok")
            self.assertEqual(int(payload["entries_total"]), 3)
            self.assertEqual(int(payload["malformed_lines_total"]), 0)
            self.assertEqual(str(payload["latest_snapshot_date"]), "2026-02-23")
            self.assertEqual(str(payload["latest_entry_id"]), "snap-2026-02-23-rerun")
            self.assertEqual(list(payload["strict_fail_reasons"]), [])
            self.assertEqual(bool(payload["checks"]["previous_snapshot_chain_ok"]), True)
            self.assertEqual(bool(payload["checks"]["run_at_monotonic"]), True)
            self.assertEqual(bool(payload["checks"]["release_consistent"]), True)

    def test_main_strict_fails_on_chain_break_and_order(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            changelog_path = root / "history_bad.jsonl"
            out_path = root / "continuity_bad.json"

            changelog_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "entry_id": "dup-entry",
                                "snapshot_date": "2026-02-22",
                                "previous_snapshot_date": "",
                                "run_at": "2026-02-23T19:09:00+00:00",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "entry_id": "dup-entry",
                                "snapshot_date": "2026-02-23",
                                "previous_snapshot_date": "2026-02-20",
                                "run_at": "2026-02-22T19:09:00+00:00",
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--changelog-jsonl",
                        str(changelog_path),
                        "--snapshot-date",
                        "2026-02-23",
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 4)

            payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(str(payload["status"]), "failed")
            reasons = set(str(item) for item in payload["strict_fail_reasons"])
            self.assertIn("duplicate_entry_id", reasons)
            self.assertIn("run_at_not_monotonic", reasons)
            self.assertIn("previous_snapshot_chain_break", reasons)
            self.assertEqual(bool(payload["checks"]["previous_snapshot_chain_ok"]), False)
            self.assertEqual(bool(payload["checks"]["run_at_monotonic"]), False)


if __name__ == "__main__":
    unittest.main()
