from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_sanction_norms_seed import import_seed
from scripts.report_sanction_norms_seed_status import build_status_report


class TestReportSanctionNormsSeedStatus(unittest.TestCase):
    def test_report_failed_when_seed_not_loaded(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "status.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "failed")
        self.assertFalse(bool(got["checks"]["seed_loaded"]))
        self.assertEqual(int(got["totals"]["norms_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_with_source_record_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_parliamentary_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_execution_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_parliamentary_vote_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibilities_with_parliamentary_evidence_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibilities_with_execution_evidence_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibilities_with_parliamentary_vote_evidence_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_with_seed_source_record_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_with_non_seed_source_record_total"]), 0)
        self.assertEqual(int(got["totals"]["lineage_edges_total"]), 0)
        self.assertFalse(bool(got["checks"]["responsibility_evidence_parliamentary_chain_started"]))
        self.assertFalse(bool(got["checks"]["responsibility_evidence_execution_chain_started"]))
        self.assertFalse(bool(got["checks"]["responsibility_evidence_vote_chain_started"]))

    def test_report_ok_when_seed_and_responsibilities_loaded(self) -> None:
        seed_doc = {
            "schema_version": "sanction_norms_seed_v1",
            "norms": [
                {
                    "norm_id": "es:boe-a-2015-11722",
                    "boe_id": "BOE-A-2015-11722",
                    "title": "Ley trafico",
                    "scope": "nacional",
                    "organismo_competente": "DGT",
                    "incidence_hypothesis": "alta",
                    "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                    "evidence_required": ["base_legal_fragment"],
                    "key_fragments": [
                        {
                            "fragment_type": "articulo",
                            "fragment_label": "Bloque principal",
                            "conducta_sancionada": "Incumplimientos",
                            "organo_competente": "DGT",
                            "via_recurso": "Reposicion",
                        }
                    ],
                    "responsibility_hints": [
                        {
                            "role": "propose",
                            "actor_label": "Gobierno",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                            "evidence_date": "2015-10-31",
                            "evidence_quote": "Fuente BOE del marco normativo publicado.",
                        },
                        {
                            "role": "approve",
                            "actor_label": "Cortes Generales",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                            "evidence_date": "2015-10-31",
                            "evidence_quote": "Fuente BOE del marco normativo publicado.",
                        },
                    ],
                    "lineage_hints": [
                        {
                            "relation_type": "desarrolla",
                            "relation_scope": "parcial",
                            "target_boe_id": "BOE-A-1990-6396",
                            "target_title": "Texto articulado previo de trafico.",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                            "evidence_date": "2015-10-31",
                            "evidence_quote": "Fuente BOE del texto refundido y su encaje con la norma previa.",
                        }
                    ],
                }
            ],
        }

        with TemporaryDirectory() as td:
            db_path = Path(td) / "status_ok.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                import_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-23")
                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertTrue(bool(got["checks"]["seed_loaded"]))
        self.assertTrue(bool(got["checks"]["all_fragments_with_responsibility"]))
        self.assertTrue(bool(got["checks"]["all_responsibilities_with_primary_evidence"]))
        self.assertTrue(bool(got["checks"]["all_responsibilities_with_evidence_items"]))
        self.assertTrue(bool(got["checks"]["all_responsibility_evidence_items_with_primary_fields"]))
        self.assertFalse(bool(got["checks"]["responsibility_evidence_source_record_chain_started"]))
        self.assertFalse(bool(got["checks"]["responsibility_evidence_parliamentary_chain_started"]))
        self.assertFalse(bool(got["checks"]["responsibility_evidence_execution_chain_started"]))
        self.assertFalse(bool(got["checks"]["responsibility_evidence_vote_chain_started"]))
        self.assertFalse(bool(got["checks"]["responsibility_evidence_non_seed_source_record_chain_started"]))
        self.assertTrue(bool(got["checks"]["all_norms_with_lineage"]))
        self.assertTrue(bool(got["checks"]["all_lineage_edges_with_primary_evidence"]))
        self.assertEqual(int(got["totals"]["norms_total"]), 1)
        self.assertEqual(int(got["totals"]["fragments_missing_responsibility"]), 0)
        self.assertEqual(int(got["totals"]["responsibilities_missing_primary_evidence"]), 0)
        self.assertEqual(int(got["totals"]["responsibilities_missing_evidence_items"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_missing_primary_fields"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_with_source_record_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_parliamentary_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_execution_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_parliamentary_vote_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibilities_with_parliamentary_evidence_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibilities_with_execution_evidence_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibilities_with_parliamentary_vote_evidence_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_with_seed_source_record_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_with_non_seed_source_record_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_missing_source_record"]), 2)
        self.assertEqual(int(got["totals"]["norms_missing_lineage"]), 0)
        self.assertEqual(int(got["totals"]["lineage_edges_missing_primary_evidence"]), 0)
        self.assertEqual(float(got["coverage"]["responsibility_coverage_pct"]), 1.0)
        self.assertEqual(float(got["coverage"]["responsibility_primary_evidence_coverage_pct"]), 1.0)
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_coverage_pct"]), 1.0)
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_primary_fields_coverage_pct"]), 1.0)
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_source_record_coverage_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_non_seed_source_record_coverage_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_parliamentary_share_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_execution_share_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_parliamentary_vote_share_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["responsibility_parliamentary_coverage_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["responsibility_execution_coverage_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["responsibility_parliamentary_vote_coverage_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["lineage_coverage_pct"]), 1.0)
        self.assertEqual(float(got["coverage"]["lineage_primary_evidence_coverage_pct"]), 1.0)

    def test_report_degraded_when_primary_evidence_missing(self) -> None:
        seed_doc = {
            "schema_version": "sanction_norms_seed_v1",
            "norms": [
                {
                    "norm_id": "es:boe-a-2015-11722",
                    "boe_id": "BOE-A-2015-11722",
                    "title": "Ley trafico",
                    "scope": "nacional",
                    "organismo_competente": "DGT",
                    "incidence_hypothesis": "alta",
                    "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                    "evidence_required": ["base_legal_fragment"],
                    "key_fragments": [
                        {
                            "fragment_type": "articulo",
                            "fragment_label": "Bloque principal",
                            "conducta_sancionada": "Incumplimientos",
                            "organo_competente": "DGT",
                            "via_recurso": "Reposicion",
                        }
                    ],
                    "responsibility_hints": [
                        {
                            "role": "propose",
                            "actor_label": "Gobierno",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                            "evidence_quote": "Fuente BOE del marco normativo publicado.",
                        }
                    ],
                    "lineage_hints": [
                        {
                            "relation_type": "desarrolla",
                            "relation_scope": "parcial",
                            "target_boe_id": "BOE-A-1990-6396",
                            "target_title": "Texto articulado previo de trafico.",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                            "evidence_date": "2015-10-31",
                            "evidence_quote": "Fuente BOE del texto refundido y su encaje con la norma previa.",
                        }
                    ],
                }
            ],
        }

        with TemporaryDirectory() as td:
            db_path = Path(td) / "status_degraded_primary_evidence.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                import_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-23")
                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertFalse(bool(got["checks"]["all_responsibilities_with_primary_evidence"]))
        self.assertEqual(int(got["totals"]["responsibilities_missing_primary_evidence"]), 1)
        self.assertFalse(bool(got["checks"]["all_responsibility_evidence_items_with_primary_fields"]))
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_missing_primary_fields"]), 1)
        self.assertEqual(float(got["coverage"]["responsibility_primary_evidence_coverage_pct"]), 0.0)

    def test_report_marks_non_seed_source_records_when_present(self) -> None:
        seed_doc = {
            "schema_version": "sanction_norms_seed_v1",
            "norms": [
                {
                    "norm_id": "es:boe-a-2015-11722",
                    "boe_id": "BOE-A-2015-11722",
                    "title": "Ley trafico",
                    "scope": "nacional",
                    "organismo_competente": "DGT",
                    "incidence_hypothesis": "alta",
                    "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                    "evidence_required": ["base_legal_fragment"],
                    "key_fragments": [
                        {
                            "fragment_type": "articulo",
                            "fragment_label": "Bloque principal",
                            "conducta_sancionada": "Incumplimientos",
                            "organo_competente": "DGT",
                            "via_recurso": "Reposicion",
                        }
                    ],
                    "responsibility_hints": [
                        {
                            "role": "propose",
                            "actor_label": "Gobierno",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                            "evidence_date": "2015-10-31",
                            "evidence_quote": "Fuente BOE del marco normativo publicado.",
                            "evidence_items": [
                                {
                                    "evidence_type": "boe_publicacion",
                                    "source_id": "boe_api_legal",
                                    "source_record_id": "BOE-A-2015-11722",
                                    "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                                    "evidence_date": "2015-10-31",
                                    "evidence_quote": "Referencia BOE del texto legal publicado.",
                                }
                            ],
                        }
                    ],
                    "lineage_hints": [
                        {
                            "relation_type": "desarrolla",
                            "relation_scope": "parcial",
                            "target_boe_id": "BOE-A-1990-6396",
                            "target_title": "Texto articulado previo de trafico.",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                            "evidence_date": "2015-10-31",
                            "evidence_quote": "Fuente BOE del texto refundido y su encaje con la norma previa.",
                        }
                    ],
                }
            ],
        }

        with TemporaryDirectory() as td:
            db_path = Path(td) / "status_non_seed_source_record.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                ts = "2026-02-24T00:00:00+00:00"
                conn.execute(
                    """
                    INSERT INTO sources (
                      source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id) DO NOTHING
                    """,
                    (
                        "boe_api_legal",
                        "BOE API Legal",
                        "nacional",
                        "https://www.boe.es/",
                        "json",
                        1,
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                import_seed(conn, seed_doc=seed_doc, source_id="boe_api_legal", snapshot_date="2026-02-23")

                row = conn.execute(
                    """
                    SELECT source_record_pk
                    FROM source_records
                    WHERE source_id = ? AND source_record_id = ?
                    """,
                    ("boe_api_legal", "BOE-A-2015-11722"),
                ).fetchone()
                self.assertIsNotNone(row)
                source_record_pk = int(row["source_record_pk"])
                conn.execute(
                    """
                    UPDATE source_records
                    SET raw_payload = ?, content_sha256 = ?, updated_at = ?
                    WHERE source_record_pk = ?
                    """,
                    (
                        '{"upstream":"boe_api_legal","record_id":"BOE-A-2015-11722"}',
                        "non-seed-sha",
                        ts,
                        source_record_pk,
                    ),
                )
                conn.commit()

                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertTrue(bool(got["checks"]["responsibility_evidence_source_record_chain_started"]))
        self.assertFalse(bool(got["checks"]["responsibility_evidence_parliamentary_chain_started"]))
        self.assertFalse(bool(got["checks"]["responsibility_evidence_execution_chain_started"]))
        self.assertFalse(bool(got["checks"]["responsibility_evidence_vote_chain_started"]))
        self.assertTrue(bool(got["checks"]["responsibility_evidence_non_seed_source_record_chain_started"]))
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_with_source_record_total"]), 1)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_parliamentary_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_execution_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_parliamentary_vote_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibilities_with_parliamentary_evidence_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibilities_with_execution_evidence_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibilities_with_parliamentary_vote_evidence_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_with_seed_source_record_total"]), 0)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_with_non_seed_source_record_total"]), 1)
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_non_seed_source_record_coverage_pct"]), 1.0)
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_parliamentary_share_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_execution_share_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_parliamentary_vote_share_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["responsibility_parliamentary_coverage_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["responsibility_execution_coverage_pct"]), 0.0)
        self.assertEqual(float(got["coverage"]["responsibility_parliamentary_vote_coverage_pct"]), 0.0)

    def test_report_marks_vote_chain_when_vote_evidence_present(self) -> None:
        seed_doc = {
            "schema_version": "sanction_norms_seed_v1",
            "norms": [
                {
                    "norm_id": "es:boe-a-2003-23514",
                    "boe_id": "BOE-A-2003-23514",
                    "title": "Ley General Tributaria",
                    "scope": "nacional",
                    "organismo_competente": "AEAT",
                    "incidence_hypothesis": "alta",
                    "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23514",
                    "evidence_required": ["base_legal_fragment"],
                    "key_fragments": [
                        {
                            "fragment_type": "articulo",
                            "fragment_label": "Bloque principal",
                            "conducta_sancionada": "Incumplimientos tributarios",
                            "organo_competente": "AEAT",
                            "via_recurso": "Reposicion",
                        }
                    ],
                    "responsibility_hints": [
                        {
                            "role": "approve",
                            "actor_label": "Cortes Generales",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23514",
                            "evidence_date": "2003-12-18",
                            "evidence_quote": "Fuente BOE del marco normativo publicado.",
                        }
                    ],
                    "lineage_hints": [
                        {
                            "relation_type": "desarrolla",
                            "relation_scope": "parcial",
                            "target_boe_id": "BOE-A-1963-2490",
                            "target_title": "Texto previo tributario.",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23514",
                            "evidence_date": "2003-12-18",
                            "evidence_quote": "Fuente BOE del texto refundido y su encaje con la norma previa.",
                        }
                    ],
                }
            ],
        }

        with TemporaryDirectory() as td:
            db_path = Path(td) / "status_vote_chain.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                ts = "2026-02-24T00:00:00+00:00"
                conn.execute(
                    """
                    INSERT INTO sources (
                      source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id) DO NOTHING
                    """,
                    (
                        "congreso_votaciones",
                        "Congreso votaciones",
                        "nacional",
                        "https://www.congreso.es/",
                        "json",
                        1,
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                import_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-23")
                responsibility_row = conn.execute(
                    """
                    SELECT responsibility_id
                    FROM legal_fragment_responsibilities
                    ORDER BY responsibility_id
                    LIMIT 1
                    """
                ).fetchone()
                self.assertIsNotNone(responsibility_row)
                responsibility_id = int(responsibility_row["responsibility_id"])

                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date, raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso_votaciones",
                        "vote:test:1",
                        "2026-02-24",
                        '{"record_kind":"parl_vote_event"}',
                        "sha-vote-test-1",
                        ts,
                        ts,
                    ),
                )
                source_record_row = conn.execute(
                    """
                    SELECT source_record_pk
                    FROM source_records
                    WHERE source_id = ? AND source_record_id = ?
                    """,
                    ("congreso_votaciones", "vote:test:1"),
                ).fetchone()
                self.assertIsNotNone(source_record_row)
                source_record_pk = int(source_record_row["source_record_pk"])

                conn.execute(
                    """
                    INSERT INTO legal_fragment_responsibility_evidence (
                      responsibility_id, evidence_type, source_id, source_url, source_record_pk, evidence_date, evidence_quote, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        responsibility_id,
                        "congreso_vote",
                        "congreso_votaciones",
                        "https://www.congreso.es/votacion/test1",
                        source_record_pk,
                        "2026-02-24",
                        "Votación de referencia tributaria.",
                        '{"record_kind":"test_vote_evidence"}',
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(int(got["totals"]["responsibility_evidence_items_parliamentary_total"]), 1)
        self.assertEqual(int(got["totals"]["responsibility_evidence_items_parliamentary_vote_total"]), 1)
        self.assertEqual(int(got["totals"]["responsibilities_with_parliamentary_evidence_total"]), 1)
        self.assertEqual(int(got["totals"]["responsibilities_with_parliamentary_vote_evidence_total"]), 1)
        self.assertTrue(bool(got["checks"]["responsibility_evidence_parliamentary_chain_started"]))
        self.assertTrue(bool(got["checks"]["responsibility_evidence_vote_chain_started"]))
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_parliamentary_share_pct"]), 0.5)
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_parliamentary_vote_share_pct"]), 0.5)
        self.assertEqual(float(got["coverage"]["responsibility_parliamentary_coverage_pct"]), 1.0)
        self.assertEqual(float(got["coverage"]["responsibility_parliamentary_vote_coverage_pct"]), 1.0)

    def test_report_marks_execution_chain_when_execution_evidence_present(self) -> None:
        seed_doc = {
            "schema_version": "sanction_norms_seed_v1",
            "norms": [
                {
                    "norm_id": "es:boe-a-2000-15060",
                    "boe_id": "BOE-A-2000-15060",
                    "title": "LISOS",
                    "scope": "nacional",
                    "organismo_competente": "ITSS",
                    "incidence_hypothesis": "alta",
                    "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2000-15060",
                    "evidence_required": ["base_legal_fragment"],
                    "key_fragments": [
                        {
                            "fragment_type": "articulo",
                            "fragment_label": "Bloque principal",
                            "conducta_sancionada": "Incumplimientos laborales",
                            "organo_competente": "ITSS",
                            "via_recurso": "Alzada",
                        }
                    ],
                    "responsibility_hints": [
                        {
                            "role": "enforce",
                            "actor_label": "Inspeccion de Trabajo",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2000-15060",
                            "evidence_date": "2000-08-05",
                            "evidence_quote": "Fuente BOE del marco normativo publicado.",
                        }
                    ],
                    "lineage_hints": [
                        {
                            "relation_type": "desarrolla",
                            "relation_scope": "parcial",
                            "target_boe_id": "BOE-A-1988-1644",
                            "target_title": "Texto previo laboral.",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2000-15060",
                            "evidence_date": "2000-08-05",
                            "evidence_quote": "Fuente BOE del texto refundido y su encaje con la norma previa.",
                        }
                    ],
                }
            ],
        }

        with TemporaryDirectory() as td:
            db_path = Path(td) / "status_execution_chain.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                ts = "2026-02-24T00:00:00+00:00"
                conn.execute(
                    """
                    INSERT INTO sources (
                      source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id) DO NOTHING
                    """,
                    (
                        "boe_api_legal",
                        "BOE API Legal",
                        "nacional",
                        "https://www.boe.es/",
                        "json",
                        1,
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                import_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-23")
                responsibility_row = conn.execute(
                    """
                    SELECT responsibility_id
                    FROM legal_fragment_responsibilities
                    ORDER BY responsibility_id
                    LIMIT 1
                    """
                ).fetchone()
                self.assertIsNotNone(responsibility_row)
                responsibility_id = int(responsibility_row["responsibility_id"])

                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date, raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "boe_api_legal",
                        "boe_ref:BOE-A-2000-15060",
                        "2026-02-24",
                        '{"record_kind":"boe_legal_norm"}',
                        "sha-boe-test-1",
                        ts,
                        ts,
                    ),
                )
                source_record_row = conn.execute(
                    """
                    SELECT source_record_pk
                    FROM source_records
                    WHERE source_id = ? AND source_record_id = ?
                    """,
                    ("boe_api_legal", "boe_ref:BOE-A-2000-15060"),
                ).fetchone()
                self.assertIsNotNone(source_record_row)
                source_record_pk = int(source_record_row["source_record_pk"])

                conn.execute(
                    """
                    INSERT INTO legal_fragment_responsibility_evidence (
                      responsibility_id, evidence_type, source_id, source_url, source_record_pk, evidence_date, evidence_quote, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        responsibility_id,
                        "other",
                        "boe_api_legal",
                        "https://www.mites.gob.es/itss/#observation_id=1",
                        source_record_pk,
                        "2025-12-31",
                        "expedientes=87000; importe_total_eur=310000000.00",
                        '{"record_kind":"sanction_norm_execution_evidence_backfill","evidence_type_hint":"sanction_volume_observation"}',
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(int(got["totals"]["responsibility_evidence_items_execution_total"]), 1)
        self.assertEqual(int(got["totals"]["responsibilities_with_execution_evidence_total"]), 1)
        self.assertEqual(int(got["totals"]["responsibilities_missing_execution_evidence"]), 0)
        self.assertTrue(bool(got["checks"]["responsibility_evidence_execution_chain_started"]))
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_execution_share_pct"]), 0.5)
        self.assertEqual(float(got["coverage"]["responsibility_execution_coverage_pct"]), 1.0)

    def test_report_counts_procedural_metric_evidence_as_execution_signal(self) -> None:
        seed_doc = {
            "schema_version": "sanction_norms_seed_v1",
            "norms": [
                {
                    "norm_id": "es:boe-a-2015-3442",
                    "boe_id": "BOE-A-2015-3442",
                    "title": "LO 4/2015",
                    "scope": "nacional",
                    "organismo_competente": "Interior",
                    "incidence_hypothesis": "alta",
                    "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-3442",
                    "evidence_required": ["base_legal_fragment"],
                    "key_fragments": [
                        {
                            "fragment_type": "articulo",
                            "fragment_label": "Bloque principal",
                            "conducta_sancionada": "Infracciones de seguridad ciudadana",
                            "organo_competente": "Interior",
                            "via_recurso": "Alzada",
                        }
                    ],
                    "responsibility_hints": [
                        {
                            "role": "approve",
                            "actor_label": "Cortes Generales",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-3442",
                            "evidence_date": "2015-03-31",
                            "evidence_quote": "Fuente BOE del marco normativo publicado.",
                        }
                    ],
                    "lineage_hints": [
                        {
                            "relation_type": "desarrolla",
                            "relation_scope": "parcial",
                            "target_boe_id": "BOE-A-1992-1338",
                            "target_title": "Texto previo de seguridad ciudadana.",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-3442",
                            "evidence_date": "2015-03-31",
                            "evidence_quote": "Fuente BOE del texto y su encaje con la norma previa.",
                        }
                    ],
                }
            ],
        }

        with TemporaryDirectory() as td:
            db_path = Path(td) / "status_procedural_execution_chain.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                ts = "2026-02-24T00:00:00+00:00"
                conn.execute(
                    """
                    INSERT INTO sources (
                      source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id) DO NOTHING
                    """,
                    (
                        "boe_api_legal",
                        "BOE API Legal",
                        "nacional",
                        "https://www.boe.es/",
                        "json",
                        1,
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                import_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-23")
                responsibility_row = conn.execute(
                    """
                    SELECT responsibility_id
                    FROM legal_fragment_responsibilities
                    ORDER BY responsibility_id
                    LIMIT 1
                    """
                ).fetchone()
                self.assertIsNotNone(responsibility_row)
                responsibility_id = int(responsibility_row["responsibility_id"])

                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date, raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "boe_api_legal",
                        "boe_ref:BOE-A-2015-3442",
                        "2026-02-24",
                        '{"record_kind":"boe_legal_norm"}',
                        "sha-boe-procedural-test-1",
                        ts,
                        ts,
                    ),
                )
                source_record_row = conn.execute(
                    """
                    SELECT source_record_pk
                    FROM source_records
                    WHERE source_id = ? AND source_record_id = ?
                    """,
                    ("boe_api_legal", "boe_ref:BOE-A-2015-3442"),
                ).fetchone()
                self.assertIsNotNone(source_record_row)
                source_record_pk = int(source_record_row["source_record_pk"])

                conn.execute(
                    """
                    INSERT INTO legal_fragment_responsibility_evidence (
                      responsibility_id, evidence_type, source_id, source_url, source_record_pk, evidence_date, evidence_quote, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        responsibility_id,
                        "other",
                        "boe_api_legal",
                        "https://www.interior.gob.es/#metric_observation_id=1",
                        source_record_pk,
                        "2025-12-31",
                        "kpi_id=kpi:formal_annulment_rate; value=0.052632",
                        '{"record_kind":"sanction_norm_procedural_metric_evidence_backfill","evidence_type_hint":"sanction_procedural_metric"}',
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(int(got["totals"]["responsibility_evidence_items_execution_total"]), 1)
        self.assertEqual(int(got["totals"]["responsibilities_with_execution_evidence_total"]), 1)
        self.assertEqual(int(got["totals"]["responsibilities_missing_execution_evidence"]), 0)
        self.assertTrue(bool(got["checks"]["responsibility_evidence_execution_chain_started"]))
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_execution_share_pct"]), 0.5)
        self.assertEqual(float(got["coverage"]["responsibility_execution_coverage_pct"]), 1.0)

    def test_report_counts_lineage_execution_evidence_as_execution_signal(self) -> None:
        seed_doc = {
            "schema_version": "sanction_norms_seed_v1",
            "norms": [
                {
                    "norm_id": "es:boe-a-1994-8985",
                    "boe_id": "BOE-A-1994-8985",
                    "title": "Reglamento sancionador trafico",
                    "scope": "nacional",
                    "organismo_competente": "DGT",
                    "incidence_hypothesis": "alta",
                    "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-1994-8985",
                    "evidence_required": ["base_legal_fragment"],
                    "key_fragments": [
                        {
                            "fragment_type": "articulo",
                            "fragment_label": "Bloque principal",
                            "conducta_sancionada": "Tramitacion sancionadora",
                            "organo_competente": "DGT",
                            "via_recurso": "Reposicion",
                        }
                    ],
                    "responsibility_hints": [
                        {
                            "role": "delegate",
                            "actor_label": "Ministerio competente en trafico",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-1994-8985",
                            "evidence_date": "1994-04-21",
                            "evidence_quote": "Fuente BOE del marco normativo publicado.",
                        }
                    ],
                    "lineage_hints": [
                        {
                            "relation_type": "desarrolla",
                            "relation_scope": "parcial",
                            "target_boe_id": "BOE-A-1990-6396",
                            "target_title": "Texto previo de trafico.",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-1994-8985",
                            "evidence_date": "1994-04-21",
                            "evidence_quote": "Fuente BOE del texto y su encaje con la norma previa.",
                        }
                    ],
                }
            ],
        }

        with TemporaryDirectory() as td:
            db_path = Path(td) / "status_lineage_execution_chain.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                ts = "2026-02-24T00:00:00+00:00"
                conn.execute(
                    """
                    INSERT INTO sources (
                      source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id) DO NOTHING
                    """,
                    (
                        "boe_api_legal",
                        "BOE API Legal",
                        "nacional",
                        "https://www.boe.es/",
                        "json",
                        1,
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                import_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-23")
                responsibility_row = conn.execute(
                    """
                    SELECT responsibility_id
                    FROM legal_fragment_responsibilities
                    ORDER BY responsibility_id
                    LIMIT 1
                    """
                ).fetchone()
                self.assertIsNotNone(responsibility_row)
                responsibility_id = int(responsibility_row["responsibility_id"])

                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date, raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "boe_api_legal",
                        "boe_ref:BOE-A-1994-8985",
                        "2026-02-24",
                        '{"record_kind":"boe_legal_norm"}',
                        "sha-boe-lineage-test-1",
                        ts,
                        ts,
                    ),
                )
                source_record_row = conn.execute(
                    """
                    SELECT source_record_pk
                    FROM source_records
                    WHERE source_id = ? AND source_record_id = ?
                    """,
                    ("boe_api_legal", "boe_ref:BOE-A-1994-8985"),
                ).fetchone()
                self.assertIsNotNone(source_record_row)
                source_record_pk = int(source_record_row["source_record_pk"])

                conn.execute(
                    """
                    INSERT INTO legal_fragment_responsibility_evidence (
                      responsibility_id, evidence_type, source_id, source_url, source_record_pk, evidence_date, evidence_quote, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        responsibility_id,
                        "other",
                        "boe_api_legal",
                        "https://www.dgt.es/#observation_id=1&lineage_bridge=1",
                        source_record_pk,
                        "2025-12-31",
                        "expedientes=100; importe_total_eur=25000.00",
                        '{"record_kind":"sanction_norm_execution_lineage_bridge_backfill","match_method":"shared_related_norm"}',
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                got = build_status_report(conn)
            finally:
                conn.close()

        self.assertEqual(int(got["totals"]["responsibility_evidence_items_execution_total"]), 1)
        self.assertEqual(int(got["totals"]["responsibilities_with_execution_evidence_total"]), 1)
        self.assertEqual(int(got["totals"]["responsibilities_missing_execution_evidence"]), 0)
        self.assertTrue(bool(got["checks"]["responsibility_evidence_execution_chain_started"]))
        self.assertEqual(float(got["coverage"]["responsibility_evidence_item_execution_share_pct"]), 0.5)
        self.assertEqual(float(got["coverage"]["responsibility_execution_coverage_pct"]), 1.0)


if __name__ == "__main__":
    unittest.main()
