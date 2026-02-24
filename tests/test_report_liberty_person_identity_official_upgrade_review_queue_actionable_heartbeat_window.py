from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat_window import main


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_text(payload, encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _heartbeat_entry(*, idx: int, status: str, actionable_rows_total: int) -> dict:
    run_at = f"2026-02-23T23:{idx:02d}:00+00:00"
    actionable_queue_empty = actionable_rows_total == 0
    return {
        "run_at": run_at,
        "heartbeat_id": f"{status}|{idx}|{actionable_rows_total}",
        "summary_path": "docs/etl/sprints/AI-OPS-153/evidence/liberty_person_identity_official_upgrade_review_queue_actionable_latest.json",
        "status": status,
        "rows_total": actionable_rows_total,
        "rows_exported_total": actionable_rows_total,
        "actionable_rows_total": actionable_rows_total,
        "likely_not_actionable_rows_total": 0,
        "manual_upgrade_rows_total": actionable_rows_total,
        "official_evidence_gap_rows_total": 0,
        "official_source_record_gap_rows_total": 0,
        "missing_seed_mapping_total": 0,
        "source_record_lookup_rows_total": 0,
        "source_record_pk_lookup_keys_total": 0,
        "source_record_pk_lookup_prefilled_total": 0,
        "source_record_pk_lookup_miss_total": 0,
        "only_actionable": True,
        "strict_empty_actionable": False,
        "actionable_queue_empty": actionable_queue_empty,
        "strict_fail_count": 0 if actionable_queue_empty else 1,
        "strict_fail_reasons": [] if actionable_queue_empty else ["actionable_rows_nonzero"],
    }


class TestReportLibertyPersonIdentityOfficialUpgradeReviewQueueActionableHeartbeatWindow(unittest.TestCase):
    def test_main_passes_strict_with_healthy_window(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_ok.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(idx=1, status="ok", actionable_rows_total=0),
                    _heartbeat_entry(idx=2, status="ok", actionable_rows_total=0),
                    _heartbeat_entry(idx=3, status="ok", actionable_rows_total=0),
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
                    "--max-actionable-nonempty-runs",
                    "0",
                    "--max-actionable-nonempty-runs-rate-pct",
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
            self.assertEqual(int(report["actionable_nonempty_runs_in_window"]), 0)
            self.assertEqual(report["strict_fail_reasons"], [])

    def test_main_fails_strict_when_latest_actionable_queue_not_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_fail.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(idx=1, status="ok", actionable_rows_total=0),
                    _heartbeat_entry(idx=2, status="failed", actionable_rows_total=1),
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
                    "--max-actionable-nonempty-runs",
                    "0",
                    "--max-actionable-nonempty-runs-rate-pct",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            report = _read_json(out)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(int(report["failed_in_window"]), 1)
            self.assertEqual(int(report["actionable_nonempty_runs_in_window"]), 1)
            self.assertIn("max_failed_exceeded", report["strict_fail_reasons"])
            self.assertIn("max_actionable_nonempty_runs_exceeded", report["strict_fail_reasons"])
            self.assertIn("latest_failed", report["strict_fail_reasons"])
            self.assertIn("latest_actionable_queue_not_empty", report["strict_fail_reasons"])


if __name__ == "__main__":
    unittest.main()
