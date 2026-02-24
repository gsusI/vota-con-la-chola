from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_product_kpis_heartbeat import main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest_fixture(*, status: str = "ok") -> dict:
    is_ok = status == "ok"
    is_degraded = status == "degraded"
    is_failed = status == "failed"

    return {
        "generated_at": "2026-02-23T16:00:00+00:00",
        "metrics": {
            "unknown_rate": 0.25,
            "time_to_first_answer_seconds": 30.0 if not is_degraded else None,
            "drilldown_click_rate": 0.5 if not is_degraded else None,
        },
        "thresholds": {
            "max_unknown_rate": 0.45,
            "max_time_to_first_answer_seconds": 120.0,
            "min_drilldown_click_rate": 0.2,
        },
        "checks": {
            "unknown_rate_within_threshold": True,
            "time_to_first_answer_within_threshold": None if is_degraded else (False if is_failed else True),
            "drilldown_click_rate_within_threshold": None if is_degraded else (False if is_failed else True),
            "telemetry_available": not is_degraded,
            "contract_complete": is_ok,
        },
        "missing_metrics": ["time_to_first_answer_seconds", "drilldown_click_rate"] if is_degraded else [],
        "failure_reasons": ["time_to_first_answer_above_threshold", "drilldown_click_rate_below_threshold"] if is_failed else [],
        "status": status,
    }


class TestReportCitizenProductKpisHeartbeat(unittest.TestCase):
    def test_main_appends_and_dedupes_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            digest = td_path / "digest_ok.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out1 = td_path / "report1.json"
            out2 = td_path / "report2.json"
            _write_json(digest, _digest_fixture(status="ok"))

            rc1 = main(
                [
                    "--digest-json",
                    str(digest),
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
                    "--digest-json",
                    str(digest),
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

    def test_main_strict_fails_when_digest_status_failed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            digest = td_path / "digest_failed.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "report.json"
            _write_json(digest, _digest_fixture(status="failed"))

            rc = main(
                [
                    "--digest-json",
                    str(digest),
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

    def test_main_degraded_passes_strict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            digest = td_path / "digest_degraded.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "report.json"
            _write_json(digest, _digest_fixture(status="degraded"))

            rc = main(
                [
                    "--digest-json",
                    str(digest),
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
