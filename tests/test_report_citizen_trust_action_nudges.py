from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_trust_action_nudges import main


class TestReportCitizenTrustActionNudges(unittest.TestCase):
    def _fixture_path(self, name: str) -> Path:
        return Path(__file__).resolve().parent / "fixtures" / name

    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
        path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")

    def test_main_passes_fixture_with_strict_complete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.json"
            rc = main(
                [
                    "--events-jsonl",
                    str(self._fixture_path("citizen_trust_action_nudge_events_sample.jsonl")),
                    "--strict",
                    "--strict-require-complete",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 0)

            got = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "ok")
            self.assertTrue(bool(got["checks"]["contract_complete"]))
            self.assertEqual(int(got["metrics"]["nudge_shown_sessions_total"]), 8)
            self.assertEqual(int(got["metrics"]["nudge_clicked_sessions_total"]), 5)
            self.assertAlmostEqual(float(got["metrics"]["nudge_clickthrough_session_rate"]), 0.625, places=6)

    def test_main_strict_fails_when_clickthrough_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            events = td_path / "events.jsonl"
            out = td_path / "out.json"

            rows = []
            for idx in range(1, 7):
                rows.append(
                    {
                        "event_type": "trust_action_nudge_shown",
                        "session_id": f"s{idx}",
                        "source_view": "topic",
                        "nudge_id": f"topic:vivienda:10{idx}:{idx}",
                    }
                )
            rows.append(
                {
                    "event_type": "trust_action_nudge_clicked",
                    "session_id": "s1",
                    "source_view": "topic",
                    "nudge_id": "topic:vivienda:101:1",
                }
            )
            for idx in range(1, 3):
                rows.append(
                    {
                        "event_type": "trust_action_nudge_shown",
                        "session_id": f"x{idx}",
                        "source_view": "concern",
                        "nudge_id": f"concern:vivienda:none:{idx}",
                    }
                )

            self._write_jsonl(events, rows)

            rc = main(
                [
                    "--events-jsonl",
                    str(events),
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            got = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "failed")
            self.assertIn("nudge_clickthrough_below_threshold", set(got.get("failure_reasons") or []))

    def test_main_degraded_without_events_fails_with_strict_complete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            events = td_path / "events.jsonl"
            out = td_path / "out.json"
            events.write_text("", encoding="utf-8")

            rc = main(
                [
                    "--events-jsonl",
                    str(events),
                    "--strict",
                    "--strict-require-complete",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            got = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "degraded")
            self.assertIn("telemetry_missing", set(got.get("degraded_reasons") or []))
            self.assertFalse(bool(got["checks"]["contract_complete"]))


if __name__ == "__main__":
    unittest.main()
