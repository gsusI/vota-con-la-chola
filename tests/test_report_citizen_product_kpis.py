from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_product_kpis import main


class TestReportCitizenProductKpis(unittest.TestCase):
    def _write_snapshot(self, path: Path, *, unknown_pct: float | None, include_quality: bool = True) -> None:
        payload: dict[str, object] = {
            "meta": {},
            "party_topic_positions": [
                {"stance": "support"},
                {"stance": "no_signal"},
                {"stance": "unclear"},
            ],
        }
        if include_quality:
            quality: dict[str, object] = {}
            if unknown_pct is not None:
                quality["unknown_pct"] = float(unknown_pct)
            payload["meta"] = {"quality": quality}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_main_passes_with_event_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            snapshot_path = td_path / "citizen.json"
            events_path = td_path / "events.jsonl"
            out_path = td_path / "kpis.json"

            self._write_snapshot(snapshot_path, unknown_pct=0.25)
            events_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "session_id": "s1",
                                "event": "view_loaded",
                                "timestamp": "2026-02-23T10:00:00Z",
                            }
                        ),
                        json.dumps(
                            {
                                "session_id": "s1",
                                "event": "first_answer",
                                "timestamp": "2026-02-23T10:00:20Z",
                            }
                        ),
                        json.dumps(
                            {
                                "session_id": "s1",
                                "event": "drilldown_click",
                                "timestamp": "2026-02-23T10:00:30Z",
                            }
                        ),
                        json.dumps(
                            {
                                "session_id": "s2",
                                "event": "view_loaded",
                                "timestamp": "2026-02-23T11:00:00Z",
                            }
                        ),
                        json.dumps(
                            {
                                "session_id": "s2",
                                "event": "first_answer",
                                "elapsed_ms": 40000,
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            rc = main(
                [
                    "--snapshot",
                    str(snapshot_path),
                    "--telemetry-events-jsonl",
                    str(events_path),
                    "--max-unknown-rate",
                    "0.3",
                    "--max-time-to-first-answer-seconds",
                    "40",
                    "--min-drilldown-click-rate",
                    "0.5",
                    "--strict",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 0)

            got = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "ok")
            self.assertAlmostEqual(float(got["metrics"]["unknown_rate"]), 0.25, places=6)
            self.assertAlmostEqual(float(got["metrics"]["time_to_first_answer_seconds"]), 30.0, places=6)
            self.assertAlmostEqual(float(got["metrics"]["drilldown_click_rate"]), 0.5, places=6)
            self.assertEqual(int(got["telemetry"]["sessions_total"]), 2)
            self.assertEqual(int(got["telemetry"]["sessions_with_first_answer"]), 2)
            self.assertEqual(int(got["telemetry"]["sessions_with_drilldown_click"]), 1)

    def test_main_degraded_without_telemetry_and_strict_complete_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            snapshot_path = td_path / "citizen.json"
            out_path = td_path / "kpis.json"

            self._write_snapshot(snapshot_path, unknown_pct=0.2)

            rc_degraded_ok = main(
                [
                    "--snapshot",
                    str(snapshot_path),
                    "--strict",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc_degraded_ok, 0)
            got = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "degraded")
            self.assertIn("time_to_first_answer_seconds", got["missing_metrics"])
            self.assertIn("drilldown_click_rate", got["missing_metrics"])

            rc_degraded_fail = main(
                [
                    "--snapshot",
                    str(snapshot_path),
                    "--strict",
                    "--strict-require-complete",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc_degraded_fail, 4)

    def test_main_strict_fails_when_unknown_rate_above_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            snapshot_path = td_path / "citizen.json"
            out_path = td_path / "kpis.json"

            # Omit meta.quality.unknown_pct to exercise fallback from party_topic_positions.
            self._write_snapshot(snapshot_path, unknown_pct=None, include_quality=False)

            rc = main(
                [
                    "--snapshot",
                    str(snapshot_path),
                    "--max-unknown-rate",
                    "0.5",
                    "--strict",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 4)
            got = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "failed")
            self.assertIn("unknown_rate_above_threshold", got["failure_reasons"])
            self.assertEqual(got["metrics"]["unknown_rate_source"], "party_topic_positions.stance")


if __name__ == "__main__":
    unittest.main()
