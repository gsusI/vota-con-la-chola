from __future__ import annotations

from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db, seed_sources
from etl.politicos_es.util import now_utc_iso
from scripts.backfill_accountability_ledger_actor_ids import backfill_accountability_ledger_actor_ids
from scripts.backfill_accountability_ledger_from_boe_appointments import (
    backfill_boe_appointment_accountability_ledger,
)


class TestBackfillAccountabilityLedgerFromBoeAppointments(unittest.TestCase):
    def test_backfill_boe_appointment_titles_to_generic_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "boe-appointments.db"
            with closing(open_db(db_path)) as conn:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                now_iso = now_utc_iso()
                conn.execute(
                    """
                    INSERT INTO persons (
                      person_id, full_name, territory_code, canonical_key, created_at, updated_at
                    ) VALUES (1, 'Ana Lopez Garcia', '', 'ana lopez garcia', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO policy_instruments (policy_instrument_id, code, label, description, created_at, updated_at)
                    VALUES (1, 'boe_legal_document', 'Documento legal BOE', 'Norma publicada', ?, ?)
                    """,
                    (now_iso, now_iso),
                )
                conn.execute(
                    """
                    INSERT INTO policy_events (
                      policy_event_id, published_date, policy_instrument_id, title, summary,
                      source_id, source_url, raw_payload, created_at, updated_at
                    ) VALUES
                      ('boe:appoint', '2024-01-01', 1,
                       'Real Decreto 1/2024, de 1 de enero, por el que se nombra a doña Ana Lopez Garcia como Directora General.',
                       'Nombramiento', 'boe_api_legal', 'https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-1', '{}', ?, ?),
                      ('boe:dismiss', '2024-01-02', 1,
                       'Real Decreto 2/2024, de 2 de enero, por el que se dispone el cese de don Beto Ruiz como Director General.',
                       'Cese', 'boe_api_legal', 'https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-2', '{}', ?, ?),
                      ('boe:appoint-role-then-name', '2024-01-03', 1,
                       'Real Decreto 3/2024, de 3 de enero, por el que se nombra Director General de Ordenacion Profesional a don Miguel Angel Manez Ortiz.',
                       'Nombramiento', 'boe_api_legal', 'https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-3', '{}', ?, ?),
                      ('boe:dismiss-with-title', '2024-01-04', 1,
                       'Real Decreto 4/2024, de 4 de enero, por el que se dispone el cese del Teniente General del Cuerpo General del Ejercito de Tierra don Alejandro Gonzalo Escamez Fernandez como Segundo Jefe del Estado Mayor del Ejercito de Tierra.',
                       'Cese', 'boe_api_legal', 'https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-4', '{}', ?, ?),
                      ('boe:other', '2024-01-03', 1,
                       'Orden sobre administracion y censo electoral.',
                       'No appointment', 'boe_api_legal', 'https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-5', '{}', ?, ?)
                    """
                    ,
                    (
                        now_iso,
                        now_iso,
                        now_iso,
                        now_iso,
                        now_iso,
                        now_iso,
                        now_iso,
                        now_iso,
                        now_iso,
                        now_iso,
                    ),
                )
                conn.commit()

                first = backfill_boe_appointment_accountability_ledger(conn)
                second = backfill_boe_appointment_accountability_ledger(conn)
                resolve = backfill_accountability_ledger_actor_ids(conn)
                rows = conn.execute(
                    """
                    SELECT entry_id, actor_label, accountability_role, actor_kind, person_id, position_id, evidence_tier
                    FROM accountability_ledger_entries
                    ORDER BY entry_id
                    """
                ).fetchall()
                memberships = conn.execute(
                    """
                    SELECT p.full_name, m.role_label, m.start_date, m.end_date, gp.position_kind
                    FROM person_org_memberships m
                    JOIN persons p ON p.person_id = m.person_id
                    LEFT JOIN government_positions gp ON gp.position_id = m.position_id
                    ORDER BY p.full_name, m.start_date, m.end_date
                    """
                ).fetchall()
                fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()

            self.assertEqual(first["source_rows_seen"], 5)
            self.assertEqual(first["appointment_candidates"], 4)
            self.assertEqual(first["entries_upserted"], 4)
            self.assertEqual(first["signals_with_role_title"], 4)
            self.assertEqual(first["persons_upserted"], 3)
            self.assertEqual(first["person_aliases_upserted"], 4)
            self.assertEqual(first["positions_upserted"], 4)
            self.assertEqual(first["memberships_upserted"], 4)
            self.assertEqual(second["entries_upserted"], 4)
            self.assertEqual(second["persons_upserted"], 0)
            self.assertEqual(second["person_aliases_upserted"], 0)
            self.assertEqual(second["positions_upserted"], 0)
            self.assertEqual(second["memberships_upserted"], 0)
            self.assertEqual(resolve["rows_resolved"], 0)
            by_entry = {row["entry_id"]: row for row in rows}
            appointed = by_entry["boe-appointment:boe:appoint"]
            dismissed = by_entry["boe-appointment:boe:dismiss"]
            appointed_role_then_name = by_entry["boe-appointment:boe:appoint-role-then-name"]
            dismissed_with_title = by_entry["boe-appointment:boe:dismiss-with-title"]
            self.assertEqual(appointed["actor_label"], "Ana Lopez Garcia")
            self.assertEqual(appointed["accountability_role"], "appointed")
            self.assertEqual(appointed["actor_kind"], "person")
            self.assertEqual(int(appointed["person_id"]), 1)
            self.assertIsNotNone(appointed["position_id"])
            self.assertEqual(int(appointed["evidence_tier"]), 1)
            self.assertEqual(dismissed["actor_label"], "Beto Ruiz")
            self.assertEqual(dismissed["accountability_role"], "dismissed")
            self.assertIsNotNone(dismissed["person_id"])
            self.assertIsNotNone(dismissed["position_id"])
            self.assertEqual(appointed_role_then_name["actor_label"], "Miguel Angel Manez Ortiz")
            self.assertEqual(appointed_role_then_name["accountability_role"], "appointed")
            self.assertIsNotNone(appointed_role_then_name["position_id"])
            self.assertEqual(dismissed_with_title["actor_label"], "Alejandro Gonzalo Escamez Fernandez")
            self.assertEqual(dismissed_with_title["accountability_role"], "dismissed")
            self.assertIsNotNone(dismissed_with_title["position_id"])
            self.assertEqual(
                [
                    (row["full_name"], row["role_label"], row["start_date"], row["end_date"], row["position_kind"])
                    for row in memberships
                ],
                [
                    (
                        "Alejandro Gonzalo Escamez Fernandez",
                        "Segundo Jefe del Estado Mayor del Ejercito de Tierra",
                        None,
                        "2024-01-04",
                        "unknown",
                    ),
                    ("Ana Lopez Garcia", "Directora General", "2024-01-01", None, "political_appointee"),
                    ("Beto Ruiz", "Director General", None, "2024-01-02", "political_appointee"),
                    (
                        "Miguel Angel Manez Ortiz",
                        "Director General de Ordenacion Profesional",
                        "2024-01-03",
                        None,
                        "political_appointee",
                    ),
                ],
            )
            self.assertEqual(fk_rows, [])


if __name__ == "__main__":
    unittest.main()
