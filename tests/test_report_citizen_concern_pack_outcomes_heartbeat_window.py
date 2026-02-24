from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_concern_pack_outcomes_heartbeat_window import main


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
    weak_followthrough_ok: bool,
    unknown_share_ok: bool,
) -> dict:
    run_at = f"2026-02-23T17:{idx:02d}:00+00:00"
    return {
        "run_at": run_at,
        "heartbeat_id": f"{run_at}|{status}|{idx}",
        "status": status,
        "digest_path": "docs/etl/sprints/AI-OPS-85/evidence/citizen_concern_pack_outcomes_latest.json",
        "digest_generated_at": run_at,
        "pack_selected_events_total": 24,
        "topic_open_with_pack_events_total": 14,
        "weak_pack_selected_events_total": 7,
        "weak_pack_followthrough_events_total": 5,
        "unknown_pack_selected_events_total": 2,
        "pack_selected_sessions_total": 12,
        "weak_pack_selected_sessions_total": 7,
        "weak_pack_followthrough_sessions_total": 5,
        "weak_pack_followthrough_rate": 0.714286,
        "unknown_pack_select_share": 0.083333,
        "min_pack_select_events": 20,
        "min_weak_pack_select_sessions": 5,
        "min_weak_pack_followthrough_rate": 0.3,
        "max_unknown_pack_select_share": 0.2,
        "weak_pack_followthrough_rate_meets_minimum": weak_followthrough_ok,
        "unknown_pack_select_share_within_threshold": unknown_share_ok,
        "telemetry_available": True,
        "contract_complete": contract_complete,
        "degraded_reasons": [] if status != "degraded" else ["telemetry_missing"],
        "failure_reasons": [] if status != "failed" else ["unknown_pack_select_share_above_threshold"],
        "strict_fail_count": 0 if status != "failed" else 1,
        "strict_fail_reasons": [] if status != "failed" else ["unknown_pack_select_share_above_threshold"],
    }


class TestReportCitizenConcernPackOutcomesHeartbeatWindow(unittest.TestCase):
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
                        weak_followthrough_ok=True,
                        unknown_share_ok=True,
                    ),
                    _heartbeat_entry(
                        idx=2,
                        status="ok",
                        contract_complete=True,
                        weak_followthrough_ok=True,
                        unknown_share_ok=True,
                    ),
                    _heartbeat_entry(
                        idx=3,
                        status="ok",
                        contract_complete=True,
                        weak_followthrough_ok=True,
                        unknown_share_ok=True,
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
                    "--max-weak-pack-followthrough-violations",
                    "0",
                    "--max-weak-pack-followthrough-violation-rate-pct",
                    "0",
                    "--max-unknown-pack-select-share-violations",
                    "0",
                    "--max-unknown-pack-select-share-violation-rate-pct",
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
            self.assertEqual(int(report["weak_pack_followthrough_violations_in_window"]), 0)
            self.assertEqual(int(report["unknown_pack_select_share_violations_in_window"]), 0)
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
                        weak_followthrough_ok=True,
                        unknown_share_ok=True,
                    ),
                    _heartbeat_entry(
                        idx=2,
                        status="degraded",
                        contract_complete=False,
                        weak_followthrough_ok=False,
                        unknown_share_ok=False,
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
                    "--max-weak-pack-followthrough-violations",
                    "0",
                    "--max-weak-pack-followthrough-violation-rate-pct",
                    "0",
                    "--max-unknown-pack-select-share-violations",
                    "0",
                    "--max-unknown-pack-select-share-violation-rate-pct",
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
            self.assertEqual(int(report["weak_pack_followthrough_violations_in_window"]), 1)
            self.assertEqual(int(report["unknown_pack_select_share_violations_in_window"]), 1)
            self.assertIn("max_contract_incomplete_exceeded", report["strict_fail_reasons"])
            self.assertIn("max_weak_pack_followthrough_violations_exceeded", report["strict_fail_reasons"])
            self.assertIn("max_unknown_pack_select_share_violations_exceeded", report["strict_fail_reasons"])
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
                        weak_followthrough_ok=True,
                        unknown_share_ok=True,
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
