from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_sanction_procedural_official_review_packet_fix_queue_heartbeat import main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fix_queue_payload(
    *,
    status: str = "ok",
    generated_at: str = "2026-02-24T12:20:17+00:00",
    queue_rows_total: int = 0,
    packets_expected_total: int = 4,
    packets_ready_total: int = 4,
    packets_not_ready_total: int = 0,
    queue_rows_by_packet_status: dict[str, int] | None = None,
    fix_queue_empty: bool = True,
    progress_report_not_failed: bool = True,
) -> dict:
    by_status = {} if queue_rows_by_packet_status is None else dict(queue_rows_by_packet_status)
    return {
        "generated_at": generated_at,
        "status": status,
        "totals": {
            "queue_rows_total": int(queue_rows_total),
            "queue_rows_by_packet_status": by_status,
            "packets_expected_total": int(packets_expected_total),
            "packets_ready_total": int(packets_ready_total),
            "packets_not_ready_total": int(packets_not_ready_total),
        },
        "checks": {
            "fix_queue_empty": bool(fix_queue_empty),
            "progress_report_not_failed": bool(progress_report_not_failed),
        },
    }


class TestReportSanctionProceduralOfficialReviewPacketFixQueueHeartbeat(unittest.TestCase):
    def test_main_appends_then_dedupes_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            fix_queue_json = td_path / "fix_queue_ok.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out1 = td_path / "heartbeat_out_1.json"
            out2 = td_path / "heartbeat_out_2.json"

            _write_json(
                fix_queue_json,
                _fix_queue_payload(
                    status="ok",
                    queue_rows_total=0,
                    packets_expected_total=4,
                    packets_ready_total=4,
                    packets_not_ready_total=0,
                    queue_rows_by_packet_status={},
                    fix_queue_empty=True,
                    progress_report_not_failed=True,
                ),
            )

            rc1 = main(
                [
                    "--fix-queue-json",
                    str(fix_queue_json),
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--strict",
                    "--out",
                    str(out1),
                ]
            )
            self.assertEqual(rc1, 0)
            report1 = _read_json(out1)
            self.assertEqual(str(report1["status"]), "ok")
            self.assertTrue(bool(report1["appended"]))
            self.assertFalse(bool(report1["already_present"]))
            self.assertEqual(int(report1["history_rows_after"]), 1)

            rc2 = main(
                [
                    "--fix-queue-json",
                    str(fix_queue_json),
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--strict",
                    "--out",
                    str(out2),
                ]
            )
            self.assertEqual(rc2, 0)
            report2 = _read_json(out2)
            self.assertEqual(str(report2["status"]), "ok")
            self.assertFalse(bool(report2["appended"]))
            self.assertTrue(bool(report2["already_present"]))
            self.assertEqual(int(report2["history_rows_after"]), 1)

    def test_main_strict_fails_when_fix_queue_failed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            fix_queue_json = td_path / "fix_queue_failed.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "heartbeat_failed_out.json"

            _write_json(
                fix_queue_json,
                _fix_queue_payload(
                    status="failed",
                    generated_at="2026-02-24T12:30:00+00:00",
                    queue_rows_total=2,
                    packets_expected_total=4,
                    packets_ready_total=2,
                    packets_not_ready_total=2,
                    queue_rows_by_packet_status={"invalid_row": 2},
                    fix_queue_empty=False,
                    progress_report_not_failed=False,
                ),
            )

            rc = main(
                [
                    "--fix-queue-json",
                    str(fix_queue_json),
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)
            report = _read_json(out)
            self.assertEqual(str(report["status"]), "failed")
            self.assertIn("fix_queue_status_failed", report["strict_fail_reasons"])
            self.assertIn("progress_report_failed", report["strict_fail_reasons"])
            self.assertTrue(bool(report["appended"]))


if __name__ == "__main__":
    unittest.main()
