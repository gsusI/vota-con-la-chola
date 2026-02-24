from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest import (
    main,
)


class TestReportSanctionProceduralOfficialReviewPacketFixQueueHeartbeatCompactionWindowDigest(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _parity_payload(
        self,
        *,
        missing_in_window: int = 0,
        incident_missing: int = 0,
        strict_fail_reasons: list[str] | None = None,
    ) -> dict[str, object]:
        reasons = list(strict_fail_reasons or [])
        window_raw_entries = 6
        present = window_raw_entries - int(missing_in_window)
        return {
            "generated_at": "2026-02-24T14:00:00+00:00",
            "heartbeat_path": "docs/etl/runs/heartbeat.jsonl",
            "compacted_path": "docs/etl/runs/heartbeat.compacted.jsonl",
            "entries_total_raw": 25,
            "entries_total_compacted": 20,
            "window_raw_entries": window_raw_entries,
            "raw_window_incidents": 2,
            "present_in_compacted_in_window": present,
            "missing_in_compacted_in_window": int(missing_in_window),
            "incident_missing_in_compacted": int(incident_missing),
            "raw_window_coverage_pct": round((present / window_raw_entries) * 100.0, 4),
            "incident_coverage_pct": 100.0 if incident_missing == 0 else 50.0,
            "checks": {
                "window_nonempty_ok": True,
                "raw_window_malformed_ok": True,
                "compacted_malformed_ok": True,
                "latest_present_ok": True,
                "incident_parity_ok": incident_missing == 0,
                "failed_parity_ok": incident_missing == 0,
                "degraded_parity_ok": incident_missing == 0,
                "strict_rows_parity_ok": incident_missing == 0,
                "malformed_parity_ok": True,
            },
            "strict_fail_reasons": reasons,
        }

    def test_digest_ok_when_parity_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            parity_path = td_path / "parity.json"
            out_path = td_path / "digest.json"
            self._write_json(parity_path, self._parity_payload())

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--compaction-window-json",
                        str(parity_path),
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 0)
            digest = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(str(digest.get("status") or ""), "ok")
            self.assertEqual(str(digest.get("risk_level") or ""), "green")
            self.assertEqual(list(digest.get("strict_fail_reasons") or []), [])
            self.assertEqual(int(digest["key_metrics"]["missing_in_compacted_in_window"]), 0)

    def test_digest_strict_fails_when_parity_report_has_strict_failures(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            parity_path = td_path / "parity_fail.json"
            out_path = td_path / "digest_fail.json"
            self._write_json(
                parity_path,
                self._parity_payload(
                    missing_in_window=1,
                    incident_missing=1,
                    strict_fail_reasons=[
                        "incident_missing_in_compacted",
                        "failed_underreported_in_compacted",
                    ],
                ),
            )

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--compaction-window-json",
                        str(parity_path),
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 4)
            digest = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(str(digest.get("status") or ""), "failed")
            self.assertEqual(str(digest.get("risk_level") or ""), "red")
            reasons = list(digest.get("strict_fail_reasons") or [])
            self.assertIn("incident_missing_in_compacted", reasons)


if __name__ == "__main__":
    unittest.main()
