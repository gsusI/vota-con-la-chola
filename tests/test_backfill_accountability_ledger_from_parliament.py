from __future__ import annotations

from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources
from etl.politicos_es.util import canonical_key, now_utc_iso
from scripts.backfill_accountability_ledger_from_parliament import backfill_parliamentary_accountability_ledger
from scripts.export_accountability_ledger_snapshot import build_accountability_ledger_snapshot


def _insert_person(conn: object, person_id: int, full_name: str) -> None:
    now_iso = now_utc_iso()
    conn.execute(
        """
        INSERT INTO persons (
          person_id, full_name, given_name, family_name, gender, gender_id,
          birth_date, territory_code, territory_id, canonical_key, created_at, updated_at
        ) VALUES (?, ?, NULL, NULL, NULL, NULL, NULL, '', NULL, ?, ?, ?)
        """,
        (person_id, full_name, canonical_key(full_name, None, ""), now_iso, now_iso),
    )


class TestBackfillAccountabilityLedgerFromParliament(unittest.TestCase):
    def test_backfill_votes_to_issue_led_accountability_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-accountability.db"
            with closing(open_db(db_path)) as conn:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                now_iso = now_utc_iso()

                conn.execute(
                    """
                    INSERT INTO parties (party_id, name, acronym, created_at, updated_at)
                    VALUES (1, 'Partido A', 'PA', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO institutions (institution_id, name, level, territory_code, created_at, updated_at)
                    VALUES (1, 'Congreso de los Diputados', 'nacional', 'ES', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO parliamentary_groups (
                      parliamentary_group_id, source_id, institution_id, legislature, group_code,
                      name, normalized_name, raw_payload, created_at, updated_at
                    ) VALUES (1, 'congreso_votaciones', 1, '15', 'PA',
                      'Grupo Parlamentario A', 'grupo parlamentario a', '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                _insert_person(conn, 10, "Ana Lopez")
                conn.execute(
                    """
                    INSERT INTO mandates (
                      mandate_id, person_id, institution_id, party_id, role_title, level,
                      start_date, end_date, is_active, source_id, source_record_id,
                      first_seen_at, last_seen_at, raw_payload
                    ) VALUES (100, 10, 1, 1, 'Diputada', 'nacional', '2023-01-01', '', 1,
                      'congreso_votaciones', 'ana-lopez', ?, ?, '{}')
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, vote_date, title, source_id, source_url,
                      raw_payload, created_at, updated_at
                    ) VALUES ('vote-1', '15', '2024-02-01', 'Votacion sobre movilidad',
                      'congreso_votaciones', 'https://example.test/vote-1', '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiatives (
                      initiative_id, legislature, expediente, title, source_id,
                      raw_payload, created_at, updated_at
                    ) VALUES ('init-1', '15', '121/000001', 'Ley de movilidad sostenible',
                      'congreso_iniciativas', '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_event_initiatives (
                      vote_event_id, initiative_id, link_method, confidence, created_at, updated_at
                    ) VALUES ('vote-1', 'init-1', 'manual', 1.0, ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_member_votes (
                      vote_event_id, seat, member_name, member_name_normalized, person_id,
                      group_code, parliamentary_group_id, vote_choice, source_id, source_url,
                      raw_payload, created_at, updated_at
                    ) VALUES
                      ('vote-1', '1', 'Ana Lopez', 'ana lopez', 10, 'PA', 1, 'SÍ',
                       'congreso_votaciones', 'https://example.test/vote-1/member/1', '{}', ?, ?),
                      ('vote-1', '2', 'Beto Ruiz', 'beto ruiz', NULL, 'GB', NULL, 'NO',
                       'congreso_votaciones', 'https://example.test/vote-1/member/2', '{}', ?, ?)
                    """,
                    (now_iso, now_iso, now_iso, now_iso),
                )
                conn.commit()

                first = backfill_parliamentary_accountability_ledger(conn)
                second = backfill_parliamentary_accountability_ledger(conn)
                self.assertEqual(first["source_rows_seen"], 2)
                self.assertEqual(first["issues_upserted"], 1)
                self.assertEqual(first["member_entries_upserted"], 2)
                self.assertEqual(first["group_entries_upserted"], 1)
                self.assertEqual(first["party_entries_upserted"], 1)
                self.assertEqual(first["entries_upserted"], 4)
                self.assertEqual(second["entries_upserted"], 4)

                rows = conn.execute(
                    """
                    SELECT
                      actor_label, actor_kind, accountability_role, person_id, party_id,
                      parliamentary_group_id, mandate_id, evidence_tier
                    FROM accountability_ledger_entries
                    WHERE issue_id = 'parl-initiative:init-1'
                    ORDER BY actor_kind, actor_label
                    """
                ).fetchall()
                self.assertEqual(len(rows), 4)
                by_actor = {(row["actor_kind"], row["actor_label"]): row for row in rows}
                group_row = by_actor[("group", "Grupo Parlamentario A")]
                party_row = by_actor[("party", "Partido A")]
                self.assertEqual(group_row["accountability_role"], "voted_for")
                self.assertEqual(int(group_row["parliamentary_group_id"]), 1)
                self.assertEqual(party_row["accountability_role"], "voted_for")
                self.assertEqual(int(party_row["party_id"]), 1)
                self.assertIsNone(party_row["parliamentary_group_id"])
                self.assertEqual(by_actor[("person", "Ana Lopez")]["accountability_role"], "voted_for")
                self.assertEqual(by_actor[("person", "Ana Lopez")]["actor_kind"], "person")
                self.assertEqual(int(by_actor[("person", "Ana Lopez")]["party_id"]), 1)
                self.assertEqual(int(by_actor[("person", "Ana Lopez")]["parliamentary_group_id"]), 1)
                self.assertEqual(int(by_actor[("person", "Ana Lopez")]["mandate_id"]), 100)
                self.assertEqual(int(by_actor[("person", "Ana Lopez")]["evidence_tier"]), 1)
                self.assertEqual(int(group_row["evidence_tier"]), 1)
                self.assertEqual(by_actor[("unknown", "Beto Ruiz")]["accountability_role"], "voted_against")
                self.assertIsNone(by_actor[("unknown", "Beto Ruiz")]["person_id"])

                snapshot = build_accountability_ledger_snapshot(
                    conn,
                    snapshot_date="2026-05-10",
                    issue_id="parl-initiative:init-1",
                )
                fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()

            self.assertEqual(snapshot["coverage"]["issues_total"], 1)
            self.assertEqual(snapshot["coverage"]["entries_total"], 4)
            self.assertEqual(snapshot["coverage"]["entries_with_parliamentary_group_id"], 2)
            self.assertEqual(snapshot["coverage"]["entries_with_party_id"], 2)
            self.assertEqual(snapshot["coverage"]["entries_by_actor_kind"]["party"], 1)
            self.assertEqual(snapshot["coverage"]["entries_by_role"]["voted_for"], 3)
            self.assertEqual(snapshot["coverage"]["entries_by_role"]["voted_against"], 1)
            self.assertEqual(snapshot["issues"][0]["label"], "Ley de movilidad sostenible")
            self.assertEqual(fk_rows, [])


if __name__ == "__main__":
    unittest.main()
