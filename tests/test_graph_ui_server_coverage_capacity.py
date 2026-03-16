from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources
from scripts import graph_ui_server as g


class TestGraphUiServerCoverageCapacity(unittest.TestCase):
    def _seed_fixture(self, db_path: Path) -> None:
        conn = open_db(db_path)
        try:
            apply_schema(conn, DEFAULT_SCHEMA)
            seed_sources(conn)
            now_iso = "2026-03-14T09:00:00Z"

            conn.execute(
                """
                INSERT INTO parl_vote_events (
                  vote_event_id, legislature, vote_date, title, source_id, source_url,
                  raw_payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "vote:1",
                    "15",
                    "2026-03-01",
                    "Voto 1",
                    "congreso_votaciones",
                    "https://example.invalid/vote-1",
                    "{}",
                    now_iso,
                    now_iso,
                ),
            )
            conn.execute(
                """
                INSERT INTO parl_vote_events (
                  vote_event_id, legislature, vote_date, title, source_id, source_url,
                  raw_payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "vote:2",
                    "15",
                    "2026-03-02",
                    "Voto 2",
                    "senado_votaciones",
                    "https://example.invalid/vote-2",
                    "{}",
                    now_iso,
                    now_iso,
                ),
            )

            conn.execute(
                """
                INSERT INTO source_records (
                  source_id, source_record_id, source_snapshot_date, raw_payload,
                  content_sha256, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "parl_initiative_docs",
                    "doc:1",
                    "2026-03-14",
                    "{}",
                    "sha-doc-1",
                    now_iso,
                    now_iso,
                ),
            )
            source_record_pk = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

            conn.execute(
                """
                INSERT INTO parl_initiatives (
                  initiative_id, legislature, expediente, title, links_bocg_json, links_ds_json,
                  source_id, source_url, raw_payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "init:1",
                    "15",
                    "121/000001/0000",
                    "Iniciativa 1",
                    '["https://example.invalid/bocg-1.pdf", "https://example.invalid/bocg-2.pdf"]',
                    '["https://example.invalid/ds-1.pdf"]',
                    "congreso_iniciativas",
                    "https://example.invalid/init-1",
                    "{}",
                    now_iso,
                    now_iso,
                ),
            )

            conn.execute(
                """
                INSERT INTO parl_vote_event_initiatives (
                  vote_event_id, initiative_id, link_method, confidence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("vote:1", "init:1", "fixture", 1.0, now_iso, now_iso),
            )

            conn.execute(
                """
                INSERT INTO parl_initiative_documents (
                  initiative_id, doc_kind, doc_url, source_record_pk, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "init:1",
                    "bocg",
                    "https://example.invalid/bocg-1.pdf",
                    source_record_pk,
                    now_iso,
                    now_iso,
                ),
            )
            conn.execute(
                """
                INSERT INTO parl_initiative_doc_extractions (
                  source_record_pk, source_id, sample_initiative_id, initiatives_count, doc_refs_count,
                  doc_kinds_csv, content_sha256, doc_format, extractor_version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_record_pk,
                    "parl_initiative_docs",
                    "init:1",
                    1,
                    1,
                    "bocg",
                    "sha-doc-1",
                    "pdf",
                    "fixture-v1",
                    now_iso,
                    now_iso,
                ),
            )

            conn.execute(
                """
                INSERT INTO parl_initiative_text_versions (
                  initiative_text_version_id, initiative_id, chamber, doc_kind, version_order,
                  published_date, stage_kind, source_id, source_url, raw_payload_json,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "tv:1",
                    "init:1",
                    "congreso",
                    "bocg",
                    1,
                    "2026-03-01",
                    "initial_text",
                    "congreso_iniciativas",
                    "https://example.invalid/bocg-1.pdf",
                    "{}",
                    now_iso,
                    now_iso,
                ),
            )

            for fragment_id, order in (("frag:1", 1), ("frag:2", 2), ("frag:3", 3)):
                conn.execute(
                    """
                    INSERT INTO parl_text_fragments (
                      fragment_id, initiative_text_version_id, initiative_id, source_id,
                      fragment_order, fragment_kind, fragment_text, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fragment_id,
                        "tv:1",
                        "init:1",
                        "congreso_iniciativas",
                        order,
                        "article",
                        f"Fragmento {order}",
                        now_iso,
                        now_iso,
                    ),
                )

            conn.execute(
                """
                INSERT INTO parl_fragment_measure_reviews (
                  fragment_id, initiative_id, initiative_text_version_id, source_id, status,
                  raw_payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("frag:1", "init:1", "tv:1", "congreso_iniciativas", "resolved", "{}", now_iso, now_iso),
            )
            conn.execute(
                """
                INSERT INTO parl_fragment_measure_reviews (
                  fragment_id, initiative_id, initiative_text_version_id, source_id, status,
                  raw_payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("frag:2", "init:1", "tv:1", "congreso_iniciativas", "ignored", "{}", now_iso, now_iso),
            )

            conn.execute(
                """
                INSERT INTO parl_initiative_measure_review_tasks (
                  task_id, initiative_id, source_id, review_reason, status, priority,
                  evidence_bundle_dir, raw_payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "task:1",
                    "init:1",
                    "congreso_iniciativas",
                    "official_docs_bundle",
                    "resolved",
                    100,
                    "tmp/bundle-1",
                    "{}",
                    now_iso,
                    now_iso,
                ),
            )
            conn.execute(
                """
                INSERT INTO parl_initiative_measure_points (
                  measure_point_id, task_id, initiative_id, source_id,
                  measure_title, citizen_summary, search_terms_json, primary_vote_event_ids_json,
                  evidence_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "mp:1",
                    "task:1",
                    "init:1",
                    "congreso_iniciativas",
                    "Medida 1",
                    "Resumen 1",
                    "[]",
                    "[]",
                    "[]",
                    now_iso,
                    now_iso,
                ),
            )

            conn.commit()
        finally:
            conn.close()

    def test_build_coverage_capacity_payload_computes_key_cells(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "coverage.db"
            self._seed_fixture(db_path)
            conn = open_db(db_path)
            try:
                payload = g.build_coverage_capacity_payload(
                    conn,
                    all_sources=[
                        {
                            "source_id": "congreso_votaciones",
                            "state": "ok",
                            "sql_status": "DONE",
                            "last_loaded": 1,
                            "flags": {"has_any": True, "blocked_note": False},
                        },
                        {
                            "source_id": "senado_votaciones",
                            "state": "degraded",
                            "sql_status": "PARTIAL",
                            "last_loaded": 1,
                            "flags": {"has_any": True, "blocked_note": True},
                        },
                        {
                            "source_id": "congreso_iniciativas",
                            "state": "ok",
                            "sql_status": "DONE",
                            "last_loaded": 1,
                            "flags": {"has_any": True, "blocked_note": False},
                        },
                        {
                            "source_id": "senado_iniciativas",
                            "state": "degraded",
                            "sql_status": "PARTIAL",
                            "last_loaded": 0,
                            "flags": {"has_any": False, "blocked_note": True},
                        },
                        {
                            "source_id": "congreso_intervenciones",
                            "state": "ok",
                            "sql_status": "DONE",
                            "last_loaded": 1,
                            "flags": {"has_any": True, "blocked_note": False},
                        },
                    ],
                    analytics_payload={
                        "evidence": {
                            "topic_evidence_declared_total": 10,
                            "declared_evidence_with_text_excerpt": 6,
                            "topic_evidence_declared_with_signal": 4,
                        }
                    },
                    parl_quality={
                        "votes": {
                            "kpis": {
                                "events_with_initiative_link": 1,
                                "events_with_theme": 1,
                            }
                        }
                    },
                )
            finally:
                conn.close()

        by_id = {str(cell.get("id")): cell for cell in payload.get("cells", [])}
        self.assertIn("national_votes", by_id)
        self.assertIn("national_initiative_docs", by_id)
        self.assertIn("declared_evidence_signal", by_id)
        self.assertIn("fragment_measure_reviews", by_id)
        self.assertIn("initiative_measure_tasks", by_id)

        votes = by_id["national_votes"]
        self.assertEqual(votes["ideal_total"], 2)
        self.assertEqual(votes["stages"]["linked"], 1)
        self.assertTrue(votes["blocked"])

        docs = by_id["national_initiative_docs"]
        self.assertEqual(docs["ideal_total"], 3)
        self.assertEqual(docs["stages"]["downloaded"], 1)
        self.assertEqual(docs["stages"]["processed"], 1)
        self.assertEqual(docs["stages"]["linked"], 1)

        declared = by_id["declared_evidence_signal"]
        self.assertEqual(declared["ideal_total"], 10)
        self.assertEqual(declared["stages"]["downloaded"], 6)
        self.assertEqual(declared["stages"]["linked"], 4)
        self.assertEqual(declared["primary_percent"], 40.0)

        fragments = by_id["fragment_measure_reviews"]
        self.assertEqual(fragments["ideal_total"], 3)
        self.assertEqual(fragments["stages"]["linked"], 2)
        self.assertEqual(fragments["stages"]["published"], 1)

        tasks = by_id["initiative_measure_tasks"]
        self.assertEqual(tasks["ideal_total"], 1)
        self.assertEqual(tasks["stages"]["downloaded"], 1)
        self.assertEqual(tasks["stages"]["linked"], 1)
        self.assertEqual(tasks["stages"]["published"], 1)

        summary = payload.get("summary") or {}
        self.assertGreaterEqual(int(summary.get("cells_total", 0)), 5)
        self.assertIsNotNone(summary.get("weighted_percent"))

    def test_sources_status_payload_includes_coverage_capacity_contract(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "status.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                conn.commit()
            finally:
                conn.close()

            payload = g.build_sources_status_payload(db_path)

        coverage = payload.get("coverage_capacity") or {}
        self.assertEqual(coverage.get("meta", {}).get("path"), "docs/coverage_capacity_model.json")
        self.assertIn("summary", coverage)
        self.assertIn("cells", coverage)


if __name__ == "__main__":
    unittest.main()
