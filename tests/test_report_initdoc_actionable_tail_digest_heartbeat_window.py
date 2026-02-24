from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_initdoc_actionable_tail_digest_heartbeat_window import main


class TestInitdocActionableTailDigestHeartbeatWindow(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        lines = [json.dumps(row) for row in rows]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _hb(self, minute: int, *, status: str = "ok") -> dict[str, object]:
        mm = f"{minute:02d}"
        return {
            "run_at": f"2026-02-23T09:{mm}:00+00:00",
            "heartbeat_id": f"hb-{mm}",
            "status": status,
            "total_missing": 119,
            "redundant_missing": 119 if status == "ok" else 118,
            "actionable_missing": 0 if status == "ok" else 1,
            "actionable_missing_pct": 0.0 if status == "ok" else 0.008403,
            "actionable_queue_empty": status == "ok",
            "max_actionable_missing": 0,
            "max_actionable_missing_pct": 0.0,
            "strict_fail_count": 0 if status != "failed" else 1,
            "strict_fail_reasons": [] if status != "failed" else ["actionable_missing_exceeds_threshold:1>0"],
        }

    def test_window_passes_strict_when_all_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_path = td_path / "heartbeat.jsonl"
            out_path = td_path / "window.json"
            self._write_jsonl(heartbeat_path, [self._hb(0), self._hb(1), self._hb(2)])

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--heartbeat-jsonl",
                        str(heartbeat_path),
                        "--last",
                        "20",
                        "--max-failed",
                        "0",
                        "--max-failed-rate-pct",
                        "0",
                        "--max-degraded",
                        "0",
                        "--max-degraded-rate-pct",
                        "0",
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 0)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(str(report.get("status") or ""), "ok")
            self.assertEqual(int(report["status_counts"]["ok"]), 3)
            self.assertEqual(int(report["status_counts"]["failed"]), 0)
            self.assertEqual(int(report["degraded_in_window"]), 0)
            self.assertEqual(list(report.get("strict_fail_reasons") or []), [])

    def test_window_fails_strict_on_failed_latest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_path = td_path / "heartbeat.jsonl"
            out_path = td_path / "window_failed.json"
            self._write_jsonl(heartbeat_path, [self._hb(0), self._hb(1, status="failed"), self._hb(2, status="failed")])

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--heartbeat-jsonl",
                        str(heartbeat_path),
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 4)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(str(report.get("status") or ""), "failed")
            self.assertEqual(int(report["failed_in_window"]), 2)
            self.assertEqual(str(report["latest"]["status"]), "failed")
            self.assertIn("max_failed_exceeded", list(report.get("strict_fail_reasons") or []))
            self.assertIn("latest_status_failed", list(report.get("strict_fail_reasons") or []))

    def test_window_degraded_allowed_by_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_path = td_path / "heartbeat.jsonl"
            out_path = td_path / "window_degraded.json"
            self._write_jsonl(heartbeat_path, [self._hb(0), self._hb(1, status="degraded"), self._hb(2)])

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--heartbeat-jsonl",
                        str(heartbeat_path),
                        "--max-degraded",
                        "2",
                        "--max-degraded-rate-pct",
                        "100",
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 0)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(str(report.get("status") or ""), "degraded")
            self.assertEqual(int(report["status_counts"]["degraded"]), 1)
            self.assertEqual(list(report.get("strict_fail_reasons") or []), [])

    def test_window_fails_on_malformed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_path = td_path / "heartbeat.jsonl"
            out_path = td_path / "window_malformed.json"
            heartbeat_path.write_text(json.dumps(self._hb(0)) + '\n{"broken_json":\n', encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--heartbeat-jsonl",
                        str(heartbeat_path),
                        "--max-failed",
                        "1",
                        "--max-failed-rate-pct",
                        "100",
                        "--max-degraded",
                        "1",
                        "--max-degraded-rate-pct",
                        "100",
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 4)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(int(report.get("malformed_entries_in_window") or 0), 1)
            self.assertIn("malformed_entries_present", list(report.get("strict_fail_reasons") or []))


if __name__ == "__main__":
    unittest.main()
