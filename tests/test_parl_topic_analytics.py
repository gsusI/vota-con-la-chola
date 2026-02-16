from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG as PARL_SOURCE_CONFIG
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.pipeline import ingest_one_source as ingest_parl_source
from etl.parlamentario_es.registry import get_connectors as get_parl_connectors
from etl.parlamentario_es.topic_analytics import backfill_topic_analytics_from_votes
from etl.politicos_es.util import canonical_key, now_utc_iso


class TestParlTopicAnalytics(unittest.TestCase):
    def test_backfill_topic_analytics_from_votes_builds_non_empty_tables_and_is_idempotent(self) -> None:
        snapshot_date = "2026-02-12"
        vote_sources = ("congreso_votaciones",)

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "topic-analytics.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)

                parl_connectors = get_parl_connectors()
                for sid in vote_sources:
                    connector = parl_connectors[sid]
                    sample_path = Path(PARL_SOURCE_CONFIG[sid]["fallback_file"])
                    self.assertTrue(sample_path.exists(), f"Missing sample for {sid}: {sample_path}")
                    ingest_parl_source(
                        conn=conn,
                        connector=connector,
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=sample_path,
                        url_override=None,
                        snapshot_date=snapshot_date,
                        strict_network=True,
                        options={},
                    )

                # Sample congreso_votaciones fixture may not include legislatura; normalize it so 'latest' works.
                conn.execute(
                    """
                    UPDATE parl_vote_events
                    SET legislature = '15'
                    WHERE source_id = 'congreso_votaciones'
                      AND (legislature IS NULL OR TRIM(legislature) = '')
                    """
                )
                conn.commit()

                # Ensure we have person_id to exercise analytics (analytics filters out NULL person_id).
                missing = int(
                    conn.execute(
                        "SELECT COUNT(*) AS c FROM parl_vote_member_votes WHERE person_id IS NULL"
                    ).fetchone()["c"]
                )
                if missing:
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
                    conn.execute(
                        "UPDATE parl_vote_member_votes SET person_id = ? WHERE person_id IS NULL",
                        (person_id,),
                    )
                    conn.commit()

                backfill_topic_analytics_from_votes(
                    conn,
                    vote_source_ids=vote_sources,
                    legislature="latest",
                    as_of_date=snapshot_date,
                    max_topics=20,
                    high_stakes_top=10,
                    dry_run=False,
                )

                counts_1 = {
                    "topic_sets": int(conn.execute("SELECT COUNT(*) AS c FROM topic_sets").fetchone()["c"]),
                    "topic_set_topics": int(
                        conn.execute("SELECT COUNT(*) AS c FROM topic_set_topics").fetchone()["c"]
                    ),
                    "topic_evidence": int(conn.execute("SELECT COUNT(*) AS c FROM topic_evidence").fetchone()["c"]),
                    "topic_positions": int(
                        conn.execute("SELECT COUNT(*) AS c FROM topic_positions").fetchone()["c"]
                    ),
                }
                self.assertGreater(counts_1["topic_sets"], 0)
                self.assertGreater(counts_1["topic_set_topics"], 0)
                self.assertGreater(counts_1["topic_evidence"], 0)
                self.assertGreater(counts_1["topic_positions"], 0)

                # Re-run: should be stable (we delete+recompute derived tables per topic_set).
                backfill_topic_analytics_from_votes(
                    conn,
                    vote_source_ids=vote_sources,
                    legislature="latest",
                    as_of_date=snapshot_date,
                    max_topics=20,
                    high_stakes_top=10,
                    dry_run=False,
                )
                counts_2 = {
                    "topic_sets": int(conn.execute("SELECT COUNT(*) AS c FROM topic_sets").fetchone()["c"]),
                    "topic_set_topics": int(
                        conn.execute("SELECT COUNT(*) AS c FROM topic_set_topics").fetchone()["c"]
                    ),
                    "topic_evidence": int(conn.execute("SELECT COUNT(*) AS c FROM topic_evidence").fetchone()["c"]),
                    "topic_positions": int(
                        conn.execute("SELECT COUNT(*) AS c FROM topic_positions").fetchone()["c"]
                    ),
                }
                self.assertEqual(counts_1, counts_2)

                fk = conn.execute("PRAGMA foreign_key_check").fetchall()
                self.assertEqual(fk, [])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
