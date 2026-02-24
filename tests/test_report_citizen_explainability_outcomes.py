from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_citizen_explainability_outcomes import main


class TestReportCitizenExplainabilityOutcomes(unittest.TestCase):
    def _fixture_path(self, name: str) -> Path:
        return Path(__file__).resolve().parent / "fixtures" / name

    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
        path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")

    def test_main_passes_fixture_with_strict_complete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.json"
            rc = main(
                [
                    "--events-jsonl",
                    str(self._fixture_path("citizen_explainability_outcome_events_sample.jsonl")),
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
            self.assertEqual(int(got["metrics"]["glossary_interaction_events_total"]), 9)
            self.assertEqual(int(got["metrics"]["help_copy_interaction_events_total"]), 5)

    def test_main_strict_fails_when_adoption_completeness_below_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.json"
            rc = main(
                [
                    "--events-jsonl",
                    str(self._fixture_path("citizen_explainability_outcome_events_sample.jsonl")),
                    "--min-adoption-completeness-rate",
                    "0.9",
                    "--strict",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            got = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "failed")
            self.assertIn("adoption_completeness_below_threshold", set(got.get("failure_reasons") or []))

    def test_main_strict_complete_fails_when_help_copy_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            events = td_path / "events.jsonl"
            out = td_path / "out.json"
            rows = [
                {"event_type": "explainability_glossary_opened", "session_id": "s1"},
                {"event_type": "explainability_glossary_term_interacted", "session_id": "s1", "term": "unknown"},
                {"event_type": "explainability_glossary_opened", "session_id": "s2"},
                {"event_type": "explainability_glossary_term_interacted", "session_id": "s2", "term": "cobertura"},
                {"event_type": "explainability_glossary_opened", "session_id": "s3"},
                {"event_type": "explainability_glossary_term_interacted", "session_id": "s3", "term": "confianza"},
                {"event_type": "explainability_glossary_opened", "session_id": "s4"},
                {"event_type": "explainability_glossary_term_interacted", "session_id": "s4", "term": "evidencia"},
            ]
            self._write_jsonl(events, rows)

            rc = main(
                [
                    "--events-jsonl",
                    str(events),
                    "--strict",
                    "--strict-require-complete",
                    "--out",
                    str(out),
                ]
            )
            self.assertEqual(rc, 4)

            got = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(got["status"], "degraded")
            self.assertIn("help_copy_interactions_below_minimum", set(got.get("degraded_reasons") or []))
            self.assertFalse(bool(got["checks"]["contract_complete"]))

    def test_main_degraded_without_events_fails_with_strict_complete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            events = td_path / "events.jsonl"
            out = td_path / "out.json"
            events.write_text("", encoding="utf-8")

            rc = main(
                [
                    "--events-jsonl",
                    str(events),
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
