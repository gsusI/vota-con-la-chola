from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.declared_positions import backfill_topic_positions_from_declared_evidence
from etl.politicos_es.util import canonical_key, now_utc_iso, sha256_bytes


class TestParlDeclaredPositions(unittest.TestCase):
    def test_backfill_topic_positions_from_declared_evidence_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "declared-positions.db"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                # Person
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

                # Topic set + topic
                conn.execute(
                    """
                    INSERT INTO topic_sets (name, description, institution_id, admin_level_id, territory_id, legislature, valid_from, valid_to, is_active, created_at, updated_at)
                    VALUES (?, NULL, NULL, NULL, NULL, 'XV', NULL, NULL, 1, ?, ?)
                    """,
                    ("Congreso Demo", now, now),
                )
                topic_set_id = int(conn.execute("SELECT topic_set_id FROM topic_sets").fetchone()["topic_set_id"])

                conn.execute(
                    """
                    INSERT INTO topics (canonical_key, label, description, parent_topic_id, created_at, updated_at)
                    VALUES (?, ?, NULL, NULL, ?, ?)
                    """,
                    ("demo_topic", "Demo topic", now, now),
                )
                topic_id = int(conn.execute("SELECT topic_id FROM topics WHERE canonical_key = ?", ("demo_topic",)).fetchone()["topic_id"])

                # Source record + evidence (already classified).
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
                      'declared:intervention', '2026-02-12', NULL, 'Votaremos a favor.',
                      'support', 1, 0.5, 0.65,
                      NULL, 'declared:regex_v1',
                      NULL, NULL,
                      'congreso_intervenciones', 'https://example.invalid', ?, '2026-02-12',
                      '{}', ?, ?
                    )
                    """,
                    (topic_id, topic_set_id, person_id, sr_pk, now, now),
                )
                conn.commit()

                result1 = backfill_topic_positions_from_declared_evidence(
                    conn,
                    source_id="congreso_intervenciones",
                    as_of_date="2026-02-12",
                    dry_run=False,
                )
                self.assertEqual(int(result1.get("positions_total", 0)), 1)

                row = conn.execute(
                    """
                    SELECT stance, computed_method, computed_version, evidence_count
                    FROM topic_positions
                    WHERE topic_set_id = ? AND topic_id = ? AND person_id = ?
                    """,
                    (topic_set_id, topic_id, person_id),
                ).fetchone()
                self.assertEqual(row["stance"], "support")
                self.assertEqual(row["computed_method"], "declared")
                self.assertEqual(row["computed_version"], "v1")
                self.assertGreaterEqual(int(row["evidence_count"]), 1)

                # Re-run: should not duplicate rows (delete+insert is deterministic).
                result2 = backfill_topic_positions_from_declared_evidence(
                    conn,
                    source_id="congreso_intervenciones",
                    as_of_date="2026-02-12",
                    dry_run=False,
                )
                self.assertEqual(int(result2.get("positions_total", 0)), 1)
                self.assertEqual(
                    int(conn.execute("SELECT COUNT(*) AS c FROM topic_positions WHERE computed_method = 'declared'").fetchone()["c"]),
                    1,
                )
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

