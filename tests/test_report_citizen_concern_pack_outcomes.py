from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_concern_pack_outcomes import main


class TestReportCitizenConcernPackOutcomes(unittest.TestCase):
    def _fixture_path(self, name: str) -> Path:
        return Path(__file__).resolve().parent / "fixtures" / name

    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
        path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")

    def _write_quality(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "packs": [
                        {"pack_id": "economia", "weak": False, "quality_score": 0.9},
                        {"pack_id": "vivienda", "weak": True, "quality_score": 0.4},
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_main_passes_fixture_with_strict_complete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.json"
            rc = main(
                [
                    "--events-jsonl",
                    str(self._fixture_path("citizen_concern_pack_outcome_events_sample.jsonl")),
                    "--concern-pack-quality-json",
                    str(self._fixture_path("citizen_concern_pack_quality_sample.json")),
                    "--strict",
                    "--strict-require-complete",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 0)

            got = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "ok")
            self.assertTrue(bool(got["checks"]["contract_complete"]))
            self.assertEqual(int(got["metrics"]["pack_selected_events_total"]), 24)
            self.assertEqual(int(got["metrics"]["weak_pack_selected_sessions_total"]), 7)
            self.assertEqual(int(got["metrics"]["unknown_pack_selected_events_total"]), 2)

    def test_main_strict_fails_when_weak_followthrough_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            events = td_path / "events.jsonl"
            quality = td_path / "quality.json"
            out = td_path / "out.json"

            rows = []
            for idx in range(1, 7):
                rows.append({"event_type": "pack_selected", "session_id": f"w{idx}", "pack_id": "vivienda"})
            for idx in range(1, 15):
                rows.append({"event_type": "pack_selected", "session_id": f"n{((idx - 1) % 4) + 1}", "pack_id": "economia"})

            self._write_jsonl(events, rows)
            self._write_quality(quality)

            rc = main(
                [
                    "--events-jsonl",
                    str(events),
                    "--concern-pack-quality-json",
                    str(quality),
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            got = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "failed")
            self.assertIn("weak_pack_followthrough_below_threshold", set(got.get("failure_reasons") or []))
            self.assertEqual(int(got["metrics"]["weak_pack_selected_sessions_total"]), 6)
            self.assertEqual(int(got["metrics"]["weak_pack_followthrough_sessions_total"]), 0)

    def test_main_strict_fails_when_unknown_pack_share_above_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.json"
            rc = main(
                [
                    "--events-jsonl",
                    str(self._fixture_path("citizen_concern_pack_outcome_events_sample.jsonl")),
                    "--concern-pack-quality-json",
                    str(self._fixture_path("citizen_concern_pack_quality_sample.json")),
                    "--max-unknown-pack-select-share",
                    "0.05",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            got = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "failed")
            self.assertIn("unknown_pack_select_share_above_threshold", set(got.get("failure_reasons") or []))

    def test_main_degraded_without_events_fails_with_strict_complete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            events = td_path / "events.jsonl"
            quality = td_path / "quality.json"
            out = td_path / "out.json"
            events.write_text("", encoding="utf-8")
            self._write_quality(quality)

            rc = main(
                [
                    "--events-jsonl",
                    str(events),
                    "--concern-pack-quality-json",
                    str(quality),
                    "--strict",
                    "--strict-require-complete",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            got = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "degraded")
            self.assertIn("telemetry_missing", set(got.get("degraded_reasons") or []))
            self.assertFalse(bool(got["checks"]["contract_complete"]))


if __name__ == "__main__":
    unittest.main()
