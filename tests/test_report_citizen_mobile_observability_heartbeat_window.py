from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_mobile_observability_heartbeat_window import main


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_text(payload, encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _heartbeat_entry(
    *,
    idx: int,
    status: str,
    p90_ms: float,
    max_p90_ms: float = 450.0,
    p90_within: bool | None = None,
) -> dict:
    run_at = f"2026-02-23T13:{idx:02d}:00+00:00"
    within = (p90_ms <= max_p90_ms) if p90_within is None else bool(p90_within)
    return {
        "run_at": run_at,
        "heartbeat_id": f"{run_at}|{status}|{idx}",
        "status": status,
        "sample_count": 30,
        "min_samples": 20,
        "input_to_render_p50_ms": 150.0,
        "input_to_render_p90_ms": p90_ms,
        "input_to_render_p95_ms": max(p90_ms, 430.0),
        "max_input_to_render_p90_ms": max_p90_ms,
        "input_to_render_p90_within_threshold": within,
        "input_to_render_p90_margin_ms": max_p90_ms - p90_ms,
        "contract_complete": status == "ok",
        "telemetry_available": True,
        "missing_metrics": [],
        "degraded_reasons": [],
        "failure_reasons": [] if status != "failed" else ["input_to_render_p90_above_threshold"],
        "strict_fail_count": 0 if status != "failed" else 1,
        "strict_fail_reasons": [] if status != "failed" else ["input_to_render_p90_above_threshold"],
    }


class TestReportCitizenMobileObservabilityHeartbeatWindow(unittest.TestCase):
    def test_main_passes_strict_with_stable_window(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(idx=1, status="ok", p90_ms=390.0),
                    _heartbeat_entry(idx=2, status="ok", p90_ms=402.0),
                    _heartbeat_entry(idx=3, status="ok", p90_ms=418.0),
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
                    "--max-p90-threshold-violations",
                    "0",
                    "--max-p90-threshold-violation-rate-pct",
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
            self.assertEqual(int(report["p90_threshold_violations_in_window"]), 0)
            self.assertEqual(report["strict_fail_reasons"], [])

    def test_main_fails_strict_when_p90_violations_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_fail.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(idx=1, status="ok", p90_ms=410.0),
                    _heartbeat_entry(idx=2, status="failed", p90_ms=620.0, p90_within=False),
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
                    "--max-p90-threshold-violations",
                    "0",
                    "--max-p90-threshold-violation-rate-pct",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            report = _read_json(out)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(int(report["p90_threshold_violations_in_window"]), 1)
            self.assertIn("max_p90_threshold_violations_exceeded", report["strict_fail_reasons"])
            self.assertIn("latest_status_failed", report["strict_fail_reasons"])
            self.assertIn("latest_p90_threshold_violation", report["strict_fail_reasons"])

    def test_main_rejects_invalid_window_size(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            _write_jsonl(heartbeat_jsonl, [_heartbeat_entry(idx=1, status="ok", p90_ms=400.0)])

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
