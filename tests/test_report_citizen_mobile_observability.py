from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_mobile_observability import main


class TestReportCitizenMobileObservability(unittest.TestCase):
    def _write_events(self, path: Path, values_ms: list[float]) -> None:
        lines = []
        for i, value_ms in enumerate(values_ms):
            lines.append(
                json.dumps(
                    {
                        "event": "input_to_render_ms",
                        "value_ms": float(value_ms),
                        "source": "topic_search_input" if i % 2 else "stance_filter_change",
                        "ts": f"2026-02-23T10:{i:02d}:00Z",
                    }
                )
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_main_passes_with_events_under_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            events_path = td_path / "events.jsonl"
            out_path = td_path / "obs.json"
            self._write_events(
                events_path,
                [
                    72,
                    80,
                    88,
                    94,
                    102,
                    110,
                    120,
                    130,
                    138,
                    145,
                    152,
                    164,
                    176,
                    188,
                    205,
                    222,
                    248,
                    280,
                    320,
                    360,
                ],
            )

            rc = main(
                [
                    "--telemetry-events-jsonl",
                    str(events_path),
                    "--min-samples",
                    "20",
                    "--max-input-to-render-p50-ms",
                    "200",
                    "--max-input-to-render-p90-ms",
                    "330",
                    "--strict",
                    "--strict-require-complete",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 0)

            got = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "ok")
            self.assertEqual(int(got["telemetry"]["sample_count"]), 20)
            self.assertTrue(got["checks"]["sample_count_meets_minimum"])
            self.assertTrue(got["checks"]["input_to_render_p50_within_threshold"])
            self.assertTrue(got["checks"]["input_to_render_p90_within_threshold"])

    def test_main_degraded_without_telemetry_fails_with_strict_complete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            summary_path = td_path / "summary.json"
            out_path = td_path / "obs.json"
            summary_path.write_text("{}\n", encoding="utf-8")

            rc = main(
                [
                    "--telemetry-json",
                    str(summary_path),
                    "--strict",
                    "--strict-require-complete",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 4)

            got = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "degraded")
            self.assertIn("telemetry_missing", got["degraded_reasons"])
            self.assertIn("input_to_render_p50_ms", got["missing_metrics"])
            self.assertIn("input_to_render_p90_ms", got["missing_metrics"])

    def test_main_strict_fails_when_percentiles_above_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            events_path = td_path / "events.jsonl"
            out_path = td_path / "obs.json"
            self._write_events(
                events_path,
                [
                    80,
                    90,
                    100,
                    110,
                    120,
                    130,
                    140,
                    150,
                    160,
                    170,
                    180,
                    190,
                    220,
                    260,
                    300,
                    360,
                    420,
                    500,
                    620,
                    740,
                ],
            )

            rc = main(
                [
                    "--telemetry-events-jsonl",
                    str(events_path),
                    "--min-samples",
                    "20",
                    "--max-input-to-render-p50-ms",
                    "150",
                    "--max-input-to-render-p90-ms",
                    "450",
                    "--strict",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 4)

            got = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "failed")
            self.assertIn("input_to_render_p50_above_threshold", got["failure_reasons"])


if __name__ == "__main__":
    unittest.main()
