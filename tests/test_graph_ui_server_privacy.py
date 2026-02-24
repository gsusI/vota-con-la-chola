from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from etl.parlamentario_es.config import DEFAULT_SCHEMA as PARL_SCHEMA
from etl.parlamentario_es.db import apply_schema as apply_parl_schema
from etl.parlamentario_es.db import open_db as open_parl_db
from etl.parlamentario_es.db import seed_sources as seed_parl_sources
from etl.politicos_es.config import DEFAULT_SCHEMA as POLITICOS_SCHEMA
from etl.politicos_es.db import apply_schema as apply_politicos_schema
from etl.politicos_es.db import open_db as open_politicos_db
from etl.politicos_es.db import seed_sources as seed_politicos_sources
from etl.politicos_es.util import now_utc_iso
from scripts import graph_ui_server as g


class TestGraphUiServerPrivacy(unittest.TestCase):
    def test_sources_status_redacts_local_file_urls_and_user_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "status.db"
            conn = open_politicos_db(db_path)
            try:
                apply_politicos_schema(conn, POLITICOS_SCHEMA)
                seed_politicos_sources(conn)
                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO ingestion_runs (
                      source_id, started_at, finished_at, status, source_url, raw_path, fetched_at,
                      records_seen, records_loaded, message
                    ) VALUES (?, ?, ?, 'ok', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "congreso_diputados",
                        now_iso,
                        now_iso,
                        "file:///Users/alice/Library/CloudStorage/GoogleDrive-alice@example.com/repo/sample.json",
                        "/tmp/sample.json",
                        now_iso,
                        5,
                        5,
                        "fixture",
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            old_tracker_path = g.TRACKER_PATH
            old_waivers_path = g.MISMATCH_WAIVERS_PATH
            try:
                g._load_tracker_items_cached.cache_clear()
                g.TRACKER_PATH = Path("/Users/alice/private/e2e-scrape-load-tracker.md")
                g.MISMATCH_WAIVERS_PATH = Path("/Users/alice/private/mismatch-waivers.json")
                payload = g.build_sources_status_payload(db_path)
            finally:
                g.TRACKER_PATH = old_tracker_path
                g.MISMATCH_WAIVERS_PATH = old_waivers_path
                g._load_tracker_items_cached.cache_clear()

        rows = payload.get("sources") or []
        by_source = {str(row.get("source_id")): row for row in rows}
        congreso = by_source["congreso_diputados"]
        self.assertEqual(congreso.get("last_source_url"), "")
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("/Users/alice", serialized)
        self.assertNotIn("alice@example.com", serialized)

    def test_vote_summary_redacts_local_file_source_url(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "votes.db"
            conn = open_parl_db(db_path)
            try:
                apply_parl_schema(conn, PARL_SCHEMA)
                seed_parl_sources(conn)
                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, vote_date, title,
                      source_id, source_url, raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "test:vote:privacy:1",
                        "15",
                        "2026-02-24",
                        "Votación privacidad",
                        "congreso_votaciones",
                        "file:///Users/alice/Library/CloudStorage/GoogleDrive-alice@example.com/repo/vote.json",
                        "{}",
                        now_iso,
                        now_iso,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            payload = g.build_vote_summary_payload(
                db_path,
                source_filter="congreso_votaciones",
                party_filter=None,
                q=None,
                limit=20,
                offset=0,
            )

        events = payload.get("events") or []
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].get("source_url"), "")
        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("/Users/alice", serialized)
        self.assertNotIn("alice@example.com", serialized)


if __name__ == "__main__":
    unittest.main()
