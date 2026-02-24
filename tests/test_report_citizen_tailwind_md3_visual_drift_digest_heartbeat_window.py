from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_tailwind_md3_visual_drift_digest_heartbeat_window import main


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    path.write_text(payload, encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _heartbeat_entry(
    *,
    idx: int,
    status: str,
    tokens_parity_ok: bool = True,
    tokens_data_parity_ok: bool = True,
    css_parity_ok: bool = True,
    ui_html_parity_ok: bool = True,
    marker_parity_ok: bool = True,
) -> dict:
    run_at = f"2026-02-23T16:{idx:02d}:00+00:00"
    source_published_parity_ok = all([tokens_parity_ok, tokens_data_parity_ok, css_parity_ok, ui_html_parity_ok])
    parity_fail_reasons: list[str] = []
    if not tokens_parity_ok:
        parity_fail_reasons.append("tokens_parity_mismatch")
    if not tokens_data_parity_ok:
        parity_fail_reasons.append("tokens_data_parity_mismatch")
    if not css_parity_ok:
        parity_fail_reasons.append("css_parity_mismatch")
    if not ui_html_parity_ok:
        parity_fail_reasons.append("ui_html_parity_mismatch")
    if not marker_parity_ok:
        parity_fail_reasons.append("source_published_marker_counts_mismatch")
    return {
        "run_at": run_at,
        "heartbeat_id": f"{run_at}|{status}|{idx}",
        "status": status,
        "source_published_parity_ok": source_published_parity_ok,
        "marker_parity_ok": marker_parity_ok,
        "tokens_parity_ok": tokens_parity_ok,
        "tokens_data_parity_ok": tokens_data_parity_ok,
        "css_parity_ok": css_parity_ok,
        "ui_html_parity_ok": ui_html_parity_ok,
        "parity_fail_count": len(parity_fail_reasons),
        "parity_fail_reasons": parity_fail_reasons,
        "strict_fail_count": 0 if status != "failed" else max(1, len(parity_fail_reasons)),
        "strict_fail_reasons": [] if status != "failed" else parity_fail_reasons or ["heartbeat_status_failed"],
    }


class TestReportCitizenTailwindMd3VisualDriftDigestHeartbeatWindow(unittest.TestCase):
    def test_main_passes_strict_with_clean_window(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(idx=1, status="ok"),
                    _heartbeat_entry(idx=2, status="ok"),
                    _heartbeat_entry(idx=3, status="ok"),
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
                    "--max-parity-mismatch",
                    "0",
                    "--max-parity-mismatch-rate-pct",
                    "0",
                    "--max-tokens-parity-mismatch",
                    "0",
                    "--max-tokens-data-parity-mismatch",
                    "0",
                    "--max-css-parity-mismatch",
                    "0",
                    "--max-ui-html-parity-mismatch",
                    "0",
                    "--max-marker-mismatch",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 0)

            report = _read_json(out)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(int(report["parity_mismatch_in_window"]), 0)
            self.assertEqual(report["strict_fail_reasons"], [])

    def test_main_fails_strict_when_latest_css_parity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            out = td_path / "window_fail.json"
            _write_jsonl(
                heartbeat_jsonl,
                [
                    _heartbeat_entry(idx=1, status="ok"),
                    _heartbeat_entry(idx=2, status="failed", css_parity_ok=False),
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
                    "--max-parity-mismatch",
                    "0",
                    "--max-parity-mismatch-rate-pct",
                    "0",
                    "--max-tokens-parity-mismatch",
                    "0",
                    "--max-tokens-data-parity-mismatch",
                    "0",
                    "--max-css-parity-mismatch",
                    "0",
                    "--max-ui-html-parity-mismatch",
                    "0",
                    "--max-marker-mismatch",
                    "0",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            report = _read_json(out)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(int(report["parity_mismatch_in_window"]), 1)
            self.assertEqual(int(report["css_parity_mismatch_in_window"]), 1)
            self.assertIn("max_parity_mismatch_exceeded", report["strict_fail_reasons"])
            self.assertIn("max_css_parity_mismatch_exceeded", report["strict_fail_reasons"])
            self.assertIn("latest_source_published_parity_mismatch", report["strict_fail_reasons"])

    def test_main_rejects_invalid_window_size(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            heartbeat_jsonl = td_path / "heartbeat.jsonl"
            _write_jsonl(
                heartbeat_jsonl,
                [_heartbeat_entry(idx=1, status="ok")],
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
