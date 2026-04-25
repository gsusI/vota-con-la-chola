from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.export_initiative_measure_review_queue import (
    fetch_review_rows,
    sync_review_queue,
    write_evidence_bundle,
)


class TestExportInitiativeMeasureReviewQueue(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE sources (source_id TEXT PRIMARY KEY, name TEXT);
            CREATE TABLE parl_initiatives (
              initiative_id TEXT PRIMARY KEY,
              source_id TEXT,
              expediente TEXT,
              title TEXT,
              type TEXT,
              supertype TEXT,
              procedure_type TEXT,
              current_status TEXT,
              source_url TEXT
            );
            CREATE TABLE parl_vote_events (
              vote_event_id TEXT PRIMARY KEY,
              vote_date TEXT,
              source_id TEXT,
              title TEXT,
              subgroup_title TEXT,
              subgroup_text TEXT,
              expediente_text TEXT,
              totals_yes INTEGER,
              totals_no INTEGER,
              totals_abstain INTEGER
            );
            CREATE TABLE parl_vote_event_initiatives (
              parl_vote_event_initiative_id INTEGER PRIMARY KEY AUTOINCREMENT,
              vote_event_id TEXT,
              initiative_id TEXT
            );
            CREATE TABLE parl_initiative_documents (
              initiative_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
              initiative_id TEXT,
              doc_kind TEXT,
              doc_url TEXT,
              source_record_pk INTEGER
            );
            CREATE TABLE text_documents (
              text_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_id TEXT,
              source_url TEXT,
              source_record_pk INTEGER,
              content_type TEXT,
              raw_path TEXT,
              text_chars INTEGER
            );
            CREATE TABLE parl_initiative_measure_review_tasks (
              task_id TEXT PRIMARY KEY,
              initiative_id TEXT NOT NULL UNIQUE,
              source_id TEXT NOT NULL,
              review_reason TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              priority INTEGER NOT NULL DEFAULT 50,
              evidence_bundle_dir TEXT,
              note TEXT,
              raw_payload_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        conn.executemany(
            "INSERT INTO sources(source_id, name) VALUES (?, ?)",
            [
                ("congreso_iniciativas", "Congreso iniciativas"),
                ("congreso_votaciones", "Congreso votaciones"),
                ("parl_initiative_docs", "Docs"),
            ],
        )
        return conn

    def test_sync_and_bundle_export(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "measure_queue.db"
            raw_doc = Path(td) / "doc.xml"
            raw_doc.write_text(
                "<root><p>Proyecto de Ley de Movilidad Sostenible. Zonas de bajas emisiones y acceso a ciudades.</p></root>",
                encoding="utf-8",
            )
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(
                      initiative_id, source_id, expediente, title, type, supertype, procedure_type, current_status, source_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "i1",
                        "congreso_iniciativas",
                        "121/000009/0000",
                        "Proyecto de Ley de Movilidad Sostenible.",
                        "Proyecto de ley",
                        "Función legislativa",
                        "Urgente",
                        "Cerrado",
                        "https://example.org/i1",
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_events(
                      vote_event_id, vote_date, source_id, title, subgroup_title, subgroup_text, expediente_text, totals_yes, totals_no, totals_abstain
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "v1",
                        "2025-11-13",
                        "congreso_votaciones",
                        "Enmiendas del Senado.",
                        "Votación separada de las enmiendas",
                        "Enmienda a la disposición adicional trigésima.",
                        "Proyecto de Ley de Movilidad Sostenible.",
                        171,
                        179,
                        0,
                    ),
                )
                conn.execute(
                    "INSERT INTO parl_vote_event_initiatives(vote_event_id, initiative_id) VALUES ('v1', 'i1')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES (?, 'bocg', ?, ?)
                    """,
                    ("i1", "https://example.org/doc1", 1),
                )
                conn.execute(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, raw_path, text_chars)
                    VALUES ('parl_initiative_docs', ?, ?, 'text/xml', ?, 100)
                    """,
                    ("https://example.org/doc1", 1, str(raw_doc)),
                )
                conn.commit()

                sync = sync_review_queue(conn, initiative_source_ids=("congreso_iniciativas",))
                self.assertEqual(sync["candidate_rows"], 1)

                rows = fetch_review_rows(
                    conn,
                    only_pending=True,
                    contains_terms=["movilidad"],
                    min_priority=0,
                    limit=0,
                    offset=0,
                )
                self.assertEqual(len(rows), 1)
                bundle = write_evidence_bundle(
                    conn,
                    rows[0],
                    doc_source_id="parl_initiative_docs",
                    evidence_root=Path(td) / "evidence",
                    max_bocg_docs=2,
                )
                bundle_path = Path(bundle)
                self.assertTrue((bundle_path / "task.json").exists())
                doc_files = list((bundle_path / "docs").glob("*.txt"))
                self.assertEqual(len(doc_files), 1)
                self.assertIn("bajas emisiones", doc_files[0].read_text(encoding="utf-8").lower())
            finally:
                conn.close()

    def test_contains_filter_applies_before_limit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "measure_queue_limit.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    """
                    INSERT INTO parl_initiatives(
                      initiative_id, source_id, expediente, title, type, supertype, procedure_type, current_status, source_url
                    ) VALUES (?, 'congreso_iniciativas', ?, ?, 'Proyecto de ley', 'Función legislativa', 'Urgente', 'Cerrado', ?)
                    """,
                    [
                        ("i1", "121/000001/0000", "Proyecto de Ley Orgánica de representación paritaria.", "https://example.org/i1"),
                        ("i2", "121/000012/0000", "Proyecto de Ley por la que se regulan los servicios de atención a la clientela.", "https://example.org/i2"),
                        ("i3", "121/000020/0000", "Proyecto de Ley de Seguridad Aérea.", "https://example.org/i3"),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_measure_review_tasks(
                      task_id, initiative_id, source_id, review_reason, status, priority, raw_payload_json, created_at, updated_at
                    ) VALUES (?, ?, 'congreso_iniciativas', 'official_docs_bundle', 'pending', ?, '{}', '2026-03-12T00:00:00Z', '2026-03-12T00:00:00Z')
                    """,
                    [
                        ("i1", "i1", 100),
                        ("i2", "i2", 90),
                        ("i3", "i3", 80),
                    ],
                )
                conn.commit()

                rows = fetch_review_rows(
                    conn,
                    only_pending=True,
                    contains_terms=["clientela"],
                    min_priority=0,
                    limit=1,
                    offset=0,
                )
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["initiative_id"], "i2")
            finally:
                conn.close()

    def test_offset_applies_without_double_slicing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "measure_queue_offset.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    """
                    INSERT INTO parl_initiatives(
                      initiative_id, source_id, expediente, title, type, supertype, procedure_type, current_status, source_url
                    ) VALUES (?, 'congreso_iniciativas', ?, ?, 'Proyecto de ley', 'Función legislativa', 'Urgente', 'Cerrado', ?)
                    """,
                    [
                        ("i1", "121/000001/0000", "Proposición de Ley A.", "https://example.org/i1"),
                        ("i2", "121/000002/0000", "Proposición de Ley B.", "https://example.org/i2"),
                        ("i3", "121/000003/0000", "Proposición de Ley C.", "https://example.org/i3"),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_measure_review_tasks(
                      task_id, initiative_id, source_id, review_reason, status, priority, raw_payload_json, created_at, updated_at
                    ) VALUES (?, ?, 'congreso_iniciativas', 'official_docs_bundle', 'pending', ?, '{}', '2026-03-12T00:00:00Z', '2026-03-12T00:00:00Z')
                    """,
                    [
                        ("i1", "i1", 100),
                        ("i2", "i2", 90),
                        ("i3", "i3", 80),
                    ],
                )
                conn.commit()

                rows = fetch_review_rows(
                    conn,
                    only_pending=True,
                    contains_terms=[],
                    min_priority=0,
                    limit=1,
                    offset=1,
                )
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["initiative_id"], "i2")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
