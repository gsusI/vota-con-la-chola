from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_liberty_focus_scope_guard import main


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_changed_paths(path: Path, paths: list[str]) -> None:
    path.write_text("\n".join(paths) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _status_payload(*, status: str, focus_gate_passed: bool | None) -> dict:
    focus_gate_obj: dict[str, object] = {}
    if focus_gate_passed is not None:
        focus_gate_obj["passed"] = bool(focus_gate_passed)
    return {
        "generated_at": "2026-02-23T00:00:00+00:00",
        "status": status,
        "focus_gate": focus_gate_obj,
    }


class TestReportLibertyFocusScopeGuard(unittest.TestCase):
    def test_degraded_with_non_rights_changes_fails_strict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            status_json = td_path / "status.json"
            changed_paths_file = td_path / "changed_paths.txt"
            out = td_path / "report.json"

            _write_json(status_json, _status_payload(status="degraded", focus_gate_passed=False))
            _write_changed_paths(changed_paths_file, ["ui/citizen/index.html", "scripts/report_liberty_restrictions_status.py"])

            rc = main(
                [
                    "--status-json",
                    str(status_json),
                    "--changed-paths-file",
                    str(changed_paths_file),
                    "--strict",
                    "--out",
                    str(out),
                ]
            )

            self.assertEqual(rc, 4)
            got = _read_json(out)
            self.assertEqual(str(got.get("status") or ""), "failed")
            reasons = set(str(x) for x in (got.get("strict_fail_reasons") or []))
            self.assertIn("non_rights_changes_under_degraded_focus", reasons)
            self.assertGreaterEqual(int(got.get("non_rights_paths_total") or 0), 1)

    def test_degraded_with_rights_only_changes_passes_strict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            status_json = td_path / "status.json"
            changed_paths_file = td_path / "changed_paths.txt"
            out = td_path / "report.json"

            _write_json(status_json, _status_payload(status="degraded", focus_gate_passed=False))
            _write_changed_paths(
                changed_paths_file,
                [
                    "scripts/report_liberty_restrictions_status.py",
                    "tests/test_report_liberty_restrictions_status.py",
                    "docs/roadmap-tecnico.md",
                ],
            )

            rc = main(
                [
                    "--status-json",
                    str(status_json),
                    "--changed-paths-file",
                    str(changed_paths_file),
                    "--strict",
                    "--out",
                    str(out),
                ]
            )

            self.assertEqual(rc, 0)
            got = _read_json(out)
            self.assertEqual(str(got.get("status") or ""), "degraded")
            self.assertEqual(int(got.get("non_rights_paths_total") or 0), 0)

    def test_focus_ok_allows_non_rights_changes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            status_json = td_path / "status.json"
            changed_paths_file = td_path / "changed_paths.txt"
            out = td_path / "report.json"

            _write_json(status_json, _status_payload(status="ok", focus_gate_passed=True))
            _write_changed_paths(changed_paths_file, ["ui/citizen/index.html"])

            rc = main(
                [
                    "--status-json",
                    str(status_json),
                    "--changed-paths-file",
                    str(changed_paths_file),
                    "--strict",
                    "--out",
                    str(out),
                ]
            )

            self.assertEqual(rc, 0)
            got = _read_json(out)
            self.assertEqual(str(got.get("status") or ""), "ok")
            self.assertEqual(int(got.get("non_rights_paths_total") or 0), 1)
            self.assertEqual(got.get("strict_fail_reasons") or [], [])

    def test_focus_gate_unknown_fails_strict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            status_json = td_path / "status.json"
            changed_paths_file = td_path / "changed_paths.txt"
            out = td_path / "report.json"

            _write_json(status_json, _status_payload(status="ok", focus_gate_passed=None))
            _write_changed_paths(changed_paths_file, ["scripts/report_liberty_restrictions_status.py"])

            rc = main(
                [
                    "--status-json",
                    str(status_json),
                    "--changed-paths-file",
                    str(changed_paths_file),
                    "--strict",
                    "--out",
                    str(out),
                ]
            )

            self.assertEqual(rc, 4)
            got = _read_json(out)
            reasons = set(str(x) for x in (got.get("strict_fail_reasons") or []))
            self.assertIn("focus_gate_unknown", reasons)


if __name__ == "__main__":
    unittest.main()
