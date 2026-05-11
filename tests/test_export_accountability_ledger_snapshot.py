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


class TestExportAccountabilityLedgerSnapshot(unittest.TestCase):
    def test_cli_writes_dated_and_latest_public_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_path = root / "ledger.db"
            out_path = root / "published" / "accountability-ledger-2026-05-10.json"
            latest_path = root / "published" / "accountability-ledger-latest.json"
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
                    ) VALUES (1, 'Cortes Generales', 'nacional', '', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO persons (
                      person_id, full_name, territory_code, canonical_key, created_at, updated_at
                    ) VALUES (1, 'Ana López', '', 'ana lopez', ?, ?)
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
                    INSERT INTO mandates (
                      mandate_id, person_id, institution_id, role_title, level, territory_code,
                      source_id, source_record_id, first_seen_at, last_seen_at, raw_payload
                    ) VALUES (1, 1, 1, 'Diputado/a', 'nacional', '', 'test_source',
                      'mandate-1', ?, ?, '{}')
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
                local_source_url = "file:" + "///private/source-record.json"
                conn.execute(
                    """
                    INSERT INTO accountability_ledger_entries (
                      entry_id, issue_id, entry_kind, accountability_role, actor_label,
                      actor_kind, person_id, parliamentary_group_id, mandate_id,
                      institution_id, evidence_tier, source_url, raw_payload_json,
                      created_at, updated_at
                    ) VALUES (
                      'entry-1', 'issue-1', 'rule', 'approved', 'Cortes Generales',
                      'institution', 1, 1, 1, 1, 5, ?, '{}', ?, ?
                    )
                    """,
                    (local_source_url, now_iso, now_iso),
                )
                conn.commit()

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/export_accountability_ledger_snapshot.py",
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

            self.assertIn("OK accountability ledger snapshot", result.stdout)
            dated = json.loads(out_path.read_text(encoding="utf-8"))
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
            self.assertEqual(dated, latest)
            self.assertEqual(dated["meta"]["schema_version"], "accountability_ledger_snapshot_v1")
            self.assertEqual(dated["coverage"]["issues_total"], 1)
            self.assertEqual(dated["coverage"]["entries_total"], 1)
            self.assertEqual(dated["coverage"]["entries_exported"], 1)
            self.assertFalse(dated["coverage"]["entries_truncated"])
            self.assertEqual(dated["coverage"]["actors_total"], 1)
            self.assertEqual(dated["coverage"]["entries_with_resolved_actor_id"], 1)
            self.assertEqual(dated["coverage"]["entries_with_person_id"], 1)
            self.assertEqual(dated["coverage"]["entries_with_parliamentary_group_id"], 1)
            self.assertEqual(dated["coverage"]["entries_with_mandate_id"], 1)
            self.assertEqual(dated["coverage"]["entries_with_institution_id"], 1)
            self.assertEqual(dated["coverage"]["entries_by_role"]["approved"], 1)
            self.assertEqual(dated["actors"][0]["actor_label"], "Cortes Generales")
            self.assertEqual(dated["actors"][0]["roles"]["approved"], 1)
            self.assertEqual(dated["issues"][0]["entries"][0]["actor_label"], "Cortes Generales")
            self.assertNotIn("source_url", dated["issues"][0]["entries"][0])

    def test_cli_can_export_bounded_issue_entries_while_preserving_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_path = root / "ledger.db"
            out_path = root / "published" / "accountability-ledger-2026-05-10.json"
            with closing(open_db(db_path)) as conn:
                apply_schema(conn, DEFAULT_SCHEMA)
                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO accountability_issues (
                      issue_id, canonical_key, label, issue_status, source_kind, created_at, updated_at
                    ) VALUES ('issue-1', 'issue-1', 'Issue 1', 'active', 'manual_seed', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                for idx in range(3):
                    conn.execute(
                        """
                        INSERT INTO accountability_ledger_entries (
                          entry_id, issue_id, entry_kind, accountability_role, actor_label,
                          actor_kind, evidence_tier, source_title, source_locator,
                          evidence_quote, raw_payload_json, created_at, updated_at
                        ) VALUES (?, 'issue-1', 'rule', 'approved', ?, 'person', 1, ?, ?, ?, '{}', ?, ?)
                        """,
                        (
                            f"entry-{idx}",
                            f"Actor {idx}",
                            f"Source {idx}",
                            f"loc-{idx}",
                            f"quote-{idx}",
                            now_iso,
                            now_iso,
                        ),
                    )
                conn.commit()

            subprocess.run(
                [
                    sys.executable,
                    "scripts/export_accountability_ledger_snapshot.py",
                    "--db",
                    str(db_path),
                    "--snapshot-date",
                    "2026-05-10",
                    "--out",
                    str(out_path),
                    "--max-entries-per-issue",
                    "1",
                ],
                cwd=Path(__file__).resolve().parent.parent,
                check=True,
                capture_output=True,
                text=True,
            )

            dated = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(dated["coverage"]["entries_total"], 3)
            self.assertEqual(dated["coverage"]["entries_exported"], 1)
            self.assertTrue(dated["coverage"]["entries_truncated"])
            self.assertEqual(dated["coverage"]["actors_total"], 3)
            self.assertEqual(dated["issues"][0]["entries_total"], 3)
            self.assertEqual(dated["issues"][0]["entries_exported"], 1)
            self.assertTrue(dated["issues"][0]["entries_truncated"])
            self.assertEqual(len(dated["issues"][0]["entries"]), 1)
            self.assertEqual(dated["actors"][2]["sample_entries"][0]["evidence_quote"], "quote-2")

    def test_cli_can_bound_actor_sample_entries_while_preserving_actor_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_path = root / "ledger.db"
            out_path = root / "published" / "accountability-ledger-2026-05-10.json"
            with closing(open_db(db_path)) as conn:
                apply_schema(conn, DEFAULT_SCHEMA)
                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO accountability_issues (
                      issue_id, canonical_key, label, issue_status, source_kind, created_at, updated_at
                    ) VALUES ('issue-1', 'issue-1', 'Issue 1', 'active', 'manual_seed', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                for idx in range(4):
                    conn.execute(
                        """
                        INSERT INTO accountability_ledger_entries (
                          entry_id, issue_id, entry_kind, accountability_role, actor_label,
                          actor_kind, evidence_tier, evidence_quote, raw_payload_json, created_at, updated_at
                        ) VALUES (?, 'issue-1', 'rule', 'approved', 'Same Actor', 'person', 1, ?, '{}', ?, ?)
                        """,
                        (f"entry-{idx}", f"quote-{idx}", now_iso, now_iso),
                    )
                conn.commit()

            subprocess.run(
                [
                    sys.executable,
                    "scripts/export_accountability_ledger_snapshot.py",
                    "--db",
                    str(db_path),
                    "--snapshot-date",
                    "2026-05-10",
                    "--out",
                    str(out_path),
                    "--max-sample-entries-per-actor",
                    "2",
                ],
                cwd=Path(__file__).resolve().parent.parent,
                check=True,
                capture_output=True,
                text=True,
            )

            dated = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(dated["meta"]["max_sample_entries_per_actor"], 2)
            self.assertEqual(dated["coverage"]["entries_total"], 4)
            self.assertEqual(dated["coverage"]["actors_total"], 1)
            self.assertEqual(dated["actors"][0]["entries_total"], 4)
            self.assertEqual(len(dated["actors"][0]["sample_entries"]), 2)


if __name__ == "__main__":
    unittest.main()
