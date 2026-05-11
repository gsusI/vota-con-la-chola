from __future__ import annotations

from contextlib import closing
from pathlib import Path
import tempfile
import unittest

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db
from etl.politicos_es.util import now_utc_iso
from scripts.backfill_accountability_ledger_from_sanction_norm_catalog import (
    backfill_sanction_norm_catalog_accountability_ledger,
)
from scripts.export_accountability_ledger_snapshot import build_accountability_ledger_snapshot


class TestBackfillAccountabilityLedgerFromSanctionNormCatalog(unittest.TestCase):
    def test_backfill_sanction_norm_catalog_to_current_owner_entries(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "sanction-accountability.db"
            with closing(open_db(db_path)) as conn:
                apply_schema(conn, DEFAULT_SCHEMA)
                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO sources (
                      source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
                    ) VALUES ('boe_api_legal', 'BOE API Legal', 'nacional', 'https://www.boe.es/', 'json', 1, ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO legal_norms (
                      norm_id, boe_id, title, scope, published_date, source_id, source_url,
                      raw_payload, created_at, updated_at
                    ) VALUES ('norm-traffic', 'BOE-A-2015-11722', 'Ley trafico', 'nacional', '2015-10-31',
                      'boe_api_legal', 'https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722',
                      '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO legal_norm_fragments (
                      fragment_id, norm_id, fragment_type, fragment_order, fragment_label,
                      fragment_title, source_url, raw_payload, created_at, updated_at
                    ) VALUES ('fragment-traffic', 'norm-traffic', 'articulo', 1, 'bloque sancionador',
                      'Infracciones y sanciones',
                      'https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722',
                      '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO sanction_norm_catalog (
                      norm_id, scope, organismo_competente, source_id, source_url,
                      raw_payload, created_at, updated_at
                    ) VALUES ('norm-traffic', 'nacional', 'DGT y jefaturas provinciales de trafico',
                      'boe_api_legal', 'https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722',
                      '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO sanction_norm_fragment_links (
                      norm_id, fragment_id, link_reason, created_at, updated_at
                    ) VALUES ('norm-traffic', 'fragment-traffic', 'seed', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO legal_fragment_responsibilities (
                      fragment_id, role, actor_label, evidence_date, raw_payload, created_at, updated_at
                    ) VALUES ('fragment-traffic', 'enforce', 'DGT', '2015-10-31', '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.commit()

                first = backfill_sanction_norm_catalog_accountability_ledger(conn)
                second = backfill_sanction_norm_catalog_accountability_ledger(conn)
                rows = conn.execute(
                    """
                    SELECT
                      actor_label,
                      actor_kind,
                      institution_id,
                      entry_kind,
                      accountability_role,
                      role_in_chain,
                      event_date,
                      published_date,
                      evidence_tier,
                      source_locator
                    FROM accountability_ledger_entries
                    WHERE issue_id = 'legal-norm:norm-traffic'
                    ORDER BY entry_id
                    """
                ).fetchall()
                snapshot = build_accountability_ledger_snapshot(
                    conn,
                    snapshot_date="2026-05-10",
                    issue_id="legal-norm:norm-traffic",
                )
                fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()

            self.assertEqual(first["source_rows_seen"], 1)
            self.assertEqual(first["issues_upserted"], 1)
            self.assertEqual(first["entries_upserted"], 1)
            self.assertEqual(first["institution_stubs_upserted"], 1)
            self.assertEqual(second["entries_upserted"], 1)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["actor_label"], "DGT y jefaturas provinciales de trafico")
            self.assertEqual(row["actor_kind"], "institution")
            self.assertIsNotNone(row["institution_id"])
            self.assertEqual(row["entry_kind"], "enforcement")
            self.assertEqual(row["accountability_role"], "current_owner")
            self.assertEqual(row["role_in_chain"], "competent_body")
            self.assertEqual(row["event_date"], "2015-10-31")
            self.assertEqual(row["published_date"], "2015-10-31")
            self.assertEqual(int(row["evidence_tier"]), 1)
            self.assertEqual(row["source_locator"], "bloque sancionador")
            self.assertEqual(snapshot["coverage"]["entries_total"], 1)
            self.assertEqual(snapshot["coverage"]["entries_by_role"]["current_owner"], 1)
            self.assertEqual(snapshot["coverage"]["entries_with_institution_id"], 1)
            self.assertEqual(fk_rows, [])


if __name__ == "__main__":
    unittest.main()
