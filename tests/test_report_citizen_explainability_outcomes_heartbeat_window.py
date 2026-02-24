from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_explainability_outcomes_heartbeat_window import main


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_text(payload, encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _heartbeat_entry(
    *,
    idx: int,
    status: str,
    contract_complete: bool,
    adoption_sessions_total: int = 6,
    complete_adoption_sessions_total: int = 4,
    adoption_completeness_rate: float = 0.666667,
) -> dict:
    run_at = f"2026-02-23T15:{idx:02d}:00+00:00"
    return {
        "run_at": run_at,
        "heartbeat_id": f"{run_at}|{status}|{idx}",
        "status": status,
        "digest_path": "docs/etl/sprints/AI-OPS-92/evidence/citizen_explainability_outcomes_latest.json",
        "digest_generated_at": run_at,
        "glossary_interaction_events_total": 9,
        "help_copy_interaction_events_total": 5,
        "adoption_sessions_total": adoption_sessions_total,
        "complete_adoption_sessions_total": complete_adoption_sessions_total,
        "adoption_completeness_rate": adoption_completeness_rate,
        "min_glossary_interaction_events": 8,
        "min_help_copy_interaction_events": 5,
        "min_adoption_sessions": 5,
        "min_adoption_completeness_rate": 0.6,
        "telemetry_available": True,
        "contract_complete": contract_complete,
        "degraded_reasons": [] if status != "degraded" else ["glossary_interactions_below_minimum"],
        "failure_reasons": [] if status != "failed" else ["adoption_completeness_below_threshold"],
        "strict_fail_count": 0 if status != "failed" else 1,
        "strict_fail_reasons": [] if status != "failed" else ["adoption_completeness_below_threshold"],
    }


class TestReportCitizenExplainabilityOutcomesHeartbeatWindow(unittest.TestCase):
    def test_main_passes_strict_with_complete_window(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(idx=1, status="ok", contract_complete=True),
                    _heartbeat_entry(idx=2, status="ok", contract_complete=True),
                    _heartbeat_entry(idx=3, status="ok", contract_complete=True),
                ],
            )

            rc = main(
                [
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--last",
                    "3",
                    "--max-failed",
                    "0",
                    "--max-failed-rate-pct",
                    "0",
                    "--max-degraded",
                    "0",
                    "--max-degraded-rate-pct",
                    "0",
                    "--max-contract-incomplete",
                    "0",
                    "--max-contract-incomplete-rate-pct",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 0)

            report = _read_json(out)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(int(report["failed_in_window"]), 0)
            self.assertEqual(int(report["degraded_in_window"]), 0)
            self.assertEqual(int(report["contract_incomplete_in_window"]), 0)
            self.assertEqual(report["strict_fail_reasons"], [])

    def test_main_fails_strict_when_latest_contract_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_fail.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(idx=1, status="ok", contract_complete=True),
                    _heartbeat_entry(idx=2, status="degraded", contract_complete=False),
                ],
            )

            rc = main(
                [
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--last",
                    "2",
                    "--max-failed",
                    "0",
                    "--max-failed-rate-pct",
                    "0",
                    "--max-degraded",
                    "0",
                    "--max-degraded-rate-pct",
                    "0",
                    "--max-contract-incomplete",
                    "0",
                    "--max-contract-incomplete-rate-pct",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            report = _read_json(out)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(int(report["contract_incomplete_in_window"]), 1)
            self.assertIn("max_contract_incomplete_exceeded", report["strict_fail_reasons"])
            self.assertIn("latest_contract_incomplete", report["strict_fail_reasons"])

    def test_main_rejects_invalid_window_size(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(idx=1, status="ok", contract_complete=True),
                ],
            )

            rc = main(
                [
                    "--heartbeat-jsonl",
                    str(heartbeat_jsonl),
                    "--last",
                    "0",
                ]
            )
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
