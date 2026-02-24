from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_liberty_restrictions_status_heartbeat import main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _status_fixture(*, status: str = "ok", focus_gate_passed: bool = True) -> dict:
    return {
        "generated_at": "2026-02-23T19:00:00+00:00",
        "status": status,
        "totals": {
            "norms_total": 8,
            "fragments_total": 8,
            "assessments_total": 8,
            "sources_total": 1,
            "sources_with_assessments_total": 1 if focus_gate_passed else 0,
            "scopes_total": 1,
            "scopes_with_assessments_total": 1 if focus_gate_passed else 0,
            "sources_with_dual_coverage_total": 1 if focus_gate_passed else 0,
            "scopes_with_dual_coverage_total": 1 if focus_gate_passed else 0,
            "accountability_edges_total": 8,
            "accountability_edges_with_primary_evidence_total": 0,
        },
        "coverage": {
            "norms_classified_pct": 1.0 if focus_gate_passed else 0.75,
            "fragments_with_irlc_pct": 1.0 if focus_gate_passed else 0.75,
            "fragments_with_accountability_pct": 1.0 if focus_gate_passed else 0.75,
            "fragments_with_dual_coverage_pct": 1.0 if focus_gate_passed else 0.75,
            "accountability_edges_with_primary_evidence_pct": 0.0,
            "right_categories_with_data_pct": 1.0 if focus_gate_passed else 0.75,
            "sources_with_assessments_pct": 1.0 if focus_gate_passed else 0.0,
            "scopes_with_assessments_pct": 1.0 if focus_gate_passed else 0.0,
            "sources_with_dual_coverage_pct": 1.0 if focus_gate_passed else 0.0,
            "scopes_with_dual_coverage_pct": 1.0 if focus_gate_passed else 0.0,
        },
        "checks": {
            "norms_classified_gate": focus_gate_passed,
            "fragments_irlc_gate": focus_gate_passed,
            "fragments_accountability_gate": focus_gate_passed,
            "rights_with_data_gate": focus_gate_passed,
            "source_representativity_gate": focus_gate_passed,
            "scope_representativity_gate": focus_gate_passed,
            "source_dual_coverage_gate": focus_gate_passed,
            "scope_dual_coverage_gate": focus_gate_passed,
            "accountability_primary_evidence_gate": focus_gate_passed,
        },
        "focus_gate": {
            "passed": focus_gate_passed,
            "thresholds": {
                "norms_classified_min": 0.8,
                "fragments_irlc_min": 0.6,
                "fragments_accountability_min": 0.6,
                "rights_with_data_min": 1.0,
                "sources_with_assessments_min_pct": 1.0,
                "scopes_with_assessments_min_pct": 1.0,
                "min_assessment_sources": 1,
                "min_assessment_scopes": 1,
                "sources_with_dual_coverage_min_pct": 1.0,
                "scopes_with_dual_coverage_min_pct": 1.0,
                "min_dual_coverage_sources": 1,
                "min_dual_coverage_scopes": 1,
                "accountability_primary_evidence_min_pct": 0.0,
                "min_accountability_primary_evidence_edges": 0,
            },
        },
    }


class TestReportLibertyRestrictionsStatusHeartbeat(unittest.TestCase):
    def test_main_appends_and_dedupes_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            status_json = td_path / "status_ok.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out1 = td_path / "report1.json"
            out2 = td_path / "report2.json"
            _write_json(status_json, _status_fixture(status="ok", focus_gate_passed=True))

            rc1 = main(
                [
                    "--status-json",
                    str(status_json),
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
                    "--status-json",
                    str(status_json),
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

    def test_main_strict_fails_when_status_failed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            status_json = td_path / "status_failed.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "report_failed.json"
            _write_json(status_json, _status_fixture(status="failed", focus_gate_passed=False))

            rc = main(
                [
                    "--status-json",
                    str(status_json),
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
            status_json = td_path / "status_degraded.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "report_degraded.json"
            _write_json(status_json, _status_fixture(status="degraded", focus_gate_passed=False))

            rc = main(
                [
                    "--status-json",
                    str(status_json),
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
