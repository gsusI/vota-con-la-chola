from __future__ import annotations

import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from etl.politicos_es.util import now_utc_iso
from scripts.backfill_persons_from_vote_member_names import backfill_persons_from_vote_member_names


def _seed_vote_source(conn) -> None:
    now_iso = now_utc_iso()
    conn.execute(
        """
        INSERT INTO sources (
          source_id, name, scope, default_url, data_format, is_active,
          created_at, updated_at
        ) VALUES (
          'congreso_votaciones', 'Congreso votaciones', 'nacional',
          'https://www.congreso.es/', 'json', 1, ?, ?
        )
        ON CONFLICT(source_id) DO NOTHING
        """,
        (now_iso, now_iso),
    )


class TestBackfillPersonsFromVoteMemberNames(unittest.TestCase):
    def test_creates_person_aliases_and_updates_member_votes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "vote-persons.db"
            with closing(open_db(db_path)) as conn:
                apply_schema(conn, DEFAULT_SCHEMA)
                _seed_vote_source(conn)
                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, vote_date, title, source_id,
                      raw_payload, created_at, updated_at
                    ) VALUES ('vote-1', '15', '2024-01-01', 'Vote 1',
                      'congreso_votaciones', '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                for seat, name, name_norm, source_url in (
                    ("1", "Ana López", "ana lopez", "file:///Users/alice/private.json"),
                    ("2", "Ana López", "ana lopez", "https://example.test/vote?token=abc&ok=1"),
                    ("3", "Beto Ruiz", "beto ruiz", "https://example.test/vote"),
                ):
                    conn.execute(
                        """
                        INSERT INTO parl_vote_member_votes (
                          vote_event_id, seat, member_name, member_name_normalized,
                          vote_choice, source_id, source_url, raw_payload, created_at, updated_at
                        ) VALUES ('vote-1', ?, ?, ?, 'SÍ', 'congreso_votaciones', ?, '{}', ?, ?)
                        """,
                        (seat, name, name_norm, source_url, now_iso, now_iso),
                    )
                conn.commit()

                first = backfill_persons_from_vote_member_names(conn, source_ids=("congreso_votaciones",))
                second = backfill_persons_from_vote_member_names(conn, source_ids=("congreso_votaciones",))
                people = conn.execute("SELECT full_name FROM persons ORDER BY full_name").fetchall()
                aliases = conn.execute(
                    """
                    SELECT alias, canonical_alias, source_kind, source_url
                    FROM person_name_aliases
                    ORDER BY alias
                    """
                ).fetchall()
                unresolved_votes = conn.execute(
                    "SELECT COUNT(*) AS n FROM parl_vote_member_votes WHERE person_id IS NULL"
                ).fetchone()
                fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()

            self.assertEqual(first["distinct_labels_seen"], 2)
            self.assertEqual(first["persons_created"], 2)
            self.assertEqual(first["aliases_upserted"], 2)
            self.assertEqual(first["member_votes_updated"], 3)
            self.assertEqual(second["persons_created"], 0)
            self.assertEqual(second["persons_existing"], 2)
            self.assertEqual(second["member_votes_updated"], 0)
            self.assertEqual([row["full_name"] for row in people], ["Ana López", "Beto Ruiz"])
            self.assertEqual([row["canonical_alias"] for row in aliases], ["ana lopez", "beto ruiz"])
            self.assertEqual({row["source_kind"] for row in aliases}, {"official_roll_call"})
            self.assertTrue(all("file:" not in str(row["source_url"] or "") for row in aliases))
            self.assertEqual(int(unresolved_votes["n"]), 0)
            self.assertEqual(fk_rows, [])

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "vote-persons-dry.db"
            with closing(open_db(db_path)) as conn:
                apply_schema(conn, DEFAULT_SCHEMA)
                _seed_vote_source(conn)
                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, vote_date, title, source_id,
                      raw_payload, created_at, updated_at
                    ) VALUES ('vote-1', '15', '2024-01-01', 'Vote 1',
                      'congreso_votaciones', '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_member_votes (
                      vote_event_id, seat, member_name, member_name_normalized,
                      vote_choice, source_id, raw_payload, created_at, updated_at
                    ) VALUES ('vote-1', '1', 'Ana López', 'ana lopez', 'SÍ',
                      'congreso_votaciones', '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.commit()
                result = backfill_persons_from_vote_member_names(
                    conn,
                    source_ids=("congreso_votaciones",),
                    dry_run=True,
                )
                person_count = conn.execute("SELECT COUNT(*) AS n FROM persons").fetchone()

            self.assertTrue(result["dry_run"])
            self.assertEqual(result["distinct_labels_seen"], 1)
            self.assertEqual(result["persons_created"], 0)
            self.assertEqual(int(person_count["n"]), 0)


if __name__ == "__main__":
    unittest.main()
