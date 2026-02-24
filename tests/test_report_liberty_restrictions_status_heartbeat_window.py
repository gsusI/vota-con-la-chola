from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_liberty_restrictions_status_heartbeat_window import main


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_text(payload, encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _heartbeat_entry(
    *,
    idx: int,
    status: str,
    focus_gate_passed: bool,
    norms_gate_passed: bool,
    fragments_irlc_gate_passed: bool,
    fragments_accountability_gate_passed: bool,
    rights_with_data_gate_passed: bool | None = True,
    source_representativity_gate_passed: bool | None = True,
    scope_representativity_gate_passed: bool | None = True,
    source_dual_coverage_gate_passed: bool | None = True,
    scope_dual_coverage_gate_passed: bool | None = True,
    accountability_primary_evidence_gate_passed: bool | None = True,
) -> dict:
    run_at = f"2026-02-23T19:{idx:02d}:00+00:00"
    return {
        "run_at": run_at,
        "heartbeat_id": f"{run_at}|{status}|{idx}",
        "status_path": "docs/etl/sprints/AI-OPS-118/evidence/liberty_restrictions_status_latest.json",
        "status_generated_at": run_at,
        "status": status,
        "norms_total": 8,
        "fragments_total": 8,
        "assessments_total": 8,
        "norms_classified_pct": 1.0 if norms_gate_passed else 0.75,
        "fragments_with_irlc_pct": 1.0 if fragments_irlc_gate_passed else 0.75,
        "fragments_with_accountability_pct": 1.0 if fragments_accountability_gate_passed else 0.75,
        "fragments_with_dual_coverage_pct": 1.0,
        "right_categories_with_data_pct": 1.0 if rights_with_data_gate_passed is not False else 0.75,
        "focus_gate_passed": focus_gate_passed,
        "norms_classified_gate_passed": norms_gate_passed,
        "fragments_irlc_gate_passed": fragments_irlc_gate_passed,
        "fragments_accountability_gate_passed": fragments_accountability_gate_passed,
        "rights_with_data_gate_passed": rights_with_data_gate_passed,
        "source_representativity_gate_passed": source_representativity_gate_passed,
        "scope_representativity_gate_passed": scope_representativity_gate_passed,
        "source_dual_coverage_gate_passed": source_dual_coverage_gate_passed,
        "scope_dual_coverage_gate_passed": scope_dual_coverage_gate_passed,
        "accountability_primary_evidence_gate_passed": accountability_primary_evidence_gate_passed,
        "strict_fail_count": 0 if status != "failed" else 1,
        "strict_fail_reasons": [] if status != "failed" else ["liberty_status_failed"],
    }


class TestReportLibertyRestrictionsStatusHeartbeatWindow(unittest.TestCase):
    def test_main_passes_strict_with_healthy_window(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_ok.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(
                        idx=1,
                        status="ok",
                        focus_gate_passed=True,
                        norms_gate_passed=True,
                        fragments_irlc_gate_passed=True,
                        fragments_accountability_gate_passed=True,
                    ),
                    _heartbeat_entry(
                        idx=2,
                        status="ok",
                        focus_gate_passed=True,
                        norms_gate_passed=True,
                        fragments_irlc_gate_passed=True,
                        fragments_accountability_gate_passed=True,
                    ),
                    _heartbeat_entry(
                        idx=3,
                        status="ok",
                        focus_gate_passed=True,
                        norms_gate_passed=True,
                        fragments_irlc_gate_passed=True,
                        fragments_accountability_gate_passed=True,
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
                    "--max-focus-gate-failed",
                    "0",
                    "--max-focus-gate-failed-rate-pct",
                    "0",
                    "--max-norms-classified-gate-failed",
                    "0",
                    "--max-fragments-irlc-gate-failed",
                    "0",
                    "--max-fragments-accountability-gate-failed",
                    "0",
                    "--max-rights-with-data-gate-failed",
                    "0",
                    "--max-source-representativity-gate-failed",
                    "0",
                    "--max-scope-representativity-gate-failed",
                    "0",
                    "--max-source-dual-coverage-gate-failed",
                    "0",
                    "--max-scope-dual-coverage-gate-failed",
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
            self.assertEqual(int(report["focus_gate_failed_in_window"]), 0)
            self.assertEqual(report["strict_fail_reasons"], [])

    def test_main_fails_strict_when_latest_has_focus_gate_failure(self) -> None:
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
                        focus_gate_passed=True,
                        norms_gate_passed=True,
                        fragments_irlc_gate_passed=True,
                        fragments_accountability_gate_passed=True,
                    ),
                    _heartbeat_entry(
                        idx=2,
                        status="degraded",
                        focus_gate_passed=False,
                        norms_gate_passed=False,
                        fragments_irlc_gate_passed=True,
                        fragments_accountability_gate_passed=True,
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
                    "--max-focus-gate-failed",
                    "0",
                    "--max-focus-gate-failed-rate-pct",
                    "0",
                    "--max-norms-classified-gate-failed",
                    "0",
                    "--max-fragments-irlc-gate-failed",
                    "0",
                    "--max-fragments-accountability-gate-failed",
                    "0",
                    "--max-rights-with-data-gate-failed",
                    "0",
                    "--max-source-representativity-gate-failed",
                    "0",
                    "--max-scope-representativity-gate-failed",
                    "0",
                    "--max-source-dual-coverage-gate-failed",
                    "0",
                    "--max-scope-dual-coverage-gate-failed",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            report = _read_json(out)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(int(report["focus_gate_failed_in_window"]), 1)
            self.assertEqual(int(report["norms_classified_gate_failed_in_window"]), 1)
            self.assertIn("max_focus_gate_failed_exceeded", report["strict_fail_reasons"])
            self.assertIn("latest_focus_gate_failed", report["strict_fail_reasons"])
            self.assertIn("latest_norms_classified_gate_failed", report["strict_fail_reasons"])

    def test_main_fails_strict_when_latest_rights_with_data_gate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_rights_fail.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(
                        idx=1,
                        status="ok",
                        focus_gate_passed=True,
                        norms_gate_passed=True,
                        fragments_irlc_gate_passed=True,
                        fragments_accountability_gate_passed=True,
                        rights_with_data_gate_passed=True,
                    ),
                    _heartbeat_entry(
                        idx=2,
                        status="degraded",
                        focus_gate_passed=False,
                        norms_gate_passed=True,
                        fragments_irlc_gate_passed=True,
                        fragments_accountability_gate_passed=True,
                        rights_with_data_gate_passed=False,
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
                    "--max-focus-gate-failed",
                    "1",
                    "--max-focus-gate-failed-rate-pct",
                    "100",
                    "--max-norms-classified-gate-failed",
                    "0",
                    "--max-fragments-irlc-gate-failed",
                    "0",
                    "--max-fragments-accountability-gate-failed",
                    "0",
                    "--max-rights-with-data-gate-failed",
                    "0",
                    "--max-source-representativity-gate-failed",
                    "0",
                    "--max-scope-representativity-gate-failed",
                    "0",
                    "--max-source-dual-coverage-gate-failed",
                    "0",
                    "--max-scope-dual-coverage-gate-failed",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            report = _read_json(out)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(int(report["rights_with_data_gate_failed_in_window"]), 1)
            self.assertIn("max_rights_with_data_gate_failed_exceeded", report["strict_fail_reasons"])
            self.assertIn("latest_rights_with_data_gate_failed", report["strict_fail_reasons"])

    def test_main_fails_strict_when_latest_source_scope_representativity_gates_fail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_source_scope_fail.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(
                        idx=1,
                        status="ok",
                        focus_gate_passed=True,
                        norms_gate_passed=True,
                        fragments_irlc_gate_passed=True,
                        fragments_accountability_gate_passed=True,
                        rights_with_data_gate_passed=True,
                        source_representativity_gate_passed=True,
                        scope_representativity_gate_passed=True,
                    ),
                    _heartbeat_entry(
                        idx=2,
                        status="degraded",
                        focus_gate_passed=False,
                        norms_gate_passed=True,
                        fragments_irlc_gate_passed=True,
                        fragments_accountability_gate_passed=True,
                        rights_with_data_gate_passed=True,
                        source_representativity_gate_passed=False,
                        scope_representativity_gate_passed=False,
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
                    "--max-focus-gate-failed",
                    "1",
                    "--max-focus-gate-failed-rate-pct",
                    "100",
                    "--max-norms-classified-gate-failed",
                    "0",
                    "--max-fragments-irlc-gate-failed",
                    "0",
                    "--max-fragments-accountability-gate-failed",
                    "0",
                    "--max-rights-with-data-gate-failed",
                    "0",
                    "--max-source-representativity-gate-failed",
                    "0",
                    "--max-scope-representativity-gate-failed",
                    "0",
                    "--max-source-dual-coverage-gate-failed",
                    "0",
                    "--max-scope-dual-coverage-gate-failed",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            report = _read_json(out)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(int(report["source_representativity_gate_failed_in_window"]), 1)
            self.assertEqual(int(report["scope_representativity_gate_failed_in_window"]), 1)
            self.assertIn("max_source_representativity_gate_failed_exceeded", report["strict_fail_reasons"])
            self.assertIn("max_scope_representativity_gate_failed_exceeded", report["strict_fail_reasons"])
            self.assertIn("latest_source_representativity_gate_failed", report["strict_fail_reasons"])
            self.assertIn("latest_scope_representativity_gate_failed", report["strict_fail_reasons"])

    def test_main_fails_strict_when_latest_source_scope_dual_coverage_gates_fail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_source_scope_dual_fail.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(
                        idx=1,
                        status="ok",
                        focus_gate_passed=True,
                        norms_gate_passed=True,
                        fragments_irlc_gate_passed=True,
                        fragments_accountability_gate_passed=True,
                        rights_with_data_gate_passed=True,
                        source_representativity_gate_passed=True,
                        scope_representativity_gate_passed=True,
                        source_dual_coverage_gate_passed=True,
                        scope_dual_coverage_gate_passed=True,
                    ),
                    _heartbeat_entry(
                        idx=2,
                        status="degraded",
                        focus_gate_passed=False,
                        norms_gate_passed=True,
                        fragments_irlc_gate_passed=True,
                        fragments_accountability_gate_passed=True,
                        rights_with_data_gate_passed=True,
                        source_representativity_gate_passed=True,
                        scope_representativity_gate_passed=True,
                        source_dual_coverage_gate_passed=False,
                        scope_dual_coverage_gate_passed=False,
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
                    "--max-focus-gate-failed",
                    "1",
                    "--max-focus-gate-failed-rate-pct",
                    "100",
                    "--max-norms-classified-gate-failed",
                    "0",
                    "--max-fragments-irlc-gate-failed",
                    "0",
                    "--max-fragments-accountability-gate-failed",
                    "0",
                    "--max-rights-with-data-gate-failed",
                    "0",
                    "--max-source-representativity-gate-failed",
                    "0",
                    "--max-scope-representativity-gate-failed",
                    "0",
                    "--max-source-dual-coverage-gate-failed",
                    "0",
                    "--max-scope-dual-coverage-gate-failed",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            report = _read_json(out)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(int(report["source_dual_coverage_gate_failed_in_window"]), 1)
            self.assertEqual(int(report["scope_dual_coverage_gate_failed_in_window"]), 1)
            self.assertIn("max_source_dual_coverage_gate_failed_exceeded", report["strict_fail_reasons"])
            self.assertIn("max_scope_dual_coverage_gate_failed_exceeded", report["strict_fail_reasons"])
            self.assertIn("latest_source_dual_coverage_gate_failed", report["strict_fail_reasons"])
            self.assertIn("latest_scope_dual_coverage_gate_failed", report["strict_fail_reasons"])

    def test_main_fails_strict_when_latest_accountability_primary_evidence_gate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_accountability_primary_evidence_fail.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(
                        idx=1,
                        status="ok",
                        focus_gate_passed=True,
                        norms_gate_passed=True,
                        fragments_irlc_gate_passed=True,
                        fragments_accountability_gate_passed=True,
                        accountability_primary_evidence_gate_passed=True,
                    ),
                    _heartbeat_entry(
                        idx=2,
                        status="degraded",
                        focus_gate_passed=True,
                        norms_gate_passed=True,
                        fragments_irlc_gate_passed=True,
                        fragments_accountability_gate_passed=True,
                        accountability_primary_evidence_gate_passed=False,
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
                    "--max-focus-gate-failed",
                    "0",
                    "--max-focus-gate-failed-rate-pct",
                    "0",
                    "--max-norms-classified-gate-failed",
                    "0",
                    "--max-fragments-irlc-gate-failed",
                    "0",
                    "--max-fragments-accountability-gate-failed",
                    "0",
                    "--max-rights-with-data-gate-failed",
                    "0",
                    "--max-source-representativity-gate-failed",
                    "0",
                    "--max-scope-representativity-gate-failed",
                    "0",
                    "--max-source-dual-coverage-gate-failed",
                    "0",
                    "--max-scope-dual-coverage-gate-failed",
                    "0",
                    "--max-accountability-primary-evidence-gate-failed",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            report = _read_json(out)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(int(report["accountability_primary_evidence_gate_failed_in_window"]), 1)
            self.assertIn("max_accountability_primary_evidence_gate_failed_exceeded", report["strict_fail_reasons"])
            self.assertIn("latest_accountability_primary_evidence_gate_failed", report["strict_fail_reasons"])

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
                        focus_gate_passed=True,
                        norms_gate_passed=True,
                        fragments_irlc_gate_passed=True,
                        fragments_accountability_gate_passed=True,
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
