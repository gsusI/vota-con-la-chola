from __future__ import annotations

import csv
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

from scripts import e2e_tracker_status as tracker


TRACKER_FIXTURE = """# Tracker

| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |
|---|---|---|---|---|
| Accion ejecutiva (Consejo de Ministros) | Ejecutivo | La Moncloa: referencias + RSS | TODO | Scraper + normalizacion; validar acuerdos y normas contra BOE cuando exista publicacion |
| Representantes y mandatos (Parlamento de Navarra) | Autonomico | Parlamento de Navarra: parlamentarios forales (fichas HTML) | PARTIAL | Bloqueado por Cloudflare challenge/403 en `--strict-network`; requiere captura manual Playwright + `--from-file <dir>` |
"""


class TestE2ETrackerStatusTrackerRules(unittest.TestCase):
    @staticmethod
    def _create_min_tracker_db(db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE sources (
                  source_id TEXT PRIMARY KEY
                );

                CREATE TABLE ingestion_runs (
                  run_id INTEGER PRIMARY KEY,
                  source_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  records_loaded INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE raw_fetches (
                  run_id INTEGER NOT NULL,
                  source_url TEXT
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def test_parse_tracker_rows_maps_moncloa_to_both_source_ids(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tracker_path = Path(td) / "tracker.md"
            tracker_path.write_text(TRACKER_FIXTURE, encoding="utf-8")

            rows = tracker.parse_tracker_rows(tracker_path)

            self.assertIn("moncloa_referencias", rows)
            self.assertIn("moncloa_rss_referencias", rows)
            self.assertEqual(rows["moncloa_referencias"]["status"], "TODO")
            self.assertEqual(rows["moncloa_rss_referencias"]["status"], "TODO")

    def test_default_waivers_path_is_canonical_registry(self) -> None:
        self.assertEqual(str(tracker.DEFAULT_WAIVERS), "docs/etl/mismatch-waivers.json")

    def test_parse_tracker_rows_maps_marco_legal_electoral_to_boe_source_id(self) -> None:
        tracker_md = """# Tracker

| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |
|---|---|---|---|---|
| Marco legal electoral | Legal | Fuente legal oficial (texto libre) | PARTIAL | Contrato en ajuste |
"""
        with tempfile.TemporaryDirectory() as td:
            tracker_path = Path(td) / "tracker.md"
            tracker_path.write_text(tracker_md, encoding="utf-8")

            rows = tracker.parse_tracker_rows(tracker_path)

            self.assertIn("boe_api_legal", rows)
            self.assertEqual(rows["boe_api_legal"]["status"], "PARTIAL")

    def test_parse_tracker_rows_maps_money_and_outcomes_rows_to_expected_source_ids(self) -> None:
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
        with tempfile.TemporaryDirectory() as td:
            tracker_path = Path(td) / "tracker.md"
            tracker_path.write_text(tracker_md, encoding="utf-8")

            rows = tracker.parse_tracker_rows(tracker_path)

            self.assertIn("placsp_autonomico", rows)
            self.assertIn("bdns_autonomico", rows)
            self.assertIn("placsp_sindicacion", rows)
            self.assertIn("bdns_api_subvenciones", rows)
            self.assertIn("eurostat_sdmx", rows)
            self.assertIn("bde_series_api", rows)
            self.assertIn("aemet_opendata_series", rows)

    def test_infer_tracker_source_ids_maps_money_outcomes_from_fuente_hints(self) -> None:
        self.assertEqual(
            tracker._infer_tracker_source_ids("Tipo desconocido", "PLACSP: sindicación/ATOM (CODICE)"),
            ["placsp_sindicacion"],
        )
        self.assertEqual(
            tracker._infer_tracker_source_ids("Tipo desconocido", "BDNS/SNPSAP: API"),
            ["bdns_api_subvenciones"],
        )
        self.assertEqual(
            tracker._infer_tracker_source_ids("Tipo desconocido", "Eurostat (API/SDMX)"),
            ["eurostat_sdmx"],
        )
        self.assertEqual(
            tracker._infer_tracker_source_ids("Tipo desconocido", "Banco de España (API series)"),
            ["bde_series_api"],
        )
        self.assertEqual(
            tracker._infer_tracker_source_ids("Tipo desconocido", "Banco de Espana (API series)"),
            ["bde_series_api"],
        )
        self.assertEqual(
            tracker._infer_tracker_source_ids("Tipo desconocido", "AEMET OpenData"),
            ["aemet_opendata_series"],
        )

    def test_blocked_guard_keeps_navarra_partial_when_latest_load_is_zero(self) -> None:
        metrics = {
            "runs_total": 6,
            "max_loaded_network": 50,
            "max_loaded_any": 50,
            "last_loaded": 0,
        }

        sql_when_unblocked = tracker.sql_status_from_metrics(metrics, tracker_blocked=False)
        sql_when_blocked = tracker.sql_status_from_metrics(metrics, tracker_blocked=True)

        self.assertEqual(sql_when_unblocked, "DONE")
        self.assertEqual(sql_when_blocked, "PARTIAL")

    def test_cli_fail_on_mismatch_returns_nonzero(self) -> None:
        tracker_md = """# Tracker

| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |
|---|---|---|---|---|
| Representantes y mandatos (Congreso) | Nacional | Congreso OpenData Diputados | PARTIAL | test |
"""
        with tempfile.TemporaryDirectory() as td:
            tracker_path = Path(td) / "tracker.md"
            tracker_path.write_text(tracker_md, encoding="utf-8")
            db_path = Path(td) / "tracker.db"
            self._create_min_tracker_db(db_path)

            conn = sqlite3.connect(db_path)
            try:
                conn.execute("INSERT INTO sources (source_id) VALUES ('congreso_diputados')")
                conn.execute(
                    "INSERT INTO ingestion_runs (run_id, source_id, status, records_loaded) VALUES (1, 'congreso_diputados', 'ok', 5)"
                )
                conn.execute("INSERT INTO raw_fetches (run_id, source_url) VALUES (1, 'https://example.invalid/run')")
                conn.commit()
            finally:
                conn.close()

            argv = [
                "e2e_tracker_status.py",
                "--db",
                str(db_path),
                "--tracker",
                str(tracker_path),
                "--waivers",
                str(Path(td) / "waivers-none.json"),
                "--fail-on-mismatch",
            ]
            with mock.patch.object(sys, "argv", argv):
                exit_code = tracker.main()

            self.assertEqual(exit_code, 1)

    def test_load_mismatch_waivers_splits_active_and_expired(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            waivers_path = Path(td) / "waivers.json"
            waivers_path.write_text(
                json.dumps(
                    {
                        "waivers": [
                            {
                                "source_id": "moncloa_referencias",
                                "reason": "blocked mismatch policy",
                                "owner": "L2",
                                "expires_on": "2026-02-20",
                            },
                            {
                                "source_id": "parlamento_navarra_parlamentarios_forales",
                                "reason": "blocked mismatch policy",
                                "owner": "L2",
                                "expires_on": "2026-02-10",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            active, expired = tracker.load_mismatch_waivers(waivers_path, as_of_date=date(2026, 2, 16))
            self.assertIn("moncloa_referencias", active)
            self.assertIn("parlamento_navarra_parlamentarios_forales", expired)

    def test_cli_normalize_run_snapshot_converts_legacy_metric_value(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            legacy_path = Path(td) / "legacy_run_snapshot.csv"
            legacy_path.write_text(
                "\n".join(
                    [
                        "metric,value",
                        "source_id,placsp_autonomico",
                        "mode,strict-network",
                        "exit_code,0",
                        "run_records_loaded,106",
                        "snapshot,20260217",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            normalized_path = Path(td) / "normalized_run_snapshot.csv"

            argv = [
                "e2e_tracker_status.py",
                "--normalize-run-snapshot-in",
                str(legacy_path),
                "--normalize-run-snapshot-out",
                str(normalized_path),
            ]
            with mock.patch.object(sys, "argv", argv):
                exit_code = tracker.main()

            self.assertEqual(exit_code, 0)
            self.assertTrue(normalized_path.exists())

            with normalized_path.open("r", encoding="utf-8", newline="") as fh:
                row = next(csv.DictReader(fh))
            self.assertEqual(row["source_id"], "placsp_autonomico")
            self.assertEqual(row["mode"], "strict-network")
            self.assertEqual(row["run_records_loaded"], "106")
            self.assertEqual(row["snapshot_date"], "2026-02-17")

    def test_cli_fail_on_mismatch_accepts_active_waiver(self) -> None:
        tracker_md = """# Tracker

| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |
|---|---|---|---|---|
| Representantes y mandatos (Congreso) | Nacional | Congreso OpenData Diputados | PARTIAL | test |
"""
        with tempfile.TemporaryDirectory() as td:
            tracker_path = Path(td) / "tracker.md"
            tracker_path.write_text(tracker_md, encoding="utf-8")
            db_path = Path(td) / "tracker.db"
            self._create_min_tracker_db(db_path)

            conn = sqlite3.connect(db_path)
            try:
                conn.execute("INSERT INTO sources (source_id) VALUES ('congreso_diputados')")
                conn.execute(
                    "INSERT INTO ingestion_runs (run_id, source_id, status, records_loaded) VALUES (1, 'congreso_diputados', 'ok', 5)"
                )
                conn.execute("INSERT INTO raw_fetches (run_id, source_url) VALUES (1, 'https://example.invalid/run')")
                conn.commit()
            finally:
                conn.close()

            waivers_path = Path(td) / "waivers.json"
            waivers_path.write_text(
                json.dumps(
                    {
                        "waivers": [
                            {
                                "source_id": "congreso_diputados",
                                "reason": "temporary policy waiver",
                                "owner": "L2",
                                "expires_on": "2026-02-20",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            argv = [
                "e2e_tracker_status.py",
                "--db",
                str(db_path),
                "--tracker",
                str(tracker_path),
                "--waivers",
                str(waivers_path),
                "--as-of-date",
                "2026-02-16",
                "--fail-on-mismatch",
            ]
            with mock.patch.object(sys, "argv", argv):
                exit_code = tracker.main()

            self.assertEqual(exit_code, 0)

    def test_cli_fail_on_mismatch_fails_with_expired_waiver(self) -> None:
        tracker_md = """# Tracker

| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |
|---|---|---|---|---|
| Representantes y mandatos (Congreso) | Nacional | Congreso OpenData Diputados | PARTIAL | test |
"""
        with tempfile.TemporaryDirectory() as td:
            tracker_path = Path(td) / "tracker.md"
            tracker_path.write_text(tracker_md, encoding="utf-8")
            db_path = Path(td) / "tracker.db"
            self._create_min_tracker_db(db_path)

            conn = sqlite3.connect(db_path)
            try:
                conn.execute("INSERT INTO sources (source_id) VALUES ('congreso_diputados')")
                conn.execute(
                    "INSERT INTO ingestion_runs (run_id, source_id, status, records_loaded) VALUES (1, 'congreso_diputados', 'ok', 5)"
                )
                conn.execute("INSERT INTO raw_fetches (run_id, source_url) VALUES (1, 'https://example.invalid/run')")
                conn.commit()
            finally:
                conn.close()

            waivers_path = Path(td) / "waivers.json"
            waivers_path.write_text(
                json.dumps(
                    {
                        "waivers": [
                            {
                                "source_id": "congreso_diputados",
                                "reason": "temporary policy waiver",
                                "owner": "L2",
                                "expires_on": "2026-02-15",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            argv = [
                "e2e_tracker_status.py",
                "--db",
                str(db_path),
                "--tracker",
                str(tracker_path),
                "--waivers",
                str(waivers_path),
                "--as-of-date",
                "2026-02-16",
                "--fail-on-mismatch",
            ]
            with mock.patch.object(sys, "argv", argv):
                exit_code = tracker.main()

            self.assertEqual(exit_code, 1)

    def test_done_zero_real_enforcement_not_weakened_by_waiver(self) -> None:
        tracker_md = """# Tracker

| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |
|---|---|---|---|---|
| Representantes y mandatos (Congreso) | Nacional | Congreso OpenData Diputados | DONE | test |
"""
        with tempfile.TemporaryDirectory() as td:
            tracker_path = Path(td) / "tracker.md"
            tracker_path.write_text(tracker_md, encoding="utf-8")
            db_path = Path(td) / "tracker.db"
            self._create_min_tracker_db(db_path)

            conn = sqlite3.connect(db_path)
            try:
                conn.execute("INSERT INTO sources (source_id) VALUES ('congreso_diputados')")
                # file-backed run only: max_net stays 0 while max_any > 0
                conn.execute(
                    "INSERT INTO ingestion_runs (run_id, source_id, status, records_loaded) VALUES (1, 'congreso_diputados', 'ok', 5)"
                )
                conn.execute("INSERT INTO raw_fetches (run_id, source_url) VALUES (1, 'file:///tmp/sample.json')")
                conn.commit()
            finally:
                conn.close()

            waivers_path = Path(td) / "waivers.json"
            waivers_path.write_text(
                json.dumps(
                    {
                        "waivers": [
                            {
                                "source_id": "congreso_diputados",
                                "reason": "temporary policy waiver",
                                "owner": "L2",
                                "expires_on": "2026-02-20",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            argv = [
                "e2e_tracker_status.py",
                "--db",
                str(db_path),
                "--tracker",
                str(tracker_path),
                "--waivers",
                str(waivers_path),
                "--as-of-date",
                "2026-02-16",
                "--fail-on-mismatch",
                "--fail-on-done-zero-real",
            ]
            with mock.patch.object(sys, "argv", argv):
                exit_code = tracker.main()

            self.assertEqual(exit_code, 1)
