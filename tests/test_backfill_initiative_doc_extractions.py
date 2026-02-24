from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.backfill_initiative_doc_extractions import (
    backfill_initiative_doc_extractions,
    ensure_extraction_table,
)


class TestBackfillInitiativeDocExtractions(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE sources (
              source_id TEXT PRIMARY KEY
            );
            CREATE TABLE source_records (
              source_record_pk INTEGER PRIMARY KEY,
              source_id TEXT,
              source_record_id TEXT
            );
            CREATE TABLE parl_initiatives (
              initiative_id TEXT PRIMARY KEY,
              source_id TEXT,
              title TEXT
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
              content_sha256 TEXT,
              bytes INTEGER,
              raw_path TEXT,
              text_excerpt TEXT
            );
            """
        )
        conn.executemany(
            "INSERT INTO sources(source_id) VALUES (?)",
            [("parl_initiative_docs",), ("congreso_iniciativas",), ("senado_iniciativas",)],
        )
        conn.commit()
        return conn

    def test_backfill_generates_rows_and_subjects(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "extract.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (?, ?, ?)",
                    [
                        (1, "parl_initiative_docs", "doc-1"),
                        (2, "parl_initiative_docs", "doc-2"),
                    ],
                )
                conn.executemany(
                    "INSERT INTO parl_initiatives(initiative_id, source_id, title) VALUES (?, ?, ?)",
                    [
                        (
                            "congreso:leg15:exp:121/000001",
                            "congreso_iniciativas",
                            "Proposición de ley para mejorar el transporte público",
                        ),
                        (
                            "senado:leg15:exp:600/000111",
                            "senado_iniciativas",
                            "Moción para reforzar la atención primaria",
                        ),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        ("congreso:leg15:exp:121/000001", "bocg", "https://example.org/doc1.pdf", 1),
                        ("senado:leg15:exp:600/000111", "ds", "https://example.org/doc2.pdf", 2),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, content_sha256, bytes, raw_path, text_excerpt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "parl_initiative_docs",
                            "https://example.org/doc1.pdf",
                            1,
                            "application/pdf",
                            "sha-doc-1",
                            100,
                            "/tmp/doc1.pdf",
                            "Boletín. Proposición de ley para mejorar el transporte público y reducir emisiones en ciudades.",
                        ),
                        (
                            "parl_initiative_docs",
                            "https://example.org/doc2.pdf",
                            2,
                            "application/pdf",
                            "sha-doc-2",
                            90,
                            "/tmp/doc2.pdf",
                            "Texto de sesión. Sin patrón fuerte al inicio pero con información general para debate.",
                        ),
                    ],
                )
                conn.commit()

                result = backfill_initiative_doc_extractions(
                    conn,
                    doc_source_id="parl_initiative_docs",
                    initiative_source_ids=("congreso_iniciativas", "senado_iniciativas"),
                    extractor_version="heuristic_subject_v1",
                    limit=0,
                    only_missing=False,
                    dry_run=False,
                )

                self.assertEqual(int(result["seen"]), 2)
                self.assertEqual(int(result["upserted"]), 2)

                rows = conn.execute(
                    "SELECT source_record_pk, extracted_subject, doc_format, needs_review FROM parl_initiative_doc_extractions ORDER BY source_record_pk"
                ).fetchall()
                self.assertEqual(len(rows), 2)
                self.assertEqual(str(rows[0]["doc_format"]), "pdf")
                self.assertIn("Proposición", str(rows[0]["extracted_subject"]))
                self.assertIn(int(rows[1]["needs_review"]), (0, 1))
            finally:
                conn.close()

    def test_only_missing_skips_existing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "extract_missing.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (1, 'parl_initiative_docs', 'doc-1')"
                )
                conn.execute(
                    "INSERT INTO parl_initiatives(initiative_id, source_id, title) VALUES ('congreso:leg15:exp:121/000001', 'congreso_iniciativas', 'Proposición de ley X')"
                )
                conn.execute(
                    "INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk) VALUES ('congreso:leg15:exp:121/000001', 'bocg', 'https://example.org/doc1.pdf', 1)"
                )
                conn.execute(
                    "INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, content_sha256, bytes, raw_path, text_excerpt) VALUES ('parl_initiative_docs', 'https://example.org/doc1.pdf', 1, 'application/pdf', 'sha-doc-1', 100, '/tmp/doc1.pdf', 'Proposición de ley X para prueba.')"
                )
                conn.commit()

                ensure_extraction_table(conn)
                conn.execute(
                    """
                    INSERT INTO parl_initiative_doc_extractions(
                      source_record_pk, source_id, sample_initiative_id,
                      initiatives_count, doc_refs_count, doc_kinds_csv,
                      content_sha256, doc_format, extractor_version,
                      extracted_title, extracted_subject, extracted_excerpt,
                      confidence, needs_review, analysis_payload_json,
                      created_at, updated_at
                    ) VALUES (1, 'parl_initiative_docs', 'congreso:leg15:exp:121/000001', 1, 1, 'bocg', 'sha-doc-1', 'pdf', 'old_v', 'old', 'old', 'old', 0.1, 1, '{}', '2026-02-22T00:00:00Z', '2026-02-22T00:00:00Z')
                    """
                )
                conn.commit()

                result = backfill_initiative_doc_extractions(
                    conn,
                    doc_source_id="parl_initiative_docs",
                    initiative_source_ids=("congreso_iniciativas",),
                    extractor_version="heuristic_subject_v1",
                    limit=0,
                    only_missing=True,
                    dry_run=False,
                )
                self.assertEqual(int(result["seen"]), 0)
                self.assertEqual(int(result["upserted"]), 0)

                row = conn.execute(
                    "SELECT extractor_version, extracted_subject FROM parl_initiative_doc_extractions WHERE source_record_pk = 1"
                ).fetchone()
                self.assertEqual(str(row["extractor_version"]), "old_v")
                self.assertEqual(str(row["extracted_subject"]), "old")
            finally:
                conn.close()

    def test_title_hint_strong_auto_clears_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "extract_title_hint_strong.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (10, 'parl_initiative_docs', 'doc-10')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(initiative_id, source_id, title)
                    VALUES (
                      'senado:leg15:exp:621/000001',
                      'senado_iniciativas',
                      'Proyecto de Ley por la que se regulan las enseñanzas artísticas superiores y se establece la organización y equivalencias de las enseñanzas artísticas profesionales'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES ('senado:leg15:exp:621/000001', 'bocg', 'https://example.org/doc-10.pdf', 10)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, content_sha256, bytes, raw_path, text_excerpt)
                    VALUES (
                      'parl_initiative_docs',
                      'https://example.org/doc-10.pdf',
                      10,
                      'application/pdf',
                      'sha-doc-10',
                      111,
                      '/tmp/doc-10.pdf',
                      'Documento de tramitación parlamentaria sin un patrón léxico fuerte en el cuerpo.'
                    )
                    """
                )
                conn.commit()

                result = backfill_initiative_doc_extractions(
                    conn,
                    doc_source_id="parl_initiative_docs",
                    initiative_source_ids=("senado_iniciativas",),
                    extractor_version="heuristic_subject_v2",
                    limit=0,
                    only_missing=False,
                    dry_run=False,
                )
                self.assertEqual(int(result["seen"]), 1)
                self.assertEqual(int(result["upserted"]), 1)

                row = conn.execute(
                    """
                    SELECT
                      confidence,
                      needs_review,
                      extracted_subject,
                      json_extract(analysis_payload_json, '$.subject_method') AS method
                    FROM parl_initiative_doc_extractions
                    WHERE source_record_pk = 10
                    """
                ).fetchone()
                self.assertAlmostEqual(float(row["confidence"]), 0.74, places=6)
                self.assertEqual(int(row["needs_review"]), 0)
                self.assertEqual(str(row["method"]), "title_hint_strong")
                self.assertIn("Proyecto de Ley", str(row["extracted_subject"]))
            finally:
                conn.close()

    def test_title_hint_explicit_international_act_auto_clears_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "extract_title_hint_actas.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (11, 'parl_initiative_docs', 'doc-11')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(initiative_id, source_id, title)
                    VALUES (
                      'senado:leg15:exp:610/000006',
                      'senado_iniciativas',
                      'Actas del XXVII Congreso de la Unión Postal Universal (UPU), adoptadas en Abidjan el 27 de agosto de 2021. (610/000006)'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES ('senado:leg15:exp:610/000006', 'bocg', 'https://example.org/doc-11.pdf', 11)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, content_sha256, bytes, raw_path, text_excerpt)
                    VALUES (
                      'parl_initiative_docs',
                      'https://example.org/doc-11.pdf',
                      11,
                      'application/pdf',
                      'sha-doc-11',
                      121,
                      '/tmp/doc-11.pdf',
                      'Documento formal con texto breve no concluyente.'
                    )
                    """
                )
                conn.commit()

                result = backfill_initiative_doc_extractions(
                    conn,
                    doc_source_id="parl_initiative_docs",
                    initiative_source_ids=("senado_iniciativas",),
                    extractor_version="heuristic_subject_v2",
                    limit=0,
                    only_missing=False,
                    dry_run=False,
                )
                self.assertEqual(int(result["seen"]), 1)
                self.assertEqual(int(result["upserted"]), 1)

                row = conn.execute(
                    """
                    SELECT
                      confidence,
                      needs_review,
                      extracted_subject,
                      json_extract(analysis_payload_json, '$.subject_method') AS method
                    FROM parl_initiative_doc_extractions
                    WHERE source_record_pk = 11
                    """
                ).fetchone()
                self.assertAlmostEqual(float(row["confidence"]), 0.74, places=6)
                self.assertEqual(int(row["needs_review"]), 0)
                self.assertEqual(str(row["method"]), "title_hint_strong")
                self.assertIn("Actas del XXVII Congreso", str(row["extracted_subject"]))
            finally:
                conn.close()

    def test_title_hint_strong_short_explicit_title_still_clears_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "extract_title_hint_strong_short.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (12, 'parl_initiative_docs', 'doc-12')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(initiative_id, source_id, title)
                    VALUES (
                      'senado:leg14:exp:621/000077',
                      'senado_iniciativas',
                      'Proyecto de Ley de Empleo. (621/000077)'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES ('senado:leg14:exp:621/000077', 'bocg', 'https://example.org/doc-12.pdf', 12)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, content_sha256, bytes, raw_path, text_excerpt)
                    VALUES (
                      'parl_initiative_docs',
                      'https://example.org/doc-12.pdf',
                      12,
                      'application/pdf',
                      'sha-doc-12',
                      131,
                      '/tmp/doc-12.pdf',
                      'Cabecera de documento parlamentario sin frase clave larga.'
                    )
                    """
                )
                conn.commit()

                result = backfill_initiative_doc_extractions(
                    conn,
                    doc_source_id="parl_initiative_docs",
                    initiative_source_ids=("senado_iniciativas",),
                    extractor_version="heuristic_subject_v2",
                    limit=0,
                    only_missing=False,
                    dry_run=False,
                )
                self.assertEqual(int(result["seen"]), 1)
                self.assertEqual(int(result["upserted"]), 1)

                row = conn.execute(
                    """
                    SELECT
                      confidence,
                      needs_review,
                      extracted_subject,
                      json_extract(analysis_payload_json, '$.subject_method') AS method
                    FROM parl_initiative_doc_extractions
                    WHERE source_record_pk = 12
                    """
                ).fetchone()
                self.assertAlmostEqual(float(row["confidence"]), 0.74, places=6)
                self.assertEqual(int(row["needs_review"]), 0)
                self.assertEqual(str(row["method"]), "title_hint_strong")
                self.assertEqual(str(row["extracted_subject"]), "Proyecto de Ley de Empleo. (621/000077)")
            finally:
                conn.close()

    def test_short_keyword_window_prefers_strong_title_hint(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "extract_short_keyword_window.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (13, 'parl_initiative_docs', 'doc-13')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(initiative_id, source_id, title)
                    VALUES (
                      'senado:leg14:exp:621/000065',
                      'senado_iniciativas',
                      'Proyecto de Ley del Deporte. (621/000065)'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES ('senado:leg14:exp:621/000065', 'bocg', 'https://example.org/doc-13.pdf', 13)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, content_sha256, bytes, raw_path, text_excerpt)
                    VALUES (
                      'parl_initiative_docs',
                      'https://example.org/doc-13.pdf',
                      13,
                      'application/pdf',
                      'sha-doc-13',
                      140,
                      '/tmp/doc-13.pdf',
                      'Tramitación: Proyecto de Ley del Gobierno ... más texto.'
                    )
                    """
                )
                conn.commit()

                result = backfill_initiative_doc_extractions(
                    conn,
                    doc_source_id="parl_initiative_docs",
                    initiative_source_ids=("senado_iniciativas",),
                    extractor_version="heuristic_subject_v2",
                    limit=0,
                    only_missing=False,
                    dry_run=False,
                )
                self.assertEqual(int(result["seen"]), 1)
                self.assertEqual(int(result["upserted"]), 1)

                row = conn.execute(
                    """
                    SELECT
                      confidence,
                      needs_review,
                      extracted_subject,
                      json_extract(analysis_payload_json, '$.subject_method') AS method
                    FROM parl_initiative_doc_extractions
                    WHERE source_record_pk = 13
                    """
                ).fetchone()
                self.assertAlmostEqual(float(row["confidence"]), 0.74, places=6)
                self.assertEqual(int(row["needs_review"]), 0)
                self.assertEqual(str(row["method"]), "title_hint_strong_from_short_window")
                self.assertEqual(str(row["extracted_subject"]), "Proyecto de Ley del Deporte. (621/000065)")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
