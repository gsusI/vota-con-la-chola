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


    def test_combined_reads_latest_snapshot_of_each_method_on_or_before_as_of(self) -> None:
        # Votes and declared positions are computed on different days. Combined at the
        # declared date must still pick the (older) votes snapshot, and never a newer one.
        with tempfile.TemporaryDirectory() as td:
            conn = open_db(Path(td) / "combined.db")
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now = now_utc_iso()
                person_ids = []
                for name in ("Persona Votos", "Persona Solo Declarada"):
                    ckey = canonical_key(full_name=name, birth_date=None, territory_code="")
                    conn.execute(
                        "INSERT INTO persons (full_name, canonical_key, created_at, updated_at) VALUES (?,?,?,?)",
                        (name, ckey, now, now),
                    )
                    person_ids.append(int(conn.execute("SELECT person_id FROM persons WHERE canonical_key = ?", (ckey,)).fetchone()["person_id"]))
                conn.execute(
                    "INSERT INTO topic_sets (name, legislature, is_active, created_at, updated_at) VALUES (?,?,?,?,?)",
                    ("Set Demo", "XV", 1, now, now),
                )
                topic_set_id = int(conn.execute("SELECT topic_set_id FROM topic_sets").fetchone()["topic_set_id"])
                conn.execute(
                    "INSERT INTO topics (canonical_key, label, created_at, updated_at) VALUES (?,?,?,?)",
                    ("t_demo", "Tema demo", now, now),
                )
                topic_id = int(conn.execute("SELECT topic_id FROM topics").fetchone()["topic_id"])

                def add(person_id: int, as_of: str, method: str, stance: str) -> None:
                    conn.execute(
                        """
                        INSERT INTO topic_positions (
                          topic_id, topic_set_id, person_id, as_of_date,
                          stance, score, confidence, evidence_count, last_evidence_date,
                          computed_method, computed_version, computed_at, created_at, updated_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (topic_id, topic_set_id, person_id, as_of, stance, 0.5, 0.8, 2, as_of, method, "v1", now, now, now),
                    )

                votes_person, declared_person = person_ids
                add(votes_person, "2026-02-16", "votes", "support")
                add(votes_person, "2026-03-10", "votes", "oppose")  # after as_of: ignored
                add(votes_person, "2026-02-28", "declared", "oppose")
                add(declared_person, "2026-02-28", "declared", "oppose")
                conn.commit()

                result = backfill_topic_positions_combined(conn, as_of_date="2026-02-28", dry_run=False)
                self.assertEqual(result["inserted"], 2)
                self.assertEqual(result["selected_from_votes"], 1)
                self.assertEqual(result["selected_from_declared"], 1)
                self.assertEqual(result["source_as_of_dates"], {"declared": ["2026-02-28"], "votes": ["2026-02-16"]})

                rows = {
                    int(r["person_id"]): (r["stance"], r["as_of_date"])
                    for r in conn.execute(
                        "SELECT person_id, stance, as_of_date FROM topic_positions WHERE computed_method = 'combined'"
                    )
                }
                self.assertEqual(rows[votes_person], ("support", "2026-02-28"))
                self.assertEqual(rows[declared_person], ("oppose", "2026-02-28"))
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

