from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction import main


class TestReportSanctionProceduralOfficialReviewPacketFixQueueHeartbeatCompaction(unittest.TestCase):
    def _hb(
        self,
        minute: int,
        *,
        status: str = "ok",
        strict_fail_count: int = 0,
    ) -> dict[str, object]:
        mm = f"{minute:02d}"
        return {
            "run_at": f"2026-02-24T12:{mm}:00+00:00",
            "heartbeat_id": f"hb-{mm}",
            "status": status,
            "strict_fail_count": strict_fail_count,
            "strict_fail_reasons": ["strict_fail"] if strict_fail_count > 0 else [],
            "queue_rows_total": 0 if status == "ok" else 1,
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        lines = [json.dumps(r) for r in rows]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_compaction_preserves_incidents_and_latest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_path = td_path / "heartbeat.jsonl"
            compacted_path = td_path / "heartbeat.compacted.jsonl"
            out_path = td_path / "report.json"

            rows = [self._hb(i) for i in range(16)]
            rows[2] = self._hb(2, status="failed", strict_fail_count=1)
            rows[7] = self._hb(7, status="degraded")
            self._write_jsonl(heartbeat_path, rows)

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--heartbeat-jsonl",
                        str(heartbeat_path),
                        "--compacted-jsonl",
                        str(compacted_path),
                        "--keep-recent",
                        "2",
                        "--keep-mid-span",
                        "4",
                        "--keep-mid-every",
                        "2",
                        "--keep-old-every",
                        "5",
                        "--min-raw-for-dropped-check",
                        "5",
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 0)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(int(report["entries_total"]), 16)
            self.assertGreater(int(report["selected_entries"]), 0)
            self.assertGreater(int(report["dropped_entries"]), 0)
            self.assertEqual(int(report["incidents_total"]), 2)
            self.assertEqual(int(report["incidents_dropped"]), 0)
            self.assertEqual(int(report["failed_total"]), 1)
            self.assertEqual(int(report["failed_dropped"]), 0)
            self.assertEqual(int(report["degraded_total"]), 1)
            self.assertEqual(int(report["degraded_dropped"]), 0)
            self.assertEqual(bool(report["anchors"]["latest_selected"]), True)
            self.assertEqual(list(report["strict_fail_reasons"]), [])

            compacted_lines = [line for line in compacted_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(compacted_lines), int(report["selected_entries"]))

    def test_compaction_strict_fails_when_no_rows_dropped_above_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_path = td_path / "heartbeat.jsonl"
            compacted_path = td_path / "heartbeat.compacted.jsonl"
            out_path = td_path / "report_fail.json"

            rows = [self._hb(i) for i in range(30)]
            self._write_jsonl(heartbeat_path, rows)

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--heartbeat-jsonl",
                        str(heartbeat_path),
                        "--compacted-jsonl",
                        str(compacted_path),
                        "--keep-recent",
                        "100",
                        "--keep-mid-span",
                        "100",
                        "--keep-mid-every",
                        "5",
                        "--keep-old-every",
                        "20",
                        "--min-raw-for-dropped-check",
                        "20",
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 4)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(int(report["entries_total"]), 30)
            self.assertEqual(int(report["dropped_entries"]), 0)
            self.assertIn("no_entries_dropped_above_threshold", list(report.get("strict_fail_reasons") or []))

    def test_compaction_all_incidents_can_keep_all_without_drop_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_path = td_path / "heartbeat.jsonl"
            compacted_path = td_path / "heartbeat.compacted.jsonl"
            out_path = td_path / "report_all_incidents.json"

            rows = [self._hb(i, status="degraded") for i in range(30)]
            self._write_jsonl(heartbeat_path, rows)

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--heartbeat-jsonl",
                        str(heartbeat_path),
                        "--compacted-jsonl",
                        str(compacted_path),
                        "--keep-recent",
                        "20",
                        "--keep-mid-span",
                        "100",
                        "--keep-mid-every",
                        "5",
                        "--keep-old-every",
                        "20",
                        "--min-raw-for-dropped-check",
                        "25",
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 0)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(int(report["entries_total"]), 30)
            self.assertEqual(int(report["dropped_entries"]), 0)
            self.assertEqual(int(report["drop_candidates_total"]), 0)
            self.assertEqual(str(report.get("status")), "degraded")
            self.assertEqual(list(report.get("strict_fail_reasons") or []), [])


if __name__ == "__main__":
    unittest.main()
