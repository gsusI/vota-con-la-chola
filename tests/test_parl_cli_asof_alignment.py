from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.cli import (
    _resolve_backfill_combined_positions_as_of_date,
    _resolve_backfill_declared_positions_as_of_date,
    _resolve_backfill_topic_analytics_as_of_date,
)
from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.politicos_es.util import canonical_key, now_utc_iso


class TestParlCliAsOfAlignment(unittest.TestCase):
    def _insert_vote_event(
        self,
        conn,
        *,
        vote_event_id: str,
        source_id: str,
        legislature: str,
        vote_date: str,
    ) -> None:
        now_iso = now_utc_iso()
        conn.execute(
            """
            INSERT INTO parl_vote_events (
              vote_event_id, legislature, vote_date, title,
              source_id, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                vote_event_id,
                legislature,
                vote_date,
                vote_event_id,
                source_id,
                "{}",
                now_iso,
                now_iso,
            ),
        )

    def _seed_topic_person_set(self, conn, *, topic_set_name: str) -> tuple[int, int, int]:
        now_iso = now_utc_iso()
        conn.execute(
            """
            INSERT INTO topic_sets (name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (topic_set_name, "fixture", now_iso, now_iso),
        )
        topic_set_id = int(
            conn.execute(
                "SELECT topic_set_id FROM topic_sets WHERE name = ?",
                (topic_set_name,),
            ).fetchone()["topic_set_id"]
        )

        topic_key = f"{topic_set_name.lower().replace(' ', '_')}_topic"
        conn.execute(
            """
            INSERT INTO topics (canonical_key, label, description, parent_topic_id, created_at, updated_at)
            VALUES (?, ?, NULL, NULL, ?, ?)
            """,
            (topic_key, topic_key, now_iso, now_iso),
        )
        topic_id = int(
            conn.execute(
                "SELECT topic_id FROM topics WHERE canonical_key = ?",
                (topic_key,),
            ).fetchone()["topic_id"]
        )

        person_name = f"Persona {topic_set_name}"
        ckey = canonical_key(full_name=person_name, birth_date=None, territory_code="")
        conn.execute(
            """
            INSERT INTO persons (full_name, canonical_key, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (person_name, ckey, now_iso, now_iso),
        )
        person_id = int(
            conn.execute(
                "SELECT person_id FROM persons WHERE canonical_key = ?",
                (ckey,),
            ).fetchone()["person_id"]
        )
        return topic_set_id, topic_id, person_id

    def test_topic_analytics_as_of_resolver_uses_latest_vote_window(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "asof-topic-analytics.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)

                self._insert_vote_event(
                    conn,
                    vote_event_id="cong-l14",
                    source_id="congreso_votaciones",
                    legislature="14",
                    vote_date="2025-11-01",
                )
                self._insert_vote_event(
                    conn,
                    vote_event_id="cong-l15",
                    source_id="congreso_votaciones",
                    legislature="15",
                    vote_date="2026-02-12",
                )
                self._insert_vote_event(
                    conn,
                    vote_event_id="sen-l14",
                    source_id="senado_votaciones",
                    legislature="14",
                    vote_date="2025-12-15",
                )
                self._insert_vote_event(
                    conn,
                    vote_event_id="sen-l15",
                    source_id="senado_votaciones",
                    legislature="15",
                    vote_date="2026-01-25",
                )
                conn.commit()

                resolved = _resolve_backfill_topic_analytics_as_of_date(
                    conn,
                    explicit_as_of_date=None,
                    vote_source_ids=("congreso_votaciones", "senado_votaciones"),
                    legislature="latest",
                )
                self.assertEqual(resolved, "2026-02-12")

                explicit = _resolve_backfill_topic_analytics_as_of_date(
                    conn,
                    explicit_as_of_date="2026-01-31",
                    vote_source_ids=("congreso_votaciones", "senado_votaciones"),
                    legislature="latest",
                )
                self.assertEqual(explicit, "2026-01-31")
            finally:
                conn.close()

    def test_declared_positions_as_of_resolver_prefers_votes_for_declared_topic_sets(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "asof-declared.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now_iso = now_utc_iso()

                set_a, topic_a, person_a = self._seed_topic_person_set(conn, topic_set_name="Set A")
                set_b, topic_b, person_b = self._seed_topic_person_set(conn, topic_set_name="Set B")

                conn.execute(
                    """
                    INSERT INTO topic_evidence (
                      topic_id, topic_set_id, person_id,
                      evidence_type, evidence_date, excerpt,
                      stance, polarity, weight, confidence,
                      topic_method, stance_method,
                      source_id, source_url, source_snapshot_date, raw_payload,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic_a,
                        set_a,
                        person_a,
                        "declared:intervention",
                        "2026-02-11",
                        "fixture",
                        "support",
                        1,
                        1.0,
                        0.8,
                        "fixture",
                        "declared:regex_v3",
                        "congreso_intervenciones",
                        "https://example.invalid/a",
                        "2026-02-12",
                        "{}",
                        now_iso,
                        now_iso,
                    ),
                )

                for topic_set_id, topic_id, person_id, as_of_date in (
                    (set_a, topic_a, person_a, "2026-02-12"),
                    (set_b, topic_b, person_b, "2026-02-16"),
                ):
                    conn.execute(
                        """
                        INSERT INTO topic_positions (
                          topic_id, topic_set_id, person_id,
                          as_of_date, stance, score, confidence, evidence_count, last_evidence_date,
                          computed_method, computed_version, computed_at,
                          created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            topic_id,
                            topic_set_id,
                            person_id,
                            as_of_date,
                            "support",
                            1.0,
                            0.9,
                            1,
                            as_of_date,
                            "votes",
                            "v1",
                            now_iso,
                            now_iso,
                            now_iso,
                        ),
                    )
                conn.commit()

                resolved = _resolve_backfill_declared_positions_as_of_date(
                    conn,
                    explicit_as_of_date=None,
                    source_id="congreso_intervenciones",
                )
                self.assertEqual(resolved, "2026-02-12")

                explicit = _resolve_backfill_declared_positions_as_of_date(
                    conn,
                    explicit_as_of_date="2026-02-20",
                    source_id="congreso_intervenciones",
                )
                self.assertEqual(explicit, "2026-02-20")
            finally:
                conn.close()

    def test_combined_positions_as_of_resolver_ignores_declared_only_newer_dates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "asof-combined.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                now_iso = now_utc_iso()

                topic_set_id, topic_id, person_id = self._seed_topic_person_set(conn, topic_set_name="Set Combined")

                conn.execute(
                    """
                    INSERT INTO topic_positions (
                      topic_id, topic_set_id, person_id,
                      as_of_date, stance, score, confidence, evidence_count, last_evidence_date,
                      computed_method, computed_version, computed_at,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic_id,
                        topic_set_id,
                        person_id,
                        "2026-02-12",
                        "support",
                        1.0,
                        0.9,
                        1,
                        "2026-02-12",
                        "votes",
                        "v1",
                        now_iso,
                        now_iso,
                        now_iso,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO topic_positions (
                      topic_id, topic_set_id, person_id,
                      as_of_date, stance, score, confidence, evidence_count, last_evidence_date,
                      computed_method, computed_version, computed_at,
                      created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic_id,
                        topic_set_id,
                        person_id,
                        "2026-02-16",
                        "oppose",
                        -1.0,
                        0.9,
                        1,
                        "2026-02-16",
                        "declared",
                        "v1",
                        now_iso,
                        now_iso,
                        now_iso,
                    ),
                )
                conn.commit()

                resolved = _resolve_backfill_combined_positions_as_of_date(
                    conn,
                    explicit_as_of_date=None,
                )
                self.assertEqual(resolved, "2026-02-12")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
