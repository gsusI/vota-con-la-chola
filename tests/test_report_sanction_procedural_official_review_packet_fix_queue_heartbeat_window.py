from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_sanction_procedural_official_review_packet_fix_queue_heartbeat_window import main


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_text(payload, encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _heartbeat_entry(*, idx: int, status: str, queue_rows_total: int) -> dict:
    return {
        "run_at": f"2026-02-24T12:{idx:02d}:00+00:00",
        "heartbeat_id": f"{status}|{idx}|{queue_rows_total}",
        "status": status,
        "queue_rows_total": int(queue_rows_total),
        "packets_expected_total": 4,
        "packets_ready_total": 4 if queue_rows_total == 0 else 2,
        "packets_not_ready_total": 0 if queue_rows_total == 0 else 2,
        "queue_rows_by_packet_status": {} if queue_rows_total == 0 else {"invalid_row": queue_rows_total},
        "fix_queue_empty": queue_rows_total == 0,
        "progress_report_not_failed": status != "failed",
        "strict_fail_count": 0,
        "strict_fail_reasons": [],
    }


class TestReportSanctionProceduralOfficialReviewPacketFixQueueHeartbeatWindow(unittest.TestCase):
    def test_main_passes_strict_with_healthy_window(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_ok.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(idx=1, status="ok", queue_rows_total=0),
                    _heartbeat_entry(idx=2, status="ok", queue_rows_total=0),
                    _heartbeat_entry(idx=3, status="ok", queue_rows_total=0),
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
                    "--max-nonempty-queue-runs",
                    "0",
                    "--max-nonempty-queue-rate-pct",
                    "0",
                    "--max-malformed",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 0)

            report = _read_json(out)
            self.assertEqual(str(report["status"]), "ok")
            self.assertEqual(int(report["failed_in_window"]), 0)
            self.assertEqual(int(report["degraded_in_window"]), 0)
            self.assertEqual(int(report["nonempty_queue_runs_in_window"]), 0)
            self.assertEqual(list(report["strict_fail_reasons"]), [])

    def test_main_fails_strict_when_failed_degraded_and_nonempty_exceed_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_failed.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(idx=1, status="ok", queue_rows_total=0),
                    _heartbeat_entry(idx=2, status="degraded", queue_rows_total=2),
                    _heartbeat_entry(idx=3, status="failed", queue_rows_total=1),
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
                    "--max-nonempty-queue-runs",
                    "0",
                    "--max-nonempty-queue-rate-pct",
                    "0",
                    "--max-malformed",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            report = _read_json(out)
            self.assertEqual(str(report["status"]), "failed")
            self.assertEqual(int(report["failed_in_window"]), 1)
            self.assertEqual(int(report["degraded_in_window"]), 1)
            self.assertEqual(int(report["nonempty_queue_runs_in_window"]), 2)
            self.assertIn("max_failed_ok_exceeded", report["strict_fail_reasons"])
            self.assertIn("max_degraded_ok_exceeded", report["strict_fail_reasons"])
            self.assertIn("max_nonempty_queue_runs_ok_exceeded", report["strict_fail_reasons"])


if __name__ == "__main__":
    unittest.main()
