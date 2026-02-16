from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.combined_positions import backfill_topic_positions_combined
from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.politicos_es.util import canonical_key, now_utc_iso


class TestParlCombinedPositions(unittest.TestCase):
    def test_backfill_topic_positions_combined_prefers_votes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "combined.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()

                # Minimal person + topic + set to satisfy FKs.
                ckey = canonical_key(full_name="Persona Demo", birth_date=None, territory_code="")
                conn.execute(
                    "INSERT INTO persons (full_name, canonical_key, created_at, updated_at) VALUES (?,?,?,?)",
                    ("Persona Demo", ckey, now, now),
                )
                person_id = int(conn.execute("SELECT person_id FROM persons WHERE canonical_key = ?", (ckey,)).fetchone()["person_id"])

                conn.execute(
                    "INSERT INTO topic_sets (name, description, institution_id, admin_level_id, territory_id, legislature, valid_from, valid_to, is_active, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    ("Set Demo", None, None, None, None, "XV", None, None, 1, now, now),
                )
                topic_set_id = int(conn.execute("SELECT topic_set_id FROM topic_sets").fetchone()["topic_set_id"])

                conn.execute(
                    "INSERT INTO topics (canonical_key, label, description, parent_topic_id, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                    ("t_demo", "Tema demo", None, None, now, now),
                )
                topic_id = int(conn.execute("SELECT topic_id FROM topics WHERE canonical_key = 't_demo'").fetchone()["topic_id"])

                # Votes says SUPPORT, declared says OPPOSE. Combined must pick votes.
                conn.execute(
                    """
                    INSERT INTO topic_positions (
                      topic_id, topic_set_id, person_id, mandate_id,
                      institution_id, admin_level_id, territory_id,
                      as_of_date, window_days,
                      stance, score, confidence, evidence_count, last_evidence_date,
                      computed_method, computed_version, computed_at,
                      created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        topic_id,
                        topic_set_id,
                        person_id,
                        None,
                        None,
                        None,
                        None,
                        "2026-02-12",
                        None,
                        "support",
                        0.9,
                        1.0,
                        5,
                        "2026-02-12",
                        "votes",
                        "v1",
                        now,
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO topic_positions (
                      topic_id, topic_set_id, person_id, mandate_id,
                      institution_id, admin_level_id, territory_id,
                      as_of_date, window_days,
                      stance, score, confidence, evidence_count, last_evidence_date,
                      computed_method, computed_version, computed_at,
                      created_at, updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        topic_id,
                        topic_set_id,
                        person_id,
                        None,
                        None,
                        None,
                        None,
                        "2026-02-12",
                        None,
                        "oppose",
                        -0.6,
                        0.6,
                        1,
                        "2026-02-12",
                        "declared",
                        "v1",
                        now,
                        now,
                        now,
                    ),
                )
                conn.commit()

                result1 = backfill_topic_positions_combined(conn, as_of_date="2026-02-12", dry_run=False)
                self.assertGreaterEqual(int(result1.get("inserted", 0)), 1)

                row = conn.execute(
                    """
                    SELECT stance, computed_method
                    FROM topic_positions
                    WHERE as_of_date = '2026-02-12'
                      AND computed_method = 'combined'
                      AND topic_id = ?
                      AND person_id = ?
                    """,
                    (topic_id, person_id),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row["computed_method"], "combined")
                self.assertEqual(row["stance"], "support")

                # Idempotent (delete+insert): count stays stable.
                result2 = backfill_topic_positions_combined(conn, as_of_date="2026-02-12", dry_run=False)
                self.assertGreaterEqual(int(result2.get("inserted", 0)), 1)
                c = int(
                    conn.execute(
                        "SELECT COUNT(*) AS c FROM topic_positions WHERE computed_method = 'combined' AND as_of_date = '2026-02-12'"
                    ).fetchone()["c"]
                )
                self.assertEqual(c, 1)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

