from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_product_kpis_heartbeat_window import main


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
    unknown_ok: bool,
    tfa_ok: bool,
    drill_ok: bool,
) -> dict:
    run_at = f"2026-02-23T16:{idx:02d}:00+00:00"
    return {
        "run_at": run_at,
        "heartbeat_id": f"{run_at}|{status}|{idx}",
        "status": status,
        "digest_path": "docs/etl/sprints/AI-OPS-98/evidence/citizen_product_kpis_latest.json",
        "digest_generated_at": run_at,
        "unknown_rate": 0.25,
        "time_to_first_answer_seconds": 30.0,
        "drilldown_click_rate": 0.5,
        "max_unknown_rate": 0.45,
        "max_time_to_first_answer_seconds": 120.0,
        "min_drilldown_click_rate": 0.2,
        "unknown_rate_within_threshold": unknown_ok,
        "time_to_first_answer_within_threshold": tfa_ok,
        "drilldown_click_rate_within_threshold": drill_ok,
        "telemetry_available": True,
        "contract_complete": contract_complete,
        "missing_metrics": [] if contract_complete else ["time_to_first_answer_seconds", "drilldown_click_rate"],
        "failure_reasons": [] if status != "failed" else ["time_to_first_answer_above_threshold"],
        "strict_fail_count": 0 if status != "failed" else 1,
        "strict_fail_reasons": [] if status != "failed" else ["time_to_first_answer_above_threshold"],
    }


class TestReportCitizenProductKpisHeartbeatWindow(unittest.TestCase):
    def test_main_passes_strict_with_healthy_window(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(idx=1, status="ok", contract_complete=True, unknown_ok=True, tfa_ok=True, drill_ok=True),
                    _heartbeat_entry(idx=2, status="ok", contract_complete=True, unknown_ok=True, tfa_ok=True, drill_ok=True),
                    _heartbeat_entry(idx=3, status="ok", contract_complete=True, unknown_ok=True, tfa_ok=True, drill_ok=True),
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
                    "--max-unknown-rate-violations",
                    "0",
                    "--max-unknown-rate-violation-rate-pct",
                    "0",
                    "--max-tfa-violations",
                    "0",
                    "--max-tfa-violation-rate-pct",
                    "0",
                    "--max-drilldown-violations",
                    "0",
                    "--max-drilldown-violation-rate-pct",
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
                    _heartbeat_entry(idx=1, status="ok", contract_complete=True, unknown_ok=True, tfa_ok=True, drill_ok=True),
                    _heartbeat_entry(idx=2, status="degraded", contract_complete=False, unknown_ok=False, tfa_ok=False, drill_ok=False),
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
                    "--max-unknown-rate-violations",
                    "0",
                    "--max-unknown-rate-violation-rate-pct",
                    "0",
                    "--max-tfa-violations",
                    "0",
                    "--max-tfa-violation-rate-pct",
                    "0",
                    "--max-drilldown-violations",
                    "0",
                    "--max-drilldown-violation-rate-pct",
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
            self.assertEqual(int(report["unknown_rate_violations_in_window"]), 1)
            self.assertEqual(int(report["tfa_violations_in_window"]), 1)
            self.assertEqual(int(report["drilldown_violations_in_window"]), 1)
            self.assertIn("max_contract_incomplete_exceeded", report["strict_fail_reasons"])
            self.assertIn("max_unknown_rate_violations_exceeded", report["strict_fail_reasons"])
            self.assertIn("max_tfa_violations_exceeded", report["strict_fail_reasons"])
            self.assertIn("max_drilldown_violations_exceeded", report["strict_fail_reasons"])
            self.assertIn("latest_contract_incomplete", report["strict_fail_reasons"])
            self.assertIn("latest_threshold_violation", report["strict_fail_reasons"])

    def test_main_rejects_invalid_window_size(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(idx=1, status="ok", contract_complete=True, unknown_ok=True, tfa_ok=True, drill_ok=True),
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
