from __future__ import annotations

from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from etl.politicos_es.util import canonical_key, now_utc_iso
from scripts.backfill_accountability_ledger_actor_ids import backfill_accountability_ledger_actor_ids


class TestBackfillAccountabilityLedgerActorIds(unittest.TestCase):
    def test_resolves_exact_actor_labels_without_fuzzy_matches(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "actor-resolution.db"
            with closing(open_db(db_path)) as conn:
                apply_schema(conn, DEFAULT_SCHEMA)
                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO sources (
                      source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
                    ) VALUES ('dir3_unidades_age', 'DIR3 AGE', 'nacional', 'https://example.test', 'xlsx', 1, ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO persons (
                      person_id, full_name, territory_code, canonical_key, created_at, updated_at
                    ) VALUES (1, 'Ana Lopez', '', ?, ?, ?)
                    """,
                    (canonical_key("Ana Lopez", None, ""), now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO parties (party_id, name, acronym, created_at, updated_at)
                    VALUES (2, 'Partido Animalista Con el Medio Ambiente', 'PACMA', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO party_aliases (party_id, alias, canonical_alias, created_at, updated_at)
                    VALUES (2, 'Partido Animalista', 'partido animalista', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO institutions (institution_id, name, level, territory_code, created_at, updated_at)
                    VALUES (3, 'Agencia Estatal de Administracion Tributaria', 'nacional', 'ES', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO government_org_units (
                      org_unit_id, source_id, source_record_id, org_unit_code, name,
                      normalized_name, raw_payload, created_at, updated_at
                    ) VALUES (4, 'dir3_unidades_age', 'unit-1', 'EA0001',
                      'Direccion General de Tributos', 'Direccion General de Tributos',
                      '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO government_positions (
                      position_id, org_unit_id, title, position_kind, raw_payload, created_at, updated_at
                    ) VALUES (5, 4, 'Secretaria de Estado de Hacienda', 'political_appointee', '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO institutions (institution_id, name, level, territory_code, created_at, updated_at)
                    VALUES
                      (6, 'Consejo Consultivo', 'autonomico', 'A', ?, ?),
                      (7, 'Consejo Consultivo', 'autonomico', 'B', ?, ?)
                    """,
                    (now_iso, now_iso, now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO accountability_issues (
                      issue_id, canonical_key, label, issue_status, source_kind, created_at, updated_at
                    ) VALUES ('issue-1', 'issue-1', 'Issue 1', 'active', 'manual_seed', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                for entry_id, actor_label in (
                    ("entry-person", "Ana Lopez"),
                    ("entry-party", "PACMA"),
                    ("entry-institution", "Agencia Estatal de Administracion Tributaria"),
                    ("entry-org", "Direccion General de Tributos"),
                    ("entry-position", "Secretaria de Estado de Hacienda"),
                    ("entry-ambiguous", "Consejo Consultivo"),
                    ("entry-unknown", "Actor Inexistente"),
                ):
                    conn.execute(
                        """
                        INSERT INTO accountability_ledger_entries (
                          entry_id, issue_id, entry_kind, actor_label, actor_kind,
                          raw_payload_json, created_at, updated_at
                        ) VALUES (?, 'issue-1', 'other', ?, 'unknown', '{}', ?, ?)
                        """,
                        (entry_id, actor_label, now_iso, now_iso),
                    )
                conn.commit()

                first = backfill_accountability_ledger_actor_ids(conn)
                second = backfill_accountability_ledger_actor_ids(conn)
                rows = conn.execute(
                    """
                    SELECT entry_id, actor_kind, person_id, party_id, institution_id, org_unit_id, position_id
                    FROM accountability_ledger_entries
                    ORDER BY entry_id
                    """
                ).fetchall()
                fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()

            self.assertEqual(first["rows_seen"], 7)
            self.assertEqual(first["rows_resolved"], 5)
            self.assertEqual(first["rows_unresolved"], 2)
            self.assertEqual(second["rows_seen"], 2)
            self.assertEqual(second["rows_resolved"], 0)
            by_entry = {row["entry_id"]: row for row in rows}
            self.assertEqual(int(by_entry["entry-person"]["person_id"]), 1)
            self.assertEqual(by_entry["entry-person"]["actor_kind"], "person")
            self.assertEqual(int(by_entry["entry-party"]["party_id"]), 2)
            self.assertEqual(int(by_entry["entry-institution"]["institution_id"]), 3)
            self.assertEqual(int(by_entry["entry-org"]["org_unit_id"]), 4)
            self.assertEqual(int(by_entry["entry-position"]["position_id"]), 5)
            self.assertIsNone(by_entry["entry-ambiguous"]["institution_id"])
            self.assertEqual(by_entry["entry-ambiguous"]["actor_kind"], "unknown")
            self.assertEqual(fk_rows, [])


if __name__ == "__main__":
    unittest.main()
