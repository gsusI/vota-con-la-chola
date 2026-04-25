from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.report_initiative_measure_review_queue_status import build_status_report


class TestReportInitiativeMeasureReviewQueueStatus(unittest.TestCase):
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
            CREATE TABLE parl_initiative_measure_points (
              measure_point_id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              initiative_id TEXT NOT NULL,
              source_id TEXT NOT NULL,
              measure_rank INTEGER NOT NULL DEFAULT 1,
              measure_title TEXT NOT NULL,
              citizen_summary TEXT NOT NULL,
              affected_groups TEXT,
              policy_area TEXT,
              measure_kind TEXT,
              measure_status TEXT,
              search_terms_json TEXT NOT NULL DEFAULT '[]',
              primary_vote_event_ids_json TEXT NOT NULL DEFAULT '[]',
              support_side TEXT,
              support_explanation TEXT,
              evidence_json TEXT NOT NULL DEFAULT '[]',
              note TEXT,
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

    def test_report_sync_bootstraps_pending_queue(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "initiative_measure_queue_status_sync.db"
            raw_doc = Path(td) / "doc.xml"
            raw_doc.write_text(
                "<root><p>Proyecto de Ley de Movilidad Sostenible y zonas de bajas emisiones.</p></root>",
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
                        "Votación separada",
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

                report = build_status_report(
                    conn,
                    initiative_source_ids=("congreso_iniciativas",),
                    doc_source_id="parl_initiative_docs",
                    review_reason="official_docs_bundle",
                    sync=True,
                    top_n=5,
                )
            finally:
                conn.close()

        self.assertEqual(str(report["status"]), "ok")
        self.assertTrue(bool(report["checks"]["queue_started_ok"]))
        self.assertEqual(int(report["sync"]["candidate_rows"]), 1)
        self.assertEqual(int(report["sync"]["upserted"]), 1)
        self.assertEqual(int(report["totals"]["tasks_total"]), 1)
        self.assertEqual(int(report["totals"]["pending_total"]), 1)
        self.assertEqual(len(report["top_pending"]), 1)
        self.assertEqual(str(report["top_pending"][0]["initiative_id"]), "i1")

    def test_report_degrades_when_resolved_task_has_no_measure_points(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "initiative_measure_queue_status_degraded.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(
                      initiative_id, source_id, expediente, title, type, supertype, procedure_type, current_status, source_url
                    ) VALUES ('i1', 'congreso_iniciativas', '121/000009/0000', 'Proyecto de Ley de Movilidad Sostenible.', 'Proyecto de ley', 'Función legislativa', 'Urgente', 'Cerrado', 'https://example.org/i1')
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_measure_review_tasks(
                      task_id, initiative_id, source_id, review_reason, status, priority, raw_payload_json, created_at, updated_at
                    ) VALUES ('i1', 'i1', 'congreso_iniciativas', 'official_docs_bundle', 'resolved', 90, '{}', '2026-03-12T00:00:00Z', '2026-03-12T00:00:00Z')
                    """
                )
                conn.commit()

                report = build_status_report(
                    conn,
                    initiative_source_ids=("congreso_iniciativas",),
                    doc_source_id="parl_initiative_docs",
                    review_reason="official_docs_bundle",
                    sync=False,
                    top_n=5,
                )
            finally:
                conn.close()

        self.assertEqual(str(report["status"]), "degraded")
        self.assertFalse(bool(report["checks"]["resolved_have_measure_points_ok"]))
        self.assertEqual(int(report["integrity"]["resolved_without_measure_points_total"]), 1)


if __name__ == "__main__":
    unittest.main()
