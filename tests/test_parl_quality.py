from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG as PARL_SOURCE_CONFIG
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.linking import link_congreso_votes_to_initiatives, link_senado_votes_to_initiatives
from etl.parlamentario_es.pipeline import backfill_vote_member_person_ids, ingest_one_source as ingest_parl_source
from etl.politicos_es.util import canonical_key, now_utc_iso, sha256_bytes
from etl.parlamentario_es.quality import (
    DEFAULT_DECLARED_QUALITY_THRESHOLDS,
    DEFAULT_INITIATIVE_QUALITY_THRESHOLDS,
    DEFAULT_VOTE_QUALITY_THRESHOLDS,
    compute_declared_quality_kpis,
    compute_initiative_quality_kpis,
    compute_vote_quality_kpis,
    evaluate_declared_quality_gate,
    evaluate_initiative_quality_gate,
    evaluate_vote_quality_gate,
)
from etl.parlamentario_es.registry import get_connectors


class TestParlVoteQuality(unittest.TestCase):
    def test_compute_kpis_is_deterministic_with_samples_and_linking(self) -> None:
        connectors = get_connectors()
        snapshot_date = "2026-02-12"
        ingest_sources = [
            "congreso_votaciones",
            "congreso_iniciativas",
            "senado_iniciativas",
            "senado_votaciones",
        ]

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)

                for sid in ingest_sources:
                    connector = connectors[sid]
                    sample_path = Path(PARL_SOURCE_CONFIG[sid]["fallback_file"])
                    self.assertTrue(sample_path.exists(), f"Missing sample for {sid}: {sample_path}")
                    ingest_parl_source(
                        conn=conn,
                        connector=connector,
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=sample_path,
                        url_override=None,
                        snapshot_date=snapshot_date,
                        strict_network=True,
                        options={},
                    )

                link_congreso_votes_to_initiatives(conn, dry_run=False)
                link_senado_votes_to_initiatives(conn, dry_run=False)

                kpis_1 = compute_vote_quality_kpis(conn)
                kpis_2 = compute_vote_quality_kpis(conn)
                self.assertEqual(kpis_1, kpis_2)

                self.assertGreater(int(kpis_1["events_total"]), 0)
                self.assertGreaterEqual(int(kpis_1["events_with_nominal_vote"]), 0)
                self.assertGreaterEqual(int(kpis_1["member_votes_total"]), 0)
                self.assertIn("events_with_initiative_link", kpis_1)
                self.assertIn("events_with_initiative_link_pct", kpis_1)
                self.assertIn("events_with_initiative_link", kpis_1["by_source"]["congreso_votaciones"])
                self.assertIn(
                    "events_with_initiative_link_pct",
                    kpis_1["by_source"]["congreso_votaciones"],
                )
                self.assertLessEqual(
                    int(kpis_1["member_votes_with_person_id"]),
                    int(kpis_1["member_votes_total"]),
                )
                self.assertIn("congreso_votaciones", kpis_1["by_source"])
                self.assertIn("senado_votaciones", kpis_1["by_source"])

                by_source = kpis_1["by_source"]
                self.assertEqual(
                    int(kpis_1["events_total"]),
                    int(by_source["congreso_votaciones"]["events_total"])
                    + int(by_source["senado_votaciones"]["events_total"]),
                )

                pass_gate = evaluate_vote_quality_gate(
                    kpis_1,
                    thresholds={metric: 0.0 for metric in DEFAULT_VOTE_QUALITY_THRESHOLDS},
                )
                self.assertTrue(bool(pass_gate["passed"]))
                self.assertEqual(pass_gate["failures"], [])

                fail_gate = evaluate_vote_quality_gate(
                    kpis_1,
                    thresholds={metric: 1.01 for metric in DEFAULT_VOTE_QUALITY_THRESHOLDS},
                )
                self.assertFalse(bool(fail_gate["passed"]))
                self.assertEqual(len(fail_gate["failures"]), len(DEFAULT_VOTE_QUALITY_THRESHOLDS))
            finally:
                conn.close()

    def test_evaluate_gate_default_and_custom_thresholds(self) -> None:
        self.assertEqual(DEFAULT_VOTE_QUALITY_THRESHOLDS["events_with_date_pct"], 0.95)
        self.assertEqual(DEFAULT_VOTE_QUALITY_THRESHOLDS["events_with_theme_pct"], 0.95)
        self.assertEqual(DEFAULT_VOTE_QUALITY_THRESHOLDS["events_with_totals_pct"], 0.95)
        self.assertEqual(DEFAULT_VOTE_QUALITY_THRESHOLDS["events_with_initiative_link_pct"], 0.95)
        self.assertEqual(DEFAULT_VOTE_QUALITY_THRESHOLDS["member_votes_with_person_id_pct"], 0.90)

        kpis = {
            "events_with_date_pct": 0.96,
            "events_with_theme_pct": 0.94,
            "events_with_totals_pct": 0.97,
            "events_with_initiative_link_pct": 0.96,
            "member_votes_with_person_id_pct": 0.91,
        }

        default_gate = evaluate_vote_quality_gate(kpis)
        self.assertFalse(bool(default_gate["passed"]))
        self.assertEqual(len(default_gate["failures"]), 1)
        self.assertEqual(default_gate["failures"][0]["metric"], "events_with_theme_pct")

        custom_gate = evaluate_vote_quality_gate(
            kpis,
            thresholds={"events_with_theme_pct": 0.94},
        )
        self.assertTrue(bool(custom_gate["passed"]))


