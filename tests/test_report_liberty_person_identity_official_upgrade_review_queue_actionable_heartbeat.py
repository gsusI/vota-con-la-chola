from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_liberty_person_identity_official_upgrade_review_queue_actionable_heartbeat import main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _summary_fixture(
    *,
    rows_total: int = 0,
    actionable_rows_total: int = 0,
    likely_not_actionable_rows_total: int = 0,
    rows_exported_total: int | None = None,
    only_actionable: bool = True,
) -> dict:
    exported = actionable_rows_total if rows_exported_total is None else rows_exported_total
    return {
        "seed_path": "etl/data/seeds/liberty_person_identity_resolution_seed_v1.json",
        "db_path": "etl/data/staging/politicos-es.db",
        "out_path": "docs/etl/sprints/AI-OPS-153/exports/liberty_person_identity_official_upgrade_review_queue_actionable_latest.csv",
        "source_record_lookup_rows_total": 173070,
        "only_actionable": only_actionable,
        "strict_empty_actionable": False,
        "rows_exported_total": exported,
        "summary": {
            "rows_total": rows_total,
            "manual_upgrade_rows_total": rows_total,
            "official_evidence_gap_rows_total": 0,
            "official_source_record_gap_rows_total": 0,
            "missing_seed_mapping_total": 0,
            "source_record_pk_lookup_keys_total": 0,
            "source_record_pk_lookup_prefilled_total": 0,
            "source_record_pk_lookup_miss_total": 0,
            "actionable_rows_total": actionable_rows_total,
            "likely_not_actionable_rows_total": likely_not_actionable_rows_total,
        },
    }


class TestReportLibertyPersonIdentityOfficialUpgradeReviewQueueActionableHeartbeat(unittest.TestCase):
    def test_main_appends_and_dedupes_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            summary_json = td_path / "summary_ok.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out1 = td_path / "heartbeat_report_1.json"
            out2 = td_path / "heartbeat_report_2.json"
            _write_json(
                summary_json,
                _summary_fixture(rows_total=0, actionable_rows_total=0, likely_not_actionable_rows_total=0),
            )

            rc1 = main(
                [
                    "--summary-json",
                    str(summary_json),
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
                    "--summary-json",
                    str(summary_json),
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

    def test_main_strict_fails_when_actionable_rows_exist(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            summary_json = td_path / "summary_failed.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "heartbeat_report_failed.json"
            _write_json(
                summary_json,
                _summary_fixture(rows_total=1, actionable_rows_total=1, likely_not_actionable_rows_total=0),
            )

            rc = main(
                [
                    "--summary-json",
                    str(summary_json),
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
            self.assertIn("actionable_rows_nonzero", report["strict_fail_reasons"])
            self.assertTrue(report["appended"])

    def test_main_strict_fails_when_only_actionable_false(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            summary_json = td_path / "summary_only_actionable_false.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "heartbeat_report_only_actionable_false.json"
            _write_json(
                summary_json,
                _summary_fixture(
                    rows_total=0,
                    actionable_rows_total=0,
                    likely_not_actionable_rows_total=0,
                    only_actionable=False,
                ),
            )

            rc = main(
                [
                    "--summary-json",
                    str(summary_json),
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
            self.assertIn("only_actionable_false", report["strict_fail_reasons"])


if __name__ == "__main__":
    unittest.main()
