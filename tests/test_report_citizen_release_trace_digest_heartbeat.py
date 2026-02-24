from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_release_trace_digest_heartbeat import main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _release_trace_digest_fixture(*, status: str = "ok") -> dict:
    is_ok = status == "ok"
    is_degraded = status == "degraded"
    is_failed = status == "failed"

    return {
        "generated_at": "2026-02-23T14:00:00+00:00",
        "status": status,
        "paths": {
            "release_hardening_json": "docs/etl/sprints/AI-OPS-81/evidence/citizen_release_hardening_latest.json"
        },
        "release_trace": {
            "release_generated_at": "2026-02-23T13:55:00+00:00",
            "release_age_minutes": 5.0 if not is_degraded else 900.0,
            "release_ready": False if is_failed else True,
            "release_readiness_status": "failed" if is_failed else "ok",
            "release_total_checks": 30,
            "release_total_fail": 1 if is_failed else 0,
            "release_failed_ids_total": 1 if is_failed else 0,
            "parity_ok_assets": 8 if is_failed else 9,
            "parity_total_assets": 9,
            "parity_failed_assets_total": 1 if is_failed else 0,
            "snapshot_as_of_date": "2026-02-16",
            "snapshot_topics_total": 111,
            "snapshot_parties_total": 16,
            "snapshot_party_topic_positions_total": 1776,
            "snapshot_has_meta_quality": True,
        },
        "thresholds": {
            "max_age_minutes": 360,
        },
        "checks": {
            "release_generated_at_present": True,
            "release_checks_present": True,
            "release_no_failures": not is_failed,
            "release_ready": not is_failed,
            "freshness_within_sla": not is_degraded,
            "parity_assets_complete": not is_failed,
            "contract_complete": is_ok,
        },
        "degraded_reasons": ["release_trace_stale"] if is_degraded else [],
        "failure_reasons": ["release_not_ready", "release_failures_present"] if is_failed else [],
        "failed_ids": ["snapshot:shape"] if is_failed else [],
        "parity_failed_assets": ["index.html"] if is_failed else [],
    }


class TestReportCitizenReleaseTraceDigestHeartbeat(unittest.TestCase):
    def test_main_appends_and_dedupes_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            digest = td_path / "release_trace_digest_ok.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out1 = td_path / "report1.json"
            out2 = td_path / "report2.json"
            _write_json(digest, _release_trace_digest_fixture(status="ok"))

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

            lines = [line for line in heartbeat_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["status"], "ok")
            self.assertEqual(entry["freshness_within_sla"], True)
            self.assertEqual(entry["stale_detected"], False)

    def test_main_strict_fails_when_digest_status_failed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            digest = td_path / "release_trace_digest_failed.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "report.json"
            _write_json(digest, _release_trace_digest_fixture(status="failed"))

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
            self.assertEqual(int(report["history_size_after"]), 1)

    def test_main_degraded_stale_passes_strict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            digest = td_path / "release_trace_digest_stale.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "report.json"
            _write_json(digest, _release_trace_digest_fixture(status="degraded"))

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

            lines = [line for line in heartbeat_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["freshness_within_sla"], False)
            self.assertEqual(entry["stale_detected"], True)


if __name__ == "__main__":
    unittest.main()
