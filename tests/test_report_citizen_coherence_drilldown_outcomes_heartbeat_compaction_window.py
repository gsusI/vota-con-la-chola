from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_coherence_drilldown_outcomes_heartbeat_compaction_window import main


class TestCitizenCoherenceDrilldownOutcomesHeartbeatCompactionWindow(unittest.TestCase):
    def _hb(
        self,
        minute: int,
        *,
        status: str = "ok",
        strict_fail_count: int = 0,
        contract_complete: bool = True,
        replay_success_ok: bool = True,
        contract_click_ok: bool = True,
        replay_failure_ok: bool = True,
    ) -> dict[str, object]:
        mm = f"{minute:02d}"
        strict_reasons = ["strict_fail"] if strict_fail_count > 0 else []
        return {
            "run_at": f"2026-02-23T15:{mm}:00+00:00",
            "heartbeat_id": f"hb-{mm}",
            "status": status,
            "strict_fail_count": strict_fail_count,
            "strict_fail_reasons": strict_reasons,
            "contract_complete": contract_complete,
            "replay_success_rate_meets_minimum": replay_success_ok,
            "contract_complete_click_rate_meets_minimum": contract_click_ok,
            "replay_failure_rate_within_threshold": replay_failure_ok,
        }

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
                self._hb(0, status="ok"),
                self._hb(
                    1,
                    status="failed",
                    strict_fail_count=1,
                    contract_complete=False,
                    replay_success_ok=False,
                    contract_click_ok=False,
                    replay_failure_ok=False,
                ),
                self._hb(
                    2,
                    status="degraded",
                    contract_complete=False,
                    replay_success_ok=True,
                    contract_click_ok=False,
                    replay_failure_ok=True,
                ),
                self._hb(3, status="ok", replay_success_ok=False),
                self._hb(4, status="ok"),
            ]
            compacted_rows = [
                self._hb(
                    1,
                    status="failed",
                    strict_fail_count=1,
                    contract_complete=False,
                    replay_success_ok=False,
                    contract_click_ok=False,
                    replay_failure_ok=False,
                ),
                self._hb(
                    2,
                    status="degraded",
                    contract_complete=False,
                    replay_success_ok=True,
                    contract_click_ok=False,
                    replay_failure_ok=True,
                ),
                self._hb(3, status="ok", replay_success_ok=False),
                self._hb(4, status="ok"),
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
            self.assertEqual(int(report["replay_success_rate_violations_missing_in_compacted"]), 0)
            self.assertEqual(bool(report["checks"]["latest_present_ok"]), True)
            self.assertEqual(list(report.get("strict_fail_reasons") or []), [])

    def test_compaction_window_strict_fails_when_replay_success_incident_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            raw_path = td_path / "raw.jsonl"
            compacted_path = td_path / "compacted.jsonl"
            out_path = td_path / "report_fail.json"

            raw_rows = [
                self._hb(0, status="ok"),
                self._hb(1, status="ok", replay_success_ok=False),
                self._hb(2, status="ok"),
            ]
            compacted_rows = [
                self._hb(2, status="ok"),
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
            self.assertIn("replay_success_rate_violations_underreported_in_compacted", reasons)

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
