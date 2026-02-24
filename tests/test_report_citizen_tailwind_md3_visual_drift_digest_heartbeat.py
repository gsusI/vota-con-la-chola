from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_tailwind_md3_visual_drift_digest_heartbeat import main


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _drift_digest_fixture(*, status: str = "ok", css_parity_ok: bool = True) -> dict:
    strict_fail_reasons: list[str] = []
    if status == "failed":
        strict_fail_reasons.append("css_parity_mismatch" if not css_parity_ok else "tailwind_contract_failed")
    return {
        "generated_at": "2026-02-23T16:00:00+00:00",
        "status": status,
        "tailwind_contract": {
            "status": "ok" if status != "failed" else "failed",
            "failure_reasons": [] if status != "failed" else ["tailwind_contract_failed"],
            "checks_all_ok": status != "failed",
        },
        "checks": {
            "tailwind_contract_exists": True,
            "tailwind_contract_status_ok": status != "failed",
            "tailwind_contract_checks_ok": status != "failed",
            "tokens_parity_ok": True,
            "tokens_data_parity_ok": True,
            "css_parity_ok": css_parity_ok,
            "ui_html_parity_ok": True,
            "source_published_marker_counts_match": True,
            "source_markers_match_contract_snapshot": True,
            "published_markers_match_contract_snapshot": True,
        },
        "parity": {
            "tokens": {"source_bytes": 100, "published_bytes": 100},
            "tokens_data": {"source_bytes": 100, "published_bytes": 100},
            "css": {"source_bytes": 200, "published_bytes": 200 if css_parity_ok else 220},
            "ui_html": {"source_bytes": 300, "published_bytes": 300},
        },
        "strict_fail_reasons": strict_fail_reasons,
    }


class TestReportCitizenTailwindMd3VisualDriftDigestHeartbeat(unittest.TestCase):
    def test_main_appends_and_dedupes_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            digest = td_path / "drift_ok.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out1 = td_path / "report1.json"
            out2 = td_path / "report2.json"
            _write_json(digest, _drift_digest_fixture(status="ok", css_parity_ok=True))

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
            self.assertEqual(entry["source_published_parity_ok"], True)
            self.assertEqual(entry["marker_parity_ok"], True)
            self.assertEqual(entry["strict_fail_count"], 0)

    def test_main_strict_fails_when_digest_status_failed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            digest = td_path / "drift_failed.json"
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "report.json"
            _write_json(digest, _drift_digest_fixture(status="failed", css_parity_ok=False))

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
            self.assertIn("css_parity_mismatch", report["strict_fail_reasons"])
            self.assertTrue(report["appended"])


if __name__ == "__main__":
    unittest.main()
