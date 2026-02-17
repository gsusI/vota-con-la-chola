from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from scripts import graph_ui_server as g


class TestGraphUiServerMismatchPayload(unittest.TestCase):
    def _seed_sources_and_runs(self, db_path: Path) -> None:
        conn = open_db(db_path)
        try:
            apply_schema(conn, DEFAULT_SCHEMA)
            now_iso = "2026-02-16T10:00:00Z"
            for source_id, source_url, data_format in (
                ("moncloa_referencias", "https://www.lamoncloa.gob.es/referencias", "html"),
                ("moncloa_rss_referencias", "https://www.lamoncloa.gob.es/rss/referencias.xml", "rss"),
            ):
                conn.execute(
                    """
                    INSERT INTO sources (
                      source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(source_id) DO UPDATE SET
                      name = excluded.name,
                      scope = excluded.scope,
                      default_url = excluded.default_url,
                      data_format = excluded.data_format,
                      is_active = 1,
                      updated_at = excluded.updated_at
                    """,
                    (
                        source_id,
                        source_id,
                        "nacional",
                        source_url,
                        data_format,
                        now_iso,
                        now_iso,
                    ),
                )

            conn.execute(
                """
                INSERT INTO ingestion_runs (
                  source_id, started_at, finished_at, status, source_url, raw_path, fetched_at,
                  records_seen, records_loaded, message
                ) VALUES (?, ?, ?, 'ok', ?, ?, ?, ?, ?, ?)
                """,
                (
                    "moncloa_referencias",
                    now_iso,
                    now_iso,
                    "https://www.lamoncloa.gob.es/referencias",
                    "/tmp/moncloa-reference.html",
                    now_iso,
                    5,
                    5,
                    "fixture",
                ),
            )
            run_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.execute(
                """
                INSERT INTO run_fetches (
                  run_id, source_id, source_url, fetched_at, raw_path, content_sha256, content_type, bytes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    "moncloa_referencias",
                    "https://www.lamoncloa.gob.es/referencias",
                    now_iso,
                    "/tmp/moncloa-reference.html",
                    "fixture-sha",
                    "text/html",
                    1234,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def test_sources_payload_exposes_waived_and_unwaived_mismatch_fields(self) -> None:
        tracker_md = """# Tracker

| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |
|---|---|---|---|---|
| Accion ejecutiva (Consejo de Ministros) | Ejecutivo | La Moncloa: referencias + RSS | PARTIAL | Contrato en ajuste |
"""
        waivers = {
            "waivers": [
                {
                    "source_id": "moncloa_referencias",
                    "reason": "temporary reconciliation window",
                    "owner": "L3",
                    "expires_on": "2099-01-01",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "status.db"
            tracker_path = Path(td) / "tracker.md"
            waivers_path = Path(td) / "waivers.json"
            tracker_path.write_text(tracker_md, encoding="utf-8")
            waivers_path.write_text(json.dumps(waivers, ensure_ascii=True), encoding="utf-8")
            self._seed_sources_and_runs(db_path)

            old_tracker_path = g.TRACKER_PATH
            old_waivers_path = g.MISMATCH_WAIVERS_PATH
            try:
                g._load_tracker_items_cached.cache_clear()
                g.TRACKER_PATH = tracker_path
                g.MISMATCH_WAIVERS_PATH = waivers_path
                payload = g.build_sources_status_payload(db_path)
            finally:
                g.TRACKER_PATH = old_tracker_path
                g.MISMATCH_WAIVERS_PATH = old_waivers_path
                g._load_tracker_items_cached.cache_clear()

        by_source = {str(row.get("source_id")): row for row in payload.get("sources", [])}

        moncloa = by_source["moncloa_referencias"]
        self.assertEqual(moncloa["tracker"]["status"], "PARTIAL")
        self.assertEqual(moncloa["sql_status"], "DONE")
        self.assertEqual(moncloa["mismatch_state"], "WAIVED_MISMATCH")
        self.assertTrue(moncloa["mismatch_waived"])
        self.assertEqual(moncloa["waiver_expiry"], "2099-01-01")

        moncloa_rss = by_source["moncloa_rss_referencias"]
        self.assertEqual(moncloa_rss["tracker"]["status"], "PARTIAL")
        self.assertEqual(moncloa_rss["mismatch_state"], "MISMATCH")
        self.assertFalse(moncloa_rss["mismatch_waived"])
        self.assertEqual(moncloa_rss["waiver_expiry"], "")

        untracked = by_source["congreso_votaciones"]
        self.assertEqual(untracked["tracker"]["status"], "")
        self.assertEqual(untracked["mismatch_state"], "UNTRACKED")
        self.assertFalse(untracked["mismatch_waived"])
        self.assertEqual(untracked["waiver_expiry"], "")

        summary_tracker = payload.get("summary", {}).get("tracker", {})
        self.assertEqual(int(summary_tracker.get("waived_mismatch", 0)), 1)
        self.assertGreaterEqual(int(summary_tracker.get("mismatch", 0)), 1)


if __name__ == "__main__":
    unittest.main()
