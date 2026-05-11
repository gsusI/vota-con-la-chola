from __future__ import annotations

from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db, seed_sources
from etl.politicos_es.util import now_utc_iso
from scripts.backfill_accountability_ledger_from_policy_events import backfill_policy_event_accountability_ledger
from scripts.export_accountability_ledger_snapshot import build_accountability_ledger_snapshot


class TestBackfillAccountabilityLedgerFromPolicyEvents(unittest.TestCase):
    def test_backfill_policy_events_to_generic_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "policy-event-accountability.db"
            with closing(open_db(db_path)) as conn:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO institutions (institution_id, name, level, territory_code, created_at, updated_at)
                    VALUES (77, 'Ministerio de Hacienda', 'nacional', 'ES', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO policy_instruments (policy_instrument_id, code, label, description, created_at, updated_at)
                    VALUES
                      (1, 'boe_legal_document', 'Documento legal BOE', 'Norma publicada', ?, ?),
                      (2, 'public_contracting', 'Contratacion publica', 'Contrato publico', ?, ?)
                    """,
                    (now_iso, now_iso, now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO policy_events (
                      policy_event_id, event_date, published_date, domain_id, policy_instrument_id,
                      title, summary, institution_id, scope, source_id, source_url, raw_payload,
                      created_at, updated_at
                    ) VALUES
                      ('boe:1', NULL, '2024-01-01', NULL, 1, 'Ley publicada', 'Publicacion oficial',
                       77, 'legal', 'boe_api_legal', 'https://www.boe.es/test', '{}', ?, ?),
                      ('money:1', '2024-02-01', '2024-02-02', NULL, 2, 'Contrato publicado', 'Adjudicacion',
                       NULL, 'money', 'placsp_contratacion', 'https://contrataciondelestado.es/test', '{}', ?, ?)
                    """
                    ,
                    (now_iso, now_iso, now_iso, now_iso),
                )
                conn.commit()

                first = backfill_policy_event_accountability_ledger(conn)
                second = backfill_policy_event_accountability_ledger(conn)
                self.assertEqual(first["source_rows_seen"], 2)
                self.assertEqual(first["entries_upserted"], 2)
                self.assertEqual(second["entries_upserted"], 2)

                rows = conn.execute(
                    """
                    SELECT issue_id, actor_label, actor_kind, entry_kind, accountability_role, evidence_tier
                    FROM accountability_ledger_entries
                    ORDER BY entry_id
                    """
                ).fetchall()
                self.assertEqual(len(rows), 2)
                by_issue = {row["issue_id"]: row for row in rows}
                self.assertEqual(by_issue["policy-event:boe:1"]["accountability_role"], "published")
                self.assertEqual(by_issue["policy-event:boe:1"]["entry_kind"], "rule")
                self.assertEqual(by_issue["policy-event:boe:1"]["actor_label"], "Ministerio de Hacienda")
                self.assertEqual(by_issue["policy-event:boe:1"]["actor_kind"], "institution")
                self.assertEqual(int(by_issue["policy-event:boe:1"]["evidence_tier"]), 1)
                self.assertEqual(by_issue["policy-event:money:1"]["accountability_role"], "contracted")
                self.assertEqual(by_issue["policy-event:money:1"]["entry_kind"], "money")
                self.assertEqual(int(by_issue["policy-event:money:1"]["evidence_tier"]), 1)

                snapshot = build_accountability_ledger_snapshot(
                    conn,
                    snapshot_date="2026-05-10",
                    issue_id="policy-event:boe:1",
                )
                fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()

            self.assertEqual(snapshot["coverage"]["issues_total"], 1)
            self.assertEqual(snapshot["coverage"]["entries_total"], 1)
            self.assertEqual(snapshot["coverage"]["entries_by_role"]["published"], 1)
            self.assertEqual(snapshot["issues"][0]["label"], "Ley publicada")
            self.assertEqual(fk_rows, [])


if __name__ == "__main__":
    unittest.main()
