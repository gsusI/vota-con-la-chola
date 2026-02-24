from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.backfill_sanction_norms_vote_evidence import backfill


class TestBackfillSanctionNormsVoteEvidence(unittest.TestCase):
    def test_backfill_inserts_and_updates_vote_evidence(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "sanction_vote_backfill.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                ts = "2026-02-24T00:00:00+00:00"
                for sid, name in [
                    ("congreso_iniciativas", "Congreso iniciativas"),
                    ("congreso_votaciones", "Congreso votaciones"),
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
                        "es:boe-a-2003-23514:fragment:articulo:bloque-principal",
                        "es:boe-a-2003-23514",
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
                        "es:boe-a-2003-23514:fragment:articulo:bloque-principal",
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
                        "es:boe-a-2003-23514:fragment:articulo:bloque-principal",
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
                        "congreso_votaciones",
                        "vote:congreso:1",
                        "2026-02-24",
                        '{"record_kind":"parl_vote_event"}',
                        "sha-vote-1",
                        ts,
                        ts,
                    ),
                )
                vote_sr = conn.execute(
                    """
                    SELECT source_record_pk
                    FROM source_records
                    WHERE source_id = ? AND source_record_id = ?
                    """,
                    ("congreso_votaciones", "vote:congreso:1"),
                ).fetchone()
                self.assertIsNotNone(vote_sr)
                vote_source_record_pk = int(vote_sr["source_record_pk"])

                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, source_id, source_url, raw_payload, created_at, updated_at, title
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso:leg15:exp:121/000023/0000",
                        "congreso_iniciativas",
                        "https://www.congreso.es/exp/121-000023",
                        "{}",
                        ts,
                        ts,
                        (
                            "Proyecto de Ley por la que se modifican la Ley 58/2003, de 17 de diciembre, "
                            "General Tributaria, y otras normas tributarias."
                        ),
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, source_id, source_url, source_record_pk, vote_date, title, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso:leg15:vote:1",
                        "congreso_votaciones",
                        "https://www.congreso.es/votacion/1",
                        vote_source_record_pk,
                        "2026-02-24",
                        "Votación final del Proyecto de Ley que modifica la Ley 58/2003, General Tributaria.",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_event_initiatives (
                      vote_event_id, initiative_id, link_method, confidence, evidence_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso:leg15:vote:1",
                        "congreso:leg15:exp:121/000023/0000",
                        "title_similarity",
                        0.95,
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                got_first = backfill(conn, roles=["approve"], limit_events=0)
                got_second = backfill(conn, roles=["approve"], limit_events=0)
                evidence_row = conn.execute(
                    """
                    SELECT
                      e.evidence_type,
                      e.source_id,
                      e.source_record_pk,
                      e.evidence_quote,
                      e.raw_payload
                    FROM legal_fragment_responsibility_evidence e
                    JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
                    WHERE r.fragment_id = ?
                    """,
                    ("es:boe-a-2003-23514:fragment:articulo:bloque-principal",),
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(int(got_first["counts"]["candidate_matches_total"]), 1)
        self.assertEqual(int(got_first["counts"]["evidence_inserted"]), 1)
        self.assertEqual(int(got_first["counts"]["evidence_updated"]), 0)
        self.assertEqual(int(got_second["counts"]["evidence_inserted"]), 0)
        self.assertEqual(int(got_second["counts"]["evidence_updated"]), 1)
        self.assertEqual(int(got_first["by_evidence_type"]["congreso_vote"]), 1)
        self.assertEqual(int(got_first["by_boe_id"]["BOE-A-2003-23514"]), 1)
        self.assertEqual(
            int(got_first["by_method"]["title_rule:ley_58_2003_general_tributaria"]),
            1,
        )

        self.assertIsNotNone(evidence_row)
        self.assertEqual(str(evidence_row["evidence_type"]), "congreso_vote")
        self.assertEqual(str(evidence_row["source_id"]), "congreso_votaciones")
        self.assertEqual(int(evidence_row["source_record_pk"]), vote_source_record_pk)
        self.assertIn("Ley 58/2003", str(evidence_row["evidence_quote"]))

        payload = json.loads(str(evidence_row["raw_payload"]))
        self.assertEqual(str(payload["record_kind"]), "sanction_norm_vote_evidence_backfill")
        self.assertEqual(str(payload["boe_id"]), "BOE-A-2003-23514")
        self.assertEqual(
            str(payload["match_method"]),
            "title_rule:ley_58_2003_general_tributaria",
        )
        self.assertEqual(str(payload["vote_event_id"]), "congreso:leg15:vote:1")

    def test_backfill_bridges_vote_evidence_via_lineage(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "sanction_vote_backfill_lineage.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                ts = "2026-02-24T00:00:00+00:00"
                for sid, name in [
                    ("congreso_iniciativas", "Congreso iniciativas"),
                    ("congreso_votaciones", "Congreso votaciones"),
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

                for norm_id, boe_id, title in [
                    ("es:boe-a-2003-23514", "BOE-A-2003-23514", "Ley General Tributaria"),
                    (
                        "es:boe-a-2004-18398",
                        "BOE-A-2004-18398",
                        "Regimen sancionador tributario (reglamento)",
                    ),
                ]:
                    conn.execute(
                        """
                        INSERT INTO legal_norms (
                          norm_id, boe_id, title, raw_payload, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (norm_id, boe_id, title, "{}", ts, ts),
                    )
                    conn.execute(
                        """
                        INSERT INTO sanction_norm_catalog (
                          norm_id, raw_payload, created_at, updated_at
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (norm_id, "{}", ts, ts),
                    )

                conn.execute(
                    """
                    INSERT INTO legal_norm_fragments (
                      fragment_id, norm_id, fragment_type, fragment_label, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "es:boe-a-2004-18398:fragment:articulo:bloque-principal",
                        "es:boe-a-2004-18398",
                        "articulo",
                        "Bloque principal",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO sanction_norm_fragment_links (
                      norm_id, fragment_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        "es:boe-a-2004-18398",
                        "es:boe-a-2004-18398:fragment:articulo:bloque-principal",
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
                        "es:boe-a-2004-18398:fragment:articulo:bloque-principal",
                        "delegate",
                        "Ministerio de Hacienda",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO legal_norm_lineage_edges (
                      norm_id, related_norm_id, relation_type, relation_scope, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "es:boe-a-2004-18398",
                        "es:boe-a-2003-23514",
                        "desarrolla",
                        "parcial",
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
                        "congreso_votaciones",
                        "vote:congreso:lineage:1",
                        "2026-02-24",
                        '{"record_kind":"parl_vote_event"}',
                        "sha-vote-lineage-1",
                        ts,
                        ts,
                    ),
                )
                vote_sr = conn.execute(
                    """
                    SELECT source_record_pk
                    FROM source_records
                    WHERE source_id = ? AND source_record_id = ?
                    """,
                    ("congreso_votaciones", "vote:congreso:lineage:1"),
                ).fetchone()
                self.assertIsNotNone(vote_sr)
                vote_source_record_pk = int(vote_sr["source_record_pk"])

                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, source_id, source_url, raw_payload, created_at, updated_at, title
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso:leg15:exp:121/000777/0000",
                        "congreso_iniciativas",
                        "https://www.congreso.es/exp/121-000777",
                        "{}",
                        ts,
                        ts,
                        "Proyecto de Ley de reforma de la Ley 58/2003, General Tributaria.",
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, source_id, source_url, source_record_pk, vote_date, title, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso:leg15:vote:lineage:1",
                        "congreso_votaciones",
                        "https://www.congreso.es/votacion/lineage-1",
                        vote_source_record_pk,
                        "2026-02-24",
                        "Votación final del Proyecto de Ley de reforma de la Ley 58/2003, General Tributaria.",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_event_initiatives (
                      vote_event_id, initiative_id, link_method, confidence, evidence_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso:leg15:vote:lineage:1",
                        "congreso:leg15:exp:121/000777/0000",
                        "title_similarity",
                        0.95,
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                got = backfill(conn, roles=["delegate"], limit_events=0)
                evidence_row = conn.execute(
                    """
                    SELECT
                      e.evidence_type,
                      e.source_id,
                      e.source_record_pk,
                      e.raw_payload
                    FROM legal_fragment_responsibility_evidence e
                    JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
                    WHERE r.fragment_id = ?
                    """,
                    ("es:boe-a-2004-18398:fragment:articulo:bloque-principal",),
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(int(got["counts"]["evidence_inserted"]), 1)
        self.assertEqual(
            int(got["by_method"]["title_rule:ley_58_2003_general_tributaria+lineage_target_to_vote_norm:desarrolla"]),
            1,
        )
        self.assertIsNotNone(evidence_row)
        self.assertEqual(str(evidence_row["evidence_type"]), "congreso_vote")
        self.assertEqual(str(evidence_row["source_id"]), "congreso_votaciones")
        self.assertEqual(int(evidence_row["source_record_pk"]), vote_source_record_pk)

        payload = json.loads(str(evidence_row["raw_payload"]))
        self.assertEqual(str(payload["boe_id"]), "BOE-A-2004-18398")
        self.assertEqual(str(payload["candidate_boe_id"]), "BOE-A-2003-23514")
        self.assertEqual(str(payload["bridge_kind"]), "lineage_target_to_vote_norm:desarrolla")
        self.assertEqual(str(payload["bridge_from_boe_id"]), "BOE-A-2003-23514")

    def test_backfill_bridges_vote_evidence_via_mixed_lineage_anchor(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "sanction_vote_backfill_lineage_mixed.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                ts = "2026-02-24T00:00:00+00:00"
                for sid, name in [
                    ("congreso_iniciativas", "Congreso iniciativas"),
                    ("congreso_votaciones", "Congreso votaciones"),
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

                for norm_id, boe_id, title in [
                    (
                        "es:boe-a-2015-11722",
                        "BOE-A-2015-11722",
                        "Ley sobre trafico, circulacion de vehiculos a motor y seguridad vial",
                    ),
                    (
                        "es:boe-a-1994-8985",
                        "BOE-A-1994-8985",
                        "Reglamento del procedimiento sancionador en materia de trafico",
                    ),
                    (
                        "es:boe-a-1990-6396",
                        "BOE-A-1990-6396",
                        "Norma ancla de trafico",
                    ),
                ]:
                    conn.execute(
                        """
                        INSERT INTO legal_norms (
                          norm_id, boe_id, title, raw_payload, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (norm_id, boe_id, title, "{}", ts, ts),
                    )

                for norm_id in ["es:boe-a-2015-11722", "es:boe-a-1994-8985"]:
                    conn.execute(
                        """
                        INSERT INTO sanction_norm_catalog (
                          norm_id, raw_payload, created_at, updated_at
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (norm_id, "{}", ts, ts),
                    )

                conn.execute(
                    """
                    INSERT INTO legal_norm_fragments (
                      fragment_id, norm_id, fragment_type, fragment_label, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "es:boe-a-1994-8985:fragment:articulo:bloque-principal",
                        "es:boe-a-1994-8985",
                        "articulo",
                        "Bloque principal",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO sanction_norm_fragment_links (
                      norm_id, fragment_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        "es:boe-a-1994-8985",
                        "es:boe-a-1994-8985:fragment:articulo:bloque-principal",
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
                        "es:boe-a-1994-8985:fragment:articulo:bloque-principal",
                        "delegate",
                        "Ministerio competente en trafico",
                        "{}",
                        ts,
                        ts,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO legal_norm_lineage_edges (
                      norm_id, related_norm_id, relation_type, relation_scope, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "es:boe-a-2015-11722",
                        "es:boe-a-1990-6396",
                        "deroga",
                        "total",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO legal_norm_lineage_edges (
                      norm_id, related_norm_id, relation_type, relation_scope, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "es:boe-a-1994-8985",
                        "es:boe-a-1990-6396",
                        "desarrolla",
                        "parcial",
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
                        "congreso_votaciones",
                        "vote:congreso:lineage-mixed:1",
                        "2026-02-24",
                        '{"record_kind":"parl_vote_event"}',
                        "sha-vote-lineage-mixed-1",
                        ts,
                        ts,
                    ),
                )
                vote_sr = conn.execute(
                    """
                    SELECT source_record_pk
                    FROM source_records
                    WHERE source_id = ? AND source_record_id = ?
                    """,
                    ("congreso_votaciones", "vote:congreso:lineage-mixed:1"),
                ).fetchone()
                self.assertIsNotNone(vote_sr)
                vote_source_record_pk = int(vote_sr["source_record_pk"])

                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, source_id, source_url, raw_payload, created_at, updated_at, title
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso:leg15:exp:121/000888/0000",
                        "congreso_iniciativas",
                        "https://www.congreso.es/exp/121-000888",
                        "{}",
                        ts,
                        ts,
                        "Proyecto de reforma del Real Decreto Legislativo 6/2015 de tráfico y seguridad vial.",
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, source_id, source_url, source_record_pk, vote_date, title, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso:leg15:vote:lineage-mixed:1",
                        "congreso_votaciones",
                        "https://www.congreso.es/votacion/lineage-mixed-1",
                        vote_source_record_pk,
                        "2026-02-24",
                        "Votación final sobre el Real Decreto Legislativo 6/2015 de tráfico y seguridad vial.",
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_event_initiatives (
                      vote_event_id, initiative_id, link_method, confidence, evidence_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso:leg15:vote:lineage-mixed:1",
                        "congreso:leg15:exp:121/000888/0000",
                        "title_similarity",
                        0.95,
                        "{}",
                        ts,
                        ts,
                    ),
                )
                conn.commit()

                got = backfill(conn, roles=["delegate"], limit_events=0)
                evidence_row = conn.execute(
                    """
                    SELECT
                      e.evidence_type,
                      e.source_id,
                      e.source_record_pk,
                      e.raw_payload
                    FROM legal_fragment_responsibility_evidence e
                    JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
                    WHERE r.fragment_id = ?
                    """,
                    ("es:boe-a-1994-8985:fragment:articulo:bloque-principal",),
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(int(got["counts"]["evidence_inserted"]), 1)
        self.assertEqual(
            int(got["by_method"]["title_rule:rdl_6_2015_trafico_seguridad_vial+lineage_shared_related_norm_mixed_relation"]),
            1,
        )
        self.assertIsNotNone(evidence_row)
        self.assertEqual(str(evidence_row["evidence_type"]), "congreso_vote")
        self.assertEqual(str(evidence_row["source_id"]), "congreso_votaciones")
        self.assertEqual(int(evidence_row["source_record_pk"]), vote_source_record_pk)

        payload = json.loads(str(evidence_row["raw_payload"]))
        self.assertEqual(str(payload["boe_id"]), "BOE-A-1994-8985")
        self.assertEqual(str(payload["candidate_boe_id"]), "BOE-A-2015-11722")
        self.assertEqual(str(payload["bridge_kind"]), "lineage_shared_related_norm_mixed_relation")
        self.assertEqual(str(payload["bridge_from_boe_id"]), "BOE-A-2015-11722")
        self.assertEqual(str(payload["bridge_anchor_related_norm_id"]), "es:boe-a-1990-6396")


if __name__ == "__main__":
    unittest.main()
