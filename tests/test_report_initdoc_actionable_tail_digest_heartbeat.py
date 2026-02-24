from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_initdoc_actionable_tail_digest_heartbeat import main


class TestInitdocActionableTailDigestHeartbeat(unittest.TestCase):
    def _write_digest(
        self,
        path: Path,
        *,
        status: str,
        actionable_missing: int,
        actionable_missing_pct: float,
        strict_fail_reasons: list[str],
    ) -> None:
        payload = {
            "generated_at": "2026-02-23T09:00:00+00:00",
            "contract_generated_at": "2026-02-23T08:59:50+00:00",
            "initiative_source_ids": ["senado_iniciativas"],
            "status": status,
            "totals": {
                "total_missing": 119,
                "redundant_missing": 119 - actionable_missing,
                "actionable_missing": actionable_missing,
                "actionable_missing_pct": actionable_missing_pct,
            },
            "thresholds": {
                "max_actionable_missing": 0,
                "max_actionable_missing_pct": 0.0,
            },
            "checks": {
                "actionable_queue_empty": actionable_missing == 0,
                "actionable_missing_within_threshold": actionable_missing == 0,
                "actionable_missing_pct_within_threshold": actionable_missing_pct == 0.0,
            },
            "strict_fail_reasons": strict_fail_reasons,
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
                actionable_missing=0,
                actionable_missing_pct=0.0,
                strict_fail_reasons=[],
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
                actionable_missing=1,
                actionable_missing_pct=0.008403,
                strict_fail_reasons=["actionable_missing_exceeds_threshold:1>0"],
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
            self.assertEqual(int(heartbeat.get("actionable_missing") or 0), 1)
            self.assertEqual(int(report.get("history_size_after") or 0), 1)


if __name__ == "__main__":
    unittest.main()
