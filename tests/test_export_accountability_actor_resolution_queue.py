from __future__ import annotations

import csv
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from etl.politicos_es.util import now_utc_iso
from scripts.export_accountability_actor_resolution_queue import build_actor_resolution_queue, write_csv


class TestExportAccountabilityActorResolutionQueue(unittest.TestCase):
    def test_groups_unresolved_actor_labels_and_sanitizes_urls(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_path = root / "actor-queue.db"
            csv_path = root / "queue.csv"
            with closing(open_db(db_path)) as conn:
                apply_schema(conn, DEFAULT_SCHEMA)
                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO sources (
                      source_id, name, scope, default_url, data_format, is_active,
                      created_at, updated_at
                    ) VALUES ('test_source', 'Test Source', 'nacional', 'https://example.test/', 'json', 1, ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO institutions (
                      institution_id, name, level, territory_code, created_at, updated_at
                    ) VALUES (1, 'Congreso de los Diputados', 'nacional', '', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO parliamentary_groups (
                      parliamentary_group_id, source_id, institution_id, legislature, group_code,
                      name, normalized_name, raw_payload, created_at, updated_at
                    ) VALUES (1, 'test_source', 1, '15', 'GS',
                      'Grupo Parlamentario Socialista', 'grupo parlamentario socialista', '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO accountability_issues (
                      issue_id, canonical_key, label, issue_status, source_kind, created_at, updated_at
                    ) VALUES ('issue-1', 'issue-1', 'Issue 1', 'active', 'manual_seed', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO parties (party_id, name, acronym, created_at, updated_at)
                    VALUES (9, 'Partido A', 'PA', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                rows = [
                    ("entry-1", "Ana Lopez", "voted_for", None, None, "file:///Users/alice/private.json"),
                    ("entry-2", "Ana Lopez", "voted_against", None, None, "https://example.test/vote?token=abc&ok=1"),
                    ("entry-3", "Partido A", "approved", 9, None, "https://example.test/party"),
                    ("entry-4", "Grupo Parlamentario Socialista", "voted_for", None, 1, "https://example.test/group"),
                ]
                for entry_id, actor_label, role, party_id, parliamentary_group_id, source_url in rows:
                    conn.execute(
                        """
                        INSERT INTO accountability_ledger_entries (
                          entry_id, issue_id, entry_kind, accountability_role, actor_label,
                          actor_kind, party_id, parliamentary_group_id, event_date, source_url,
                          raw_payload_json, created_at, updated_at
                        ) VALUES (?, 'issue-1', 'parliamentary_action', ?, ?, 'unknown',
                          ?, ?, '2024-01-01', ?, '{}', ?, ?)
                        """,
                        (entry_id, role, actor_label, party_id, parliamentary_group_id, source_url, now_iso, now_iso),
                    )
                conn.commit()

                payload = build_actor_resolution_queue(conn, snapshot_date="2026-05-10")

            self.assertEqual(payload["coverage"]["entries_total"], 4)
            self.assertEqual(payload["coverage"]["unresolved_entries_total"], 2)
            self.assertEqual(payload["coverage"]["resolved_entries_total"], 2)
            self.assertEqual(payload["coverage"]["unresolved_actor_labels_total"], 1)
            queue_row = payload["queue"][0]
            self.assertEqual(queue_row["actor_label"], "Ana Lopez")
            self.assertEqual(queue_row["unresolved_entries"], 2)
            self.assertEqual(queue_row["roles"]["voted_against"], 1)
            self.assertEqual(queue_row["roles"]["voted_for"], 1)
            self.assertNotIn("file:", json.dumps(queue_row, ensure_ascii=True))
            self.assertEqual(queue_row["sample_source_urls"], ["https://example.test/vote?token=REDACTED&ok=1"])

            write_csv(csv_path, payload["queue"])
            with csv_path.open("r", encoding="utf-8", newline="") as fh:
                csv_rows = list(csv.DictReader(fh))
            self.assertEqual(len(csv_rows), 1)
            self.assertEqual(csv_rows[0]["actor_label"], "Ana Lopez")
            self.assertIn("voted_for", csv_rows[0]["roles"])


if __name__ == "__main__":
    unittest.main()
