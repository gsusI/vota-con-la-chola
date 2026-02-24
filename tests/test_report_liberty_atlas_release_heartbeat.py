from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_liberty_atlas_release_heartbeat import main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _release_fixture(*, snapshot_date: str = "2026-02-23", entry_id: str = "snap-2026-02-23") -> dict:
    return {
        "generated_at": "2026-02-23T19:24:12+00:00",
        "status": "ok",
        "snapshot_date": snapshot_date,
        "schema_version": "liberty_restrictions_snapshot_v1",
        "snapshot_totals": {"restrictions_total": 8},
        "snapshot_restrictions_total": 8,
        "diff": {
            "status": "unchanged",
            "changed_sections_total": 0,
            "items_added_total": 0,
            "items_removed_total": 0,
            "totals_changed": [],
        },
        "changelog": {
            "entry_id": entry_id,
            "appended": True,
            "history_entries_total": 4,
            "history_malformed_lines_total": 0,
            "history_latest_entry_id": entry_id,
            "history_latest_snapshot_date": snapshot_date,
        },
    }


def _continuity_fixture(*, snapshot_date: str = "2026-02-23", entry_id: str = "snap-2026-02-23") -> dict:
    return {
        "generated_at": "2026-02-23T19:24:12+00:00",
        "status": "ok",
        "expected_snapshot_date": snapshot_date,
        "entries_total": 4,
        "malformed_lines_total": 0,
        "latest_entry_id": entry_id,
        "latest_snapshot_date": snapshot_date,
        "checks": {
            "history_nonempty": True,
            "malformed_lines_ok": True,
            "entry_ids_unique": True,
            "run_at_monotonic": True,
            "previous_snapshot_chain_ok": True,
            "latest_snapshot_matches_expected": True,
            "release_consistent": True,
        },
        "strict_fail_reasons": [],
    }


class TestReportLibertyAtlasReleaseHeartbeat(unittest.TestCase):
    def test_main_strict_ok_with_local_hf_mirror(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            published_json = root / "published.json"
            gh_json = root / "gh.json"
            hf_json = root / "hf.json"
            continuity_json = root / "continuity.json"
            heartbeat_jsonl = root / "heartbeat.jsonl"
            out = root / "report.json"

            payload = _release_fixture()
            _write_json(published_json, payload)
            _write_json(gh_json, payload)
            _write_json(hf_json, payload)
            _write_json(continuity_json, _continuity_fixture())

            rc = main(
                [
                    "--published-release-json",
                    str(published_json),
                    "--gh-pages-release-json",
                    str(gh_json),
                    "--continuity-json",
                    str(continuity_json),
                    "--hf-release-json",
                    str(hf_json),
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--snapshot-date",
                    "2026-02-23",
                    "--max-snapshot-age-days",
                    "14",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 0)
            report = _read_json(out)
            self.assertEqual(str(report["status"]), "ok")
            self.assertEqual(list(report["strict_fail_reasons"]), [])
            self.assertTrue(bool(report["appended"]))
            hb = report["heartbeat"]
            self.assertEqual(str(hb["status"]), "ok")
            self.assertEqual(int(hb["stale_alerts_count"]), 0)
            self.assertEqual(int(hb["drift_alerts_count"]), 0)
            self.assertEqual(bool(hb["checks"]["published_gh_parity_ok"]), True)
            self.assertEqual(bool(hb["checks"]["published_hf_parity_ok"]), True)

    def test_main_strict_fails_on_published_gh_drift(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            published_json = root / "published.json"
            gh_json = root / "gh.json"
            hf_json = root / "hf.json"
            continuity_json = root / "continuity.json"
            heartbeat_jsonl = root / "heartbeat.jsonl"
            out = root / "report_drift.json"

            published = _release_fixture(entry_id="snap-2026-02-23")
            gh = _release_fixture(entry_id="snap-2026-02-23-gh")
            hf = _release_fixture(entry_id="snap-2026-02-23")

            _write_json(published_json, published)
            _write_json(gh_json, gh)
            _write_json(hf_json, hf)
            _write_json(continuity_json, _continuity_fixture(entry_id="snap-2026-02-23"))

            rc = main(
                [
                    "--published-release-json",
                    str(published_json),
                    "--gh-pages-release-json",
                    str(gh_json),
                    "--continuity-json",
                    str(continuity_json),
                    "--hf-release-json",
                    str(hf_json),
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--snapshot-date",
                    "2026-02-23",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)
            report = _read_json(out)
            self.assertEqual(str(report["status"]), "failed")
            reasons = set(str(item) for item in report["strict_fail_reasons"])
            self.assertIn("published_gh_pages_drift_detected", reasons)
            self.assertGreaterEqual(int(report["heartbeat"]["drift_alerts_count"]), 1)

    def test_main_strict_fails_on_stale_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            published_json = root / "published.json"
            gh_json = root / "gh.json"
            continuity_json = root / "continuity.json"
            heartbeat_jsonl = root / "heartbeat.jsonl"
            out = root / "report_stale.json"

            stale_payload = _release_fixture(snapshot_date="2025-01-01", entry_id="snap-2025-01-01")
            _write_json(published_json, stale_payload)
            _write_json(gh_json, stale_payload)
            _write_json(
                continuity_json,
                _continuity_fixture(snapshot_date="2025-01-01", entry_id="snap-2025-01-01"),
            )

            rc = main(
                [
                    "--published-release-json",
                    str(published_json),
                    "--gh-pages-release-json",
                    str(gh_json),
                    "--continuity-json",
                    str(continuity_json),
                    "--allow-hf-unavailable",
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--snapshot-date",
                    "2025-01-01",
                    "--max-snapshot-age-days",
                    "1",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)
            report = _read_json(out)
            self.assertEqual(str(report["status"]), "failed")
            reasons = set(str(item) for item in report["strict_fail_reasons"])
            self.assertIn("stale_snapshot:published", reasons)
            self.assertIn("stale_snapshot:gh_pages", reasons)
            self.assertGreaterEqual(int(report["heartbeat"]["stale_alerts_count"]), 2)


if __name__ == "__main__":
    unittest.main()
