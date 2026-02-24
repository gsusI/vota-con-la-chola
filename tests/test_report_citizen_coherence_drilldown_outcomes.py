from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_coherence_drilldown_outcomes import main


class TestReportCitizenCoherenceDrilldownOutcomes(unittest.TestCase):
    def _fixture_path(self, name: str) -> Path:
        return Path(__file__).resolve().parent / "fixtures" / name

    def test_main_passes_fixture_with_strict_complete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.json"
            rc = main(
                [
                    "--events-jsonl",
                    str(self._fixture_path("citizen_coherence_drilldown_events_sample.jsonl")),
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
            self.assertEqual(int(got["metrics"]["drilldown_click_events_total"]), 10)
            self.assertEqual(int(got["metrics"]["replay_attempt_events_total"]), 10)
            self.assertAlmostEqual(float(got["metrics"]["replay_success_rate"]), 0.9, places=6)
            self.assertAlmostEqual(float(got["metrics"]["contract_complete_click_rate"]), 0.9, places=6)

    def test_main_strict_fails_when_contract_click_rate_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.json"
            rc = main(
                [
                    "--events-jsonl",
                    str(self._fixture_path("citizen_coherence_drilldown_events_sample.jsonl")),
                    "--min-contract-complete-click-rate",
                    "0.95",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            got = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "failed")
            self.assertIn("contract_complete_click_rate_below_threshold", set(got.get("failure_reasons") or []))

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
