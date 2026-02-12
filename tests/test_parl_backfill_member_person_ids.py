from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources
from etl.parlamentario_es.pipeline import backfill_vote_member_person_ids
from etl.politicos_es.util import canonical_key, now_utc_iso


def _insert_person(conn: object, person_id: int, full_name: str, birth_date: str | None) -> None:
    now_iso = now_utc_iso()
    conn.execute(
        """
        INSERT INTO persons (
          person_id, full_name, given_name, family_name, gender, gender_id,
          birth_date, territory_code, territory_id, canonical_key, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            person_id,
            full_name,
            None,
            None,
            None,
            None,
            birth_date,
            "",
            None,
            canonical_key(full_name, birth_date, ""),
            now_iso,
            now_iso,
        ),
    )


def _insert_vote_event(
    conn: object,
    vote_event_id: str,
    source_id: str,
    legislature: str,
    vote_date: str = "2026-02-12",
) -> None:
    now_iso = now_utc_iso()
    conn.execute(  # type: ignore[func-returns-value]
        """
        INSERT INTO parl_vote_events (
          vote_event_id, legislature, vote_date, title, source_id,
          raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            vote_event_id,
            legislature,
            vote_date,
            "Votación de prueba",
            source_id,
            "{}",
            now_iso,
            now_iso,
        ),
    )


