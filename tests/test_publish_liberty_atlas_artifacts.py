from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.publish_liberty_atlas_artifacts import main


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class TestPublishLibertyAtlasArtifacts(unittest.TestCase):
    def test_main_publishes_release_and_latest(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            inputs_dir = root / "inputs"
            published_dir = root / "published"
            gh_pages_out = root / "gh-pages" / "liberty-atlas-release.json"
            out_path = root / "evidence" / "publish_report.json"

            snapshot_json = inputs_dir / "snapshot.json"
            irlc_parquet = inputs_dir / "irlc.parquet"
            accountability_parquet = inputs_dir / "accountability.parquet"
            diff_json = inputs_dir / "diff.json"
            changelog_entry_json = inputs_dir / "changelog_entry.json"
            changelog_history_jsonl = inputs_dir / "changelog_history.jsonl"

            _write_json(
                snapshot_json,
                {
                    "snapshot_date": "2026-02-23",
                    "schema_version": "liberty_restrictions_snapshot_v1",
                    "totals": {
                        "restrictions_total": 8,
                        "accountability_edges_total": 15,
                    },
                },
            )
            irlc_parquet.parent.mkdir(parents=True, exist_ok=True)
            irlc_parquet.write_bytes(b"PAR1irlc")
            accountability_parquet.write_bytes(b"PAR1accountability")
            _write_json(
                diff_json,
                {
                    "status": "changed",
                    "changed_sections_total": 1,
                    "items_added_total": 2,
                    "items_removed_total": 0,
                    "totals_changed": ["restrictions_total"],
                },
            )
            _write_json(
                changelog_entry_json,
                {
                    "entry_id": "snap-2026-02-23",
                    "snapshot_date": "2026-02-23",
                    "appended": True,
                    "history_entries_total": 2,
                    "history_malformed_lines_total": 0,
                },
            )
            changelog_history_jsonl.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "entry_id": "snap-2026-02-22",
                                "snapshot_date": "2026-02-22",
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
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--snapshot-json",
                        str(snapshot_json),
                        "--irlc-parquet",
                        str(irlc_parquet),
                        "--accountability-parquet",
                        str(accountability_parquet),
                        "--diff-json",
                        str(diff_json),
                        "--changelog-entry-json",
                        str(changelog_entry_json),
                        "--changelog-history-jsonl",
                        str(changelog_history_jsonl),
                        "--published-dir",
                        str(published_dir),
                        "--gh-pages-out",
                        str(gh_pages_out),
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 0)

            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(str(report["status"]), "ok")
            self.assertEqual(str(report["snapshot_date"]), "2026-02-23")

            release_path = Path(str(report["release_path"]))
            release_latest_path = Path(str(report["release_latest_path"]))
            self.assertTrue(release_path.exists())
            self.assertTrue(release_latest_path.exists())

            release_latest = json.loads(release_latest_path.read_text(encoding="utf-8"))
            self.assertEqual(str(release_latest["status"]), "ok")
            self.assertEqual(int(release_latest["snapshot_totals"]["restrictions_total"]), 8)
            self.assertEqual(str(release_latest["changelog"]["entry_id"]), "snap-2026-02-23")
            self.assertEqual(str(release_latest["changelog"]["history_latest_snapshot_date"]), "2026-02-23")

            gh_payload = json.loads(gh_pages_out.read_text(encoding="utf-8"))
            self.assertEqual(str(gh_payload["snapshot_date"]), "2026-02-23")
            self.assertEqual(str(gh_payload["status"]), "ok")

            copied = report["published_files"]
            self.assertTrue(Path(str(copied["snapshot_json"]["path"])).exists())
            self.assertTrue(Path(str(copied["irlc_parquet"]["path"])).exists())
            self.assertTrue(Path(str(copied["accountability_parquet"]["path"])).exists())

    def test_main_missing_inputs_obeys_allow_missing(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            snapshot_json = root / "snapshot.json"
            published_dir = root / "published"
            missing_dir = root / "missing"
            missing_irlc = missing_dir / "irlc.parquet"
            missing_accountability = missing_dir / "accountability.parquet"
            missing_diff = missing_dir / "diff.json"
            missing_changelog_entry = missing_dir / "changelog_entry.json"
            missing_changelog_history = missing_dir / "changelog_history.jsonl"
            out_fail = root / "out_fail.json"
            out_pass = root / "out_pass.json"

            _write_json(
                snapshot_json,
                {
                    "snapshot_date": "2026-02-23",
                    "schema_version": "liberty_restrictions_snapshot_v1",
                    "totals": {"restrictions_total": 8},
                },
            )

            with contextlib.redirect_stdout(io.StringIO()):
                rc_fail = main(
                    [
                        "--snapshot-json",
                        str(snapshot_json),
                        "--irlc-parquet",
                        str(missing_irlc),
                        "--accountability-parquet",
                        str(missing_accountability),
                        "--diff-json",
                        str(missing_diff),
                        "--changelog-entry-json",
                        str(missing_changelog_entry),
                        "--changelog-history-jsonl",
                        str(missing_changelog_history),
                        "--published-dir",
                        str(published_dir),
                        "--out",
                        str(out_fail),
                    ]
                )
            self.assertEqual(rc_fail, 2)
            fail_payload = json.loads(out_fail.read_text(encoding="utf-8"))
            self.assertEqual(str(fail_payload["status"]), "missing_inputs")
            self.assertGreater(len(list(fail_payload["missing_inputs"])), 0)

            with contextlib.redirect_stdout(io.StringIO()):
                rc_pass = main(
                    [
                        "--snapshot-json",
                        str(snapshot_json),
                        "--irlc-parquet",
                        str(missing_irlc),
                        "--accountability-parquet",
                        str(missing_accountability),
                        "--diff-json",
                        str(missing_diff),
                        "--changelog-entry-json",
                        str(missing_changelog_entry),
                        "--changelog-history-jsonl",
                        str(missing_changelog_history),
                        "--published-dir",
                        str(published_dir),
                        "--allow-missing",
                        "--out",
                        str(out_pass),
                    ]
                )
            self.assertEqual(rc_pass, 0)
            pass_payload = json.loads(out_pass.read_text(encoding="utf-8"))
            self.assertEqual(str(pass_payload["status"]), "missing_inputs")


if __name__ == "__main__":
    unittest.main()
