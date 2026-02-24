from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_sanction_norms_seed import import_seed


class TestImportSanctionNormsSeed(unittest.TestCase):
    def test_import_seed_upserts_norms_fragments_and_responsibilities(self) -> None:
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
                            "fragment_title": "Tipificacion",
                            "conducta_sancionada": "Incumplimientos",
                            "organo_competente": "DGT",
                            "via_recurso": "Reposicion",
                            "importe_min_eur": 100,
                            "importe_max_eur": 200,
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
                                    "evidence_quote": "Publicacion oficial en BOE del texto normativo.",
                                }
                            ],
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
            db_path = Path(td) / "seed.db"
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
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "boe_api_legal",
                        "BOE-A-2015-11722",
                        "2026-02-24",
                        "{}",
                        "seed-sha-1",
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                got1 = import_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-23")
                self.assertEqual(int(got1["counts"]["norms_inserted"]), 1)
                self.assertEqual(int(got1["counts"]["fragments_inserted"]), 1)
                self.assertEqual(int(got1["counts"]["responsibilities_inserted"]), 2)
                self.assertEqual(int(got1["counts"]["responsibility_evidence_inserted"]), 2)
                self.assertEqual(int(got1["counts"]["responsibility_evidence_source_record_pk_auto_resolved"]), 1)
                self.assertEqual(int(got1["counts"]["responsibility_evidence_source_record_seed_rows_inserted"]), 0)
                self.assertEqual(int(got1["counts"]["responsibility_evidence_source_record_pk_auto_resolve_missed"]), 0)
                self.assertEqual(int(got1["counts"]["lineage_related_norms_inserted"]), 1)
                self.assertEqual(int(got1["counts"]["lineage_edges_inserted"]), 1)

                got2 = import_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-23")
                self.assertEqual(int(got2["counts"]["norms_inserted"]), 0)
                self.assertGreaterEqual(int(got2["counts"]["norms_updated"]), 1)
                self.assertGreaterEqual(int(got2["counts"]["fragments_updated"]), 1)
                self.assertGreaterEqual(int(got2["counts"]["responsibility_evidence_updated"]), 2)
                self.assertGreaterEqual(
                    int(got2["counts"]["responsibility_evidence_source_record_pk_auto_resolved"]), 1
                )
                self.assertEqual(int(got2["counts"]["responsibility_evidence_source_record_seed_rows_inserted"]), 0)
                self.assertGreaterEqual(int(got2["counts"]["lineage_edges_updated"]), 1)

                row = conn.execute("SELECT COUNT(*) AS n FROM legal_norms").fetchone()
                self.assertEqual(int(row["n"]), 2)
                row = conn.execute("SELECT COUNT(*) AS n FROM legal_norm_fragments").fetchone()
                self.assertEqual(int(row["n"]), 1)
                row = conn.execute("SELECT COUNT(*) AS n FROM legal_fragment_responsibilities").fetchone()
                self.assertEqual(int(row["n"]), 2)
                row = conn.execute("SELECT COUNT(*) AS n FROM legal_fragment_responsibility_evidence").fetchone()
                self.assertEqual(int(row["n"]), 2)
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS n
                    FROM legal_fragment_responsibility_evidence
                    WHERE source_record_pk IS NOT NULL
                    """
                ).fetchone()
                self.assertEqual(int(row["n"]), 1)
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS n
                    FROM legal_fragment_responsibilities
                    WHERE COALESCE(TRIM(source_url), '') <> ''
                      AND COALESCE(TRIM(evidence_date), '') <> ''
                      AND COALESCE(TRIM(evidence_quote), '') <> ''
                    """
                ).fetchone()
                self.assertEqual(int(row["n"]), 2)
                row = conn.execute("SELECT COUNT(*) AS n FROM sanction_norm_catalog").fetchone()
                self.assertEqual(int(row["n"]), 1)
                row = conn.execute("SELECT COUNT(*) AS n FROM sanction_norm_fragment_links").fetchone()
                self.assertEqual(int(row["n"]), 1)
                row = conn.execute("SELECT COUNT(*) AS n FROM legal_norm_lineage_edges").fetchone()
                self.assertEqual(int(row["n"]), 1)
            finally:
                conn.close()

    def test_import_seed_upserts_source_record_when_missing(self) -> None:
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
                            "fragment_title": "Tipificacion",
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
                                    "evidence_quote": "Publicacion oficial en BOE del texto normativo.",
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
            db_path = Path(td) / "seed_source_record_upsert.db"
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

                got = import_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-23")
                self.assertEqual(int(got["counts"]["responsibility_evidence_source_record_pk_auto_resolved"]), 0)
                self.assertEqual(int(got["counts"]["responsibility_evidence_source_record_seed_rows_inserted"]), 1)
                self.assertEqual(int(got["counts"]["responsibility_evidence_source_record_pk_auto_resolve_missed"]), 0)

                row = conn.execute(
                    """
                    SELECT COUNT(*) AS n
                    FROM source_records
                    WHERE source_id = ? AND source_record_id = ?
                    """,
                    ("boe_api_legal", "BOE-A-2015-11722"),
                ).fetchone()
                self.assertEqual(int(row["n"]), 1)
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS n
                    FROM legal_fragment_responsibility_evidence
                    WHERE source_record_pk IS NOT NULL
                    """
                ).fetchone()
                self.assertEqual(int(row["n"]), 1)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
