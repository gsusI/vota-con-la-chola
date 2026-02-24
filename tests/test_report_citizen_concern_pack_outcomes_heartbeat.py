from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_concern_pack_outcomes_heartbeat import main


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
        "generated_at": "2026-02-23T17:00:00+00:00",
        "status": status,
        "paths": {
            "events_jsonl": "tests/fixtures/citizen_concern_pack_outcome_events_sample.jsonl",
            "concern_pack_quality_json": "tests/fixtures/citizen_concern_pack_quality_sample.json",
        },
        "telemetry": {
            "events_total": 40,
            "recognized_events_total": 40 if not is_degraded else 0,
            "ignored_events_total": 0,
            "parse_errors": 0,
            "sessions_total": 16,
            "selected_pack_ids_total": 3,
        },
        "metrics": {
            "pack_selected_events_total": 24,
            "topic_open_with_pack_events_total": 14,
            "weak_pack_selected_events_total": 7,
            "weak_pack_followthrough_events_total": 5 if not is_failed else 2,
            "unknown_pack_selected_events_total": 2 if not is_failed else 6,
            "pack_selected_sessions_total": 12,
            "weak_pack_selected_sessions_total": 7,
            "weak_pack_followthrough_sessions_total": 5 if not is_failed else 2,
            "weak_pack_followthrough_rate": 0.714286 if not is_failed else 0.285714,
            "unknown_pack_select_share": 0.083333 if not is_failed else 0.25,
        },
        "thresholds": {
            "min_pack_select_events": 20,
            "min_weak_pack_select_sessions": 5,
            "min_weak_pack_followthrough_rate": 0.30,
            "max_unknown_pack_select_share": 0.20,
        },
        "checks": {
            "telemetry_available": not is_degraded,
            "pack_select_events_meet_minimum": True,
            "weak_pack_select_sessions_meet_minimum": True,
            "weak_pack_followthrough_rate_meets_minimum": None if is_degraded else (False if is_failed else True),
            "unknown_pack_select_share_within_threshold": None if is_degraded else (False if is_failed else True),
            "contract_complete": is_ok,
        },
        "degraded_reasons": ["telemetry_missing"] if is_degraded else [],
        "failure_reasons": (
            ["weak_pack_followthrough_below_threshold", "unknown_pack_select_share_above_threshold"] if is_failed else []
        ),
        "by_pack": [
            {
                "pack_id": "economia",
                "pack_selected_events": 10,
                "topic_open_with_pack_events": 8,
                "weak_pack_selected_events": 0,
                "weak_pack_followthrough_events": 0,
            }
        ],
    }


class TestReportCitizenConcernPackOutcomesHeartbeat(unittest.TestCase):
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
