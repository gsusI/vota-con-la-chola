from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from etl.politicos_es.util import canonical_key, now_utc_iso
from scripts.backfill_parliamentary_groups_from_vote_member_votes import (
    backfill_parliamentary_groups_from_vote_member_votes,
)


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


def _seed_person(conn, full_name: str) -> int:
    now_iso = now_utc_iso()
    row = conn.execute(
        """
        INSERT INTO persons (full_name, territory_code, canonical_key, created_at, updated_at)
        VALUES (?, '', ?, ?, ?)
        RETURNING person_id
        """,
        (full_name, canonical_key(full_name, None, ""), now_iso, now_iso),
    ).fetchone()
    return int(row["person_id"])


class TestBackfillParliamentaryGroupsFromVoteMemberVotes(unittest.TestCase):
    def test_creates_group_membership_and_updates_member_votes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "vote-groups.db"
            with closing(open_db(db_path)) as conn:
                apply_schema(conn, DEFAULT_SCHEMA)
                _seed_vote_source(conn)
                person_id = _seed_person(conn, "Ana López")
                now_iso = now_utc_iso()
                for vote_event_id, legislature, vote_date in (
                    ("vote-0", "", "2024-01-15"),
                    ("vote-1", "15", "2024-01-01"),
                    ("vote-2", "15", "2024-02-03"),
                ):
                    conn.execute(
                        """
                        INSERT INTO parl_vote_events (
                          vote_event_id, legislature, vote_date, title, source_id,
                          raw_payload, created_at, updated_at
                        ) VALUES (?, ?, ?, 'Vote', 'congreso_votaciones', '{}', ?, ?)
                        """,
                        (vote_event_id, legislature, vote_date, now_iso, now_iso),
                    )
                    conn.execute(
                        """
                        INSERT INTO parl_vote_member_votes (
                          vote_event_id, seat, member_name, member_name_normalized, person_id,
                          group_code, vote_choice, source_id, source_url, raw_payload,
                          created_at, updated_at
                        ) VALUES (?, '1', 'Ana López', 'ana lopez', ?, 'GS', 'SÍ',
                          'congreso_votaciones', 'file:///Users/alice/private.json', '{}', ?, ?)
                        """,
                        (vote_event_id, person_id, now_iso, now_iso),
                    )
                conn.commit()

                first = backfill_parliamentary_groups_from_vote_member_votes(
                    conn,
                    source_ids=("congreso_votaciones",),
                )
                second = backfill_parliamentary_groups_from_vote_member_votes(
                    conn,
                    source_ids=("congreso_votaciones",),
                )
                group = conn.execute("SELECT * FROM parliamentary_groups").fetchone()
                membership = conn.execute("SELECT * FROM person_parliamentary_group_memberships").fetchone()
                linked_votes = conn.execute(
                    "SELECT COUNT(*) AS n FROM parl_vote_member_votes WHERE parliamentary_group_id IS NOT NULL"
                ).fetchone()
                fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()

            self.assertEqual(first["groups_seen"], 1)
            self.assertEqual(first["groups_upserted"], 1)
            self.assertEqual(first["memberships_upserted"], 1)
            self.assertEqual(first["member_votes_updated"], 3)
            self.assertEqual(second["groups_upserted"], 1)
            self.assertEqual(second["memberships_upserted"], 1)
            self.assertEqual(group["group_code"], "GS")
            self.assertEqual(group["name"], "Grupo Parlamentario Socialista")
            self.assertEqual(group["legislature"], "15")
            self.assertNotIn("file:", group["source_url"] or "")
            self.assertEqual(membership["person_id"], person_id)
            self.assertEqual(membership["parliamentary_group_id"], group["parliamentary_group_id"])
            self.assertEqual(membership["start_date"], "2024-01-01")
            self.assertEqual(membership["end_date"], "2024-02-03")
            self.assertEqual(json.loads(membership["raw_payload"])["vote_rows"], 3)
            self.assertEqual(int(linked_votes["n"]), 3)
            self.assertEqual(fk_rows, [])

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "vote-groups-dry.db"
            with closing(open_db(db_path)) as conn:
                apply_schema(conn, DEFAULT_SCHEMA)
                _seed_vote_source(conn)
                person_id = _seed_person(conn, "Ana López")
                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, vote_date, title, source_id,
                      raw_payload, created_at, updated_at
                    ) VALUES ('vote-1', '15', '2024-01-01', 'Vote',
                      'congreso_votaciones', '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_member_votes (
                      vote_event_id, seat, member_name, member_name_normalized, person_id,
                      group_code, vote_choice, source_id, raw_payload, created_at, updated_at
                    ) VALUES ('vote-1', '1', 'Ana López', 'ana lopez', ?, 'GS', 'SÍ',
                      'congreso_votaciones', '{}', ?, ?)
                    """,
                    (person_id, now_iso, now_iso),
                )
                conn.commit()
                result = backfill_parliamentary_groups_from_vote_member_votes(
                    conn,
                    source_ids=("congreso_votaciones",),
                    dry_run=True,
                )
                group_count = conn.execute("SELECT COUNT(*) AS n FROM parliamentary_groups").fetchone()
                membership_count = conn.execute(
                    "SELECT COUNT(*) AS n FROM person_parliamentary_group_memberships"
                ).fetchone()

            self.assertTrue(result["dry_run"])
            self.assertEqual(result["groups_seen"], 1)
            self.assertEqual(result["groups_upserted"], 0)
            self.assertEqual(int(group_count["n"]), 0)
            self.assertEqual(int(membership_count["n"]), 0)


if __name__ == "__main__":
    unittest.main()