def _insert_member_vote(
    conn: object,
    vote_event_id: str,
    source_id: str,
    member_name_normalized: str,
    member_name: str,
    person_id: int | None = None,
) -> None:
    now_iso = now_utc_iso()
    conn.execute(  # type: ignore[func-returns-value]
        """
        INSERT INTO parl_vote_member_votes (
          vote_event_id, seat, member_name, member_name_normalized,
          person_id, vote_choice, source_id, raw_payload, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            vote_event_id,
            f"{vote_event_id}-seat-1",
            member_name,
            member_name_normalized,
            person_id,
            "SÍ",
            source_id,
            "{}",
            now_iso,
            now_iso,
        ),
    )


class TestBackfillVoteMemberPersonIds(unittest.TestCase):
    def test_backfill_vote_member_person_ids_is_deterministic_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "backfill.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)

                _insert_person(conn, 101, "Ana López", "1970-01-01")
                _insert_person(conn, 201, "Ana López", "1980-01-01")

                _insert_vote_event(conn, "vote-ana", "congreso_votaciones", "15", "2023-06-10")
                _insert_member_vote(conn, "vote-ana", "congreso_votaciones", "ana lopez", "Ana López")
                conn.commit()

                candidates = {
                    "ana lopez": [
                        {"person_id": 201, "is_active": 1, "legislature": "15", "start_date": "2005-01-01", "end_date": "2016-12-31"},
                        {"person_id": 101, "is_active": 1, "legislature": "15", "start_date": "2020-01-01", "end_date": "2028-12-31"},
                    ]
                }

                with patch(
                    "etl.parlamentario_es.pipeline._load_mandate_name_index",
                    return_value=candidates,
                ):
                    res1 = backfill_vote_member_person_ids(conn, vote_source_ids=("congreso_votaciones",))

                    # Deterministic second pass against already-resolved rows.
                    res2 = backfill_vote_member_person_ids(conn, vote_source_ids=("congreso_votaciones",))

                row = conn.execute(
                    "SELECT person_id FROM parl_vote_member_votes WHERE vote_event_id = ?",
                    ("vote-ana",),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(int(row["person_id"]), 101)
                self.assertEqual(res1["total_checked"], 1)
                self.assertEqual(res1["total_matched"], 1)
                self.assertEqual(res1["total_updated"], 1)
                self.assertEqual(res2["total_checked"], 0)
                self.assertEqual(res2["total_matched"], 0)
                self.assertEqual(res2["total_updated"], 0)
            finally:
                conn.close()

    def test_backfill_vote_member_person_ids_reports_ambiguous_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "backfill.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)

                _insert_person(conn, 201, "Javier Ruiz", "1975-01-01")
                _insert_person(conn, 301, "Javier Ruiz", "1978-07-09")

                _insert_vote_event(conn, "vote-ambig", "congreso_votaciones", "15", "2023-11-20")
                _insert_member_vote(conn, "vote-ambig", "congreso_votaciones", "javier ruiz", "Javier Ruiz")
                conn.commit()

                def load_mandates(conn_obj, mandate_source_id):  # noqa: ARG001
                    _ = conn_obj
                    if mandate_source_id == "congreso_diputados":
                        return {
                            "javier ruiz": [
                                {"person_id": 201, "is_active": 1, "legislature": "15", "start_date": "2020-01-01", "end_date": ""},
                                {"person_id": 301, "is_active": 1, "legislature": "15", "start_date": "2020-01-01", "end_date": ""},
                            ]
                        }
                    return {}

                with patch(
                    "etl.parlamentario_es.pipeline._load_mandate_name_index", side_effect=load_mandates
                ):
                    res = backfill_vote_member_person_ids(
                        conn,
                        vote_source_ids=("congreso_votaciones",),
                    )

                row = conn.execute(
                    "SELECT person_id FROM parl_vote_member_votes WHERE vote_event_id = ?",
                    ("vote-ambig",),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertIsNone(row["person_id"])
                self.assertEqual(res["total_checked"], 1)
                self.assertEqual(res["total_matched"], 0)
                self.assertEqual(res["total_ambiguous"], 1)
            finally:
                conn.close()

    def test_backfill_vote_member_person_ids_targets_both_vote_sources(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "backfill.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)

                _insert_person(conn, 1111, "Carmen Soto", "1985-08-10")
                _insert_person(conn, 2222, "Pablo Núñez", "1969-06-07")

                _insert_vote_event(conn, "vote-cong", "congreso_votaciones", "15", "2024-03-01")
                _insert_vote_event(conn, "vote-sen", "senado_votaciones", "15", "2024-03-01")
                _insert_member_vote(conn, "vote-cong", "congreso_votaciones", "carmen soto", "Carmen Soto")
                _insert_member_vote(conn, "vote-sen", "senado_votaciones", "pablo nunez", "Pablo Núñez")
                conn.commit()

                def load_mandates(conn_obj, mandate_source_id):  # noqa: ARG001
                    _ = conn_obj
                    if mandate_source_id == "congreso_diputados":
                        return {
                            "carmen soto": [
                                {"person_id": 1111, "is_active": 1, "legislature": "15", "start_date": "2023-01-01", "end_date": "2024-12-31"},
                            ]
                        }
                    if mandate_source_id == "senado_senadores":
                        return {
                            "pablo nunez": [
                                {"person_id": 2222, "is_active": 1, "legislature": "15", "start_date": "2023-01-01", "end_date": "2024-12-31"},
                            ]
                        }
                    return {}

                with patch(
                    "etl.parlamentario_es.pipeline._load_mandate_name_index", side_effect=load_mandates
                ):
                    res = backfill_vote_member_person_ids(
                        conn,
                        vote_source_ids=("congreso_votaciones", "senado_votaciones"),
                    )

                rows = conn.execute(
                    "SELECT source_id, person_id FROM parl_vote_member_votes ORDER BY member_vote_id"
                ).fetchall()
                by_source = {str(r["source_id"]): int(r["person_id"]) for r in rows}
                self.assertEqual(by_source["congreso_votaciones"], 1111)
                self.assertEqual(by_source["senado_votaciones"], 2222)
                self.assertEqual(res["total_checked"], 2)
                self.assertEqual(res["total_matched"], 2)
                self.assertEqual(res["total_updated"], 2)
            finally:
                conn.close()

    def test_backfill_vote_member_person_ids_prefers_matching_legislature(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "backfill.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)

                _insert_person(conn, 111, "María Torres", "1970-01-01")
                _insert_person(conn, 222, "María Torres", "1980-01-01")

                _insert_vote_event(conn, "vote-15", "congreso_votaciones", "15")
                _insert_vote_event(conn, "vote-14", "congreso_votaciones", "14")
                conn.execute("UPDATE parl_vote_events SET vote_date = ? WHERE vote_event_id = ?", ("2023-06-01", "vote-15"))
                conn.execute("UPDATE parl_vote_events SET vote_date = ? WHERE vote_event_id = ?", ("2014-06-01", "vote-14"))
                _insert_member_vote(conn, "vote-15", "congreso_votaciones", "maria torres", "María Torres")
                _insert_member_vote(conn, "vote-14", "congreso_votaciones", "maria torres", "María Torres")
                conn.commit()

                def load_mandates(conn_obj, mandate_source_id):  # noqa: ARG001
                    _ = conn_obj
                    if mandate_source_id == "congreso_diputados":
                        return {
                            "maria torres": [
                                {
                                    "person_id": 111,
                                    "is_active": 1,
                                    "start_date": "2020-01-01",
                                    "end_date": "2025-12-31",
                                },
                                {
                                    "person_id": 222,
                                    "is_active": 1,
                                    "start_date": "1990-01-01",
                                    "end_date": "2015-12-31",
                                },
                            ]
                        }
                    return {}

                with patch(
                    "etl.parlamentario_es.pipeline._load_mandate_name_index", side_effect=load_mandates
                ):
                    backfill_vote_member_person_ids(conn, vote_source_ids=("congreso_votaciones",))

                rows = conn.execute(
                    """
                    SELECT vote_event_id, person_id
                    FROM parl_vote_member_votes
                    ORDER BY vote_event_id
                    """
                ).fetchall()
                self.assertEqual(len(rows), 2)
                person_map = {str(r["vote_event_id"]): int(r["person_id"]) for r in rows}
                self.assertEqual(person_map["vote-15"], 111)
                self.assertEqual(person_map["vote-14"], 222)
            finally:
                conn.close()

    def test_backfill_vote_member_person_ids_preserves_existing_person_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "backfill.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)

                _insert_person(conn, 999, "Luis Ramos", "1975-04-03")
                _insert_person(conn, 1000, "Luis Ramos", "1980-01-01")

                _insert_vote_event(conn, "vote-existing", "congreso_votaciones", "15")
                _insert_member_vote(
                    conn,
                    "vote-existing",
                    "congreso_votaciones",
                    "luis ramos",
                    "Luis Ramos",
                    person_id=999,
                )
                conn.commit()

                def load_mandates(conn_obj, mandate_source_id):  # noqa: ARG001
                    _ = conn_obj
                    if mandate_source_id == "congreso_diputados":
                        return {
                            "luis ramos": [
                                {"person_id": 1000, "is_active": 1, "legislature": "15", "start_date": "1990-01-01", "end_date": ""}
                            ]
                        }
                    return {}

                with patch(
                    "etl.parlamentario_es.pipeline._load_mandate_name_index", side_effect=load_mandates
                ):
                    res = backfill_vote_member_person_ids(conn, vote_source_ids=("congreso_votaciones",))

                row = conn.execute(
                    "SELECT person_id FROM parl_vote_member_votes WHERE vote_event_id = ?",
                    ("vote-existing",),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(int(row["person_id"]), 999)
                self.assertEqual(res["total_checked"], 0)
                self.assertEqual(res["total_matched"], 0)
                self.assertEqual(res["total_updated"], 0)
            finally:
                conn.close()

    def test_backfill_vote_member_person_ids_reports_without_writing_on_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "backfill.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)

                _insert_person(conn, 1010, "Rosa Díaz", "1977-02-02")

                _insert_vote_event(conn, "vote-dry", "congreso_votaciones", "15")
                _insert_member_vote(conn, "vote-dry", "congreso_votaciones", "rosa diaz", "Rosa Díaz")
                conn.commit()

                def load_mandates(conn_obj, mandate_source_id):  # noqa: ARG001
                    _ = conn_obj
                    if mandate_source_id == "congreso_diputados":
                        return {
                            "rosa diaz": [
                                {"person_id": 1010, "is_active": 1, "legislature": "15", "start_date": "2019-01-01", "end_date": ""}
                            ]
                        }
                    return {}

                with patch(
                    "etl.parlamentario_es.pipeline._load_mandate_name_index", side_effect=load_mandates
                ):
                    res = backfill_vote_member_person_ids(
                        conn,
                        vote_source_ids=("congreso_votaciones",),
                        dry_run=True,
                    )

                row = conn.execute(
                    "SELECT person_id FROM parl_vote_member_votes WHERE vote_event_id = ?",
                    ("vote-dry",),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertIsNone(row["person_id"])
                self.assertTrue(res["dry_run"])
                self.assertEqual(res["total_checked"], 1)
                self.assertEqual(res["total_matched"], 1)
                self.assertEqual(res["total_updated"], 1)
                self.assertEqual(len(res["sources"]), 1)
                congreso_stats = res["sources"][0]
                self.assertEqual(congreso_stats["source_id"], "congreso_votaciones")
                self.assertEqual(congreso_stats["updated"], 1)
            finally:
                conn.close()

    def test_backfill_vote_member_person_ids_reports_unmatched_reasons_and_sample(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "backfill.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)

                _insert_person(conn, 333, "Marcos Peña", "1980-10-10")

                _insert_vote_event(conn, "vote-clean", "congreso_votaciones", "15")
                _insert_member_vote(
                    conn,
                    "vote-clean",
                    "congreso_votaciones",
                    "marcos pena",
                    "Marcos Peña",
                )

                _insert_vote_event(conn, "vote-empty-name", "congreso_votaciones", "15")
                _insert_member_vote(
                    conn,
                    "vote-empty-name",
                    "congreso_votaciones",
                    "",
                    "",
                )

                _insert_vote_event(conn, "vote-no-candidate", "congreso_votaciones", "15")
                _insert_member_vote(
                    conn,
                    "vote-no-candidate",
                    "congreso_votaciones",
                    "nadie",
                    "Nadie",
                )
                conn.commit()

                def load_mandates(conn_obj, mandate_source_id):  # noqa: ARG001
                    _ = conn_obj
                    if mandate_source_id == "congreso_diputados":
                        return {
                            "marcos pena": [
                                {
                                    "person_id": 333,
                                    "is_active": 1,
                                    "legislature": "15",
                                    "start_date": "2019-01-01",
                                    "end_date": "",
                                }
                            ]
                        }
                    return {}

                with patch(
                    "etl.parlamentario_es.pipeline._load_mandate_name_index", side_effect=load_mandates
                ):
                    res = backfill_vote_member_person_ids(
                        conn,
                        vote_source_ids=("congreso_votaciones",),
                        unmatched_sample_limit=1,
                    )

                row = conn.execute(
                    "SELECT person_id FROM parl_vote_member_votes WHERE vote_event_id = ?",
                    ("vote-clean",),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(int(row["person_id"]), 333)

                self.assertEqual(res["total_checked"], 3)
                self.assertEqual(res["total_matched"], 1)
                self.assertEqual(res["total_unmatched"], 2)
                self.assertEqual(res["total_updated"], 1)
                self.assertEqual(res["unmatched_by_reason"]["skipped_no_name"], 1)
                self.assertEqual(res["unmatched_by_reason"]["no_candidates"], 1)
                self.assertEqual(len(res["unmatched_sample"]), 1)
                self.assertIn("reason", res["unmatched_sample"][0])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
