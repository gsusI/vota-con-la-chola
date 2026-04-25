from __future__ import annotations

import sqlite3
import unittest

from scripts import export_elections_behavior_snapshot as elections_behavior


class TestExportElectionsBehaviorSnapshot(unittest.TestCase):
    def test_load_election_result_coverage_handles_missing_text_documents_table(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript(
                """
                CREATE TABLE infoelectoral_proceso_resultados (
                  proceso_id TEXT,
                  tipo_dato TEXT,
                  url TEXT,
                  source_record_pk INTEGER
                );
                INSERT INTO infoelectoral_proceso_resultados(proceso_id, tipo_dato, url, source_record_pk)
                VALUES
                  ('conv:1', 'municipal', 'https://results.test/1', 101),
                  ('conv:1', 'detalle', 'https://results.test/2', 102);
                """
            )

            coverage = elections_behavior.load_election_result_coverage(conn, ["conv:1"])
        finally:
            conn.close()

        self.assertEqual(
            coverage,
            {
                "conv:1": {
                    "result_rows": 2,
                    "types": ["detalle", "municipal"],
                    "urls": ["https://results.test/1", "https://results.test/2"],
                    "text_documents": 0,
                    "has_official_result_rows": True,
                }
            },
        )

    def test_load_election_result_coverage_counts_attached_text_documents(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript(
                """
                CREATE TABLE infoelectoral_proceso_resultados (
                  proceso_id TEXT,
                  tipo_dato TEXT,
                  url TEXT,
                  source_record_pk INTEGER
                );
                CREATE TABLE text_documents (
                  text_document_id INTEGER PRIMARY KEY,
                  source_record_pk INTEGER
                );
                INSERT INTO infoelectoral_proceso_resultados(proceso_id, tipo_dato, url, source_record_pk)
                VALUES
                  ('conv:2', 'general', 'https://results.test/a', 201),
                  ('conv:2', 'general', 'https://results.test/b', 202);
                INSERT INTO text_documents(text_document_id, source_record_pk)
                VALUES
                  (1, 201),
                  (2, 999);
                """
            )

            coverage = elections_behavior.load_election_result_coverage(conn, ["conv:2"])
        finally:
            conn.close()

        self.assertEqual(coverage["conv:2"]["result_rows"], 2)
        self.assertEqual(coverage["conv:2"]["text_documents"], 1)
        self.assertTrue(coverage["conv:2"]["has_official_result_rows"])


if __name__ == "__main__":
    unittest.main()
