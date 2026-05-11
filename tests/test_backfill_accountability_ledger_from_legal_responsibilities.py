from __future__ import annotations

from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import now_utc_iso
from scripts.backfill_accountability_ledger_from_legal_responsibilities import (
    backfill_legal_responsibility_accountability_ledger,
)
from scripts.export_accountability_ledger_snapshot import build_accountability_ledger_snapshot


class TestBackfillAccountabilityLedgerFromLegalResponsibilities(unittest.TestCase):
    def test_backfill_legal_responsibilities_to_generic_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "legal-accountability.db"
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
                    INSERT INTO institutions (institution_id, name, level, territory_code, created_at, updated_at)
                    VALUES (20, 'Agencia Estatal de Administracion Tributaria', 'nacional', 'ES', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO legal_norms (
                      norm_id, boe_id, title, scope, published_date, source_id, source_url,
                      raw_payload, created_at, updated_at
                    ) VALUES ('norm-cash', 'BOE-A-2012-13416', 'Ley 7/2012', 'nacional', '2012-10-30',
                      'boe_api_legal', 'https://www.boe.es/buscar/act.php?id=BOE-A-2012-13416',
                      '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO legal_norm_fragments (
                      fragment_id, norm_id, fragment_type, fragment_order, fragment_label,
                      fragment_title, source_url, raw_payload, created_at, updated_at
                    ) VALUES ('fragment-cash', 'norm-cash', 'articulo', 1, 'art. 7',
                      'Limitacion de pagos en efectivo',
                      'https://www.boe.es/buscar/act.php?id=BOE-A-2012-13416',
                      '{}', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO legal_fragment_responsibilities (
                      responsibility_id, fragment_id, role, person_id, institution_id,
                      actor_label, evidence_date, source_id, source_url, evidence_quote,
                      raw_payload, created_at, updated_at
                    ) VALUES
                      (1, 'fragment-cash', 'approve', NULL, NULL, 'Cortes Generales', '2012-10-30',
                       'boe_api_legal', 'https://www.boe.es/buscar/act.php?id=BOE-A-2012-13416',
                       'Ley aprobada por las Cortes Generales.', '{}', ?, ?),
                      (2, 'fragment-cash', 'enforce', NULL, 20, 'AEAT', '2012-10-30',
                       'boe_api_legal', 'https://www.boe.es/buscar/act.php?id=BOE-A-2012-13416',
                       'Competencia sancionadora atribuida a la Agencia Tributaria.', '{}', ?, ?)
                    """,
                    (now_iso, now_iso, now_iso, now_iso),
                )
                conn.commit()

                first = backfill_legal_responsibility_accountability_ledger(conn)
                second = backfill_legal_responsibility_accountability_ledger(conn)
                self.assertEqual(first["source_rows_seen"], 2)
                self.assertEqual(first["issues_upserted"], 1)
                self.assertEqual(first["entries_upserted"], 2)
                self.assertEqual(first["institution_stubs_upserted"], 1)
                self.assertEqual(second["entries_upserted"], 2)

                rows = conn.execute(
                    """
                    SELECT actor_label, actor_kind, entry_kind, accountability_role, institution_id, evidence_tier
                    FROM accountability_ledger_entries
                    WHERE issue_id = 'legal-norm:norm-cash'
                    ORDER BY actor_label
                    """
                ).fetchall()
                self.assertEqual(len(rows), 2)
                by_actor = {row["actor_label"]: row for row in rows}
                self.assertEqual(by_actor["AEAT"]["entry_kind"], "enforcement")
                self.assertEqual(by_actor["AEAT"]["accountability_role"], "enforced")
                self.assertEqual(by_actor["AEAT"]["actor_kind"], "institution")
                self.assertEqual(int(by_actor["AEAT"]["institution_id"]), 20)
                self.assertEqual(by_actor["Cortes Generales"]["entry_kind"], "rule")
                self.assertEqual(by_actor["Cortes Generales"]["accountability_role"], "approved")
                self.assertEqual(by_actor["Cortes Generales"]["actor_kind"], "institution")
                self.assertIsNotNone(by_actor["Cortes Generales"]["institution_id"])
                self.assertEqual(int(by_actor["Cortes Generales"]["evidence_tier"]), 1)
                responsibility_row = conn.execute(
                    """
                    SELECT institution_id
                    FROM legal_fragment_responsibilities
                    WHERE responsibility_id = 1
                    """
                ).fetchone()
                self.assertIsNotNone(responsibility_row["institution_id"])

                snapshot = build_accountability_ledger_snapshot(
                    conn,
                    snapshot_date="2026-05-10",
                    issue_id="legal-norm:norm-cash",
                )
                fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()

            self.assertEqual(snapshot["coverage"]["issues_total"], 1)
            self.assertEqual(snapshot["coverage"]["entries_total"], 2)
            self.assertEqual(snapshot["coverage"]["entries_by_role"]["approved"], 1)
            self.assertEqual(snapshot["coverage"]["entries_by_role"]["enforced"], 1)
            self.assertEqual(snapshot["issues"][0]["label"], "Ley 7/2012")
            self.assertEqual(fk_rows, [])


if __name__ == "__main__":
    unittest.main()
