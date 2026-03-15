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

    def test_empty_excerpt_uses_title_fallback_strong(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "extract_empty_excerpt.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (3, 'parl_initiative_docs', 'doc-3')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(initiative_id, source_id, title)
                    VALUES (
                      'congreso:leg15:exp:121/000777',
                      'congreso_iniciativas',
                      'Proposición de Ley para reforzar la protección del ahorro familiar'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES ('congreso:leg15:exp:121/000777', 'bocg', 'https://example.org/doc3.pdf', 3)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, content_sha256, bytes, raw_path, text_excerpt)
                    VALUES ('parl_initiative_docs', 'https://example.org/doc3.pdf', 3, 'application/pdf', 'sha-doc-3', 80, '/tmp/doc3.pdf', NULL)
                    """
                )
                conn.commit()

                result = backfill_initiative_doc_extractions(
                    conn,
                    doc_source_id="parl_initiative_docs",
                    initiative_source_ids=("congreso_iniciativas",),
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
                      extracted_excerpt,
                      json_extract(analysis_payload_json, '$.subject_method') AS method
                    FROM parl_initiative_doc_extractions
                    WHERE source_record_pk = 3
                    """
                ).fetchone()
                self.assertAlmostEqual(float(row["confidence"]), 0.74, places=6)
                self.assertEqual(int(row["needs_review"]), 0)
                self.assertEqual(str(row["method"]), "title_fallback_strong")
                self.assertIn("Proposición de Ley", str(row["extracted_subject"]))
                self.assertIsNone(row["extracted_excerpt"])
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

    def test_noisy_html_keyword_window_falls_back_to_strong_title(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "extract_noisy_html_keyword.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (14, 'parl_initiative_docs', 'doc-14')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(initiative_id, source_id, title)
                    VALUES (
                      'senado:leg12:exp:621/000005',
                      'senado_iniciativas',
                      'Proyecto de Ley por la que se modifica la Ley de Enjuiciamiento Civil'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES ('senado:leg12:exp:621/000005', 'ds', 'https://example.org/doc-14.html', 14)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, content_sha256, bytes, raw_path, text_excerpt)
                    VALUES (
                      'parl_initiative_docs',
                      'https://example.org/doc-14.html',
                      14,
                      'text/html',
                      'sha-doc-14',
                      222,
                      '/tmp/doc-14.html',
                      'Enmiendas | Senado de España !function(a){var e=\"https://www.senado.es\";}'
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
                      text_quality,
                      extracted_subject,
                      json_extract(analysis_payload_json, '$.subject_method') AS method
                    FROM parl_initiative_doc_extractions
                    WHERE source_record_pk = 14
                    """
                ).fetchone()
                self.assertAlmostEqual(float(row["confidence"]), 0.74, places=6)
                self.assertEqual(int(row["needs_review"]), 1)
                self.assertEqual(str(row["text_quality"]), "shell_html")
                self.assertEqual(str(row["method"]), "title_hint_strong")
                self.assertNotIn("!function(", str(row["extracted_subject"]))
                self.assertIn("Proyecto de Ley", str(row["extracted_subject"]))
            finally:
                conn.close()

    def test_noisy_senado_nav_sentence_falls_back_to_strong_title(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "extract_noisy_senado_nav.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (15, 'parl_initiative_docs', 'doc-15')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(initiative_id, source_id, title)
                    VALUES (
                      'senado:leg14:exp:621/000089',
                      'senado_iniciativas',
                      'Proyecto de Ley de pesca sostenible e investigación pesquera'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES ('senado:leg14:exp:621/000089', 'ds', 'https://example.org/doc-15.html', 15)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, content_sha256, bytes, raw_path, text_excerpt)
                    VALUES (
                      'parl_initiative_docs',
                      'https://example.org/doc-15.html',
                      15,
                      'text/html',
                      'sha-doc-15',
                      222,
                      '/tmp/doc-15.html',
                      'Ir al Contenido (Presione enter) SENADO DE ESPAÑA Menú Enlaces Diccionario parlamentario Preguntas frecuentes Mapa Web Contactar Síguenos Actividad parlamentaria Actualidad Pleno y Diputación Permanente'
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
                      text_quality,
                      extracted_subject,
                      json_extract(analysis_payload_json, '$.subject_method') AS method
                    FROM parl_initiative_doc_extractions
                    WHERE source_record_pk = 15
                    """
                ).fetchone()
                self.assertAlmostEqual(float(row["confidence"]), 0.74, places=6)
                self.assertEqual(int(row["needs_review"]), 1)
                self.assertEqual(str(row["text_quality"]), "shell_html")
                self.assertEqual(str(row["method"]), "title_hint_strong")
                self.assertIn("Proyecto de Ley", str(row["extracted_subject"]))
                self.assertNotIn("Ir al Contenido", str(row["extracted_subject"]))
            finally:
                conn.close()

    def test_materializes_full_text_and_flags_pdf_needs_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "extract_pdf_needs_ocr.db"
            raw_path = Path(td) / "doc-20.pdf"
            raw_path.write_bytes(b"%PDF-1.4 fake pdf without text layer")
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (20, 'parl_initiative_docs', 'doc-20')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(initiative_id, source_id, title)
                    VALUES (
                      'congreso:leg15:exp:121/000020',
                      'congreso_iniciativas',
                      'Proyecto de Ley de prueba para extracción OCR'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES ('congreso:leg15:exp:121/000020', 'bocg', 'https://example.org/doc-20.pdf', 20)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, content_sha256, bytes, raw_path, text_excerpt)
                    VALUES (
                      'parl_initiative_docs',
                      'https://example.org/doc-20.pdf',
                      20,
                      'application/pdf',
                      'sha-doc-20',
                      512,
                      ?,
                      NULL
                    )
                    """,
                    (str(raw_path),),
                )
                conn.commit()

                result = backfill_initiative_doc_extractions(
                    conn,
                    doc_source_id="parl_initiative_docs",
                    initiative_source_ids=("congreso_iniciativas",),
                    extractor_version="heuristic_subject_v3",
                    text_output_root=Path(td) / "texts",
                    limit=0,
                    only_missing=False,
                    dry_run=False,
                )
                self.assertEqual(int(result["seen"]), 1)
                self.assertEqual(int(result["needs_ocr"]), 1)

                row = conn.execute(
                    """
                    SELECT
                      text_extraction_method,
                      text_quality,
                      needs_ocr,
                      full_text_path,
                      needs_review,
                      extracted_subject
                    FROM parl_initiative_doc_extractions
                    WHERE source_record_pk = 20
                    """
                ).fetchone()
                self.assertEqual(str(row["text_extraction_method"]), "pdf_text")
                self.assertEqual(str(row["text_quality"]), "needs_ocr")
                self.assertEqual(int(row["needs_ocr"]), 1)
                self.assertEqual(int(row["needs_review"]), 1)
                self.assertIsNone(row["full_text_path"])
                self.assertIn("Proyecto de Ley", str(row["extracted_subject"]))
            finally:
                conn.close()

    def test_materializes_full_text_artifact_for_structured_xml(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "extract_xml_artifact.db"
            raw_path = Path(td) / "doc-21.xml"
            raw_path.write_text(
                "<root><titulo>Proyecto de Ley de vivienda asequible</titulo><p>Medidas para ampliar parque público y limitar alquileres abusivos.</p></root>",
                encoding="utf-8",
            )
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (21, 'parl_initiative_docs', 'doc-21')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(initiative_id, source_id, title)
                    VALUES (
                      'senado:leg15:exp:621/000021',
                      'senado_iniciativas',
                      'Proyecto de Ley de vivienda asequible'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES ('senado:leg15:exp:621/000021', 'bocg', 'https://example.org/doc-21.xml', 21)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, content_sha256, bytes, raw_path, text_excerpt)
                    VALUES (
                      'parl_initiative_docs',
                      'https://example.org/doc-21.xml',
                      21,
                      'text/xml',
                      'sha-doc-21',
                      321,
                      ?,
                      'Proyecto de Ley de vivienda asequible.'
                    )
                    """,
                    (str(raw_path),),
                )
                conn.commit()

                result = backfill_initiative_doc_extractions(
                    conn,
                    doc_source_id="parl_initiative_docs",
                    initiative_source_ids=("senado_iniciativas",),
                    extractor_version="heuristic_subject_v3",
                    text_output_root=Path(td) / "texts",
                    limit=0,
                    only_missing=False,
                    dry_run=False,
                )
                self.assertEqual(int(result["seen"]), 1)

                row = conn.execute(
                    """
                    SELECT
                      text_extraction_method,
                      text_quality,
                      needs_ocr,
                      full_text_path,
                      full_text_chars,
                      needs_review
                    FROM parl_initiative_doc_extractions
                    WHERE source_record_pk = 21
                    """
                ).fetchone()
                self.assertEqual(str(row["text_extraction_method"]), "xml_structured")
                self.assertEqual(str(row["text_quality"]), "structured_good")
                self.assertEqual(int(row["needs_ocr"]), 0)
                self.assertEqual(int(row["needs_review"]), 0)
                artifact_path = Path(str(row["full_text_path"]))
                self.assertTrue(artifact_path.is_file())
                self.assertGreater(int(row["full_text_chars"] or 0), 50)
                self.assertIn("limitar alquileres abusivos", artifact_path.read_text(encoding="utf-8"))
            finally:
                conn.close()

    def test_iso_8859_xml_is_not_marked_garbled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "extract_iso_xml.db"
            raw_path = Path(td) / "doc-22.xml"
            raw_path.write_bytes(
                (
                    "<?xml version='1.0' encoding='ISO-8859-15'?>"
                    "<root><p>Enmiendas y vetos del Senado. Información sobre tráfico y circulación con señalización específica.</p></root>"
                ).encode("iso-8859-15")
            )
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    "INSERT INTO source_records(source_record_pk, source_id, source_record_id) VALUES (22, 'parl_initiative_docs', 'doc-22')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(initiative_id, source_id, title)
                    VALUES (
                      'senado:leg15:exp:621/000022',
                      'senado_iniciativas',
                      'Proyecto de Ley de prueba con enmiendas del Senado'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents(initiative_id, doc_kind, doc_url, source_record_pk)
                    VALUES ('senado:leg15:exp:621/000022', 'bocg', 'https://example.org/doc-22.xml', 22)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO text_documents(source_id, source_url, source_record_pk, content_type, content_sha256, bytes, raw_path, text_excerpt)
                    VALUES (
                      'parl_initiative_docs',
                      'https://example.org/doc-22.xml',
                      22,
                      'text/xml',
                      'sha-doc-22',
                      333,
                      ?,
                      'Enmiendas y vetos del Senado.'
                    )
                    """,
                    (str(raw_path),),
                )
                conn.commit()

                result = backfill_initiative_doc_extractions(
                    conn,
                    doc_source_id="parl_initiative_docs",
                    initiative_source_ids=("senado_iniciativas",),
                    extractor_version="heuristic_subject_v3",
                    text_output_root=Path(td) / "texts",
                    limit=0,
                    only_missing=False,
                    dry_run=False,
                )
                self.assertEqual(int(result["seen"]), 1)

                row = conn.execute(
                    """
                    SELECT text_quality, full_text_path
                    FROM parl_initiative_doc_extractions
                    WHERE source_record_pk = 22
                    """
                ).fetchone()
                self.assertEqual(str(row["text_quality"]), "structured_good")
                artifact_path = Path(str(row["full_text_path"]))
                self.assertTrue(artifact_path.is_file())
                text = artifact_path.read_text(encoding="utf-8")
                self.assertIn("tráfico y circulación", text)
                self.assertNotIn("tr�fico", text)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
