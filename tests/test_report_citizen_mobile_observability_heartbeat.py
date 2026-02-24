from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_mobile_observability_heartbeat import main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _observability_fixture(*, status: str = "ok") -> dict:
    is_ok = status == "ok"
    is_failed = status == "failed"
    sample_count = 30 if is_ok else (10 if status == "degraded" else 30)
    p90 = 420.0 if not is_failed else 620.0
    failure_reasons = ["input_to_render_p90_above_threshold"] if is_failed else []
    degraded_reasons = ["sample_count_below_minimum"] if status == "degraded" else []
    return {
        "generated_at": "2026-02-23T13:20:00+00:00",
        "status": status,
        "telemetry": {
            "sample_count": sample_count,
            "events_total": sample_count,
            "parse_errors": 0,
            "source_breakdown": {"topic_search_input": sample_count},
        },
        "metrics": {
            "input_to_render_p50_ms": 150.0,
            "input_to_render_p90_ms": p90,
            "input_to_render_p95_ms": 440.0 if not is_failed else 680.0,
        },
        "thresholds": {
            "min_samples": 20,
            "max_input_to_render_p50_ms": 180.0,
            "max_input_to_render_p90_ms": 450.0,
        },
        "checks": {
            "telemetry_available": sample_count > 0,
            "sample_count_meets_minimum": sample_count >= 20,
            "input_to_render_p50_within_threshold": True,
            "input_to_render_p90_within_threshold": not is_failed,
            "contract_complete": is_ok,
        },
        "missing_metrics": [],
        "degraded_reasons": degraded_reasons,
        "failure_reasons": failure_reasons,
    }


class TestReportCitizenMobileObservabilityHeartbeat(unittest.TestCase):
    def test_main_appends_and_dedupes_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            observability = td_path / "observability_ok.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out1 = td_path / "report1.json"
            out2 = td_path / "report2.json"
            _write_json(observability, _observability_fixture(status="ok"))

            rc1 = main(
                [
                    "--observability-json",
                    str(observability),
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--strict",
                    "--out",
                    str(out1),
                ]
            )
            self.assertEqual(rc1, 0)
            report1 = _read_json(out1)
            self.assertEqual(report1["status"], "ok")
            self.assertTrue(report1["appended"])
            self.assertFalse(report1["duplicate_detected"])
            self.assertEqual(int(report1["history_size_after"]), 1)

            rc2 = main(
                [
                    "--observability-json",
                    str(observability),
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--strict",
                    "--out",
                    str(out2),
                ]
            )
            self.assertEqual(rc2, 0)
            report2 = _read_json(out2)
            self.assertEqual(report2["status"], "ok")
            self.assertFalse(report2["appended"])
            self.assertTrue(report2["duplicate_detected"])
            self.assertEqual(int(report2["history_size_after"]), 1)

            lines = [line for line in heartbeat_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["status"], "ok")
            self.assertTrue(entry["input_to_render_p90_within_threshold"])

    def test_main_strict_fails_when_observability_status_failed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            observability = td_path / "observability_failed.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "report.json"
            _write_json(observability, _observability_fixture(status="failed"))

            rc = main(
                [
                    "--observability-json",
                    str(observability),
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            report = _read_json(out)
            self.assertEqual(report["status"], "failed")
            self.assertIn("heartbeat_status_failed", report["strict_fail_reasons"])
            self.assertTrue(report["appended"])
            self.assertEqual(int(report["history_size_after"]), 1)

    def test_main_degraded_passes_strict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            observability = td_path / "observability_degraded.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "report.json"
            _write_json(observability, _observability_fixture(status="degraded"))

            rc = main(
                [
                    "--observability-json",
                    str(observability),
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 0)

            report = _read_json(out)
            self.assertEqual(report["status"], "degraded")
            self.assertEqual(report["strict_fail_reasons"], [])
            self.assertTrue(report["appended"])


if __name__ == "__main__":
    unittest.main()
