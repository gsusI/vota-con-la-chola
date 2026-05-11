from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from etl.politicos_es.util import canonical_key, now_utc_iso
from scripts.backfill_mandates_from_vote_member_names import backfill_mandates_from_vote_member_names


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


class TestBackfillMandatesFromVoteMemberNames(unittest.TestCase):
    def test_creates_observed_mandate_from_roll_call_participation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "vote-mandates.db"
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
                          group_code, vote_choice, source_id, raw_payload, created_at, updated_at
                        ) VALUES (?, '1', 'Ana López', 'ana lopez', ?, 'GS', 'SÍ',
                          'congreso_votaciones', '{}', ?, ?)
                        """,
                        (vote_event_id, person_id, now_iso, now_iso),
                    )
                conn.commit()

                first = backfill_mandates_from_vote_member_names(conn, source_ids=("congreso_votaciones",))
                second = backfill_mandates_from_vote_member_names(conn, source_ids=("congreso_votaciones",))
                mandates = conn.execute(
                    """
                    SELECT m.*, i.name AS institution_name, r.title AS role_name
                    FROM mandates m
                    JOIN institutions i ON i.institution_id = m.institution_id
                    LEFT JOIN roles r ON r.role_id = m.role_id
                    """
                ).fetchall()
                fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()

            self.assertEqual(first["observed_mandates_seen"], 1)
            self.assertEqual(first["mandates_upserted"], 1)
            self.assertEqual(second["observed_mandates_seen"], 1)
            self.assertEqual(second["mandates_upserted"], 1)
            self.assertEqual(len(mandates), 1)
            mandate = mandates[0]
            self.assertEqual(mandate["person_id"], person_id)
            self.assertEqual(mandate["institution_name"], "Congreso de los Diputados")
            self.assertEqual(mandate["role_title"], "Diputado/a")
            self.assertEqual(mandate["role_name"], "Diputado/a")
            self.assertEqual(mandate["start_date"], "2024-01-01")
            self.assertEqual(mandate["end_date"], "2024-02-03")
            self.assertEqual(mandate["source_record_id"], "observed-rollcall-mandate:leg15:ana lopez")
            self.assertEqual(json.loads(mandate["raw_payload"])["vote_rows"], 3)
            self.assertEqual(fk_rows, [])

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "vote-mandates-dry.db"
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
                result = backfill_mandates_from_vote_member_names(
                    conn,
                    source_ids=("congreso_votaciones",),
                    dry_run=True,
                )
                mandate_count = conn.execute("SELECT COUNT(*) AS n FROM mandates").fetchone()

            self.assertTrue(result["dry_run"])
            self.assertEqual(result["observed_mandates_seen"], 1)
            self.assertEqual(result["mandates_upserted"], 0)
            self.assertEqual(int(mandate_count["n"]), 0)


if __name__ == "__main__":
    unittest.main()
