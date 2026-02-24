from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_explainability_outcomes_heartbeat import main


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
        "generated_at": "2026-02-23T15:40:00+00:00",
        "status": status,
        "paths": {
            "events_jsonl": "tests/fixtures/citizen_explainability_outcome_events_sample.jsonl"
        },
        "telemetry": {
            "events_total": 14,
            "recognized_events_total": 14,
            "ignored_events_total": 0,
            "parse_errors": 0,
            "sessions_total": 6,
        },
        "metrics": {
            "glossary_opened_events_total": 4,
            "glossary_term_interaction_events_total": 5,
            "glossary_interaction_events_total": 9 if not is_degraded else 2,
            "help_copy_interaction_events_total": 5 if not is_degraded else 1,
            "adoption_sessions_total": 6,
            "complete_adoption_sessions_total": 4,
            "adoption_completeness_rate": 0.666667 if not is_failed else 0.4,
            "interacted_terms_total": 4,
        },
        "thresholds": {
            "min_glossary_interaction_events": 8,
            "min_help_copy_interaction_events": 5,
            "min_adoption_sessions": 5,
            "min_adoption_completeness_rate": 0.60,
        },
        "checks": {
            "telemetry_available": True,
            "glossary_interactions_meet_minimum": is_ok,
            "help_copy_interactions_meet_minimum": is_ok,
            "adoption_sessions_meet_minimum": True,
            "adoption_completeness_meets_minimum": False if is_failed else True,
            "contract_complete": is_ok,
        },
        "degraded_reasons": [
            "glossary_interactions_below_minimum",
            "help_copy_interactions_below_minimum",
        ]
        if is_degraded
        else [],
        "failure_reasons": ["adoption_completeness_below_threshold"] if is_failed else [],
    }


class TestReportCitizenExplainabilityOutcomesHeartbeat(unittest.TestCase):
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
