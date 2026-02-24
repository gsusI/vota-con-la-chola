from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_liberty_atlas_release_heartbeat_window import main


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_text(payload, encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _heartbeat_entry(
    *,
    idx: int,
    status: str,
    stale_alerts_count: int,
    drift_alerts_count: int,
    hf_unavailable: bool,
    continuity_ok: bool,
    parity_ok: bool,
    expected_snapshot_match_ok: bool,
) -> dict:
    run_at = f"2026-02-23T19:{idx:02d}:00+00:00"
    return {
        "run_at": run_at,
        "heartbeat_id": f"{run_at}|{status}|{idx}",
        "status": status,
        "snapshot_date_expected": "2026-02-23",
        "stale_alerts_count": stale_alerts_count,
        "drift_alerts_count": drift_alerts_count,
        "hf_unavailable": hf_unavailable,
        "checks": {
            "continuity_ok": continuity_ok,
            "published_gh_parity_ok": parity_ok,
            "expected_snapshot_match_ok": expected_snapshot_match_ok,
        },
    }


class TestReportLibertyAtlasReleaseHeartbeatWindow(unittest.TestCase):
    def test_main_passes_strict_with_healthy_window(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_ok.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(
                        idx=1,
                        status="ok",
                        stale_alerts_count=0,
                        drift_alerts_count=0,
                        hf_unavailable=False,
                        continuity_ok=True,
                        parity_ok=True,
                        expected_snapshot_match_ok=True,
                    ),
                    _heartbeat_entry(
                        idx=2,
                        status="ok",
                        stale_alerts_count=0,
                        drift_alerts_count=0,
                        hf_unavailable=False,
                        continuity_ok=True,
                        parity_ok=True,
                        expected_snapshot_match_ok=True,
                    ),
                ],
            )

            rc = main(
                [
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--last",
                    "2",
                    "--max-failed",
                    "0",
                    "--max-degraded",
                    "0",
                    "--max-stale-alerts",
                    "0",
                    "--max-drift-alerts",
                    "0",
                    "--max-hf-unavailable",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 0)

            report = _read_json(out)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(int(report["failed_in_window"]), 0)
            self.assertEqual(int(report["stale_alerts_in_window"]), 0)
            self.assertEqual(int(report["drift_alerts_in_window"]), 0)
            self.assertEqual(report["strict_fail_reasons"], [])

    def test_main_fails_strict_on_latest_drift_stale(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_fail.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(
                        idx=1,
                        status="ok",
                        stale_alerts_count=0,
                        drift_alerts_count=0,
                        hf_unavailable=False,
                        continuity_ok=True,
                        parity_ok=True,
                        expected_snapshot_match_ok=True,
                    ),
                    _heartbeat_entry(
                        idx=2,
                        status="failed",
                        stale_alerts_count=1,
                        drift_alerts_count=1,
                        hf_unavailable=True,
                        continuity_ok=False,
                        parity_ok=False,
                        expected_snapshot_match_ok=False,
                    ),
                ],
            )

            rc = main(
                [
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--last",
                    "2",
                    "--max-failed",
                    "0",
                    "--max-degraded",
                    "0",
                    "--max-stale-alerts",
                    "0",
                    "--max-drift-alerts",
                    "0",
                    "--max-hf-unavailable",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            report = _read_json(out)
            self.assertEqual(report["status"], "failed")
            reasons = set(str(item) for item in report["strict_fail_reasons"])
            self.assertIn("max_failed_exceeded", reasons)
            self.assertIn("max_stale_alerts_exceeded", reasons)
            self.assertIn("max_drift_alerts_exceeded", reasons)
            self.assertIn("latest_stale_alert_present", reasons)
            self.assertIn("latest_drift_alert_present", reasons)
            self.assertIn("latest_continuity_not_ok", reasons)
            self.assertIn("latest_published_gh_parity_not_ok", reasons)
            self.assertIn("latest_expected_snapshot_mismatch", reasons)

    def test_main_rejects_invalid_window_size(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(
                        idx=1,
                        status="ok",
                        stale_alerts_count=0,
                        drift_alerts_count=0,
                        hf_unavailable=False,
                        continuity_ok=True,
                        parity_ok=True,
                        expected_snapshot_match_ok=True,
                    )
                ],
            )

            rc = main(
                [
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--last",
                    "0",
                ]
            )
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
