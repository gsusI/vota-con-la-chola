from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.export_senado_waf_cohort_packets import main


class TestExportSenadoWafCohortPackets(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE parl_initiatives (
              initiative_id TEXT PRIMARY KEY,
              source_id TEXT
            );
            CREATE TABLE parl_initiative_documents (
              initiative_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
              initiative_id TEXT,
              doc_kind TEXT,
              doc_url TEXT,
              source_record_pk INTEGER
            );
            CREATE TABLE parl_vote_event_initiatives (
              vote_event_id TEXT,
              initiative_id TEXT
            );
            CREATE TABLE text_documents (
              source_record_pk INTEGER,
              source_id TEXT
            );
            CREATE TABLE document_fetches (
              doc_url TEXT,
              source_id TEXT,
              last_http_status INTEGER,
              attempts INTEGER,
              last_error TEXT,
              last_attempt_at TEXT
            );
            """
        )
        return conn

    def test_exports_cohort_packets_and_excludes_redundant_global(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "packets.db"
            out_json = td_path / "packets.json"
            out_csv = td_path / "packets.csv"

            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO parl_initiatives(initiative_id, source_id) VALUES (?, ?)",
                    [
                        ("senado:leg14:exp:621/000001", "senado_iniciativas"),
                        ("senado:leg14:exp:622/000002", "senado_iniciativas"),
                        ("senado:leg10:exp:610/000003", "senado_iniciativas"),
                        ("senado:leg15:exp:623/000004", "senado_iniciativas"),  # unlinked
                    ],
                )
                conn.executemany(
                    "INSERT INTO parl_vote_event_initiatives(vote_event_id, initiative_id) VALUES (?, ?)",
                    [
                        ("vote-a", "senado:leg14:exp:621/000001"),
                        ("vote-b", "senado:leg14:exp:622/000002"),
                        ("vote-c", "senado:leg10:exp:610/000003"),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            "senado:leg14:exp:621/000001",
                            "bocg",
                            "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=621&numEx=000001",
                            None,
                        ),
                        (
                            "senado:leg14:exp:621/000001",
                            "bocg",
                            "https://www.senado.es/web/actividadparlamentaria/iniciativas/detalleiniciativa/index.html?legis=14&id1=621&id2=000001",
                            None,
                        ),
                        (
                            "senado:leg14:exp:622/000002",
                            "bocg",
                            "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=622&numEx=000002",
                            None,
                        ),
                        (
                            "senado:leg10:exp:610/000003",
                            "bocg",
                            "https://www.senado.es/legis10/expedientes/610/enmiendas/global_enmiendas_vetos_10_610000003.xml",
                            None,
                        ),
                        (
                            "senado:leg10:exp:610/000003",
                            "bocg",
                            "https://www.senado.es/web/ficopendataservlet?legis=10&tipoFich=3&tipoEx=610&numEx=000003",
                            9003,
                        ),
                        (
                            "senado:leg15:exp:623/000004",
                            "bocg",
                            "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=623&numEx=000004",
                            None,
                        ),
                    ],
                )
                conn.execute(
                    "INSERT INTO text_documents(source_record_pk, source_id) VALUES (?, ?)",
                    (9003, "parl_initiative_docs"),
                )
                conn.executemany(
                    """
                    INSERT INTO document_fetches(doc_url, source_id, last_http_status, attempts, last_error, last_attempt_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=621&numEx=000001",
                            "parl_initiative_docs",
                            403,
                            6,
                            "HTTPError: HTTP Error 403: Forbidden",
                            "2026-02-28T10:00:00Z",
                        ),
                        (
                            "https://www.senado.es/web/actividadparlamentaria/iniciativas/detalleiniciativa/index.html?legis=14&id1=621&id2=000001",
                            "parl_initiative_docs",
                            500,
                            2,
                            "HTTPError: HTTP Error 500: Internal Server Error",
                            "2026-02-28T10:05:00Z",
                        ),
                        (
                            "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=622&numEx=000002",
                            "parl_initiative_docs",
                            403,
                            4,
                            "HTTPStatusError: HTTP 403 (playwright)",
                            "2026-02-28T10:10:00Z",
                        ),
                        (
                            "https://www.senado.es/legis10/expedientes/610/enmiendas/global_enmiendas_vetos_10_610000003.xml",
                            "parl_initiative_docs",
                            404,
                            3,
                            "HTTPError: HTTP Error 404: Not Found",
                            "2026-02-28T10:15:00Z",
                        ),
                        (
                            "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=623&numEx=000004",
                            "parl_initiative_docs",
                            403,
                            1,
                            "HTTPError: HTTP Error 403: Forbidden",
                            "2026-02-28T10:20:00Z",
                        ),
                    ],
                )
                conn.commit()
            finally:
                conn.close()

            rc = main(
                [
                    "--db",
                    str(db_path),
                    "--cohort-top-n",
                    "2",
                    "--max-urls-per-cohort",
                    "2",
                    "--max-total-rows",
                    "10",
                    "--max-zero-doc-rows",
                    "5",
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                    "--strict",
                ]
            )
            self.assertEqual(rc, 0)

            summary = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(str(summary.get("status") or ""), "ok")
            totals = summary.get("totals") or {}
            self.assertEqual(int(totals.get("missing_urls") or 0), 3)
            self.assertEqual(int(totals.get("selected_cohorts_total") or 0), 2)
            self.assertGreaterEqual(int(totals.get("packet_rows_total") or 0), 2)

            with out_csv.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertTrue(rows)
            urls = [str(r.get("doc_url") or "") for r in rows]
            self.assertFalse(any("global_enmiendas_vetos_" in u for u in urls))
            self.assertFalse(any("numEx=000004" in u for u in urls))  # unlinked initiative excluded

    def test_strict_fails_when_queue_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "empty.db"
            out_json = td_path / "empty.json"
            out_csv = td_path / "empty.csv"
            conn = self._open_db(db_path)
            conn.close()

            rc = main(
                [
                    "--db",
                    str(db_path),
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                    "--strict",
                ]
            )
            self.assertEqual(rc, 4)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(str(payload.get("status") or ""), "degraded")
            reasons = payload.get("strict_fail_reasons") or []
            self.assertIn("no_missing_urls", reasons)


if __name__ == "__main__":
    unittest.main()
