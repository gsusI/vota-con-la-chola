from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_release_trace_digest_heartbeat_window import main


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_text(payload, encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _heartbeat_entry(
    *,
    idx: int,
    status: str,
    freshness_within_sla: bool,
    release_age_minutes: float,
    max_age_minutes: float = 360.0,
) -> dict:
    run_at = f"2026-02-23T14:{idx:02d}:00+00:00"
    stale_detected = not bool(freshness_within_sla)
    return {
        "run_at": run_at,
        "heartbeat_id": f"{run_at}|{status}|{idx}",
        "status": status,
        "digest_path": "docs/etl/sprints/AI-OPS-88/evidence/citizen_release_trace_digest_latest.json",
        "digest_generated_at": run_at,
        "release_generated_at": "2026-02-23T13:55:00+00:00",
        "release_age_minutes": release_age_minutes,
        "max_age_minutes": max_age_minutes,
        "freshness_within_sla": freshness_within_sla,
        "stale_detected": stale_detected,
        "release_ready": status != "failed",
        "release_total_fail": 0 if status != "failed" else 1,
        "release_failed_ids_total": 0 if status != "failed" else 1,
        "parity_ok_assets": 9 if status != "failed" else 8,
        "parity_total_assets": 9,
        "contract_complete": status == "ok",
        "degraded_reasons": ["release_trace_stale"] if stale_detected else [],
        "failure_reasons": [] if status != "failed" else ["release_failures_present"],
        "strict_fail_count": 0 if status != "failed" else 1,
        "strict_fail_reasons": [] if status != "failed" else ["release_failures_present"],
    }


class TestReportCitizenReleaseTraceDigestHeartbeatWindow(unittest.TestCase):
    def test_main_passes_strict_with_fresh_window(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(idx=1, status="ok", freshness_within_sla=True, release_age_minutes=20.0),
                    _heartbeat_entry(idx=2, status="ok", freshness_within_sla=True, release_age_minutes=25.0),
                    _heartbeat_entry(idx=3, status="ok", freshness_within_sla=True, release_age_minutes=30.0),
                ],
            )

            rc = main(
                [
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--last",
                    "3",
                    "--max-failed",
                    "0",
                    "--max-failed-rate-pct",
                    "0",
                    "--max-degraded",
                    "0",
                    "--max-degraded-rate-pct",
                    "0",
                    "--max-stale",
                    "0",
                    "--max-stale-rate-pct",
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
            self.assertEqual(int(report["stale_in_window"]), 0)
            self.assertEqual(report["strict_fail_reasons"], [])

    def test_main_fails_strict_when_stale_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_fail.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(idx=1, status="ok", freshness_within_sla=True, release_age_minutes=20.0),
                    _heartbeat_entry(idx=2, status="degraded", freshness_within_sla=False, release_age_minutes=900.0),
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
                    "--max-failed-rate-pct",
                    "0",
                    "--max-degraded",
                    "0",
                    "--max-degraded-rate-pct",
                    "0",
                    "--max-stale",
                    "0",
                    "--max-stale-rate-pct",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            report = _read_json(out)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(int(report["stale_in_window"]), 1)
            self.assertIn("max_stale_exceeded", report["strict_fail_reasons"])
            self.assertIn("latest_release_trace_stale", report["strict_fail_reasons"])

    def test_main_rejects_invalid_window_size(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            _write_jsonl(
                heartbeat_jsonl,
                [_heartbeat_entry(idx=1, status="ok", freshness_within_sla=True, release_age_minutes=30.0)],
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
