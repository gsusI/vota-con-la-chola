from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest import (
    main,
)


class TestSanctionProceduralPacketFixDigestHeartbeatCompactionWindowDigestHeartbeatCompactionWindowDigestHeartbeatCompactionWindowDigest(unittest.TestCase):
    def _write_json(self, path: Path, payload: dict[str, object]) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _parity(self, **overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "generated_at": "2026-02-24T16:00:00+00:00",
            "heartbeat_path": "/tmp/sanction_cd_trend_hb.jsonl",
            "compacted_path": "/tmp/sanction_cd_trend_hb.compacted.jsonl",
            "entries_total_raw": 20,
            "entries_total_compacted": 20,
            "window_raw_entries": 20,
            "raw_window_incidents": 2,
            "present_in_compacted_in_window": 20,
            "missing_in_compacted_in_window": 0,
            "incident_missing_in_compacted": 0,
            "raw_window_coverage_pct": 100.0,
            "incident_coverage_pct": 100.0,
            "checks": {
                "window_nonempty_ok": True,
                "raw_window_malformed_ok": True,
                "compacted_malformed_ok": True,
                "latest_present_ok": True,
                "incident_parity_ok": True,
                "failed_parity_ok": True,
                "degraded_parity_ok": True,
                "strict_rows_parity_ok": True,
                "malformed_parity_ok": True,
            },
            "strict_fail_reasons": [],
        }
        base.update(overrides)
        return base

    def test_digest_ok_strict_when_parity_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            parity_path = td_path / "parity_ok.json"
            out_path = td_path / "digest_ok.json"
            self._write_json(parity_path, self._parity())

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
            self.assertEqual(list(digest.get("risk_reasons") or []), [])
            self.assertEqual(list(digest.get("strict_fail_reasons") or []), [])

    def test_digest_degraded_when_non_incident_rows_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            parity_path = td_path / "parity_degraded.json"
            out_path = td_path / "digest_degraded.json"
            self._write_json(
                parity_path,
                self._parity(
                    entries_total_compacted=19,
                    present_in_compacted_in_window=19,
                    missing_in_compacted_in_window=1,
                    raw_window_coverage_pct=95.0,
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
            self.assertEqual(rc, 0)
            digest = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(str(digest.get("status") or ""), "degraded")
            self.assertEqual(str(digest.get("risk_level") or ""), "amber")
            risk_reasons = list(digest.get("risk_reasons") or [])
            self.assertIn("non_incident_rows_missing_in_compacted_window", risk_reasons)
            self.assertIn("raw_window_coverage_below_100", risk_reasons)
            self.assertEqual(list(digest.get("strict_fail_reasons") or []), [])

    def test_digest_strict_fails_when_parity_has_strict_fail_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            parity_path = td_path / "parity_failed.json"
            out_path = td_path / "digest_failed.json"
            self._write_json(
                parity_path,
                self._parity(
                    entries_total_compacted=19,
                    present_in_compacted_in_window=19,
                    missing_in_compacted_in_window=1,
                    incident_missing_in_compacted=1,
                    raw_window_coverage_pct=95.0,
                    incident_coverage_pct=50.0,
                    checks={
                        "window_nonempty_ok": True,
                        "raw_window_malformed_ok": True,
                        "compacted_malformed_ok": True,
                        "latest_present_ok": False,
                        "incident_parity_ok": False,
                        "failed_parity_ok": False,
                        "degraded_parity_ok": False,
                        "strict_rows_parity_ok": False,
                        "malformed_parity_ok": True,
                    },
                    strict_fail_reasons=[
                        "latest_raw_missing_in_compacted",
                        "incident_missing_in_compacted",
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
            strict_reasons = list(digest.get("strict_fail_reasons") or [])
            self.assertIn("latest_raw_missing_in_compacted", strict_reasons)
            self.assertIn("incident_missing_in_compacted", strict_reasons)


if __name__ == "__main__":
    unittest.main()
