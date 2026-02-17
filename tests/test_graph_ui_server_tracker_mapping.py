from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from scripts import graph_ui_server as g


class TestGraphUiTrackerMapping(unittest.TestCase):
    def test_infer_tracker_source_ids_maps_moncloa_row(self) -> None:
        source_ids = g._infer_tracker_source_ids("La Moncloa: referencias + RSS")
        self.assertEqual(source_ids, ["moncloa_referencias", "moncloa_rss_referencias"])

    def test_infer_tracker_source_ids_maps_bde_hint_without_tilde(self) -> None:
        source_ids = g._infer_tracker_source_ids("Banco de Espana (API series)")
        self.assertEqual(source_ids, ["bde_series_api"])

    def test_load_tracker_items_sets_moncloa_source_ids(self) -> None:
        tracker_md = """# Tracker

| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |
|---|---|---|---|---|
| Accion ejecutiva (Consejo de Ministros) | Ejecutivo | La Moncloa: referencias + RSS | TODO | Scraper + normalizacion |
"""
        with tempfile.TemporaryDirectory() as td:
            tracker_path = Path(td) / "tracker.md"
            tracker_path.write_text(tracker_md, encoding="utf-8")

            g._load_tracker_items_cached.cache_clear()
            items = g.load_tracker_items(tracker_path)
            g._load_tracker_items_cached.cache_clear()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["source_ids"], ["moncloa_referencias", "moncloa_rss_referencias"])

    def test_infer_tracker_source_ids_maps_marco_legal_to_boe_source(self) -> None:
        source_ids = g._infer_tracker_source_ids(
            "Fuente legal oficial (texto libre)",
            tipo_dato="Marco legal electoral",
        )
        self.assertEqual(source_ids, ["boe_api_legal"])

    def test_load_tracker_items_sets_boe_source_ids(self) -> None:
        tracker_md = """# Tracker

| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |
|---|---|---|---|---|
| Marco legal electoral | Legal | Fuente legal oficial (texto libre) | PARTIAL | Contrato en ajuste |
"""
        with tempfile.TemporaryDirectory() as td:
            tracker_path = Path(td) / "tracker.md"
            tracker_path.write_text(tracker_md, encoding="utf-8")

            g._load_tracker_items_cached.cache_clear()
            items = g.load_tracker_items(tracker_path)
            g._load_tracker_items_cached.cache_clear()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["source_ids"], ["boe_api_legal"])

    def test_boe_payload_exposes_tracker_and_mismatch_fields_after_mapping(self) -> None:
        tracker_md = """# Tracker

| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |
|---|---|---|---|---|
| Marco legal electoral | Legal | Fuente legal oficial (texto libre) | PARTIAL | Contrato en ajuste |
"""
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "status.db"
            tracker_path = Path(td) / "tracker.md"
            tracker_path.write_text(tracker_md, encoding="utf-8")

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                now_iso = "2026-02-16T10:00:00Z"
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
                        "boe_api_legal",
                        "BOE API legal",
                        "nacional",
                        "https://www.boe.es/",
                        "xml",
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
                        "boe_api_legal",
                        now_iso,
                        now_iso,
                        "https://www.boe.es/",
                        "/tmp/boe.xml",
                        now_iso,
                        3,
                        3,
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
                        "boe_api_legal",
                        "https://www.boe.es/",
                        now_iso,
                        "/tmp/boe.xml",
                        "fixture-sha",
                        "application/xml",
                        1234,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            old_tracker_path = g.TRACKER_PATH
            old_waivers_path = g.MISMATCH_WAIVERS_PATH
            try:
                g._load_tracker_items_cached.cache_clear()
                g.TRACKER_PATH = tracker_path
                g.MISMATCH_WAIVERS_PATH = Path(td) / "waivers-missing.json"
                payload = g.build_sources_status_payload(db_path)
            finally:
                g.TRACKER_PATH = old_tracker_path
                g.MISMATCH_WAIVERS_PATH = old_waivers_path
                g._load_tracker_items_cached.cache_clear()

        by_source = {str(row.get("source_id")): row for row in payload.get("sources", [])}
        boe = by_source["boe_api_legal"]
        self.assertEqual(boe["tracker"]["status"], "PARTIAL")
        self.assertEqual(boe["sql_status"], "DONE")
        self.assertEqual(boe["mismatch_state"], "MISMATCH")
        self.assertFalse(boe["mismatch_waived"])
        self.assertEqual(boe["waiver_expiry"], "")

    def test_load_tracker_items_maps_money_and_outcomes_rows(self) -> None:
        tracker_md = """# Tracker

| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |
|---|---|---|---|---|
| Contratación autonómica (piloto 3 CCAA) | Dinero | PLACSP (filtrado por órganos autonómicos) | TODO | pendiente |
| Subvenciones autonómicas (piloto 3 CCAA) | Dinero | BDNS/SNPSAP (filtrado por órgano convocante/territorio) | TODO | pendiente |
| Contratacion publica (Espana) | Dinero | PLACSP: sindicación/ATOM (CODICE) | TODO | pendiente |
| Subvenciones y ayudas (Espana) | Dinero | BDNS/SNPSAP: API | TODO | pendiente |
| Indicadores (outcomes): Eurostat | Outcomes | Eurostat (API/SDMX) | TODO | pendiente |
| Indicadores (confusores): Banco de Espana | Outcomes | Banco de España (API series) | TODO | pendiente |
| Indicadores (confusores): AEMET | Outcomes | AEMET OpenData | TODO | pendiente |
"""
        expected = {
            "placsp_autonomico",
            "bdns_autonomico",
            "placsp_sindicacion",
            "bdns_api_subvenciones",
            "eurostat_sdmx",
            "bde_series_api",
            "aemet_opendata_series",
        }
        with tempfile.TemporaryDirectory() as td:
            tracker_path = Path(td) / "tracker.md"
            tracker_path.write_text(tracker_md, encoding="utf-8")

            g._load_tracker_items_cached.cache_clear()
            items = g.load_tracker_items(tracker_path)
            g._load_tracker_items_cached.cache_clear()

        got: set[str] = set()
        for item in items:
            got.update(str(sid) for sid in (item.get("source_ids") or []))
        self.assertTrue(expected.issubset(got))

    def test_payload_exposes_money_outcomes_tracker_status_not_untracked(self) -> None:
        tracker_md = """# Tracker

| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |
|---|---|---|---|---|
| Contratación autonómica (piloto 3 CCAA) | Dinero | PLACSP (filtrado por órganos autonómicos) | TODO | pendiente |
| Subvenciones autonómicas (piloto 3 CCAA) | Dinero | BDNS/SNPSAP (filtrado por órgano convocante/territorio) | TODO | pendiente |
| Contratacion publica (Espana) | Dinero | PLACSP: sindicación/ATOM (CODICE) | TODO | pendiente |
| Subvenciones y ayudas (Espana) | Dinero | BDNS/SNPSAP: API | TODO | pendiente |
| Indicadores (outcomes): Eurostat | Outcomes | Eurostat (API/SDMX) | TODO | pendiente |
| Indicadores (confusores): Banco de Espana | Outcomes | Banco de España (API series) | TODO | pendiente |
| Indicadores (confusores): AEMET | Outcomes | AEMET OpenData | TODO | pendiente |
"""
        expected_sources = [
            "placsp_autonomico",
            "bdns_autonomico",
            "placsp_sindicacion",
            "bdns_api_subvenciones",
            "eurostat_sdmx",
            "bde_series_api",
            "aemet_opendata_series",
        ]

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "status.db"
            tracker_path = Path(td) / "tracker.md"
            tracker_path.write_text(tracker_md, encoding="utf-8")

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                conn.commit()
            finally:
                conn.close()

            old_tracker_path = g.TRACKER_PATH
            old_waivers_path = g.MISMATCH_WAIVERS_PATH
            try:
                g._load_tracker_items_cached.cache_clear()
                g.TRACKER_PATH = tracker_path
                g.MISMATCH_WAIVERS_PATH = Path(td) / "waivers-missing.json"
                payload = g.build_sources_status_payload(db_path)
            finally:
                g.TRACKER_PATH = old_tracker_path
                g.MISMATCH_WAIVERS_PATH = old_waivers_path
                g._load_tracker_items_cached.cache_clear()

        by_source = {str(row.get("source_id")): row for row in payload.get("sources", [])}
        for source_id in expected_sources:
            row = by_source[source_id]
            self.assertEqual(row["tracker"]["status"], "TODO")
            self.assertEqual(row["sql_status"], "TODO")
            self.assertEqual(row["mismatch_state"], "MATCH")
            self.assertFalse(row["mismatch_waived"])
            self.assertEqual(row["waiver_expiry"], "")
