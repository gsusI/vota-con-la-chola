from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.export_missing_initiative_doc_urls import main


class TestExportMissingInitiativeDocUrls(unittest.TestCase):
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
            CREATE TABLE text_documents (
              source_record_pk INTEGER,
              source_id TEXT
            );
            CREATE TABLE document_fetches (
              doc_url TEXT,
              last_http_status INTEGER,
              attempts INTEGER,
              fetched_ok INTEGER,
              last_attempt_at TEXT
            );
            """
        )
        return conn

    def test_only_actionable_missing_excludes_redundant_senado_global_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "missing_urls.db"
            out_path = td_path / "queue.csv"

            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO parl_initiatives(initiative_id, source_id) VALUES (?, ?)",
                    [
                        ("senado:leg15:exp:600/000001", "senado_iniciativas"),
                        ("senado:leg15:exp:600/000002", "senado_iniciativas"),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            "senado:leg15:exp:600/000001",
                            "bocg",
                            "https://www.senado.es/legis15/expedientes/600/enmiendas/global_enmiendas_vetos_15_600000001.xml",
                            None,
                        ),
                        (
                            "senado:leg15:exp:600/000001",
                            "bocg",
                            "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=600&numEx=000001",
                            101,
                        ),
                        (
                            "senado:leg15:exp:600/000002",
                            "bocg",
                            "https://www.senado.es/legis15/expedientes/600/enmiendas/global_enmiendas_vetos_15_600000002.xml",
                            None,
                        ),
                    ],
                )
                conn.execute(
                    "INSERT INTO text_documents(source_record_pk, source_id) VALUES (101, 'parl_initiative_docs')"
                )
                conn.commit()
            finally:
                conn.close()

            exit_code = main(
                [
                    "--db",
                    str(db_path),
                    "--initiative-source-ids",
                    "senado_iniciativas",
                    "--only-actionable-missing",
                    "--format",
                    "csv",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(exit_code, 0)

            with out_path.open("r", encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["initiative_id"], "senado:leg15:exp:600/000002")

    def test_strict_empty_returns_nonzero_when_actionable_rows_exist(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "strict_nonempty.db"
            out_path = td_path / "queue.txt"

            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO parl_initiatives(initiative_id, source_id) VALUES ('senado:leg15:exp:600/000009', 'senado_iniciativas')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES ('senado:leg15:exp:600/000009', 'bocg', 'https://www.senado.es/legis15/expedientes/600/enmiendas/global_enmiendas_vetos_15_600000009.xml', NULL)
                    """
                )
                conn.commit()
            finally:
                conn.close()

            exit_code = main(
                [
                    "--db",
                    str(db_path),
                    "--initiative-source-ids",
                    "senado_iniciativas",
                    "--only-actionable-missing",
                    "--strict-empty",
                    "--format",
                    "txt",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(exit_code, 4)

    def test_strict_empty_passes_when_filtered_queue_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "strict_empty.db"
            out_path = td_path / "queue.txt"

            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO parl_initiatives(initiative_id, source_id) VALUES ('senado:leg15:exp:600/000011', 'senado_iniciativas')"
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            "senado:leg15:exp:600/000011",
                            "bocg",
                            "https://www.senado.es/legis15/expedientes/600/enmiendas/global_enmiendas_vetos_15_600000011.xml",
                            None,
                        ),
                        (
                            "senado:leg15:exp:600/000011",
                            "bocg",
                            "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=600&numEx=000011",
                            111,
                        ),
                    ],
                )
                conn.execute(
                    "INSERT INTO text_documents(source_record_pk, source_id) VALUES (111, 'parl_initiative_docs')"
                )
                conn.commit()
            finally:
                conn.close()

            exit_code = main(
                [
                    "--db",
                    str(db_path),
                    "--initiative-source-ids",
                    "senado_iniciativas",
                    "--only-actionable-missing",
                    "--strict-empty",
                    "--format",
                    "txt",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(out_path.read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()

