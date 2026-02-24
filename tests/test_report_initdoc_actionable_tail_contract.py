from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.report_initdoc_actionable_tail_contract import build_actionable_report, main


class TestReportInitdocActionableTailContract(unittest.TestCase):
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

    def test_build_actionable_report_splits_redundant_and_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "gate.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO parl_initiatives(initiative_id, source_id) VALUES (?, ?)",
                    [
                        ("senado:leg15:exp:600/000701", "senado_iniciativas"),
                        ("senado:leg15:exp:600/000702", "senado_iniciativas"),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            "senado:leg15:exp:600/000701",
                            "bocg",
                            "https://www.senado.es/legis15/expedientes/600/enmiendas/global_enmiendas_vetos_15_600000701.xml",
                            None,
                        ),
                        (
                            "senado:leg15:exp:600/000701",
                            "bocg",
                            "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=600&numEx=000701",
                            701,
                        ),
                        (
                            "senado:leg15:exp:600/000702",
                            "bocg",
                            "https://www.senado.es/legis15/expedientes/600/enmiendas/global_enmiendas_vetos_15_600000702.xml",
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
                    INSERT INTO document_fetches(doc_url, last_http_status, attempts, fetched_ok, last_attempt_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "https://www.senado.es/legis15/expedientes/600/enmiendas/global_enmiendas_vetos_15_600000701.xml",
                            404,
                            4,
                            0,
                            "2026-02-22T00:00:00Z",
                        ),
                        (
                            "https://www.senado.es/legis15/expedientes/600/enmiendas/global_enmiendas_vetos_15_600000702.xml",
                            404,
                            3,
                            0,
                            "2026-02-22T00:00:00Z",
                        ),
                    ],
                )
                conn.commit()

                report = build_actionable_report(
                    conn,
                    source_ids=["senado_iniciativas"],
                    sample_limit=10,
                )
                self.assertEqual(int(report["total_missing"]), 2)
                self.assertEqual(int(report["redundant_missing"]), 1)
                self.assertEqual(int(report["actionable_missing"]), 1)
                self.assertFalse(bool(report["checks"]["actionable_queue_empty"]))
                self.assertEqual(len(report["actionable_sample"]), 1)
            finally:
                conn.close()

    def test_main_strict_exit_codes_and_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "gate_strict.db"
            out_path = td_path / "report.json"

            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO parl_initiatives(initiative_id, source_id) VALUES (?, ?)",
                    [
                        ("senado:leg15:exp:600/000801", "senado_iniciativas"),
                    ],
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        "senado:leg15:exp:600/000801",
                        "bocg",
                        "https://www.senado.es/legis15/expedientes/600/enmiendas/global_enmiendas_vetos_15_600000801.xml",
                        None,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            rc_fail = main(
                [
                    "--db",
                    str(db_path),
                    "--initiative-source-ids",
                    "senado_iniciativas",
                    "--strict",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc_fail, 4)
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(int(payload["actionable_missing"]), 1)

            conn2 = sqlite3.connect(str(db_path))
            try:
                conn2.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        "senado:leg15:exp:600/000801",
                        "bocg",
                        "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=600&numEx=000801",
                        801,
                    ),
                )
                conn2.execute(
                    "INSERT INTO text_documents(source_record_pk, source_id) VALUES (?, ?)",
                    (801, "parl_initiative_docs"),
                )
                conn2.commit()
            finally:
                conn2.close()

            rc_pass = main(
                [
                    "--db",
                    str(db_path),
                    "--initiative-source-ids",
                    "senado_iniciativas",
                    "--strict",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc_pass, 0)
            payload2 = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(int(payload2["actionable_missing"]), 0)
            self.assertEqual(int(payload2["redundant_missing"]), 1)


if __name__ == "__main__":
    unittest.main()

