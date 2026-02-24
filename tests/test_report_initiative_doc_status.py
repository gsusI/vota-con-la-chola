from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.politicos_es.util import now_utc_iso
from scripts.report_initiative_doc_status import _extraction_counts, _senado_global_enmiendas_analysis


class TestInitiativeDocStatusReport(unittest.TestCase):
    def test_extraction_counts_reports_downloaded_and_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "report-initiative-doc-status-extractions.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, legislature, expediente, title,
                      source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso:leg15:exp:121/000777/0000",
                        "15",
                        "121/000777/0000",
                        "Iniciativa test extracción",
                        "congreso_iniciativas",
                        "{}",
                        now,
                        now,
                    ),
                )

                conn.executemany(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "parl_initiative_docs",
                            "https://example.org/doc-a.pdf",
                            "2026-02-22",
                            "{}",
                            "sha-doc-a",
                            now,
                            now,
                        ),
                        (
                            "parl_initiative_docs",
                            "https://example.org/doc-b.pdf",
                            "2026-02-22",
                            "{}",
                            "sha-doc-b",
                            now,
                            now,
                        ),
                    ],
                )
                rows = conn.execute(
                    """
                    SELECT source_record_pk, source_record_id
                    FROM source_records
                    WHERE source_id = 'parl_initiative_docs'
                    ORDER BY source_record_pk
                    """
                ).fetchall()
                sr_a = int(rows[0]["source_record_pk"])
                sr_b = int(rows[1]["source_record_pk"])

                conn.executemany(
                    """
                    INSERT INTO parl_initiative_documents (
                      initiative_id, doc_kind, doc_url, source_record_pk, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        ("congreso:leg15:exp:121/000777/0000", "bocg", "https://example.org/doc-a.pdf", sr_a, now, now),
                        ("congreso:leg15:exp:121/000777/0000", "ds", "https://example.org/doc-b.pdf", sr_b, now, now),
                    ],
                )

                conn.executemany(
                    """
                    INSERT INTO text_documents (
                      source_id, source_url, source_record_pk,
                      fetched_at, content_type, content_sha256, bytes, raw_path,
                      text_excerpt, text_chars, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "parl_initiative_docs",
                            "https://example.org/doc-a.pdf",
                            sr_a,
                            now,
                            "application/pdf",
                            "sha-doc-a",
                            123,
                            "raw/doc-a.pdf",
                            "texto A",
                            7,
                            now,
                            now,
                        ),
                        (
                            "parl_initiative_docs",
                            "https://example.org/doc-b.pdf",
                            sr_b,
                            now,
                            "application/pdf",
                            "sha-doc-b",
                            234,
                            "raw/doc-b.pdf",
                            "texto B",
                            7,
                            now,
                            now,
                        ),
                    ],
                )

                conn.execute(
                    """
                    INSERT INTO parl_initiative_doc_extractions (
                      source_record_pk, source_id, sample_initiative_id,
                      initiatives_count, doc_refs_count, doc_kinds_csv,
                      content_sha256, doc_format, extractor_version,
                      extracted_title, extracted_subject, extracted_excerpt,
                      confidence, needs_review, analysis_payload_json,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sr_a,
                        "parl_initiative_docs",
                        "congreso:leg15:exp:121/000777/0000",
                        1,
                        1,
                        "bocg",
                        "sha-doc-a",
                        "pdf",
                        "heuristic_subject_v1",
                        "t",
                        "s",
                        "e",
                        0.7,
                        1,
                        "{}",
                        now,
                        now,
                    ),
                )
                conn.commit()

                got = _extraction_counts(
                    conn,
                    source_ids=["congreso_iniciativas"],
                    doc_source_id="parl_initiative_docs",
                )
                self.assertIn("congreso_iniciativas", got)
                self.assertEqual(int(got["congreso_iniciativas"]["downloaded_with_extraction"]), 1)
                self.assertEqual(int(got["congreso_iniciativas"]["extraction_needs_review"]), 1)
            finally:
                conn.close()

    def test_senado_global_enmiendas_marks_redundant_when_alt_bocg_downloaded(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "report-initiative-doc-status.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                initiative_id = "senado:leg15:exp:600/000555"
                global_url = "https://www.senado.es/legis15/expedientes/600/enmiendas/global_enmiendas_vetos_15_600000555.xml"
                detail_url = "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=600&numEx=000555"

                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, legislature, expediente, title,
                      source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        initiative_id,
                        "15",
                        "600/000555",
                        "Iniciativa Senado test",
                        "senado_iniciativas",
                        "{}",
                        now,
                        now,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "parl_initiative_docs",
                        detail_url,
                        "2026-02-22",
                        '{"url":"https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=600&numEx=000555"}',
                        "sha-report-detail-555",
                        now,
                        now,
                    ),
                )
                sr_pk = int(
                    conn.execute(
                        """
                        SELECT source_record_pk
                        FROM source_records
                        WHERE source_id = 'parl_initiative_docs'
                          AND source_record_id = ?
                        """,
                        (detail_url,),
                    ).fetchone()["source_record_pk"]
                )

                conn.execute(
                    """
                    INSERT INTO text_documents (
                      source_id, source_url, source_record_pk,
                      fetched_at, content_type, content_sha256, bytes, raw_path,
                      text_excerpt, text_chars, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "parl_initiative_docs",
                        detail_url,
                        sr_pk,
                        now,
                        "application/xml",
                        "sha-report-detail-555",
                        222,
                        "raw/detail_555.xml",
                        "",
                        0,
                        now,
                        now,
                    ),
                )

                conn.executemany(
                    """
                    INSERT INTO parl_initiative_documents (
                      initiative_id, doc_kind, doc_url, source_record_pk, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (initiative_id, "bocg", global_url, None, now, now),
                        (initiative_id, "bocg", detail_url, sr_pk, now, now),
                    ],
                )

                conn.execute(
                    """
                    INSERT INTO document_fetches (
                      doc_url, source_id, first_attempt_at, last_attempt_at,
                      attempts, fetched_ok, last_http_status, last_error,
                      content_type, content_sha256, bytes, raw_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        global_url,
                        "parl_initiative_docs",
                        now,
                        now,
                        5,
                        0,
                        404,
                        "HTTP Error 404: Not Found",
                        None,
                        None,
                        None,
                        None,
                    ),
                )
                conn.commit()

                result = _senado_global_enmiendas_analysis(
                    conn,
                    doc_source_id="parl_initiative_docs",
                    sample_limit=10,
                )

                self.assertEqual(int(result["total_global_enmiendas_missing"]), 1)
                self.assertEqual(int(result["likely_not_expected_redundant_global_url"]), 1)
                self.assertEqual(int(result["likely_not_expected_total"]), 1)
                self.assertEqual(int(result["actionable_missing_count"]), 0)
                self.assertEqual(result["actionable_missing_sample"], [])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
