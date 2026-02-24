from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_release_trace_digest_heartbeat_compaction_window import main


class TestCitizenReleaseTraceDigestHeartbeatCompactionWindow(unittest.TestCase):
    def _hb(
        self,
        minute: int,
        *,
        status: str = "ok",
        strict_fail_count: int = 0,
        freshness_within_sla: bool = True,
        stale_detected: bool | None = None,
    ) -> dict[str, object]:
        mm = f"{minute:02d}"
        strict_reasons = ["strict_fail"] if strict_fail_count > 0 else []
        stale = bool(stale_detected) if stale_detected is not None else (not bool(freshness_within_sla))
        row: dict[str, object] = {
            "run_at": f"2026-02-23T15:{mm}:00+00:00",
            "heartbeat_id": f"hb-{mm}",
            "status": status,
            "strict_fail_count": strict_fail_count,
            "strict_fail_reasons": strict_reasons,
            "freshness_within_sla": bool(freshness_within_sla),
            "stale_detected": stale,
            "degraded_reasons": ["release_trace_stale"] if stale else [],
        }
        return row

    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        lines = [json.dumps(r) for r in rows]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_compaction_window_passes_when_incidents_and_latest_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            raw_path = td_path / "raw.jsonl"
            compacted_path = td_path / "compacted.jsonl"
            out_path = td_path / "report.json"

            raw_rows = [
                self._hb(0, status="ok", freshness_within_sla=True, stale_detected=False),
                self._hb(1, status="failed", strict_fail_count=1, freshness_within_sla=True, stale_detected=False),
                self._hb(2, status="degraded", freshness_within_sla=False, stale_detected=True),
                self._hb(3, status="ok", freshness_within_sla=False, stale_detected=True),
                self._hb(4, status="ok", freshness_within_sla=True, stale_detected=False),
            ]
            compacted_rows = [
                self._hb(1, status="failed", strict_fail_count=1, freshness_within_sla=True, stale_detected=False),
                self._hb(2, status="degraded", freshness_within_sla=False, stale_detected=True),
                self._hb(3, status="ok", freshness_within_sla=False, stale_detected=True),
                self._hb(4, status="ok", freshness_within_sla=True, stale_detected=False),
            ]
            self._write_jsonl(raw_path, raw_rows)
            self._write_jsonl(compacted_path, compacted_rows)

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--heartbeat-jsonl",
                        str(raw_path),
                        "--compacted-jsonl",
                        str(compacted_path),
                        "--last",
                        "20",
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 0)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(str(report.get("status") or ""), "degraded")
            self.assertEqual(int(report["window_raw_entries"]), 5)
            self.assertEqual(int(report["incident_missing_in_compacted"]), 0)
            self.assertEqual(int(report["stale_rows_missing_in_compacted"]), 0)
            self.assertEqual(bool(report["checks"]["latest_present_ok"]), True)
            self.assertEqual(list(report.get("strict_fail_reasons") or []), [])

    def test_compaction_window_strict_fails_when_stale_incident_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            raw_path = td_path / "raw.jsonl"
            compacted_path = td_path / "compacted.jsonl"
            out_path = td_path / "report_fail.json"

            raw_rows = [
                self._hb(0, status="ok", freshness_within_sla=True, stale_detected=False),
                self._hb(1, status="ok", freshness_within_sla=False, stale_detected=True),
                self._hb(2, status="ok", freshness_within_sla=True, stale_detected=False),
            ]
            compacted_rows = [
                self._hb(2, status="ok", freshness_within_sla=True, stale_detected=False),
            ]
            self._write_jsonl(raw_path, raw_rows)
            self._write_jsonl(compacted_path, compacted_rows)

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--heartbeat-jsonl",
                        str(raw_path),
                        "--compacted-jsonl",
                        str(compacted_path),
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 4)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            reasons = list(report.get("strict_fail_reasons") or [])
            self.assertIn("incident_missing_in_compacted", reasons)
            self.assertIn("stale_rows_underreported_in_compacted", reasons)

    def test_compaction_window_strict_fails_when_latest_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            raw_path = td_path / "raw.jsonl"
            compacted_path = td_path / "compacted.jsonl"
            out_path = td_path / "report_latest_fail.json"

            raw_rows = [self._hb(0, status="ok"), self._hb(1, status="ok")]
            compacted_rows = [self._hb(0, status="ok")]
            self._write_jsonl(raw_path, raw_rows)
            self._write_jsonl(compacted_path, compacted_rows)

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--heartbeat-jsonl",
                        str(raw_path),
                        "--compacted-jsonl",
                        str(compacted_path),
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 4)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIn("latest_raw_missing_in_compacted", list(report.get("strict_fail_reasons") or []))


if __name__ == "__main__":
    unittest.main()
