from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.backfill_sanction_norms_procedural_metric_evidence import backfill


class TestBackfillSanctionNormsProceduralMetricEvidence(unittest.TestCase):
    def test_backfill_inserts_and_updates_procedural_metric_evidence(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "sanction_procedural_metric_backfill.db"
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
                conn.execute(
                    """
                    INSERT INTO sanction_volume_sources (
                      sanction_source_id, label, organismo, admin_scope, territory_scope, publication_frequency, source_url, source_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "es:sanctions:aeat_memoria",
                        "AEAT",
                        "AEAT",
                        "nacional",
                        "es",
                        "yearly",
                        "https://sede.agenciatributaria.gob.es/",
                        "boe_api_legal",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO sanction_procedural_kpi_definitions (
                      kpi_id, label, metric_formula, interpretation, target_direction, source_requirements_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "kpi:recurso_estimation_rate",
                        "% recursos estimados",
                        "numerator/denominator",
                        "Higher means higher successful appeal ratio",
                        "lower_is_better",
                        "{}",
                        ts,
                        ts,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO legal_norms (
                      norm_id, boe_id, title, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "es:boe-a-2003-23514",
                        "BOE-A-2003-23514",
                        "Ley General Tributaria",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO legal_norm_fragments (
                      fragment_id, norm_id, fragment_type, fragment_label, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "es:boe-a-2003-23514:fragment:articulo:bloque-tributario",
                        "es:boe-a-2003-23514",
                        "articulo",
                        "Bloque tributario",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO sanction_norm_catalog (
                      norm_id, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    ("es:boe-a-2003-23514", "{}", ts, ts),
                )
                conn.execute(
                    """
                    INSERT INTO sanction_norm_fragment_links (
                      norm_id, fragment_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        "es:boe-a-2003-23514",
                        "es:boe-a-2003-23514:fragment:articulo:bloque-tributario",
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO legal_fragment_responsibilities (
                      fragment_id, role, actor_label, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "es:boe-a-2003-23514:fragment:articulo:bloque-tributario",
                        "approve",
                        "Cortes Generales",
                        "{}",
                        ts,
                        ts,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date, raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "boe_api_legal",
                        "boe_ref:BOE-A-2003-23514",
                        "2026-02-24",
                        '{"record_kind":"boe_legal_norm"}',
                        "sha-boe-2",
                        ts,
                        ts,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO sanction_volume_observations (
                      observation_key,
                      sanction_source_id,
                      period_date,
                      period_granularity,
                      norm_id,
                      fragment_id,
                      expediente_count,
                      source_id,
                      source_url,
                      raw_payload,
                      created_at,
                      updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "obs:test:proc:1",
                        "es:sanctions:aeat_memoria",
                        "2025-12-31",
                        "year",
                        "es:boe-a-2003-23514",
                        "es:boe-a-2003-23514:fragment:articulo:bloque-tributario",
                        102000,
                        "boe_api_legal",
                        "https://sede.agenciatributaria.gob.es/",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO sanction_procedural_metrics (
                      metric_key,
                      kpi_id,
                      sanction_source_id,
                      period_date,
                      period_granularity,
                      value,
                      numerator,
                      denominator,
                      source_id,
                      source_url,
                      raw_payload,
                      created_at,
                      updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "metric:test:1",
                        "kpi:recurso_estimation_rate",
                        "es:sanctions:aeat_memoria",
                        "2025-12-31",
                        "year",
                        0.264706,
                        27000.0,
                        102000.0,
                        "boe_api_legal",
                        "https://sede.agenciatributaria.gob.es/",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                got_first = backfill(conn, roles=["approve"], limit=0)
                got_second = backfill(conn, roles=["approve"], limit=0)
                evidence_row = conn.execute(
                    """
                    SELECT
                      e.evidence_type,
                      e.source_id,
                      e.source_url,
                      e.source_record_pk,
                      e.evidence_quote,
                      e.raw_payload
                    FROM legal_fragment_responsibility_evidence e
                    JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
                    WHERE r.fragment_id = ?
                    """,
                    ("es:boe-a-2003-23514:fragment:articulo:bloque-tributario",),
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(int(got_first["counts"]["metrics_scanned_total"]), 1)
        self.assertEqual(int(got_first["counts"]["metrics_with_fragment_candidates_total"]), 1)
        self.assertEqual(int(got_first["counts"]["metrics_with_responsibility_total"]), 1)
        self.assertEqual(int(got_first["counts"]["evidence_inserted"]), 1)
        self.assertEqual(int(got_first["counts"]["evidence_updated"]), 0)
        self.assertEqual(int(got_first["counts"]["source_record_pk_resolved_total"]), 1)
        self.assertEqual(int(got_second["counts"]["evidence_inserted"]), 0)
        self.assertEqual(int(got_second["counts"]["evidence_updated"]), 1)
        self.assertEqual(int(got_first["by_role"]["approve"]), 1)
        self.assertEqual(int(got_first["by_norm"]["es:boe-a-2003-23514"]), 1)
        self.assertEqual(int(got_first["by_kpi"]["kpi:recurso_estimation_rate"]), 1)

        self.assertIsNotNone(evidence_row)
        self.assertEqual(str(evidence_row["evidence_type"]), "other")
        self.assertEqual(str(evidence_row["source_id"]), "boe_api_legal")
        self.assertIn("#metric_observation_id=1", str(evidence_row["source_url"]))
        self.assertGreater(int(evidence_row["source_record_pk"]), 0)
        self.assertIn("kpi_id=kpi:recurso_estimation_rate", str(evidence_row["evidence_quote"]))

        payload = json.loads(str(evidence_row["raw_payload"]))
        self.assertEqual(str(payload["record_kind"]), "sanction_norm_procedural_metric_evidence_backfill")
        self.assertEqual(str(payload["evidence_type_hint"]), "sanction_procedural_metric")
        self.assertEqual(str(payload["match_method"]), "sanction_source_to_observed_fragment_set")
        self.assertEqual(str(payload["source_record_pk_resolution"]), "resolved:boe_ref:BOE-A-2003-23514")


if __name__ == "__main__":
    unittest.main()
