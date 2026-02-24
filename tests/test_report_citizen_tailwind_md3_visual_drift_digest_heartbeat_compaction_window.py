from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_tailwind_md3_visual_drift_digest_heartbeat_compaction_window import main


class TestCitizenTailwindMd3DriftHeartbeatCompactionWindow(unittest.TestCase):
    def _hb(
        self,
        minute: int,
        *,
        status: str = "ok",
        strict_fail_count: int = 0,
        contract_exists_ok: bool = True,
        contract_status_ok: bool = True,
        contract_checks_ok: bool = True,
        source_published_parity_ok: bool = True,
        marker_parity_ok: bool = True,
        tokens_parity_ok: bool = True,
        tokens_data_parity_ok: bool = True,
        css_parity_ok: bool = True,
        ui_html_parity_ok: bool = True,
    ) -> dict[str, object]:
        mm = f"{minute:02d}"
        parity_fail_reasons: list[str] = []
        if not source_published_parity_ok:
            parity_fail_reasons.append("source_published_parity_mismatch")
        if not marker_parity_ok:
            parity_fail_reasons.append("marker_parity_mismatch")
        if not tokens_parity_ok:
            parity_fail_reasons.append("tokens_parity_mismatch")
        if not tokens_data_parity_ok:
            parity_fail_reasons.append("tokens_data_parity_mismatch")
        if not css_parity_ok:
            parity_fail_reasons.append("css_parity_mismatch")
        if not ui_html_parity_ok:
            parity_fail_reasons.append("ui_html_parity_mismatch")

        strict_reasons = ["strict_fail"] if strict_fail_count > 0 else []
        return {
            "run_at": f"2026-02-23T18:{mm}:00+00:00",
            "heartbeat_id": f"hb-{mm}",
            "status": status,
            "strict_fail_count": strict_fail_count,
            "strict_fail_reasons": strict_reasons,
            "tailwind_contract_exists": contract_exists_ok,
            "tailwind_contract_status_ok": contract_status_ok,
            "tailwind_contract_checks_ok": contract_checks_ok,
            "source_published_parity_ok": source_published_parity_ok,
            "marker_parity_ok": marker_parity_ok,
            "tokens_parity_ok": tokens_parity_ok,
            "tokens_data_parity_ok": tokens_data_parity_ok,
            "css_parity_ok": css_parity_ok,
            "ui_html_parity_ok": ui_html_parity_ok,
            "parity_fail_count": len(parity_fail_reasons),
            "parity_fail_reasons": parity_fail_reasons,
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        lines = [json.dumps(r) for r in rows]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_compaction_window_passes_when_incidents_and_latest_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            raw_path = td_path / "raw.jsonl"
            compacted_path = td_path / "compacted.jsonl"
            out_path = td_path / "report.json"

            raw_rows = [
                self._hb(0, status="ok"),
                self._hb(
                    1,
                    status="failed",
                    strict_fail_count=1,
                    contract_status_ok=False,
                    source_published_parity_ok=False,
                    css_parity_ok=False,
                ),
                self._hb(
                    2,
                    status="degraded",
                    contract_checks_ok=False,
                    source_published_parity_ok=False,
                    marker_parity_ok=False,
                ),
                self._hb(3, status="ok", tokens_parity_ok=False),
                self._hb(4, status="ok"),
            ]
            compacted_rows = [
                self._hb(
                    1,
                    status="failed",
                    strict_fail_count=1,
                    contract_status_ok=False,
                    source_published_parity_ok=False,
                    css_parity_ok=False,
                ),
                self._hb(
                    2,
                    status="degraded",
                    contract_checks_ok=False,
                    source_published_parity_ok=False,
                    marker_parity_ok=False,
                ),
                self._hb(3, status="ok", tokens_parity_ok=False),
                self._hb(4, status="ok"),
            ]
            self._write_jsonl(raw_path, raw_rows)
            self._write_jsonl(compacted_path, compacted_rows)

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--heartbeat-jsonl",
                        str(raw_path),
                        "--compacted-jsonl",
                        str(compacted_path),
                        "--last",
                        "20",
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 0)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(str(report.get("status") or ""), "degraded")
            self.assertEqual(int(report["window_raw_entries"]), 5)
            self.assertEqual(int(report["incident_missing_in_compacted"]), 0)
            self.assertEqual(int(report["tokens_parity_mismatch_missing_in_compacted"]), 0)
            self.assertEqual(int(report["source_published_parity_mismatch_missing_in_compacted"]), 0)
            self.assertEqual(int(report["css_parity_mismatch_missing_in_compacted"]), 0)
            self.assertEqual(bool(report["checks"]["latest_present_ok"]), True)
            self.assertEqual(list(report.get("strict_fail_reasons") or []), [])

    def test_compaction_window_strict_fails_when_tokens_incident_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            raw_path = td_path / "raw.jsonl"
            compacted_path = td_path / "compacted.jsonl"
            out_path = td_path / "report_fail.json"

            raw_rows = [
                self._hb(0, status="ok"),
                self._hb(1, status="ok", tokens_parity_ok=False),
                self._hb(2, status="ok"),
            ]
            compacted_rows = [
                self._hb(2, status="ok"),
            ]
            self._write_jsonl(raw_path, raw_rows)
            self._write_jsonl(compacted_path, compacted_rows)

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--heartbeat-jsonl",
                        str(raw_path),
                        "--compacted-jsonl",
                        str(compacted_path),
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 4)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            reasons = list(report.get("strict_fail_reasons") or [])
            self.assertIn("incident_missing_in_compacted", reasons)
            self.assertIn("tokens_parity_mismatch_underreported_in_compacted", reasons)

    def test_compaction_window_strict_fails_when_latest_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            raw_path = td_path / "raw.jsonl"
            compacted_path = td_path / "compacted.jsonl"
            out_path = td_path / "report_latest_fail.json"

            raw_rows = [self._hb(0, status="ok"), self._hb(1, status="ok")]
            compacted_rows = [self._hb(0, status="ok")]
            self._write_jsonl(raw_path, raw_rows)
            self._write_jsonl(compacted_path, compacted_rows)

            with contextlib.redirect_stdout(io.StringIO()):
                rc = main(
                    [
                        "--heartbeat-jsonl",
                        str(raw_path),
                        "--compacted-jsonl",
                        str(compacted_path),
                        "--strict",
                        "--out",
                        str(out_path),
                    ]
                )
            self.assertEqual(rc, 4)
            report = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIn("latest_raw_missing_in_compacted", list(report.get("strict_fail_reasons") or []))


if __name__ == "__main__":
    unittest.main()
