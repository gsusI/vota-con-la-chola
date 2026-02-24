from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_coherence_drilldown_outcomes_heartbeat_window import main



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
    replay_success_ok: bool,
    contract_click_ok: bool,
    replay_failure_ok: bool,
) -> dict:
    run_at = f"2026-02-23T17:{idx:02d}:00+00:00"
    return {
        "run_at": run_at,
        "heartbeat_id": f"{run_at}|{status}|{idx}",
        "status": status,
        "digest_path": "docs/etl/sprints/AI-OPS-99/evidence/citizen_coherence_drilldown_outcomes_latest.json",
        "digest_generated_at": run_at,
        "drilldown_click_events_total": 10,
        "replay_attempt_events_total": 10,
        "replay_success_events_total": 9,
        "replay_failure_events_total": 1,
        "contract_complete_click_events_total": 9,
        "replay_success_rate": 0.9,
        "replay_failure_rate": 0.1,
        "contract_complete_click_rate": 0.9,
        "min_drilldown_click_events": 8,
        "min_replay_attempt_events": 8,
        "min_replay_success_rate": 0.85,
        "min_contract_complete_click_rate": 0.9,
        "max_replay_failure_rate": 0.15,
        "replay_success_rate_meets_minimum": replay_success_ok,
        "contract_complete_click_rate_meets_minimum": contract_click_ok,
        "replay_failure_rate_within_threshold": replay_failure_ok,
        "telemetry_available": True,
        "contract_complete": contract_complete,
        "degraded_reasons": [] if status != "degraded" else ["contract_complete_click_rate_below_minimum"],
        "failure_reasons": [] if status != "failed" else ["replay_success_rate_below_threshold"],
        "strict_fail_count": 0 if status != "failed" else 1,
        "strict_fail_reasons": [] if status != "failed" else ["replay_success_rate_below_threshold"],
    }


class TestReportCitizenCoherenceDrilldownOutcomesHeartbeatWindow(unittest.TestCase):
    def test_main_passes_strict_with_healthy_window(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(
                        idx=1,
                        status="ok",
                        contract_complete=True,
                        replay_success_ok=True,
                        contract_click_ok=True,
                        replay_failure_ok=True,
                    ),
                    _heartbeat_entry(
                        idx=2,
                        status="ok",
                        contract_complete=True,
                        replay_success_ok=True,
                        contract_click_ok=True,
                        replay_failure_ok=True,
                    ),
                    _heartbeat_entry(
                        idx=3,
                        status="ok",
                        contract_complete=True,
                        replay_success_ok=True,
                        contract_click_ok=True,
                        replay_failure_ok=True,
                    ),
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
                    "--max-replay-success-rate-violations",
                    "0",
                    "--max-replay-success-rate-violation-rate-pct",
                    "0",
                    "--max-contract-click-rate-violations",
                    "0",
                    "--max-contract-click-rate-violation-rate-pct",
                    "0",
                    "--max-replay-failure-rate-violations",
                    "0",
                    "--max-replay-failure-rate-violation-rate-pct",
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

    def test_main_fails_strict_when_latest_has_threshold_violations(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_fail.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(
                        idx=1,
                        status="ok",
                        contract_complete=True,
                        replay_success_ok=True,
                        contract_click_ok=True,
                        replay_failure_ok=True,
                    ),
                    _heartbeat_entry(
                        idx=2,
                        status="degraded",
                        contract_complete=False,
                        replay_success_ok=False,
                        contract_click_ok=False,
                        replay_failure_ok=False,
                    ),
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
                    "--max-replay-success-rate-violations",
                    "0",
                    "--max-replay-success-rate-violation-rate-pct",
                    "0",
                    "--max-contract-click-rate-violations",
                    "0",
                    "--max-contract-click-rate-violation-rate-pct",
                    "0",
                    "--max-replay-failure-rate-violations",
                    "0",
                    "--max-replay-failure-rate-violation-rate-pct",
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
            self.assertEqual(int(report["replay_success_rate_violations_in_window"]), 1)
            self.assertEqual(int(report["contract_click_rate_violations_in_window"]), 1)
            self.assertEqual(int(report["replay_failure_rate_violations_in_window"]), 1)
            self.assertIn("max_contract_incomplete_exceeded", report["strict_fail_reasons"])
            self.assertIn("max_replay_success_rate_violations_exceeded", report["strict_fail_reasons"])
            self.assertIn("max_contract_click_rate_violations_exceeded", report["strict_fail_reasons"])
            self.assertIn("max_replay_failure_rate_violations_exceeded", report["strict_fail_reasons"])
            self.assertIn("latest_contract_incomplete", report["strict_fail_reasons"])
            self.assertIn("latest_threshold_violation", report["strict_fail_reasons"])

    def test_main_rejects_invalid_window_size(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(
                        idx=1,
                        status="ok",
                        contract_complete=True,
                        replay_success_ok=True,
                        contract_click_ok=True,
                        replay_failure_ok=True,
                    ),
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
