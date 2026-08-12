from __future__ import annotations

import datetime as dt
import json
import unittest

from scripts import generar_proximas_elecciones_espana as calendario


class TestGenerarProximasEleccionesEspana(unittest.TestCase):
    def test_snapshot_keeps_official_calendar_event_first_when_upcoming(self) -> None:
        today = dt.date(2026, 5, 16)

        snapshot = calendario.construir_snapshot(
            today,
            scraped_events=[
                {
                    "event_id": "autonomico-andalucia-2026-05-17",
                    "level": "Autonómico",
                    "scope": "autonomico",
                    "election": "Parlamento de Andalucía",
                    "election_type": "parlamento_autonomico",
                    "territory": "Andalucía",
                    "date": "2026-05-17",
                    "date_precision": "day",
                    "status": "convocada",
                    "certainty": "oficial",
                    "source_kind": "official_calendar",
                    "source_id": "jec_andalucia_2026_calendario",
                    "source_url": "https://example.test/andalucia.pdf",
                    "source_verified": True,
                    "source_status": "ok",
                    "notes": "Calendario oficial.",
                }
            ],
            scraped_sources=[
                {
                    "source_id": "jec_andalucia_2026_calendario",
                    "status": "ok",
                    "source_verified": True,
                    "url": "https://example.test/andalucia.pdf",
                }
            ],
        )

        self.assertEqual(snapshot["schema_version"], "election-calendar.v1")
        self.assertEqual(snapshot["timeline_events"][0]["event_id"], "autonomico-andalucia-2026-05-17")
        self.assertEqual(snapshot["timeline_events"][0]["source_kind"], "official_calendar")
        self.assertIn("municipal-local-2027-05-23", {row["event_id"] for row in snapshot["events"]})
        self.assertGreaterEqual(snapshot["totales"]["legal_cycle_events"], 8)
        self.assertEqual(snapshot["totales"]["official_calendar_events"], 1)

    def test_past_official_event_drops_from_upcoming_calendar(self) -> None:
        today = dt.date(2026, 5, 18)

        snapshot = calendario.construir_snapshot(today, no_network=True)

        event_ids = {row["event_id"] for row in snapshot["events"]}
        self.assertNotIn("autonomico-andalucia-2026-05-17", event_ids)
        self.assertIn("municipal-local-2027-05-23", event_ids)
        self.assertTrue(snapshot["undated_events"])

    def test_markdown_contains_operational_state_and_scraped_sources(self) -> None:
        snapshot = calendario.construir_snapshot(dt.date(2026, 5, 16), no_network=True)

        text = calendario.a_markdown(snapshot)
        payload_text = json.dumps(snapshot, ensure_ascii=False)

        self.assertIn("## Timeline", text)
        self.assertIn("## Fuentes scrapeadas", text)
        self.assertIn("## Estado operativo", text)
        self.assertIn("años", payload_text)
        self.assertNotIn(" anos", text)
        self.assertNotIn(" anos", payload_text)


if __name__ == "__main__":
    unittest.main()
