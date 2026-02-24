from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_window import (
    main,
)


class TestSanctionProceduralPacketFixCompactionWindowDigestHeartbeatCompactionWindowDigestHeartbeatCompactionWindowDigestHeartbeatCompactionWindowDigestHeartbeatWindow(
    unittest.TestCase
):
    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        lines = [json.dumps(row) for row in rows]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _hb(self, minute: int, *, status: str = "ok", risk_level: str = "green") -> dict[str, object]:
        mm = f"{minute:02d}"
        strict_reasons = ["incident_missing_in_compacted"] if status == "failed" else []
        risk_reasons = ["non_incident_rows_missing_in_compacted_window"] if status == "degraded" else []
        return {
            "run_at": f"2026-02-24T13:{mm}:00+00:00",
            "heartbeat_id": f"hb-{mm}",
            "status": status,
            "risk_level": risk_level,
            "window_raw_entries": 20,
            "raw_window_incidents": 2,
            "missing_in_compacted_in_window": 0 if status == "ok" else 1,
            "incident_missing_in_compacted": 0 if status != "failed" else 1,
            "raw_window_coverage_pct": 100.0 if status == "ok" else 95.0,
            "incident_coverage_pct": 100.0 if status != "failed" else 50.0,
            "strict_fail_count": len(strict_reasons),
            "risk_reason_count": len(risk_reasons),
            "strict_fail_reasons": strict_reasons,
            "risk_reasons": risk_reasons,
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
            self.assertEqual(int(report["risk_level_counts"]["green"]), 3)
            self.assertEqual(list(report.get("strict_fail_reasons") or []), [])

    def test_window_fails_strict_on_failed_latest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_path = td_path / "heartbeat.jsonl"
            out_path = td_path / "window_failed.json"
            self._write_jsonl(heartbeat_path, [self._hb(0), self._hb(1, status="failed", risk_level="red"), self._hb(2, status="failed", risk_level="red")])

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
            self.assertEqual(int(report["risk_level_counts"]["red"]), 2)
            self.assertIn("max_failed_exceeded", list(report.get("strict_fail_reasons") or []))
            self.assertIn("latest_status_failed", list(report.get("strict_fail_reasons") or []))

    def test_window_degraded_allowed_by_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_path = td_path / "heartbeat.jsonl"
            out_path = td_path / "window_degraded.json"
            self._write_jsonl(
                heartbeat_path,
                [self._hb(0), self._hb(1, status="degraded", risk_level="amber"), self._hb(2)],
            )

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
            self.assertEqual(int(report["risk_level_counts"]["amber"]), 1)
            self.assertEqual(list(report.get("strict_fail_reasons") or []), [])


if __name__ == "__main__":
    unittest.main()
