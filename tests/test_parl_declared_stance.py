from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.declared_stance import backfill_declared_stance_from_topic_evidence, infer_declared_stance
from etl.politicos_es.util import canonical_key, now_utc_iso, sha256_bytes


class TestParlDeclaredStance(unittest.TestCase):
    def test_infer_declared_stance_support_oppose_abstain(self) -> None:
        sup = infer_declared_stance("Votaremos a favor.")
        opp = infer_declared_stance("Votaremos en contra.")
        abst = infer_declared_stance("Nos abstendremos.")
        low = infer_declared_stance("Apoyamos esta iniciativa.")
        self.assertIsNotNone(sup)
        self.assertIsNotNone(opp)
        self.assertIsNotNone(abst)
        self.assertIsNotNone(low)
        self.assertEqual(sup[0], "support")
        self.assertEqual(opp[0], "oppose")
        self.assertEqual(abst[0], "mixed")
        self.assertEqual(low[0], "support")
        self.assertGreaterEqual(float(sup[2]), 0.7)
        self.assertLess(float(low[2]), 0.62)
        self.assertIsNone(infer_declared_stance("No apoyamos esta iniciativa."))
        self.assertIsNone(infer_declared_stance("Sin señal explícita."))

    def test_backfill_declared_stance_from_topic_evidence_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "declared-stance.db"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                ckey = canonical_key(full_name="Persona Demo", birth_date=None, territory_code="")
                conn.execute(
                    """
                    INSERT INTO persons (full_name, canonical_key, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    ("Persona Demo", ckey, now, now),
                )
                person_id = int(
                    conn.execute(
                        "SELECT person_id FROM persons WHERE canonical_key = ?",
                        (ckey,),
                    ).fetchone()["person_id"]
                )

                sr_payload = '{"kind":"intervention","id":"test"}'
                sr_sha = sha256_bytes(sr_payload.encode("utf-8"))
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("congreso_intervenciones", "test:1", "2026-02-12", sr_payload, sr_sha, now, now),
                )
                sr_pk = int(
                    conn.execute(
                        "SELECT source_record_pk FROM source_records WHERE source_id = ? AND source_record_id = ?",
                        ("congreso_intervenciones", "test:1"),
                    ).fetchone()["source_record_pk"]
                )
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("congreso_intervenciones", "test:2", "2026-02-12", sr_payload, sr_sha, now, now),
                )
                sr_pk_2 = int(
                    conn.execute(
                        "SELECT source_record_pk FROM source_records WHERE source_id = ? AND source_record_id = ?",
                        ("congreso_intervenciones", "test:2"),
                    ).fetchone()["source_record_pk"]
                )
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("congreso_intervenciones", "test:3", "2026-02-12", sr_payload, sr_sha, now, now),
                )
                sr_pk_3 = int(
                    conn.execute(
                        "SELECT source_record_pk FROM source_records WHERE source_id = ? AND source_record_id = ?",
                        ("congreso_intervenciones", "test:3"),
                    ).fetchone()["source_record_pk"]
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
                      NULL, NULL,
                      ?, NULL,
                      NULL, NULL, NULL,
                      'declared:intervention', '2026-02-12', NULL, ?,
                      'unclear', 0, 0.5, 0.2,
                      NULL, 'intervention_metadata',
                      NULL, NULL,
                      'congreso_intervenciones', 'https://example.invalid', ?, '2026-02-12',
                      '{}', ?, ?
                    )
                    """,
                    (person_id, "Votaremos a favor de esta iniciativa.", sr_pk, now, now),
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
                      NULL, NULL,
                      ?, NULL,
                      NULL, NULL, NULL,
                      'declared:intervention', '2026-02-12', NULL, ?,
                      'unclear', 0, 0.5, 0.2,
                      NULL, 'intervention_metadata',
                      NULL, NULL,
                      'congreso_intervenciones', 'https://example.invalid', ?, '2026-02-12',
                      '{}', ?, ?
                    )
                    """,
                    (person_id, "Apoyamos esta iniciativa.", sr_pk_2, now, now),
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
                      NULL, NULL,
                      ?, NULL,
                      NULL, NULL, NULL,
                      'declared:intervention', '2026-02-12', NULL, NULL,
                      'unclear', 0, 0.5, 0.2,
                      NULL, 'intervention_metadata',
                      NULL, NULL,
                      'congreso_intervenciones', 'https://example.invalid', ?, '2026-02-12',
                      '{}', ?, ?
                    )
                    """,
                    (person_id, sr_pk_3, now, now),
                )
                conn.commit()

                result1 = backfill_declared_stance_from_topic_evidence(
                    conn,
                    source_id="congreso_intervenciones",
                    limit=0,
                    min_auto_confidence=0.62,
                    dry_run=False,
                )
                self.assertEqual(int(result1.get("updated", 0)), 1)
                self.assertEqual(int(result1.get("review_pending", 0)), 2)

                row = conn.execute(
                    "SELECT stance, polarity, confidence, stance_method FROM topic_evidence WHERE source_record_pk = ?",
                    (sr_pk,),
                ).fetchone()
                self.assertEqual(row["stance"], "support")
                self.assertEqual(int(row["polarity"]), 1)
                self.assertGreater(float(row["confidence"]), 0.2)
                self.assertEqual(row["stance_method"], "declared:regex_v2")

                low_row = conn.execute(
                    "SELECT stance, stance_method FROM topic_evidence WHERE source_record_pk = ?",
                    (sr_pk_2,),
                ).fetchone()
                self.assertEqual(low_row["stance"], "unclear")
                self.assertEqual(low_row["stance_method"], "intervention_metadata")

                review_rows = conn.execute(
                    """
                    SELECT source_record_pk, review_reason, status
                    FROM topic_evidence_reviews
                    ORDER BY source_record_pk ASC
                    """
                ).fetchall()
                self.assertEqual(len(review_rows), 2)
                self.assertEqual(str(review_rows[0]["review_reason"]), "low_confidence")
                self.assertEqual(str(review_rows[0]["status"]), "pending")
                self.assertEqual(str(review_rows[1]["review_reason"]), "missing_text")
                self.assertEqual(str(review_rows[1]["status"]), "pending")

                result2 = backfill_declared_stance_from_topic_evidence(
                    conn,
                    source_id="congreso_intervenciones",
                    limit=0,
                    min_auto_confidence=0.62,
                    dry_run=False,
                )
                self.assertEqual(int(result2.get("updated", 0)), 0)
                self.assertEqual(int(result2.get("review_pending", 0)), 2)
                self.assertEqual(
                    int(conn.execute("SELECT COUNT(*) AS c FROM topic_evidence_reviews").fetchone()["c"]),
                    2,
                )

                fk = conn.execute("PRAGMA foreign_key_check").fetchall()
                self.assertEqual(fk, [])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
