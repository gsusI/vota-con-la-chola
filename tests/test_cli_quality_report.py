from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from etl.parlamentario_es.cli import main
from etl.parlamentario_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG as PARL_SOURCE_CONFIG
from etl.parlamentario_es.db import (
    apply_schema,
    open_db,
    seed_sources as seed_parl_sources,
    upsert_source_records_with_content_sha256,
)
from etl.parlamentario_es.linking import link_congreso_votes_to_initiatives, link_senado_votes_to_initiatives
from etl.parlamentario_es.pipeline import ingest_one_source as ingest_parl_source
from etl.parlamentario_es.registry import get_connectors
from etl.politicos_es.util import canonical_key, now_utc_iso, sha256_bytes


class TestParlCliQualityReport(unittest.TestCase):
    def _seed_minimal_quality_fixture(
        self,
        conn,
        *,
        extraction_needs_review: int,
        actionable_missing_doc_links: int = 0,
    ) -> None:
        now = now_utc_iso()
        initiative_id = "congreso:init:test:1"
        doc_url = "https://example.org/congreso/doc-test-1.pdf"

        sr_map = upsert_source_records_with_content_sha256(
            conn,
            source_id="parl_initiative_docs",
            rows=[
                {
                    "source_record_id": doc_url,
                    "raw_payload": '{"url":"https://example.org/congreso/doc-test-1.pdf"}',
                    "content_sha256": "sha-test-doc-1",
                }
            ],
            snapshot_date="2026-02-22",
            now_iso=now,
        )
        source_record_pk = int(sr_map[doc_url])

        conn.execute(
            """
            INSERT INTO persons (full_name, canonical_key, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            ("Diputado Test", "person:test:1", now, now),
        )
        person_id = int(
            conn.execute(
                "SELECT person_id FROM persons WHERE canonical_key = ?",
                ("person:test:1",),
            ).fetchone()["person_id"]
        )

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
                "121/000999/0000",
                "Proyecto de Ley Test",
                "congreso_iniciativas",
                "{}",
                now,
                now,
            ),
        )

        conn.execute(
            """
            INSERT INTO parl_vote_events (
              vote_event_id, legislature, vote_date, title,
              totals_yes, totals_no, source_id, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "congreso:vote:test:1",
                "15",
                "2026-02-22",
                "Votación de prueba",
                1,
                0,
                "congreso_votaciones",
                "{}",
                now,
                now,
            ),
        )

        conn.execute(
            """
            INSERT INTO parl_vote_event_initiatives (
              vote_event_id, initiative_id, link_method, confidence, evidence_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "congreso:vote:test:1",
                initiative_id,
                "test",
                1.0,
                "{}",
                now,
                now,
            ),
        )

        conn.execute(
            """
            INSERT INTO parl_vote_member_votes (
              vote_event_id, seat, member_name, member_name_normalized, person_id,
              vote_choice, source_id, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "congreso:vote:test:1",
                "1",
                "Diputado Test",
                "diputado test",
                person_id,
                "si",
                "congreso_votaciones",
                "{}",
                now,
                now,
            ),
        )

        docs_rows = [
            (
                initiative_id,
                "bocg",
                doc_url,
                source_record_pk,
                now,
                now,
            )
        ]
        if int(actionable_missing_doc_links) > 0:
            docs_rows.append(
                (
                    initiative_id,
                    "ds",
                    "https://example.org/congreso/doc-test-missing.xml",
                    None,
                    now,
                    now,
                )
            )
        conn.executemany(
            """
            INSERT INTO parl_initiative_documents (
              initiative_id, doc_kind, doc_url, source_record_pk, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            docs_rows,
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
                doc_url,
                source_record_pk,
                now,
                "application/pdf",
                "sha-test-doc-1",
                123,
                "raw/test-doc-1.pdf",
                "texto",
                5,
                now,
                now,
            ),
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
                source_record_pk,
                "parl_initiative_docs",
                initiative_id,
                1,
                1,
                "bocg",
                "sha-test-doc-1",
                "pdf",
                "heuristic_subject_v2",
                "Proyecto de Ley Test",
                "Proyecto de Ley Test",
                "texto",
                0.95,
                int(extraction_needs_review),
                '{"subject_method":"title_hint_strong"}',
                now,
                now,
            ),
        )

        conn.commit()

    def _seed_minimal_declared_fixture(
        self,
        conn,
        *,
        review_pending: int,
        include_declared_position: int,
    ) -> None:
        now = now_utc_iso()
        ckey = canonical_key(full_name="Partido Declared Test", birth_date=None, territory_code="")
        conn.execute(
            """
            INSERT INTO persons (full_name, canonical_key, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            ("Partido Declared Test", ckey, now, now),
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
            ("Programas CLI quality", now, now),
        )
        topic_set_id = int(conn.execute("SELECT topic_set_id FROM topic_sets").fetchone()["topic_set_id"])
        conn.execute(
            """
            INSERT INTO topics (canonical_key, label, description, parent_topic_id, created_at, updated_at)
            VALUES (?, ?, NULL, NULL, ?, ?)
            """,
            ("vivienda", "Vivienda", now, now),
        )
        topic_id = int(
            conn.execute(
                "SELECT topic_id FROM topics WHERE canonical_key = ?",
                ("vivienda",),
            ).fetchone()["topic_id"]
        )

        raw_payload = '{"party_id":2020,"kind":"programa"}'
        conn.execute(
            """
            INSERT INTO source_records (
              source_id, source_record_id, source_snapshot_date,
              raw_payload, content_sha256, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "programas_partidos",
                "programas_partidos:es_generales_2023:2020:programa",
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
                "https://example.invalid/programa-cli-quality.html",
                source_record_pk,
                now,
                "text/html",
                "sha-programa-cli-quality",
                111,
                "raw/programa-cli-quality.html",
                "texto",
                5,
                now,
                now,
            ),
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
              'support', 1, 1.0, 0.9,
              'programa:concern:v1', 'programa_metadata',
              NULL, NULL,
              'programas_partidos', 'https://example.invalid/programa-cli-quality.html', ?, '2026-02-22',
              '{}', ?, ?
            )
            """,
            (
                topic_id,
                topic_set_id,
                person_id,
                "Programa test",
                "Texto test",
                source_record_pk,
                now,
                now,
            ),
        )
        evidence_id = int(
            conn.execute(
                """
                SELECT evidence_id
                FROM topic_evidence
                WHERE source_id = 'programas_partidos'
                ORDER BY evidence_id DESC
                LIMIT 1
                """
            ).fetchone()["evidence_id"]
        )

        review_status = "pending" if int(review_pending) else "ignored"
        conn.execute(
            """
            INSERT INTO topic_evidence_reviews (
              evidence_id, source_id, source_record_pk, review_reason, status,
              suggested_stance, suggested_polarity, suggested_confidence,
              extractor_version, note, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                "programas_partidos",
                source_record_pk,
                "low_confidence",
                review_status,
                "support",
                1,
                0.9,
                "declared:regex_v2",
                "",
                now,
                now,
            ),
        )

        if int(include_declared_position):
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
                    topic_id,
                    topic_set_id,
                    person_id,
                    "2026-02-22",
                    "support",
                    0.9,
                    0.9,
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

    def test_quality_report_json_out_is_written_and_stable(self) -> None:
        snapshot_date = "2026-02-12"
        out_file_name = f"votaciones-kpis-cli-test-{snapshot_date}.json"
        connectors = get_connectors()

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality-cli.db"
            raw_dir = Path(td) / "raw"
            out_path = Path(td) / out_file_name

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                for source_id in ("congreso_votaciones", "senado_votaciones"):
                    connector = connectors[source_id]
                    sample_path = Path(PARL_SOURCE_CONFIG[source_id]["fallback_file"])
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
            finally:
                conn.close()

            stdout1 = io.StringIO()
            with redirect_stdout(stdout1):
                code = main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones,senado_votaciones",
                        "--json-out",
                        str(out_path),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue(out_path.exists(), f"Missing quality json output: {out_path}")

            snapshot = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["source_ids"], ["congreso_votaciones", "senado_votaciones"])
            self.assertIn("kpis", snapshot)
            self.assertIn("gate", snapshot)
            self.assertIn("OK wrote:", stdout1.getvalue())

            content_first = out_path.read_bytes()
            stdout2 = io.StringIO()
            with redirect_stdout(stdout2):
                code2 = main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones,senado_votaciones",
                        "--json-out",
                        str(out_path),
                    ]
                )
            self.assertEqual(code2, 0)
            self.assertEqual(content_first, out_path.read_bytes())
            self.assertIn("OK unchanged:", stdout2.getvalue())

    def test_quality_report_include_unmatched_people_preview(self) -> None:
        snapshot_date = "2026-02-12"
        out_file_name = f"votaciones-kpis-cli-unmatched-test-{snapshot_date}.json"
        connectors = get_connectors()

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality-cli-unmatched.db"
            raw_dir = Path(td) / "raw"
            out_path = Path(td) / out_file_name

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                for source_id in ("congreso_votaciones", "senado_votaciones"):
                    connector = connectors[source_id]
                    sample_path = Path(PARL_SOURCE_CONFIG[source_id]["fallback_file"])
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
            finally:
                conn.close()

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones,senado_votaciones",
                        "--include-unmatched",
                        "--unmatched-sample-limit",
                        "3",
                        "--json-out",
                        str(out_path),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue(out_path.exists(), f"Missing quality json output: {out_path}")

            snapshot = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIn("unmatched_vote_ids", snapshot)
            unmatched = snapshot["unmatched_vote_ids"]
            self.assertIn("dry_run", unmatched)
            self.assertTrue(unmatched["dry_run"])
            self.assertIn("total_checked", unmatched)
            self.assertIn("unmatched_by_reason", unmatched)
            self.assertLessEqual(len(unmatched.get("unmatched_sample", [])), 3)

    def test_quality_report_include_unmatched_rejects_negative_sample_limit(self) -> None:
        snapshot_date = "2026-02-12"
        connectors = get_connectors()

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality-cli-invalid.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                connector = connectors["congreso_votaciones"]
                sample_path = Path(PARL_SOURCE_CONFIG["congreso_votaciones"]["fallback_file"])
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
            finally:
                conn.close()

            with self.assertRaises(SystemExit):
                main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones",
                        "--include-unmatched",
                        "--unmatched-sample-limit",
                        "-1",
                    ]
                )

    def test_quality_report_include_initiatives_exposes_doc_link_kpis(self) -> None:
        snapshot_date = "2026-02-12"
        connectors = get_connectors()

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality-cli-initiatives.db"
            raw_dir = Path(td) / "raw"
            out_path = Path(td) / f"votaciones-kpis-cli-initiatives-{snapshot_date}.json"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                for source_id in (
                    "congreso_votaciones",
                    "congreso_iniciativas",
                    "senado_iniciativas",
                    "senado_votaciones",
                ):
                    connector = connectors[source_id]
                    sample_path = Path(PARL_SOURCE_CONFIG[source_id]["fallback_file"])
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
            finally:
                conn.close()

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones,senado_votaciones",
                        "--include-initiatives",
                        "--initiative-source-ids",
                        "congreso_iniciativas,senado_iniciativas",
                        "--json-out",
                        str(out_path),
                    ]
                )
            self.assertEqual(code, 0)
            snapshot = json.loads(out_path.read_text(encoding="utf-8"))

            self.assertIn("initiatives", snapshot)
            self.assertIn("kpis", snapshot["initiatives"])
            kpis = snapshot["initiatives"]["kpis"]

            required_keys = {
                "total_doc_links",
                "downloaded_doc_links",
                "missing_doc_links",
                "missing_doc_links_likely_not_expected",
                "missing_doc_links_actionable",
                "downloaded_doc_links_pct",
                "effective_downloaded_doc_links_pct",
                "actionable_doc_links_closed_pct",
                "doc_links_with_fetch_status",
                "doc_links_missing_fetch_status",
                "fetch_status_coverage_pct",
                "downloaded_doc_links_with_excerpt",
                "downloaded_doc_links_missing_excerpt",
                "excerpt_coverage_pct",
                "downloaded_doc_links_with_extraction",
                "downloaded_doc_links_missing_extraction",
                "extraction_needs_review_doc_links",
                "extraction_coverage_pct",
                "extraction_needs_review_pct",
                "extraction_review_closed_pct",
                "missing_doc_links_status_buckets",
                "by_source",
            }
            self.assertFalse(required_keys - set(kpis.keys()))
            self.assertIsInstance(kpis["missing_doc_links_status_buckets"], list)

            self.assertIn("congreso_iniciativas", kpis["by_source"])
            self.assertIn("senado_iniciativas", kpis["by_source"])
            self.assertIn("missing_doc_links_status_buckets", kpis["by_source"]["congreso_iniciativas"])
            self.assertIn("missing_doc_links_status_buckets", kpis["by_source"]["senado_iniciativas"])
            self.assertIn(
                "missing_doc_links_actionable",
                kpis["by_source"]["congreso_iniciativas"],
            )
            self.assertIn(
                "missing_doc_links_likely_not_expected",
                kpis["by_source"]["senado_iniciativas"],
            )
            self.assertIn(
                "effective_downloaded_doc_links_pct",
                kpis["by_source"]["senado_iniciativas"],
            )
            self.assertIn(
                "actionable_doc_links_closed_pct",
                kpis["by_source"]["senado_iniciativas"],
            )
            self.assertIn(
                "extraction_review_closed_pct",
                kpis["by_source"]["senado_iniciativas"],
            )
            self.assertIsInstance(
                kpis["by_source"]["congreso_iniciativas"]["missing_doc_links_status_buckets"],
                list,
            )

    def test_quality_report_include_initiatives_enforce_gate_fails_when_extraction_open(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality-cli-initiatives-enforce-fail.db"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                self._seed_minimal_quality_fixture(conn, extraction_needs_review=1)
            finally:
                conn.close()

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones",
                        "--include-initiatives",
                        "--initiative-source-ids",
                        "congreso_iniciativas",
                        "--enforce-gate",
                    ]
                )
            self.assertEqual(code, 1)
            payload = json.loads(stdout.getvalue())
            self.assertIn("initiatives", payload)
            failures = payload["initiatives"]["gate"]["failures"]
            metrics = {str(f["metric"]) for f in failures}
            self.assertIn("extraction_review_closed_pct", metrics)

    def test_quality_report_include_initiatives_enforce_gate_passes_when_extraction_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality-cli-initiatives-enforce-pass.db"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                self._seed_minimal_quality_fixture(conn, extraction_needs_review=0)
            finally:
                conn.close()

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones",
                        "--include-initiatives",
                        "--initiative-source-ids",
                        "congreso_iniciativas",
                        "--enforce-gate",
                    ]
                )
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(bool(payload["gate"]["passed"]))
            self.assertTrue(bool(payload["initiatives"]["gate"]["passed"]))

    def test_quality_report_include_initiatives_enforce_gate_fails_when_actionable_missing_open(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality-cli-initiatives-enforce-actionable-fail.db"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                self._seed_minimal_quality_fixture(
                    conn,
                    extraction_needs_review=0,
                    actionable_missing_doc_links=1,
                )
            finally:
                conn.close()

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones",
                        "--include-initiatives",
                        "--initiative-source-ids",
                        "congreso_iniciativas",
                        "--enforce-gate",
                    ]
                )
            self.assertEqual(code, 1)
            payload = json.loads(stdout.getvalue())
            failures = payload["initiatives"]["gate"]["failures"]
            metrics = {str(f["metric"]) for f in failures}
            self.assertIn("actionable_doc_links_closed_pct", metrics)

    def test_quality_report_include_declared_exposes_declared_kpis(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality-cli-declared.db"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                self._seed_minimal_quality_fixture(conn, extraction_needs_review=0)
                self._seed_minimal_declared_fixture(
                    conn,
                    review_pending=0,
                    include_declared_position=1,
                )
            finally:
                conn.close()

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones",
                        "--include-declared",
                        "--declared-source-ids",
                        "programas_partidos",
                    ]
                )
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertIn("declared", payload)
            declared = payload["declared"]
            self.assertIn("kpis", declared)
            self.assertIn("gate", declared)
            for key in (
                "topic_evidence_total",
                "topic_evidence_with_nonempty_stance_pct",
                "review_closed_pct",
                "declared_positions_coverage_pct",
                "by_source",
            ):
                self.assertIn(key, declared["kpis"])
            self.assertIn("programas_partidos", declared["kpis"]["by_source"])

    def test_quality_report_include_declared_enforce_gate_fails_when_pending_review_open(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality-cli-declared-enforce-fail.db"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                self._seed_minimal_quality_fixture(conn, extraction_needs_review=0)
                self._seed_minimal_declared_fixture(
                    conn,
                    review_pending=1,
                    include_declared_position=0,
                )
            finally:
                conn.close()

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones",
                        "--include-declared",
                        "--declared-source-ids",
                        "programas_partidos",
                        "--enforce-gate",
                    ]
                )
            self.assertEqual(code, 1)
            payload = json.loads(stdout.getvalue())
            self.assertIn("declared", payload)
            failures = payload["declared"]["gate"]["failures"]
            metrics = {str(f["metric"]) for f in failures}
            self.assertIn("review_closed_pct", metrics)
            self.assertIn("declared_positions_coverage_pct", metrics)

    def test_quality_report_include_declared_enforce_gate_passes_when_queue_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality-cli-declared-enforce-pass.db"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                self._seed_minimal_quality_fixture(conn, extraction_needs_review=0)
                self._seed_minimal_declared_fixture(
                    conn,
                    review_pending=0,
                    include_declared_position=1,
                )
            finally:
                conn.close()

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones",
                        "--include-declared",
                        "--declared-source-ids",
                        "programas_partidos",
                        "--enforce-gate",
                    ]
                )
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(bool(payload["gate"]["passed"]))
            self.assertTrue(bool(payload["declared"]["gate"]["passed"]))

    def test_quality_report_include_declared_skip_vote_gate_decouples_enforce(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality-cli-declared-skip-vote-gate.db"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                # No vote fixture on purpose -> base vote gate should fail.
                self._seed_minimal_declared_fixture(
                    conn,
                    review_pending=0,
                    include_declared_position=1,
                )
            finally:
                conn.close()

            stdout_fail = io.StringIO()
            with redirect_stdout(stdout_fail):
                code_fail = main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones",
                        "--include-declared",
                        "--declared-source-ids",
                        "programas_partidos",
                        "--enforce-gate",
                    ]
                )
            self.assertEqual(code_fail, 1)
            payload_fail = json.loads(stdout_fail.getvalue())
            self.assertFalse(bool(payload_fail["gate"]["passed"]))
            self.assertTrue(bool(payload_fail["declared"]["gate"]["passed"]))

            stdout_pass = io.StringIO()
            with redirect_stdout(stdout_pass):
                code_pass = main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones",
                        "--include-declared",
                        "--declared-source-ids",
                        "programas_partidos",
                        "--enforce-gate",
                        "--skip-vote-gate",
                    ]
                )
            self.assertEqual(code_pass, 0)
            payload_pass = json.loads(stdout_pass.getvalue())
            self.assertFalse(bool(payload_pass["gate"]["passed"]))
            self.assertTrue(bool(payload_pass["declared"]["gate"]["passed"]))


if __name__ == "__main__":
    unittest.main()