class TestParlInitiativeQuality(unittest.TestCase):
    def test_evaluate_initiative_gate_includes_extraction_thresholds(self) -> None:
        self.assertEqual(DEFAULT_INITIATIVE_QUALITY_THRESHOLDS["actionable_doc_links_closed_pct"], 1.0)
        self.assertEqual(DEFAULT_INITIATIVE_QUALITY_THRESHOLDS["extraction_coverage_pct"], 0.95)
        self.assertEqual(DEFAULT_INITIATIVE_QUALITY_THRESHOLDS["extraction_review_closed_pct"], 0.95)

        kpis = {
            "initiatives_with_title_pct": 0.99,
            "initiatives_with_expediente_pct": 0.99,
            "initiatives_with_legislature_pct": 0.99,
            "initiatives_linked_to_votes_pct": 1.0,
            "actionable_doc_links_closed_pct": 1.0,
            "extraction_coverage_pct": 1.0,
            "extraction_review_closed_pct": 0.94,
        }

        gate = evaluate_initiative_quality_gate(kpis)
        self.assertFalse(bool(gate["passed"]))
        self.assertEqual(
            [f["metric"] for f in gate["failures"]],
            ["extraction_review_closed_pct"],
        )

        gate_relaxed = evaluate_initiative_quality_gate(
            kpis,
            thresholds={"extraction_review_closed_pct": 0.90},
        )
        self.assertTrue(bool(gate_relaxed["passed"]))

    def test_evaluate_initiative_gate_fails_when_actionable_doc_links_open(self) -> None:
        kpis = {
            "initiatives_with_title_pct": 1.0,
            "initiatives_with_expediente_pct": 1.0,
            "initiatives_with_legislature_pct": 1.0,
            "initiatives_linked_to_votes_pct": 1.0,
            "actionable_doc_links_closed_pct": 0.99,
            "extraction_coverage_pct": 1.0,
            "extraction_review_closed_pct": 1.0,
        }
        gate = evaluate_initiative_quality_gate(kpis)
        self.assertFalse(bool(gate["passed"]))
        self.assertEqual([f["metric"] for f in gate["failures"]], ["actionable_doc_links_closed_pct"])

    def test_compute_initiative_kpis_include_doc_link_fetch_excerpt_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-init-quality.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)

                now = now_utc_iso()

                # Source records for downloaded initiative docs.
                from etl.parlamentario_es.db import upsert_source_records_with_content_sha256

                sr_map = upsert_source_records_with_content_sha256(
                    conn,
                    source_id="parl_initiative_docs",
                    rows=[
                        {
                            "source_record_id": "doc-cong-1",
                            "raw_payload": '{"url":"https://example.org/congreso/doc1.pdf"}',
                            "content_sha256": "sha-doc-cong-1",
                        },
                        {
                            "source_record_id": "doc-sen-1",
                            "raw_payload": '{"url":"https://example.org/senado/doc1.xml"}',
                            "content_sha256": "sha-doc-sen-1",
                        },
                    ],
                    snapshot_date="2026-02-22",
                    now_iso=now,
                )
                sr_cong = int(sr_map["doc-cong-1"])
                sr_sen = int(sr_map["doc-sen-1"])

                conn.executemany(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, legislature, expediente, title,
                      source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "congreso:init:1",
                            "15",
                            "121/000001/0000",
                            "Congreso iniciativa 1",
                            "congreso_iniciativas",
                            "{}",
                            now,
                            now,
                        ),
                        (
                            "congreso:init:2",
                            "15",
                            "121/000002/0000",
                            "Congreso iniciativa 2",
                            "congreso_iniciativas",
                            "{}",
                            now,
                            now,
                        ),
                        (
                            "senado:init:1",
                            "15",
                            "610/000001",
                            "Senado iniciativa 1",
                            "senado_iniciativas",
                            "{}",
                            now,
                            now,
                        ),
                        (
                            "senado:init:2",
                            "15",
                            "610/000002",
                            "Senado iniciativa 2",
                            "senado_iniciativas",
                            "{}",
                            now,
                            now,
                        ),
                    ],
                )

                conn.executemany(
                    """
                    INSERT INTO parl_initiative_documents (
                      initiative_id, doc_kind, doc_url, source_record_pk, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        # Congreso: one downloaded, one missing.
                        (
                            "congreso:init:1",
                            "bocg",
                            "https://example.org/congreso/doc1.pdf",
                            sr_cong,
                            now,
                            now,
                        ),
                        (
                            "congreso:init:1",
                            "ds",
                            "https://example.org/congreso/doc2.pdf",
                            None,
                            now,
                            now,
                        ),
                        # Senado: one downloaded, two missing.
                        (
                            "senado:init:1",
                            "bocg",
                            "https://example.org/senado/doc1.xml",
                            sr_sen,
                            now,
                            now,
                        ),
                        (
                            "senado:init:1",
                            "ds",
                            "https://example.org/senado/doc2.xml",
                            None,
                            now,
                            now,
                        ),
                        (
                            "senado:init:2",
                            "bocg",
                            "https://example.org/senado/doc3.xml",
                            None,
                            now,
                            now,
                        ),
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
                            "https://example.org/congreso/doc1.pdf",
                            sr_cong,
                            now,
                            "application/pdf",
                            "sha-doc-cong-1",
                            1234,
                            "raw/a.pdf",
                            "excerpt ok",
                            10,
                            now,
                            now,
                        ),
                        (
                            "parl_initiative_docs",
                            "https://example.org/senado/doc1.xml",
                            sr_sen,
                            now,
                            "text/xml",
                            "sha-doc-sen-1",
                            432,
                            "raw/b.xml",
                            None,
                            None,
                            now,
                            now,
                        ),
                    ],
                )

                conn.executemany(
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
                    [
                        (
                            sr_cong,
                            "parl_initiative_docs",
                            "congreso:init:1",
                            1,
                            1,
                            "bocg",
                            "sha-doc-cong-1",
                            "pdf",
                            "heuristic_subject_v2",
                            "Congreso iniciativa 1",
                            "Proyecto de ley de ejemplo",
                            "excerpt ok",
                            0.91,
                            0,
                            '{"subject_method":"title_hint_strong"}',
                            now,
                            now,
                        ),
                        (
                            sr_sen,
                            "parl_initiative_docs",
                            "senado:init:1",
                            1,
                            1,
                            "bocg",
                            "sha-doc-sen-1",
                            "xml",
                            "heuristic_subject_v2",
                            "Senado iniciativa 1",
                            "Convenio de ejemplo",
                            "",
                            0.74,
                            1,
                            '{"subject_method":"title_hint_strong"}',
                            now,
                            now,
                        ),
                    ],
                )

                conn.executemany(
                    """
                    INSERT INTO document_fetches (
                      doc_url, source_id, first_attempt_at, last_attempt_at,
                      attempts, fetched_ok, last_http_status, last_error,
                      content_type, content_sha256, bytes, raw_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "https://example.org/congreso/doc1.pdf",
                            "parl_initiative_docs",
                            now,
                            now,
                            1,
                            1,
                            200,
                            None,
                            "application/pdf",
                            "sha-doc-cong-1",
                            1234,
                            "raw/a.pdf",
                        ),
                        (
                            "https://example.org/congreso/doc2.pdf",
                            "parl_initiative_docs",
                            now,
                            now,
                            2,
                            0,
                            403,
                            "HTTPError: 403",
                            None,
                            None,
                            None,
                            None,
                        ),
                        (
                            "https://example.org/senado/doc1.xml",
                            "parl_initiative_docs",
                            now,
                            now,
                            1,
                            1,
                            200,
                            None,
                            "text/xml",
                            "sha-doc-sen-1",
                            432,
                            "raw/b.xml",
                        ),
                        (
                            "https://example.org/senado/doc2.xml",
                            "parl_initiative_docs",
                            now,
                            now,
                            3,
                            0,
                            404,
                            "HTTPError: 404",
                            None,
                            None,
                            None,
                            None,
                        ),
                        # senado/doc3.xml intentionally has no fetch row -> status bucket 0.
                    ],
                )

                conn.executemany(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        ("vote-cong-1", "congreso_votaciones", "{}", now, now),
                        ("vote-cong-2", "congreso_votaciones", "{}", now, now),
                        ("vote-sen-1", "senado_votaciones", "{}", now, now),
                        ("vote-sen-2", "senado_votaciones", "{}", now, now),
                    ],
                )

                conn.executemany(
                    """
                    INSERT INTO parl_vote_event_initiatives (
                      vote_event_id, initiative_id, link_method, confidence, evidence_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        ("vote-cong-1", "congreso:init:1", "test", 1.0, "{}", now, now),
                        ("vote-cong-2", "congreso:init:2", "test", 1.0, "{}", now, now),
                        ("vote-sen-1", "senado:init:1", "test", 1.0, "{}", now, now),
                        ("vote-sen-2", "senado:init:2", "test", 1.0, "{}", now, now),
                    ],
                )

                conn.commit()

                kpis = compute_initiative_quality_kpis(
                    conn,
                    source_ids=("congreso_iniciativas", "senado_iniciativas"),
                )

                # Overall doc-link metrics.
                self.assertEqual(int(kpis["total_doc_links"]), 5)
                self.assertEqual(int(kpis["downloaded_doc_links"]), 2)
                self.assertEqual(int(kpis["missing_doc_links"]), 3)
                self.assertEqual(int(kpis["missing_doc_links_likely_not_expected"]), 0)
                self.assertEqual(int(kpis["missing_doc_links_actionable"]), 3)
                self.assertAlmostEqual(float(kpis["downloaded_doc_links_pct"]), 0.4)
                self.assertAlmostEqual(float(kpis["effective_downloaded_doc_links_pct"]), 0.4)
                self.assertAlmostEqual(float(kpis["actionable_doc_links_closed_pct"]), 0.4)

                self.assertEqual(int(kpis["doc_links_with_fetch_status"]), 4)
                self.assertEqual(int(kpis["doc_links_missing_fetch_status"]), 1)
                self.assertAlmostEqual(float(kpis["fetch_status_coverage_pct"]), 0.8)

                self.assertEqual(int(kpis["downloaded_doc_links_with_excerpt"]), 1)
                self.assertEqual(int(kpis["downloaded_doc_links_missing_excerpt"]), 1)
                self.assertAlmostEqual(float(kpis["excerpt_coverage_pct"]), 0.5)
                self.assertEqual(int(kpis["downloaded_doc_links_with_extraction"]), 2)
                self.assertEqual(int(kpis["downloaded_doc_links_missing_extraction"]), 0)
                self.assertEqual(int(kpis["extraction_needs_review_doc_links"]), 1)
                self.assertAlmostEqual(float(kpis["extraction_coverage_pct"]), 1.0)
                self.assertAlmostEqual(float(kpis["extraction_needs_review_pct"]), 0.5)
                self.assertAlmostEqual(float(kpis["extraction_review_closed_pct"]), 0.5)

                self.assertEqual(
                    kpis["missing_doc_links_status_buckets"],
                    [
                        {"status": 404, "count": 1},
                        {"status": 403, "count": 1},
                        {"status": 0, "count": 1},
                    ],
                )

                by_source = kpis["by_source"]

                # Congreso source metrics.
                cong = by_source["congreso_iniciativas"]
                self.assertEqual(int(cong["total_doc_links"]), 2)
                self.assertEqual(int(cong["downloaded_doc_links"]), 1)
                self.assertEqual(int(cong["missing_doc_links"]), 1)
                self.assertEqual(int(cong["missing_doc_links_likely_not_expected"]), 0)
                self.assertEqual(int(cong["missing_doc_links_actionable"]), 1)
                self.assertAlmostEqual(float(cong["downloaded_doc_links_pct"]), 0.5)
                self.assertAlmostEqual(float(cong["effective_downloaded_doc_links_pct"]), 0.5)
                self.assertAlmostEqual(float(cong["actionable_doc_links_closed_pct"]), 0.5)
                self.assertEqual(int(cong["doc_links_with_fetch_status"]), 2)
                self.assertEqual(int(cong["doc_links_missing_fetch_status"]), 0)
                self.assertAlmostEqual(float(cong["fetch_status_coverage_pct"]), 1.0)
                self.assertEqual(int(cong["downloaded_doc_links_with_excerpt"]), 1)
                self.assertEqual(int(cong["downloaded_doc_links_missing_excerpt"]), 0)
                self.assertAlmostEqual(float(cong["excerpt_coverage_pct"]), 1.0)
                self.assertEqual(int(cong["downloaded_doc_links_with_extraction"]), 1)
                self.assertEqual(int(cong["downloaded_doc_links_missing_extraction"]), 0)
                self.assertEqual(int(cong["extraction_needs_review_doc_links"]), 0)
                self.assertAlmostEqual(float(cong["extraction_coverage_pct"]), 1.0)
                self.assertAlmostEqual(float(cong["extraction_needs_review_pct"]), 0.0)
                self.assertAlmostEqual(float(cong["extraction_review_closed_pct"]), 1.0)
                self.assertEqual(
                    cong["missing_doc_links_status_buckets"],
                    [{"status": 403, "count": 1}],
                )
                self.assertEqual(int(cong["initiatives_linked_to_votes"]), 2)
                self.assertEqual(int(cong["initiatives_linked_to_votes_with_downloaded_docs"]), 1)

                # Senado source metrics.
                sen = by_source["senado_iniciativas"]
                self.assertEqual(int(sen["total_doc_links"]), 3)
                self.assertEqual(int(sen["downloaded_doc_links"]), 1)
                self.assertEqual(int(sen["missing_doc_links"]), 2)
                self.assertEqual(int(sen["missing_doc_links_likely_not_expected"]), 0)
                self.assertEqual(int(sen["missing_doc_links_actionable"]), 2)
                self.assertAlmostEqual(float(sen["downloaded_doc_links_pct"]), 1.0 / 3.0)
                self.assertAlmostEqual(float(sen["effective_downloaded_doc_links_pct"]), 1.0 / 3.0)
                self.assertAlmostEqual(float(sen["actionable_doc_links_closed_pct"]), 1.0 / 3.0)
                self.assertEqual(int(sen["doc_links_with_fetch_status"]), 2)
                self.assertEqual(int(sen["doc_links_missing_fetch_status"]), 1)
                self.assertAlmostEqual(float(sen["fetch_status_coverage_pct"]), 2.0 / 3.0)
                self.assertEqual(int(sen["downloaded_doc_links_with_excerpt"]), 0)
                self.assertEqual(int(sen["downloaded_doc_links_missing_excerpt"]), 1)
                self.assertAlmostEqual(float(sen["excerpt_coverage_pct"]), 0.0)
                self.assertEqual(int(sen["downloaded_doc_links_with_extraction"]), 1)
                self.assertEqual(int(sen["downloaded_doc_links_missing_extraction"]), 0)
                self.assertEqual(int(sen["extraction_needs_review_doc_links"]), 1)
                self.assertAlmostEqual(float(sen["extraction_coverage_pct"]), 1.0)
                self.assertAlmostEqual(float(sen["extraction_needs_review_pct"]), 1.0)
                self.assertAlmostEqual(float(sen["extraction_review_closed_pct"]), 0.0)
                self.assertEqual(
                    sen["missing_doc_links_status_buckets"],
                    [
                        {"status": 404, "count": 1},
                        {"status": 0, "count": 1},
                    ],
                )
                self.assertEqual(
                    sen["global_enmiendas_vetos_analysis"],
                    {
                        "total_global_enmiendas_missing": 0,
                        "likely_not_expected_redundant_global_url": 0,
                        "likely_not_expected_total": 0,
                        "actionable_missing_count": 0,
                        "classification_counts": {
                            "likely_not_expected_redundant_global_url": 0,
                        },
                    },
                )
                self.assertEqual(int(sen["initiatives_linked_to_votes"]), 2)
                self.assertEqual(int(sen["initiatives_linked_to_votes_with_downloaded_docs"]), 1)
            finally:
                conn.close()

    def test_compute_initiative_kpis_classifies_redundant_senado_global_links(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-init-quality-senado-redundant.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                from etl.parlamentario_es.db import upsert_source_records_with_content_sha256

                detail_url = "https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=600&numEx=000777"
                global_url = "https://www.senado.es/legis15/expedientes/600/enmiendas/global_enmiendas_vetos_15_600000777.xml"

                sr_map = upsert_source_records_with_content_sha256(
                    conn,
                    source_id="parl_initiative_docs",
                    rows=[
                        {
                            "source_record_id": detail_url,
                            "raw_payload": '{"url":"https://www.senado.es/web/ficopendataservlet?legis=15&tipoFich=3&tipoEx=600&numEx=000777"}',
                            "content_sha256": "sha-senado-detail-777",
                        }
                    ],
                    snapshot_date="2026-02-22",
                    now_iso=now,
                )
                sr_detail = int(sr_map[detail_url])

                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, legislature, expediente, title,
                      source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "senado:init:redundant:1",
                        "15",
                        "600/000777",
                        "Senado iniciativa redundant global",
                        "senado_iniciativas",
                        "{}",
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
                        (
                            "senado:init:redundant:1",
                            "bocg",
                            detail_url,
                            sr_detail,
                            now,
                            now,
                        ),
                        (
                            "senado:init:redundant:1",
                            "bocg",
                            global_url,
                            None,
                            now,
                            now,
                        ),
                    ],
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
                        sr_detail,
                        now,
                        "text/xml",
                        "sha-senado-detail-777",
                        333,
                        "raw/senado_detail_777.xml",
                        "",
                        0,
                        now,
                        now,
                    ),
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
                        4,
                        0,
                        404,
                        "HTTPError: 404",
                        None,
                        None,
                        None,
                        None,
                    ),
                )
                conn.commit()

                kpis = compute_initiative_quality_kpis(
                    conn,
                    source_ids=("senado_iniciativas",),
                )

                self.assertEqual(int(kpis["total_doc_links"]), 2)
                self.assertEqual(int(kpis["downloaded_doc_links"]), 1)
                self.assertEqual(int(kpis["missing_doc_links"]), 1)
                self.assertEqual(int(kpis["missing_doc_links_likely_not_expected"]), 1)
                self.assertEqual(int(kpis["missing_doc_links_actionable"]), 0)
                self.assertAlmostEqual(float(kpis["effective_downloaded_doc_links_pct"]), 1.0)
                self.assertAlmostEqual(float(kpis["actionable_doc_links_closed_pct"]), 1.0)

                sen = kpis["by_source"]["senado_iniciativas"]
                self.assertEqual(int(sen["missing_doc_links_likely_not_expected"]), 1)
                self.assertEqual(int(sen["missing_doc_links_actionable"]), 0)
                self.assertAlmostEqual(float(sen["effective_downloaded_doc_links_pct"]), 1.0)
                self.assertAlmostEqual(float(sen["actionable_doc_links_closed_pct"]), 1.0)
                self.assertEqual(
                    sen["global_enmiendas_vetos_analysis"],
                    {
                        "total_global_enmiendas_missing": 1,
                        "likely_not_expected_redundant_global_url": 1,
                        "likely_not_expected_total": 1,
                        "actionable_missing_count": 0,
                        "classification_counts": {
                            "likely_not_expected_redundant_global_url": 1,
                        },
                    },
                )
            finally:
                conn.close()


class TestParlDeclaredQuality(unittest.TestCase):
    def test_evaluate_declared_gate_default_and_custom_thresholds(self) -> None:
        self.assertEqual(DEFAULT_DECLARED_QUALITY_THRESHOLDS["topic_evidence_with_nonempty_stance_pct"], 0.99)
        self.assertEqual(DEFAULT_DECLARED_QUALITY_THRESHOLDS["review_closed_pct"], 0.95)
        self.assertEqual(DEFAULT_DECLARED_QUALITY_THRESHOLDS["declared_positions_coverage_pct"], 0.95)

        kpis = {
            "topic_evidence_with_nonempty_stance_pct": 1.0,
            "review_closed_pct": 0.50,
            "declared_positions_coverage_pct": 0.50,
        }
        gate = evaluate_declared_quality_gate(kpis)
        self.assertFalse(bool(gate["passed"]))
        self.assertEqual(
            [f["metric"] for f in gate["failures"]],
            ["declared_positions_coverage_pct", "review_closed_pct"],
        )

        relaxed = evaluate_declared_quality_gate(
            kpis,
            thresholds={
                "review_closed_pct": 0.50,
                "declared_positions_coverage_pct": 0.50,
            },
        )
        self.assertTrue(bool(relaxed["passed"]))

    def test_compute_declared_kpis_review_and_positions_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-declared-quality.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                ckey = canonical_key(full_name="Partido Calidad", birth_date=None, territory_code="")
                conn.execute(
                    """
                    INSERT INTO persons (full_name, canonical_key, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    ("Partido Calidad", ckey, now, now),
                )
                person_id = int(
                    conn.execute(
                        "SELECT person_id FROM persons WHERE canonical_key = ?",
                        (ckey,),
                    ).fetchone()["person_id"]
                )

                conn.execute(
                    """
                    INSERT INTO topic_sets (name, description, institution_id, admin_level_id, territory_id, legislature, valid_from, valid_to, is_active, created_at, updated_at)
                    VALUES (?, NULL, NULL, NULL, NULL, 'XV', NULL, NULL, 1, ?, ?)
                    """,
                    ("Programas calidad", now, now),
                )
                topic_set_id = int(conn.execute("SELECT topic_set_id FROM topic_sets").fetchone()["topic_set_id"])
                conn.executemany(
                    """
                    INSERT INTO topics (canonical_key, label, description, parent_topic_id, created_at, updated_at)
                    VALUES (?, ?, NULL, NULL, ?, ?)
                    """,
                    [
                        ("vivienda", "Vivienda", now, now),
                        ("energia", "Energia", now, now),
                        ("empleo", "Empleo", now, now),
                    ],
                )
                topic_map = {
                    str(r["canonical_key"]): int(r["topic_id"])
                    for r in conn.execute(
                        "SELECT topic_id, canonical_key FROM topics WHERE canonical_key IN ('vivienda','energia','empleo')"
                    ).fetchall()
                }

                raw_payload = '{"party_id":1010,"kind":"programa"}'
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "programas_partidos",
                        "programas_partidos:es_generales_2023:1010:programa",
                        "2026-02-22",
                        raw_payload,
                        sha256_bytes(raw_payload.encode("utf-8")),
                        now,
                        now,
                    ),
                )
                source_record_pk = int(
                    conn.execute(
                        """
                        SELECT source_record_pk
                        FROM source_records
                        WHERE source_id = 'programas_partidos'
                        """,
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
                        "programas_partidos",
                        "https://example.invalid/programa-calidad.html",
                        source_record_pk,
                        now,
                        "text/html",
                        "sha-doc-calidad",
                        234,
                        "raw/programa-calidad.html",
                        "Texto de calidad",
                        16,
                        now,
                        now,
                    ),
                )

                conn.executemany(
                    """
                    INSERT INTO topic_evidence (
                      topic_id, topic_set_id,
                      person_id, mandate_id,
                      institution_id, admin_level_id, territory_id,
                      evidence_type, evidence_date, title, excerpt,
                      stance, polarity, weight, confidence,
                      topic_method, stance_method,
                      vote_event_id, initiative_id,
                      source_id, source_url, source_record_pk, source_snapshot_date,
                      raw_payload, created_at, updated_at
                    ) VALUES (
                      ?, ?,
                      ?, NULL,
                      NULL, NULL, NULL,
                      'declared:programa', '2026-02-22', ?, ?,
                      ?, 0, 0.5, 0.6,
                      'programa:concern:v1', 'programa_metadata',
                      NULL, NULL,
                      'programas_partidos', 'https://example.invalid/programa-calidad.html', ?, '2026-02-22',
                      '{}', ?, ?
                    )
                    """,
                    [
                        (
                            topic_map["vivienda"],
                            topic_set_id,
                            person_id,
                            "Programa + vivienda",
                            "Construiremos vivienda",
                            "support",
                            source_record_pk,
                            now,
                            now,
                        ),
                        (
                            topic_map["energia"],
                            topic_set_id,
                            person_id,
                            "Programa - energia",
                            "No apoyamos esta medida",
                            "oppose",
                            source_record_pk,
                            now,
                            now,
                        ),
                        (
                            topic_map["empleo"],
                            topic_set_id,
                            person_id,
                            "Programa empleo sin señal",
                            "Texto ambiguo",
                            "unclear",
                            source_record_pk,
                            now,
                            now,
                        ),
                    ],
                )
                evidence_rows = conn.execute(
                    """
                    SELECT evidence_id, stance
                    FROM topic_evidence
                    WHERE source_id = 'programas_partidos'
                    ORDER BY evidence_id
                    """
                ).fetchall()
                ev_support = int(evidence_rows[0]["evidence_id"])
                ev_oppose = int(evidence_rows[1]["evidence_id"])

                conn.executemany(
                    """
                    INSERT INTO topic_evidence_reviews (
                      evidence_id, source_id, source_record_pk, review_reason, status,
                      suggested_stance, suggested_polarity, suggested_confidence,
                      extractor_version, note, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            ev_support,
                            "programas_partidos",
                            source_record_pk,
                            "low_confidence",
                            "pending",
                            "support",
                            1,
                            0.61,
                            "declared:regex_v2",
                            "",
                            now,
                            now,
                        ),
                        (
                            ev_oppose,
                            "programas_partidos",
                            source_record_pk,
                            "no_signal",
                            "ignored",
                            None,
                            None,
                            None,
                            "declared:regex_v2",
                            "manual",
                            now,
                            now,
                        ),
                    ],
                )

                conn.execute(
                    """
                    INSERT INTO topic_positions (
                      topic_id, topic_set_id, person_id, mandate_id,
                      institution_id, admin_level_id, territory_id,
                      as_of_date, window_days, stance, score, confidence,
                      evidence_count, last_evidence_date, computed_method,
                      computed_version, computed_at, created_at, updated_at
                    ) VALUES (?, ?, ?, NULL, NULL, NULL, NULL, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic_map["vivienda"],
                        topic_set_id,
                        person_id,
                        "2026-02-22",
                        "support",
                        0.75,
                        0.75,
                        1,
                        "2026-02-22",
                        "declared",
                        "declared:v1",
                        now,
                        now,
                        now,
                    ),
                )
                conn.commit()

                kpis = compute_declared_quality_kpis(
                    conn,
                    source_ids=("programas_partidos",),
                )
                self.assertEqual(int(kpis["source_records"]), 1)
                self.assertEqual(int(kpis["text_documents"]), 1)
                self.assertEqual(int(kpis["topic_evidence_total"]), 3)
                self.assertEqual(int(kpis["topic_evidence_with_nonempty_stance"]), 3)
                self.assertEqual(int(kpis["topic_evidence_with_supported_stance"]), 2)
                self.assertEqual(int(kpis["review_total"]), 2)
                self.assertEqual(int(kpis["review_pending"]), 1)
                self.assertEqual(int(kpis["review_ignored"]), 1)
                self.assertEqual(int(kpis["declared_positions_scope_total"]), 2)
                self.assertEqual(int(kpis["declared_positions_total"]), 1)
                self.assertAlmostEqual(float(kpis["topic_evidence_with_nonempty_stance_pct"]), 1.0)
                self.assertAlmostEqual(float(kpis["review_closed_pct"]), 0.5)
                self.assertAlmostEqual(float(kpis["declared_positions_coverage_pct"]), 0.5)

                by_source = kpis["by_source"]["programas_partidos"]
                self.assertEqual(int(by_source["topic_evidence_total"]), 3)
                self.assertAlmostEqual(float(by_source["review_closed_pct"]), 0.5)
                self.assertAlmostEqual(float(by_source["declared_positions_coverage_pct"]), 0.5)
            finally:
                conn.close()

    def test_compute_declared_kpis_scope_zero_has_full_positions_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-declared-quality-unclear-only.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                ckey = canonical_key(full_name="Partido Ambiguo", birth_date=None, territory_code="")
                conn.execute(
                    """
                    INSERT INTO persons (full_name, canonical_key, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    ("Partido Ambiguo", ckey, now, now),
                )
                person_id = int(
                    conn.execute(
                        "SELECT person_id FROM persons WHERE canonical_key = ?",
                        (ckey,),
                    ).fetchone()["person_id"]
                )
                conn.execute(
                    """
                    INSERT INTO topic_sets (name, description, institution_id, admin_level_id, territory_id, legislature, valid_from, valid_to, is_active, created_at, updated_at)
                    VALUES (?, NULL, NULL, NULL, NULL, 'XV', NULL, NULL, 1, ?, ?)
                    """,
                    ("Programas ambiguos", now, now),
                )
                topic_set_id = int(conn.execute("SELECT topic_set_id FROM topic_sets").fetchone()["topic_set_id"])
                conn.execute(
                    """
                    INSERT INTO topics (canonical_key, label, description, parent_topic_id, created_at, updated_at)
                    VALUES (?, ?, NULL, NULL, ?, ?)
                    """,
                    ("sanidad", "Sanidad", now, now),
                )
                topic_id = int(
                    conn.execute(
                        "SELECT topic_id FROM topics WHERE canonical_key = 'sanidad'"
                    ).fetchone()["topic_id"]
                )
                conn.execute(
                    """
                    INSERT INTO topic_evidence (
                      topic_id, topic_set_id,
                      person_id, mandate_id,
                      institution_id, admin_level_id, territory_id,
                      evidence_type, evidence_date, title, excerpt,
                      stance, polarity, weight, confidence,
                      topic_method, stance_method,
                      vote_event_id, initiative_id,
                      source_id, source_url, source_record_pk, source_snapshot_date,
                      raw_payload, created_at, updated_at
                    ) VALUES (
                      ?, ?,
                      ?, NULL,
                      NULL, NULL, NULL,
                      'declared:programa', '2026-02-22', ?, ?,
                      ?, 0, 0.5, 0.6,
                      'programa:concern:v1', 'programa_metadata',
                      NULL, NULL,
                      'programas_partidos', 'https://example.invalid/ambiguo.html', NULL, '2026-02-22',
                      '{}', ?, ?
                    )
                    """,
                    (
                        topic_id,
                        topic_set_id,
                        person_id,
                        "Programa ambiguo",
                        "Sin postura clara",
                        "unclear",
                        now,
                        now,
                    ),
                )
                conn.commit()

                kpis = compute_declared_quality_kpis(conn, source_ids=("programas_partidos",))
                self.assertEqual(int(kpis["topic_evidence_total"]), 1)
                self.assertEqual(int(kpis["topic_evidence_with_supported_stance"]), 0)
                self.assertEqual(int(kpis["declared_positions_scope_total"]), 0)
                self.assertEqual(int(kpis["declared_positions_total"]), 0)
                self.assertAlmostEqual(float(kpis["declared_positions_coverage_pct"]), 1.0)
                self.assertAlmostEqual(float(kpis["review_closed_pct"]), 1.0)
            finally:
                conn.close()


class TestParlBackfillMemberIds(unittest.TestCase):
    def _seed_institution(self, conn: sqlite3.Connection, *, name: str = "Congreso") -> int:
        row = conn.execute(
            "SELECT institution_id FROM institutions WHERE name = ? AND level = ? AND territory_code = ''",
            (name, "nacional"),
        ).fetchone()
        if row is not None:
            return int(row["institution_id"])

        now = now_utc_iso()
        conn.execute(
            """
            INSERT INTO institutions (
                name, level, territory_code, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (name, "nacional", "", now, now),
        )
        return int(
            conn.execute(
                "SELECT institution_id FROM institutions WHERE name = ? AND level = ?",
                (name, "nacional"),
            ).fetchone()["institution_id"]
        )

    def _seed_source_if_missing(
        self,
        conn: sqlite3.Connection,
        source_id: str,
        *,
        name: str,
        scope: str = "nacional",
        default_url: str = "",
        data_format: str = "json",
    ) -> None:
        exists = conn.execute(
            "SELECT 1 FROM sources WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        if exists is not None:
            return
        now = now_utc_iso()
        conn.execute(
            """
            INSERT INTO sources (source_id, name, scope, default_url, data_format, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (source_id, name, scope, default_url, data_format, now, now),
        )

    def _seed_person_and_mandate(
        self,
        conn: sqlite3.Connection,
        *,
        full_name: str,
        given_name: str | None,
        family_name: str | None,
        source_id: str,
        is_active: int,
        start_date: str | None = None,
        end_date: str | None = None,
        source_record_id: str,
    ) -> int:
        now = now_utc_iso()
        institution_id = self._seed_institution(conn)
        ckey = canonical_key(full_name=full_name, birth_date=None, territory_code="")

        cur = conn.execute(
            """
            INSERT INTO persons (
                full_name, given_name, family_name, canonical_key, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (full_name, given_name, family_name, ckey, now, now),
        )
        person_id = int(cur.lastrowid)

        conn.execute(
            """
            INSERT INTO mandates (
              person_id, institution_id, role_title, level, territory_code,
              start_date, end_date, is_active, source_id, source_record_id,
              first_seen_at, last_seen_at, raw_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                person_id,
                institution_id,
                "Diputado",
                "nacional",
                "",
                start_date,
                end_date,
                is_active,
                source_id,
                source_record_id,
                now,
                now,
                "{}",
            ),
        )
        return person_id

    def _seed_mandate_for_person(
        self,
        conn: sqlite3.Connection,
        *,
        person_id: int,
        source_id: str,
        is_active: int,
        start_date: str | None = None,
        end_date: str | None = None,
        source_record_id: str,
    ) -> None:
        now = now_utc_iso()
        institution_id = self._seed_institution(conn)
        conn.execute(
            """
            INSERT INTO mandates (
              person_id, institution_id, role_title, level, territory_code,
              start_date, end_date, is_active, source_id, source_record_id,
              first_seen_at, last_seen_at, raw_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                person_id,
                institution_id,
                "Diputado",
                "nacional",
                "",
                start_date,
                end_date,
                is_active,
                source_id,
                source_record_id,
                now,
                now,
                "{}",
            ),
        )

    def test_backfill_vote_member_ids_matches_on_name_and_legislature(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-backfill.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                self._seed_source_if_missing(conn, "congreso_diputados", name="Congreso de los Diputados")
                self._seed_source_if_missing(conn, "senado_senadores", name="Senado de España")

                person_same_leg = self._seed_person_and_mandate(
                    conn,
                    full_name="Ana Torres",
                    given_name="Ana",
                    family_name="Torres",
                    source_id="congreso_diputados",
                    is_active=1,
                    start_date="2025-01-01",
                    source_record_id="m-cong-same-leg",
                )
                self._seed_mandate_for_person(
                    conn,
                    person_id=person_same_leg,
                    source_id="congreso_diputados",
                    is_active=1,
                    start_date="2023-01-01",
                    source_record_id="m-cong-other-leg",
                )
                person_senado = self._seed_person_and_mandate(
                    conn,
                    full_name="Luis Pérez",
                    given_name="Luis",
                    family_name="Pérez",
                    source_id="senado_senadores",
                    is_active=1,
                    start_date="2024-01-01",
                    source_record_id="m-sen-old",
                )

                now = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, vote_date, source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("ev-cong", "XV", "2026-01-15", "congreso_votaciones", "{}", now, now),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, vote_date, source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("ev-sen", "15", "2024-03-10", "senado_votaciones", "{}", now, now),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_member_votes (
                      vote_event_id, seat, member_name, member_name_normalized, vote_choice, source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("ev-cong", "s1", "Torres, Ana", "ana torres", "SI", "congreso_votaciones", "{}", now, now),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_member_votes (
                      vote_event_id, seat, member_name, member_name_normalized, vote_choice, source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("ev-sen", "s2", "Luis Pérez", "luis perez", "NO", "senado_votaciones", "{}", now, now),
                )
                conn.commit()

                report = backfill_vote_member_person_ids(conn, vote_source_ids=("congreso_votaciones", "senado_votaciones"))
                self.assertEqual(report.get("total_checked"), 2)
                self.assertEqual(report.get("total_updated"), 2)
                self.assertEqual(report.get("total_unmatched"), 0)

                rows = conn.execute(
                    """
                    SELECT person_id FROM parl_vote_member_votes
                    ORDER BY seat
                    """
                ).fetchall()
                self.assertEqual(int(rows[0]["person_id"]), person_same_leg)
                self.assertEqual(int(rows[1]["person_id"]), person_senado)
            finally:
                conn.close()

    def test_backfill_vote_member_ids_dry_run_does_not_mutate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-backfill-dry.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                self._seed_source_if_missing(conn, "senado_senadores", name="Senado de España")

                self._seed_person_and_mandate(
                    conn,
                    full_name="María Rojas",
                    given_name="María",
                    family_name="Rojas",
                    source_id="senado_senadores",
                    is_active=0,
                    source_record_id="m-sen-dry",
                )

                now = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, vote_date, source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("ev-sen-2", "14", "2024-04-10", "senado_votaciones", "{}", now, now),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_member_votes (
                      vote_event_id, seat, member_name, member_name_normalized, vote_choice, source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("ev-sen-2", "s1", "María Rojas", "maria rojas", "ABST", "senado_votaciones", "{}", now, now),
                )
                conn.commit()

                report = backfill_vote_member_person_ids(
                    conn,
                    vote_source_ids=("senado_votaciones",),
                    dry_run=True,
                )
                self.assertEqual(report.get("total_checked"), 1)
                self.assertEqual(report.get("total_updated"), 1)
                self.assertEqual(report.get("total_unmatched"), 0)

                row = conn.execute(
                    "SELECT person_id FROM parl_vote_member_votes WHERE vote_event_id = ?",
                    ("ev-sen-2",),
                ).fetchone()
                self.assertIsNone(row["person_id"])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
