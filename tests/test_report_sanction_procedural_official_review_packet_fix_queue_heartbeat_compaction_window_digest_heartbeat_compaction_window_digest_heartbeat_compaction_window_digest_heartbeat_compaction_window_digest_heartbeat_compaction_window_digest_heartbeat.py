from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat import (
    main,
)


class TestSanctionProceduralPacketFixDigestHeartbeatCompactionWindowDigestHeartbeatCompactionWindowDigestHeartbeatCompactionWindowDigestHeartbeat(
    unittest.TestCase
):
    def _write_digest(
        self,
        path: Path,
        *,
        status: str,
        risk_level: str,
        strict_fail_reasons: list[str],
        risk_reasons: list[str],
        missing_in_compacted: int,
    ) -> None:
        payload = {
            "generated_at": "2026-02-24T13:00:00+00:00",
            "input": {
                "compaction_window_generated_at": "2026-02-24T12:59:59+00:00",
                "heartbeat_path": "/tmp/sanction_hb.jsonl",
                "compacted_path": "/tmp/sanction_hb.compacted.jsonl",
            },
            "status": status,
            "risk_level": risk_level,
            "risk_reasons": risk_reasons,
            "strict_fail_reasons": strict_fail_reasons,
            "strict_fail_count": len(strict_fail_reasons),
            "risk_reason_count": len(risk_reasons),
            "key_metrics": {
                "entries_total_raw": 20,
                "entries_total_compacted": 20 - missing_in_compacted,
                "window_raw_entries": 20,
                "raw_window_incidents": 2,
                "present_in_compacted_in_window": 20 - missing_in_compacted,
                "missing_in_compacted_in_window": missing_in_compacted,
                "incident_missing_in_compacted": 0,
                "raw_window_coverage_pct": 100.0 - (missing_in_compacted * 5.0),
                "incident_coverage_pct": 100.0,
            },
            "validation_errors": [],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_append_and_dedupe(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            digest_path = td_path / "digest_ok.json"
            heartbeat_path = td_path / "heartbeat.jsonl"
            out_a = td_path / "append_a.json"
            out_b = td_path / "append_b.json"

            self._write_digest(
                digest_path,
                status="ok",
                risk_level="green",
                strict_fail_reasons=[],
                risk_reasons=[],
                missing_in_compacted=0,
            )

            with contextlib.redirect_stdout(io.StringIO()):
                rc_a = main(
                    [
                        "--digest-json",
                        str(digest_path),
                        "--heartbeat-jsonl",
                        str(heartbeat_path),
                        "--strict",
                        "--out",
                        str(out_a),
                    ]
                )
            self.assertEqual(rc_a, 0)
            report_a = json.loads(out_a.read_text(encoding="utf-8"))
            self.assertEqual(bool(report_a["appended"]), True)
            self.assertEqual(bool(report_a["duplicate_detected"]), False)
            self.assertEqual(int(report_a["history_size_after"]), 1)

            with contextlib.redirect_stdout(io.StringIO()):
                rc_b = main(
                    [
                        "--digest-json",
                        str(digest_path),
                        "--heartbeat-jsonl",
                        str(heartbeat_path),
                        "--strict",
                        "--out",
                        str(out_b),
                    ]
                )
            self.assertEqual(rc_b, 0)
            report_b = json.loads(out_b.read_text(encoding="utf-8"))
            self.assertEqual(bool(report_b["appended"]), False)
            self.assertEqual(bool(report_b["duplicate_detected"]), True)
            self.assertEqual(int(report_b["history_size_after"]), 1)

            lines = [line for line in heartbeat_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)

    def test_strict_fails_when_digest_status_failed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            digest_path = td_path / "digest_failed.json"
            heartbeat_path = td_path / "heartbeat.jsonl"
            out_path = td_path / "append_failed.json"

            self._write_digest(
                digest_path,
                status="failed",
                risk_level="red",
                strict_fail_reasons=["incident_missing_in_compacted"],
                risk_reasons=[],
                missing_in_compacted=1,
            )

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--digest-json",
                        str(digest_path),
                        "--heartbeat-jsonl",
                        str(heartbeat_path),
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 4)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            heartbeat = report.get("heartbeat", {})
            self.assertEqual(str(heartbeat.get("status") or ""), "failed")
            self.assertEqual(str(heartbeat.get("risk_level") or ""), "red")
            self.assertEqual(int(report.get("history_size_after") or 0), 1)


if __name__ == "__main__":
    unittest.main()
