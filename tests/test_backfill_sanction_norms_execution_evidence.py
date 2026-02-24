from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.backfill_sanction_norms_execution_evidence import backfill


class TestBackfillSanctionNormsExecutionEvidence(unittest.TestCase):
    def test_backfill_inserts_and_updates_execution_evidence(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "sanction_execution_backfill.db"
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
                        "es:sanctions:tgss_itss",
                        "TGSS/ITSS",
                        "ITSS",
                        "nacional",
                        "es",
                        "yearly",
                        "https://www.mites.gob.es/itss/",
                        "boe_api_legal",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO sanction_infraction_types (
                      infraction_type_id, label, domain, description, canonical_unit, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "inf:labor_compliance_breach",
                        "Incumplimientos laborales",
                        "laboral",
                        "Tipologia laboral",
                        "expedientes",
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
                        "es:boe-a-2000-15060",
                        "BOE-A-2000-15060",
                        "LISOS",
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
                        "es:boe-a-2000-15060:fragment:articulo:bloque-lisos",
                        "es:boe-a-2000-15060",
                        "articulo",
                        "Bloque LISOS",
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
                    ("es:boe-a-2000-15060", "{}", ts, ts),
                )
                conn.execute(
                    """
                    INSERT INTO sanction_norm_fragment_links (
                      norm_id, fragment_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        "es:boe-a-2000-15060",
                        "es:boe-a-2000-15060:fragment:articulo:bloque-lisos",
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
                        "es:boe-a-2000-15060:fragment:articulo:bloque-lisos",
                        "enforce",
                        "ITSS",
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
                        "boe_ref:BOE-A-2000-15060",
                        "2026-02-24",
                        '{"record_kind":"boe_legal_norm"}',
                        "sha-boe-1",
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
                      infraction_type_id,
                      expediente_count,
                      importe_total_eur,
                      source_id,
                      source_url,
                      raw_payload,
                      created_at,
                      updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "obs:test:1",
                        "es:sanctions:tgss_itss",
                        "2025-12-31",
                        "year",
                        "es:boe-a-2000-15060",
                        "es:boe-a-2000-15060:fragment:articulo:bloque-lisos",
                        "inf:labor_compliance_breach",
                        87000,
                        310000000.0,
                        "boe_api_legal",
                        "https://www.mites.gob.es/itss/",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                got_first = backfill(conn, roles=["enforce"], limit=0)
                got_second = backfill(conn, roles=["enforce"], limit=0)
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
                    ("es:boe-a-2000-15060:fragment:articulo:bloque-lisos",),
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(int(got_first["counts"]["observations_scanned_total"]), 1)
        self.assertEqual(int(got_first["counts"]["observations_with_responsibility_total"]), 1)
        self.assertEqual(int(got_first["counts"]["evidence_inserted"]), 1)
        self.assertEqual(int(got_first["counts"]["evidence_updated"]), 0)
        self.assertEqual(int(got_first["counts"]["source_record_pk_resolved_total"]), 1)
        self.assertEqual(int(got_second["counts"]["evidence_inserted"]), 0)
        self.assertEqual(int(got_second["counts"]["evidence_updated"]), 1)
        self.assertEqual(int(got_first["by_role"]["enforce"]), 1)
        self.assertEqual(int(got_first["by_norm"]["es:boe-a-2000-15060"]), 1)

        self.assertIsNotNone(evidence_row)
        self.assertEqual(str(evidence_row["evidence_type"]), "other")
        self.assertEqual(str(evidence_row["source_id"]), "boe_api_legal")
        self.assertIn("#observation_id=1", str(evidence_row["source_url"]))
        self.assertGreater(int(evidence_row["source_record_pk"]), 0)
        self.assertIn("expedientes=87000", str(evidence_row["evidence_quote"]))

        payload = json.loads(str(evidence_row["raw_payload"]))
        self.assertEqual(str(payload["record_kind"]), "sanction_norm_execution_evidence_backfill")
        self.assertEqual(str(payload["evidence_type_hint"]), "sanction_volume_observation")
        self.assertEqual(str(payload["match_method"]), "sanction_volume_observation_fragment_exact")
        self.assertEqual(str(payload["source_record_pk_resolution"]), "resolved:boe_ref:BOE-A-2000-15060")


if __name__ == "__main__":
    unittest.main()
