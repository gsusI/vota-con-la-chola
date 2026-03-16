from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.report_senado_waf_block_profile import build_waf_block_profile, main


class TestReportSenadoWafBlockProfile(unittest.TestCase):
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

    def test_build_waf_profile_groups_cohorts_and_prioritizes_zero_doc(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "waf.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO parl_initiatives(initiative_id, source_id) VALUES (?, ?)",
                    [
                        ("senado:leg14:exp:622/000701", "senado_iniciativas"),
                        ("senado:leg14:exp:626/000702", "senado_iniciativas"),
                        ("senado:leg14:exp:622/000703", "senado_iniciativas"),  # unlinked
                    ],
                )
                conn.executemany(
                    "INSERT INTO parl_vote_event_initiatives(vote_event_id, initiative_id) VALUES (?, ?)",
                    [
                        ("vote-a", "senado:leg14:exp:622/000701"),
                        ("vote-b", "senado:leg14:exp:626/000702"),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            "senado:leg14:exp:622/000701",
                            "bocg",
                            "https://www.senado.es/legis14/expedientes/622/enmiendas/global_enmiendas_vetos_14_622000701.xml",
                            None,
                        ),
                        (
                            "senado:leg14:exp:622/000701",
                            "bocg",
                            "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=622&numEx=000701",
                            None,
                        ),
                        (
                            "senado:leg14:exp:622/000701",
                            "bocg",
                            "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=622&numEx=000701",
                            701,
                        ),
                        (
                            "senado:leg14:exp:626/000702",
                            "bocg",
                            "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=626&numEx=000702",
                            None,
                        ),
                        (
                            "senado:leg14:exp:622/000703",
                            "bocg",
                            "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=622&numEx=000703",
                            None,
                        ),
                    ],
                )
                conn.execute(
                    "INSERT INTO text_documents(source_record_pk, source_id) VALUES (?, ?)",
                    (701, "parl_initiative_docs"),
                )
                conn.executemany(
                    """
                    INSERT INTO document_fetches(doc_url, source_id, last_http_status, attempts, last_error, last_attempt_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "https://www.senado.es/legis14/expedientes/622/enmiendas/global_enmiendas_vetos_14_622000701.xml",
                            "parl_initiative_docs",
                            404,
                            3,
                            "HTTPError: HTTP Error 404: Not Found",
                            "2026-02-27T00:00:01Z",
                        ),
                        (
                            "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=622&numEx=000701",
                            "parl_initiative_docs",
                            403,
                            5,
                            "HTTPStatusError: HTTP 403 (playwright)",
                            "2026-02-27T00:00:02Z",
                        ),
                        (
                            "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=626&numEx=000702",
                            "parl_initiative_docs",
                            403,
                            4,
                            "HTTPError: HTTP Error 403: Forbidden",
                            "2026-02-27T00:00:03Z",
                        ),
                        (
                            "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=622&numEx=000703",
                            "parl_initiative_docs",
                            403,
                            4,
                            "HTTPError: HTTP Error 403: Forbidden",
                            "2026-02-27T00:00:04Z",
                        ),
                    ],
                )
                conn.commit()

                report = build_waf_block_profile(
                    conn,
                    initiative_source_id="senado_iniciativas",
                    doc_source_id="parl_initiative_docs",
                    only_linked_to_votes=True,
                    sample_limit=10,
                )
                totals = report.get("totals") or {}
                self.assertEqual(int(totals.get("missing_urls") or 0), 2)
                self.assertEqual(int(totals.get("blocked_403_urls") or 0), 2)
                self.assertEqual(int(totals.get("zero_doc_initiatives") or 0), 1)

                cohorts = report.get("cohorts") or []
                self.assertEqual(len(cohorts), 2)
                cohort_keys = {str(c.get("cohort") or "") for c in cohorts}
                self.assertIn("leg14:tipo622", cohort_keys)
                self.assertIn("leg14:tipo626", cohort_keys)

                priority = report.get("zero_doc_priority") or []
                self.assertEqual(len(priority), 1)
                self.assertEqual(str(priority[0].get("initiative_id") or ""), "senado:leg14:exp:626/000702")
                self.assertEqual(str(priority[0].get("top_method_hint") or ""), "http")
                self.assertEqual(str(report.get("status") or ""), "ok")
            finally:
                conn.close()

    def test_main_strict_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "waf_strict.db"
            out_path = td_path / "report.json"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO parl_initiatives(initiative_id, source_id) VALUES (?, ?)",
                    ("senado:leg14:exp:622/000801", "senado_iniciativas"),
                )
                conn.execute(
                    "INSERT INTO parl_vote_event_initiatives(vote_event_id, initiative_id) VALUES (?, ?)",
                    ("vote-x", "senado:leg14:exp:622/000801"),
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        "senado:leg14:exp:622/000801",
                        "bocg",
                        "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=622&numEx=000801",
                        None,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO document_fetches(doc_url, source_id, last_http_status, attempts, last_error, last_attempt_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=622&numEx=000801",
                        "parl_initiative_docs",
                        500,
                        2,
                        "HTTPError: HTTP Error 500: Internal Server Error",
                        "2026-02-27T00:10:00Z",
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            rc = main(
                [
                    "--db",
                    str(db_path),
                    "--strict",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 4)
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(str(payload.get("status") or ""), "degraded")
            checks = payload.get("checks") or {}
            self.assertFalse(bool(checks.get("has_403_signal")))


if __name__ == "__main__":
    unittest.main()
