from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources
from scripts.export_vote_database_shards import export_database_shards
from scripts.validate_member_vote_shards import validate_shards


class TestExportVoteDatabaseShards(unittest.TestCase):
    def test_exports_and_validates_without_monolithic_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "votes.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                now = "2026-08-10T00:00:00Z"
                raw = json.dumps({"url": "https://www.senado.es/vote/1"})
                source_record = conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES ('senado_votaciones', 'url:https://www.senado.es/vote/1',
                              '2026-08-10', ?, ?, ?, ?)
                    """,
                    (raw, "a" * 64, now, now),
                )
                conn.execute(
                    """
                    INSERT INTO persons (
                      full_name, territory_code, canonical_key, created_at, updated_at
                    ) VALUES ('Person One', '', 'person one', ?, ?)
                    """,
                    (now, now),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_events (
                      vote_event_id, legislature, vote_date, title,
                      totals_present, totals_yes, totals_no, totals_abstain,
                      totals_no_vote, totals_absent, source_id, source_url,
                      source_record_pk, source_snapshot_date, raw_payload,
                      created_at, updated_at
                    ) VALUES (
                      'vote-1', '15', '2026-08-10', 'Vote one',
                      1, 1, 0, 0, 0, 0, 'senado_votaciones',
                      'https://www.senado.es/vote/1', ?, '2026-08-10', ?, ?, ?
                    )
                    """,
                    (int(source_record.lastrowid), raw, now, now),
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_member_votes (
                      vote_event_id, seat, member_name, member_name_normalized,
                      person_id, vote_choice, source_id, source_url,
                      source_snapshot_date, raw_payload, created_at, updated_at
                    ) VALUES (
                      'vote-1', '1', 'Person One', 'person one', 1, 'SI',
                      'senado_votaciones', 'https://www.senado.es/vote/1',
                      '2026-08-10', '{}', ?, ?
                    )
                    """,
                    (now, now),
                )
                conn.commit()
            finally:
                conn.close()

            manifest_path = root / "manifest.json"
            manifest = export_database_shards(
                db_path,
                snapshot_date="2026-08-10",
                source_ids=("senado_votaciones",),
                shard_root=root / "shards",
                manifest_out=manifest_path,
                snapshot_key="votes-2026-08-10",
                max_index_bytes=100_000,
                max_shard_bytes=100_000,
                max_members_per_shard=10,
            )
            validation = validate_shards(manifest_path, shard_root=root / "shards")
            shard_path = root / "shards" / manifest["entries"][0]["shard"]
            with gzip.open(shard_path, "rt", encoding="utf-8") as handle:
                item = json.load(handle)

        self.assertEqual(manifest["source_kind"], "sqlite_direct")
        self.assertTrue(manifest["bounded_delivery_gate_passed"])
        self.assertEqual(manifest["events_total"], 1)
        self.assertEqual(manifest["member_votes_total"], 1)
        self.assertEqual(item["event"]["totals_absent"], 0)
        self.assertEqual(item["member_votes"][0]["person_id"], 1)
        self.assertEqual(validation["status"], "ok")


if __name__ == "__main__":
    unittest.main()
