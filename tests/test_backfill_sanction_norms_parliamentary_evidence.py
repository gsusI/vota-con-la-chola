from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.backfill_sanction_norms_parliamentary_evidence import backfill


class TestBackfillSanctionNormsParliamentaryEvidence(unittest.TestCase):
    def test_backfill_inserts_and_updates_parliamentary_evidence(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "sanction_parl_backfill.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                ts = "2026-02-24T00:00:00+00:00"
                for sid, name in [
                    ("senado_iniciativas", "Senado iniciativas"),
                    ("parl_initiative_docs", "Parl initiative docs"),
                ]:
                    conn.execute(
                        """
                        INSERT INTO sources (
                          source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(source_id) DO NOTHING
                        """,
                        (sid, name, "nacional", "https://example.org", "json", 1, ts, ts),
                    )

                conn.execute(
                    """
                    INSERT INTO legal_norms (
                      norm_id, boe_id, title, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "es:boe-a-2003-23186",
                        "BOE-A-2003-23186",
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
                        "es:boe-a-2003-23186:fragment:articulo:bloque-principal",
                        "es:boe-a-2003-23186",
                        "articulo",
                        "Bloque principal",
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
                    ("es:boe-a-2003-23186", "{}", ts, ts),
                )
                conn.execute(
                    """
                    INSERT INTO sanction_norm_fragment_links (
                      norm_id, fragment_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        "es:boe-a-2003-23186",
                        "es:boe-a-2003-23186:fragment:articulo:bloque-principal",
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
                        "es:boe-a-2003-23186:fragment:articulo:bloque-principal",
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
                        "parl_initiative_docs",
                        "doc:senado:621/000157:bocg",
                        "2026-02-24",
                        '{"record_kind":"parl_initiative_doc"}',
                        "sha-doc-1",
                        ts,
                        ts,
                    ),
                )
                sr = conn.execute(
                    """
                    SELECT source_record_pk
                    FROM source_records
                    WHERE source_id = ? AND source_record_id = ?
                    """,
                    ("parl_initiative_docs", "doc:senado:621/000157:bocg"),
                ).fetchone()
                self.assertIsNotNone(sr)
                source_record_pk = int(sr["source_record_pk"])

                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, source_id, source_url, raw_payload, created_at, updated_at, title
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "senado:leg7:exp:621/000157",
                        "senado_iniciativas",
                        "https://www.senado.es/exp/621-000157",
                        "{}",
                        ts,
                        ts,
                        "Proyecto de Ley General Tributaria",
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents (
                      initiative_id, doc_kind, doc_url, source_record_pk, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "senado:leg7:exp:621/000157",
                        "bocg",
                        "http://www.senado.es/legis7/expedientes/621/xml/INI-3-621000157.xml",
                        source_record_pk,
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO text_documents (
                      source_id, source_url, source_record_pk, text_excerpt, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "parl_initiative_docs",
                        "http://www.senado.es/legis7/expedientes/621/xml/INI-3-621000157.xml",
                        source_record_pk,
                        "Referencia expresa a BOE-A-2003-23186 en el texto del expediente.",
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
                      e.source_record_pk,
                      e.evidence_quote
                    FROM legal_fragment_responsibility_evidence e
                    JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
                    WHERE r.fragment_id = ?
                    """,
                    ("es:boe-a-2003-23186:fragment:articulo:bloque-principal",),
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(int(got_first["counts"]["evidence_inserted"]), 1)
        self.assertEqual(int(got_first["counts"]["evidence_updated"]), 0)
        self.assertEqual(int(got_second["counts"]["evidence_inserted"]), 0)
        self.assertEqual(int(got_second["counts"]["evidence_updated"]), 1)
        self.assertEqual(int(got_first["by_evidence_type"]["senado_diario"]), 1)
        self.assertEqual(int(got_first["by_boe_id"]["BOE-A-2003-23186"]), 1)
        self.assertIsNotNone(evidence_row)
        self.assertEqual(str(evidence_row["evidence_type"]), "senado_diario")
        self.assertEqual(str(evidence_row["source_id"]), "senado_iniciativas")
        self.assertGreater(int(evidence_row["source_record_pk"]), 0)
        self.assertIn("BOE-A-2003-23186", str(evidence_row["evidence_quote"]))

    def test_backfill_inserts_lisos_via_title_rule_without_boe_token(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "sanction_parl_backfill_title_rule.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                ts = "2026-02-24T00:00:00+00:00"
                for sid, name in [
                    ("senado_iniciativas", "Senado iniciativas"),
                    ("parl_initiative_docs", "Parl initiative docs"),
                ]:
                    conn.execute(
                        """
                        INSERT INTO sources (
                          source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(source_id) DO NOTHING
                        """,
                        (sid, name, "nacional", "https://example.org", "json", 1, ts, ts),
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
                        "Texto refundido de la Ley sobre infracciones y sanciones en el orden social",
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
                        "es:boe-a-2000-15060:fragment:articulo:bloque-principal",
                        "es:boe-a-2000-15060",
                        "articulo",
                        "Bloque principal",
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
                        "es:boe-a-2000-15060:fragment:articulo:bloque-principal",
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
                        "es:boe-a-2000-15060:fragment:articulo:bloque-principal",
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
                        "parl_initiative_docs",
                        "doc:senado:621/000026:xml",
                        "2026-02-24",
                        '{"record_kind":"parl_initiative_doc"}',
                        "sha-doc-title-1",
                        ts,
                        ts,
                    ),
                )
                sr = conn.execute(
                    """
                    SELECT source_record_pk
                    FROM source_records
                    WHERE source_id = ? AND source_record_id = ?
                    """,
                    ("parl_initiative_docs", "doc:senado:621/000026:xml"),
                ).fetchone()
                self.assertIsNotNone(sr)
                source_record_pk = int(sr["source_record_pk"])

                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, source_id, source_url, raw_payload, created_at, updated_at, title
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "senado:leg5:exp:621/000026",
                        "senado_iniciativas",
                        "http://www.senado.es/legis5/expedientes/621/xml/INI-3-621000026.xml",
                        "{}",
                        ts,
                        ts,
                        "Proyecto de ley de modificación de la Ley sobre infracciones y sanciones en el orden social",
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_documents (
                      initiative_id, doc_kind, doc_url, source_record_pk, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "senado:leg5:exp:621/000026",
                        "xml",
                        "http://www.senado.es/legis5/expedientes/621/xml/INI-3-621000026.xml",
                        source_record_pk,
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO text_documents (
                      source_id, source_url, source_record_pk, text_excerpt, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "parl_initiative_docs",
                        "http://www.senado.es/legis5/expedientes/621/xml/INI-3-621000026.xml",
                        source_record_pk,
                        "Proyecto de ley por la que se modifican determinados artículos de la Ley sobre infracciones y sanciones en el orden social.",
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                got = backfill(conn, roles=["approve"], limit=0)
                evidence_row = conn.execute(
                    """
                    SELECT
                      e.evidence_type,
                      e.source_id,
                      e.evidence_quote,
                      e.raw_payload
                    FROM legal_fragment_responsibility_evidence e
                    JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
                    WHERE r.fragment_id = ?
                    """,
                    ("es:boe-a-2000-15060:fragment:articulo:bloque-principal",),
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(int(got["counts"]["docs_with_boe_token_total"]), 0)
        self.assertEqual(int(got["counts"]["docs_with_title_rule_match_total"]), 1)
        self.assertEqual(int(got["counts"]["candidate_matches_total"]), 1)
        self.assertEqual(int(got["counts"]["evidence_inserted"]), 1)
        self.assertEqual(int(got["by_method"]["title_rule:lisos_orden_social"]), 1)
        self.assertEqual(int(got["by_boe_id"]["BOE-A-2000-15060"]), 1)
        self.assertIsNotNone(evidence_row)
        payload = json.loads(str(evidence_row["raw_payload"] or "{}"))
        self.assertEqual(str(payload.get("match_method")), "title_rule:lisos_orden_social")
        self.assertEqual(str(evidence_row["evidence_type"]), "senado_diario")
        self.assertIn("infracciones y sanciones en el orden social", str(evidence_row["evidence_quote"]).lower())


if __name__ == "__main__":
    unittest.main()
