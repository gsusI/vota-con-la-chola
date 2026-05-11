from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from etl.politicos_es.util import now_utc_iso
from scripts.export_accountability_dossier_snapshot import build_accountability_dossier_snapshot


class TestExportAccountabilityDossierSnapshot(unittest.TestCase):
    def test_builds_compact_actor_and_issue_dossiers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "dossiers.db"
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
                    INSERT INTO persons (
                      person_id, full_name, territory_code, canonical_key, created_at, updated_at
                    ) VALUES (1, 'Ana Lopez', '', 'ana lopez', ?, ?)
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
                      issue_id, canonical_key, label, summary, issue_status, source_kind,
                      created_at, updated_at
                    ) VALUES ('issue-1', 'issue-1', 'Issue 1', ?,
                      'active', 'manual_seed', ?, ?)
                    """,
                    ("Summary " + "/" + "Users/alice", now_iso, now_iso),
                )
                rows = [
                    ("entry-1", "Ana Lopez", "person", 1, None, "voted_for"),
                    ("entry-2", "Grupo Parlamentario Socialista", "group", None, 1, "voted_for"),
                ]
                for entry_id, actor_label, actor_kind, person_id, group_id, role in rows:
                    conn.execute(
                        """
                        INSERT INTO accountability_ledger_entries (
                          entry_id, issue_id, entry_kind, accountability_role, actor_label,
                          actor_kind, person_id, parliamentary_group_id, institution_id,
                          event_date, raw_payload_json, created_at, updated_at
                        ) VALUES (?, 'issue-1', 'parliamentary_action', ?, ?, ?, ?, ?, 1,
                          '2024-01-01', '{}', ?, ?)
                        """,
                        (entry_id, role, actor_label, actor_kind, person_id, group_id, now_iso, now_iso),
                    )
                conn.commit()

                payload = build_accountability_dossier_snapshot(conn, snapshot_date="2026-05-10")

            self.assertEqual(payload["meta"]["schema_version"], "accountability_dossier_snapshot_v1")
            self.assertEqual(payload["coverage"]["entries_total"], 2)
            self.assertEqual(payload["coverage"]["actors_total"], 2)
            self.assertEqual(payload["coverage"]["issues_total"], 1)
            self.assertEqual(payload["coverage"]["issue_actor_edges_total"], 2)
            self.assertEqual(payload["coverage"]["entries_with_person_id"], 1)
            self.assertEqual(payload["coverage"]["entries_with_parliamentary_group_id"], 1)
            self.assertEqual(payload["coverage"]["entries_by_actor_kind"], {"group": 1, "person": 1})
            self.assertNotIn("/" + "Users" + "/alice", json.dumps(payload, ensure_ascii=True))
            issue = payload["issues"][0]
            self.assertEqual(issue["actors_total"], 2)
            self.assertEqual(issue["roles"], {"voted_for": 2})
            self.assertEqual(payload["actors"][0]["top_issues"][0]["issue_id"], "issue-1")

    def test_build_bounds_nested_actor_issue_lists_without_hiding_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "dossiers.db"
            with closing(open_db(db_path)) as conn:
                apply_schema(conn, DEFAULT_SCHEMA)
                now_iso = now_utc_iso()
                for issue_idx in range(3):
                    conn.execute(
                        """
                        INSERT INTO accountability_issues (
                          issue_id, canonical_key, label, issue_status, source_kind, created_at, updated_at
                        ) VALUES (?, ?, ?, 'active', 'manual_seed', ?, ?)
                        """,
                        (
                            f"issue-{issue_idx}",
                            f"issue-{issue_idx}",
                            f"Issue {issue_idx}",
                            now_iso,
                            now_iso,
                        ),
                    )
                rows = [
                    ("entry-a0", "issue-0", "Actor A"),
                    ("entry-a1", "issue-1", "Actor A"),
                    ("entry-a2", "issue-2", "Actor A"),
                    ("entry-b0", "issue-0", "Actor B"),
                    ("entry-c0", "issue-0", "Actor C"),
                ]
                for entry_id, issue_id, actor_label in rows:
                    conn.execute(
                        """
                        INSERT INTO accountability_ledger_entries (
                          entry_id, issue_id, entry_kind, accountability_role, actor_label,
                          actor_kind, event_date, raw_payload_json, created_at, updated_at
                        ) VALUES (?, ?, 'rule', 'approved', ?, 'person',
                          '2024-01-01', '{}', ?, ?)
                        """,
                        (entry_id, issue_id, actor_label, now_iso, now_iso),
                    )
                conn.commit()

                payload = build_accountability_dossier_snapshot(
                    conn,
                    snapshot_date="2026-05-10",
                    max_issues_per_actor=2,
                    max_actors_per_issue=2,
                )

            self.assertEqual(payload["coverage"]["entries_total"], 5)
            self.assertEqual(payload["coverage"]["actors_total"], 3)
            self.assertEqual(payload["coverage"]["issues_total"], 3)
            self.assertEqual(payload["coverage"]["issue_actor_edges_total"], 5)
            actor_a = next(actor for actor in payload["actors"] if actor["actor_label"] == "Actor A")
            issue_0 = next(issue for issue in payload["issues"] if issue["issue_id"] == "issue-0")
            self.assertEqual(actor_a["issues_total"], 3)
            self.assertEqual(len(actor_a["top_issues"]), 2)
            self.assertEqual(issue_0["actors_total"], 3)
            self.assertEqual(len(issue_0["top_actors"]), 2)

    def test_cli_writes_dated_and_latest_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_path = root / "empty.db"
            out_path = root / "published" / "accountability-dossiers-2026-05-10.json"
            latest_path = root / "published" / "accountability-dossiers-latest.json"
            with closing(open_db(db_path)) as conn:
                apply_schema(conn, DEFAULT_SCHEMA)
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/export_accountability_dossier_snapshot.py",
                    "--db",
                    str(db_path),
                    "--snapshot-date",
                    "2026-05-10",
                    "--out",
                    str(out_path),
                    "--latest-out",
                    str(latest_path),
                ],
                cwd=Path(__file__).resolve().parent.parent,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("OK accountability dossier snapshot", result.stdout)
            self.assertEqual(json.loads(out_path.read_text(encoding="utf-8")), json.loads(latest_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
