from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.export_vote_implication_review_queue import fetch_review_rows, sync_review_queue


class TestExportVoteImplicationReviewQueue(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE sources (
              source_id TEXT PRIMARY KEY,
              name TEXT
            );
            CREATE TABLE parl_vote_events (
              vote_event_id TEXT PRIMARY KEY,
              vote_date TEXT,
              legislature TEXT,
              title TEXT,
              subgroup_title TEXT,
              expediente_text TEXT,
              totals_yes INTEGER,
              totals_no INTEGER,
              totals_abstain INTEGER,
              totals_no_vote INTEGER,
              source_id TEXT,
              source_url TEXT
            );
            CREATE TABLE parl_vote_event_initiatives (
              parl_vote_event_initiative_id INTEGER PRIMARY KEY AUTOINCREMENT,
              vote_event_id TEXT,
              initiative_id TEXT
            );
            CREATE TABLE parl_initiatives (
              initiative_id TEXT PRIMARY KEY,
              title TEXT,
              type TEXT,
              procedure_type TEXT,
              source_url TEXT
            );
            CREATE TABLE parl_initiative_doc_extractions (
              source_record_pk INTEGER PRIMARY KEY,
              source_id TEXT,
              sample_initiative_id TEXT,
              extracted_subject TEXT,
              extracted_excerpt TEXT,
              confidence REAL,
              needs_review INTEGER,
              analysis_payload_json TEXT
            );
            CREATE TABLE text_documents (
              source_record_pk INTEGER,
              source_id TEXT,
              source_url TEXT,
              raw_path TEXT
            );
            CREATE TABLE parl_vote_implication_reviews (
              review_id INTEGER PRIMARY KEY AUTOINCREMENT,
              review_key TEXT NOT NULL UNIQUE,
              vote_event_id TEXT NOT NULL,
              initiative_id TEXT,
              source_id TEXT NOT NULL,
              review_reason TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              priority INTEGER NOT NULL DEFAULT 50,
              heuristic_subject TEXT,
              heuristic_implication_kind TEXT,
              heuristic_binding_strength TEXT,
              citizen_title TEXT,
              citizen_question TEXT,
              citizen_summary TEXT,
              impact_if_approved TEXT,
              impact_if_rejected TEXT,
              affected_groups TEXT,
              evidence_quote TEXT,
              final_implication_kind TEXT,
              final_binding_strength TEXT,
              confidence REAL,
              extractor_version TEXT,
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
                ("congreso_votaciones", "Congreso"),
                ("parl_initiative_docs", "Docs"),
            ],
        )
        return conn

    def test_sync_queue_flags_generic_split_vote_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "vote_queue.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_vote_events(
                      vote_event_id, vote_date, legislature, title, subgroup_title, expediente_text,
                      totals_yes, totals_no, totals_abstain, totals_no_vote, source_id, source_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "v1",
                        "2025-10-08",
                        "15",
                        "Proposiciones no de Ley.",
                        "Votación separada por puntos.",
                        "Proposición no de Ley del Grupo Parlamentario Republicano, de medidas fiscales, regulatorias y de adquisición pública para asegurar el derecho a la vivienda.",
                        48,
                        177,
                        122,
                        3,
                        "congreso_votaciones",
                        "https://example.org/v1",
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(initiative_id, title, type, procedure_type, source_url)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        "i1",
                        "Proposición no de Ley del Grupo Parlamentario Republicano, de medidas fiscales, regulatorias y de adquisición pública para asegurar el derecho a la vivienda.",
                        "",
                        "",
                        "https://example.org/i1",
                    ),
                )
                conn.execute(
                    "INSERT INTO parl_vote_event_initiatives(vote_event_id, initiative_id) VALUES ('v1', 'i1')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_doc_extractions(
                      source_record_pk, source_id, sample_initiative_id, extracted_subject, extracted_excerpt,
                      confidence, needs_review, analysis_payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        10,
                        "parl_initiative_docs",
                        "i1",
                        "Proposición no de Ley del Grupo Parlamentario Republicano, de medidas fiscales, regulatorias y de adquisición pública para asegurar el derecho a la vivienda.",
                        "",
                        0.74,
                        0,
                        '{"subject_method":"title_fallback_strong"}',
                    ),
                )
                conn.commit()

                sync = sync_review_queue(
                    conn,
                    source_id="congreso_votaciones",
                    extract_source_id="parl_initiative_docs",
                )
                self.assertEqual(sync["candidate_rows"], 1)

                rows = fetch_review_rows(
                    conn,
                    source_id="congreso_votaciones",
                    only_pending=True,
                    review_reasons=[],
                    max_margin=-1,
                    contains_terms=[],
                    limit=0,
                    offset=0,
                )
                self.assertEqual(len(rows), 1)
                self.assertEqual(str(rows[0]["review_reason"]), "split_vote_point")
                self.assertEqual(str(rows[0]["heuristic_implication_kind"]), "non_binding_motion")
                self.assertEqual(str(rows[0]["heuristic_binding_strength"]), "non_binding")
                self.assertGreaterEqual(int(rows[0]["priority"] or 0), 90)
            finally:
                conn.close()

    def test_fetch_rows_respects_offset_batching(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "vote_queue_offset.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    """
                    INSERT INTO parl_vote_events(
                      vote_event_id, vote_date, legislature, title, subgroup_title, expediente_text,
                      totals_yes, totals_no, totals_abstain, totals_no_vote, source_id, source_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        ("v1", "2025-10-08", "15", "Proposiciones no de Ley.", "", "A", 10, 11, 0, 0, "congreso_votaciones", "https://example.org/v1"),
                        ("v2", "2025-10-09", "15", "Enmiendas del Senado.", "", "B", 10, 10, 0, 0, "congreso_votaciones", "https://example.org/v2"),
                    ],
                )
                conn.executemany(
                    "INSERT INTO parl_initiatives(initiative_id, title, type, procedure_type, source_url) VALUES (?, ?, '', '', ?)",
                    [
                        ("i1", "Proposición no de Ley A", "https://example.org/i1"),
                        ("i2", "Proyecto de Ley B", "https://example.org/i2"),
                    ],
                )
                conn.executemany(
                    "INSERT INTO parl_vote_event_initiatives(vote_event_id, initiative_id) VALUES (?, ?)",
                    [("v1", "i1"), ("v2", "i2")],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_doc_extractions(
                      source_record_pk, source_id, sample_initiative_id, extracted_subject, extracted_excerpt,
                      confidence, needs_review, analysis_payload_json
                    ) VALUES (?, 'parl_initiative_docs', ?, ?, '', 0.70, 0, '{\"subject_method\":\"title_fallback_strong\"}')
                    """,
                    [
                        (10, "i1", "Proposición no de Ley A"),
                        (11, "i2", "Proyecto de Ley B"),
                    ],
                )
                conn.commit()

                sync_review_queue(conn, source_id="congreso_votaciones", extract_source_id="parl_initiative_docs")
                rows = fetch_review_rows(
                    conn,
                    source_id="congreso_votaciones",
                    only_pending=True,
                    review_reasons=[],
                    max_margin=-1,
                    contains_terms=[],
                    limit=1,
                    offset=1,
                )
                self.assertEqual(len(rows), 1)
                self.assertEqual(str(rows[0]["vote_event_id"]), "v1")
            finally:
                conn.close()

    def test_sync_queue_excludes_file_url_vote_events(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "vote_queue_file_url.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    """
                    INSERT INTO parl_vote_events(
                      vote_event_id, vote_date, legislature, title, subgroup_title, expediente_text,
                      totals_yes, totals_no, totals_abstain, totals_no_vote, source_id, source_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "v_https",
                            "2025-12-11",
                            "15",
                            "Enmiendas del Senado.",
                            "",
                            "Proyecto de Ley por la que se regulan los servicios de atención al cliente.",
                            170,
                            173,
                            5,
                            2,
                            "congreso_votaciones",
                            "https://example.org/v_https",
                        ),
                        (
                            "v_file",
                            "2025-12-11",
                            "15",
                            "Enmiendas del Senado.",
                            "",
                            "Proyecto de Ley por la que se regulan los servicios de atención al cliente.",
                            170,
                            173,
                            5,
                            2,
                            "congreso_votaciones",
                            "file:///workspace/etl/data/raw/samples/congreso_votaciones_sample.json",
                        ),
                    ],
                )
                conn.executemany(
                    "INSERT INTO parl_initiatives(initiative_id, title, type, procedure_type, source_url) VALUES (?, ?, 'Proyecto de ley', 'Urgente', ?)",
                    [
                        ("i_https", "Proyecto de Ley por la que se regulan los servicios de atención al cliente.", "https://example.org/i_https"),
                        ("i_file", "Proyecto de Ley por la que se regulan los servicios de atención al cliente.", "https://example.org/i_file"),
                    ],
                )
                conn.executemany(
                    "INSERT INTO parl_vote_event_initiatives(vote_event_id, initiative_id) VALUES (?, ?)",
                    [("v_https", "i_https"), ("v_file", "i_file")],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_doc_extractions(
                      source_record_pk, source_id, sample_initiative_id, extracted_subject, extracted_excerpt,
                      confidence, needs_review, analysis_payload_json
                    ) VALUES (?, 'parl_initiative_docs', ?, ?, '', 0.70, 0, '{\"subject_method\":\"title_fallback_strong\"}')
                    """,
                    [
                        (10, "i_https", "Proyecto de Ley por la que se regulan los servicios de atención al cliente."),
                        (11, "i_file", "Proyecto de Ley por la que se regulan los servicios de atención al cliente."),
                    ],
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_implication_reviews(
                      review_key, vote_event_id, initiative_id, source_id, review_reason, status, priority,
                      heuristic_subject, heuristic_implication_kind, heuristic_binding_strength,
                      extractor_version, raw_payload_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'pending', 50, '', 'binding_law', 'binding', 'test', '{}', '2026-03-08T00:00:00Z', '2026-03-08T00:00:00Z')
                    """,
                    (
                        "v_file|i_file",
                        "v_file",
                        "i_file",
                        "congreso_votaciones",
                        "generic_title",
                    ),
                )
                conn.commit()

                sync = sync_review_queue(
                    conn,
                    source_id="congreso_votaciones",
                    extract_source_id="parl_initiative_docs",
                )
                self.assertEqual(sync["candidate_rows"], 1)

                rows = fetch_review_rows(
                    conn,
                    source_id="congreso_votaciones",
                    only_pending=False,
                    review_reasons=[],
                    max_margin=-1,
                    contains_terms=[],
                    limit=0,
                    offset=0,
                )
                self.assertEqual([str(row["vote_event_id"]) for row in rows], ["v_https"])
                stored = conn.execute(
                    "SELECT COUNT(*) FROM parl_vote_implication_reviews WHERE vote_event_id = 'v_file'"
                ).fetchone()[0]
                self.assertEqual(int(stored), 0)
            finally:
                conn.close()

    def test_fetch_rows_supports_reason_margin_and_text_filters(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "vote_queue_filters.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    """
                    INSERT INTO parl_vote_events(
                      vote_event_id, vote_date, legislature, title, subgroup_title, expediente_text,
                      totals_yes, totals_no, totals_abstain, totals_no_vote, source_id, source_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "v1",
                            "2025-10-08",
                            "15",
                            "Proposiciones no de Ley.",
                            "Votación separada por puntos.",
                            "Proposición no de Ley del Grupo Parlamentario Republicano, de medidas para asegurar el derecho a la vivienda.",
                            176,
                            174,
                            0,
                            0,
                            "congreso_votaciones",
                            "https://example.org/v1",
                        ),
                        (
                            "v2",
                            "2025-10-09",
                            "15",
                            "Enmiendas del Senado.",
                            "",
                            "Proyecto de Ley de Movilidad Sostenible.",
                            200,
                            150,
                            0,
                            0,
                            "congreso_votaciones",
                            "https://example.org/v2",
                        ),
                    ],
                )
                conn.executemany(
                    "INSERT INTO parl_initiatives(initiative_id, title, type, procedure_type, source_url) VALUES (?, ?, '', '', ?)",
                    [
                        ("i1", "Proposición no de Ley del Grupo Parlamentario Republicano, de medidas para asegurar el derecho a la vivienda.", "https://example.org/i1"),
                        ("i2", "Proyecto de Ley de Movilidad Sostenible.", "https://example.org/i2"),
                    ],
                )
                conn.executemany(
                    "INSERT INTO parl_vote_event_initiatives(vote_event_id, initiative_id) VALUES (?, ?)",
                    [("v1", "i1"), ("v2", "i2")],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_doc_extractions(
                      source_record_pk, source_id, sample_initiative_id, extracted_subject, extracted_excerpt,
                      confidence, needs_review, analysis_payload_json
                    ) VALUES (?, 'parl_initiative_docs', ?, ?, '', 0.70, 0, '{\"subject_method\":\"title_fallback_strong\"}')
                    """,
                    [
                        (10, "i1", "Proposición no de Ley del Grupo Parlamentario Republicano, de medidas para asegurar el derecho a la vivienda."),
                        (11, "i2", "Proyecto de Ley de Movilidad Sostenible."),
                    ],
                )
                conn.commit()

                sync_review_queue(
                    conn,
                    source_id="congreso_votaciones",
                    extract_source_id="parl_initiative_docs",
                )
                rows = fetch_review_rows(
                    conn,
                    source_id="congreso_votaciones",
                    only_pending=True,
                    review_reasons=["split_vote_point"],
                    max_margin=5,
                    contains_terms=["vivienda"],
                    limit=0,
                    offset=0,
                )
                self.assertEqual([str(row["vote_event_id"]) for row in rows], ["v1"])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
