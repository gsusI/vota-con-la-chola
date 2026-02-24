from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_concern_pack_outcomes_heartbeat_compaction import main


class TestCitizenConcernPackOutcomesHeartbeatCompaction(unittest.TestCase):
    def _hb(
        self,
        minute: int,
        *,
        status: str = "ok",
        strict_fail_count: int = 0,
        contract_complete: bool = True,
        followthrough_ok: bool = True,
        unknown_share_ok: bool = True,
    ) -> dict[str, object]:
        mm = f"{minute:02d}"
        strict_reasons = ["threshold_exceeded"] if strict_fail_count > 0 else []
        return {
            "run_at": f"2026-02-23T14:{mm}:00+00:00",
            "heartbeat_id": f"hb-{mm}",
            "status": status,
            "strict_fail_count": strict_fail_count,
            "strict_fail_reasons": strict_reasons,
            "contract_complete": contract_complete,
            "weak_pack_followthrough_rate_meets_minimum": followthrough_ok,
            "unknown_pack_select_share_within_threshold": unknown_share_ok,
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        lines = [json.dumps(r) for r in rows]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_compaction_preserves_incidents_and_threshold_violations(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_path = td_path / "heartbeat.jsonl"
            compacted_path = td_path / "heartbeat.compacted.jsonl"
            out_path = td_path / "report.json"

            rows = [self._hb(i) for i in range(16)]
            rows[3] = self._hb(
                3,
                status="failed",
                strict_fail_count=1,
                contract_complete=False,
                followthrough_ok=False,
                unknown_share_ok=False,
            )
            rows[9] = self._hb(
                9,
                status="degraded",
                contract_complete=False,
                followthrough_ok=True,
                unknown_share_ok=False,
            )
            rows[12] = self._hb(
                12,
                status="ok",
                contract_complete=True,
                followthrough_ok=False,
                unknown_share_ok=True,
            )
            rows[13] = self._hb(
                13,
                status="ok",
                contract_complete=True,
                followthrough_ok=True,
                unknown_share_ok=True,
            )
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
            self.assertEqual(int(report["incidents_total"]), 3)
            self.assertEqual(int(report["incidents_dropped"]), 0)
            self.assertEqual(int(report["failed_total"]), 1)
            self.assertEqual(int(report["failed_dropped"]), 0)
            self.assertEqual(int(report["degraded_total"]), 1)
            self.assertEqual(int(report["degraded_dropped"]), 0)
            self.assertEqual(int(report["contract_incomplete_total"]), 2)
            self.assertEqual(int(report["contract_incomplete_dropped"]), 0)
            self.assertEqual(int(report["weak_pack_followthrough_violations_total"]), 2)
            self.assertEqual(int(report["weak_pack_followthrough_violations_dropped"]), 0)
            self.assertEqual(int(report["unknown_pack_select_share_violations_total"]), 2)
            self.assertEqual(int(report["unknown_pack_select_share_violations_dropped"]), 0)
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


if __name__ == "__main__":
    unittest.main()
