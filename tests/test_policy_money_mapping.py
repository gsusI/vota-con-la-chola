from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.pipeline import ingest_one_source
from etl.politicos_es.policy_events import backfill_money_policy_events
from etl.politicos_es.registry import get_connectors
from scripts.backfill_accountability_ledger_from_policy_events import backfill_policy_event_accountability_ledger


PLACSP_OFFICIAL_ARCHIVE = Path(
    "etl/data/object-origin/placsp-contracts/bd/a7/"
    "bda70aa0a7437d031e5d3f6114e5a637920ea1a460e1aba67d200209ae5eab7f.zip"
)
PLACSP_OFFICIAL_MEMBER = "licitacionesPerfilesContratanteCompleto3.atom"
PLACSP_OFFICIAL_URL = (
    "https://contrataciondelsectorpublico.gob.es/sindicacion/sindicacion_643/"
    "licitacionesPerfilesContratanteCompleto3_2025.zip"
)
BDNS_OFFICIAL_CAPTURE = Path(
    "etl/data/raw/official-captures/bdns/concesiones-page-0-20260812.json"
)
BDNS_OFFICIAL_URL = (
    "https://www.infosubvenciones.es/bdnstrans/api/concesiones/busqueda"
    "?page=0&size=10&sort=fechaAlta,desc"
)


def _write_official_placsp_capture(directory: Path) -> Path:
    capture_path = directory / PLACSP_OFFICIAL_MEMBER
    with zipfile.ZipFile(PLACSP_OFFICIAL_ARCHIVE) as archive:
        capture_path.write_bytes(archive.read(PLACSP_OFFICIAL_MEMBER))
    return capture_path


class TestPolicyMoneyMapping(unittest.TestCase):
    def test_backfill_money_policy_events_is_idempotent_and_traceable(self) -> None:
        snapshot_date = "2026-08-12"
        self.assertTrue(PLACSP_OFFICIAL_ARCHIVE.exists())
        self.assertTrue(BDNS_OFFICIAL_CAPTURE.exists())

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "money-policy-events.db"
            raw_dir = td_path / "raw"
            placsp_capture = _write_official_placsp_capture(td_path)
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                connectors = get_connectors()
                for source_id, capture_path, source_url in (
                    ("placsp_sindicacion", placsp_capture, PLACSP_OFFICIAL_URL),
                    ("bdns_api_subvenciones", BDNS_OFFICIAL_CAPTURE, BDNS_OFFICIAL_URL),
                ):
                    ingest_one_source(
                        conn=conn,
                        connector=connectors[source_id],
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=capture_path,
                        url_override=source_url,
                        snapshot_date=snapshot_date,
                        strict_network=True,
                    )

                result_1 = backfill_money_policy_events(conn)
                self.assertGreater(result_1["policy_events_total"], 0)
                self.assertEqual(result_1["policy_events_total"], result_1["policy_events_with_domain_id"])
                self.assertEqual(result_1["policy_events_unresolved_domain"], 0)
                self.assertGreaterEqual(result_1["policy_domains_seeded"], 1)
                self.assertEqual(
                    result_1["policy_events_total"],
                    result_1["policy_events_with_source_url"],
                )
                self.assertEqual(
                    result_1["policy_events_total"],
                    result_1["policy_events_with_source_record_pk"],
                )
                self.assertGreater(result_1["policy_events_by_source"].get("placsp_contratacion", 0), 0)
                self.assertGreater(result_1["policy_events_by_source"].get("bdns_subvenciones", 0), 0)

                instruments = {
                    row["code"]: row["label"]
                    for row in conn.execute(
                        """
                        SELECT code, label
                        FROM policy_instruments
                        WHERE code IN ('public_contracting', 'public_subsidy')
                        ORDER BY code
                        """
                    ).fetchall()
                }
                self.assertIn("public_contracting", instruments)
                self.assertIn("public_subsidy", instruments)

                domain_rows = conn.execute(
                    """
                    SELECT canonical_key, label, tier
                    FROM domains
                    WHERE canonical_key = 'impuestos_gasto_fiscalidad'
                    """
                ).fetchall()
                self.assertEqual(len(domain_rows), 1)
                self.assertEqual(str(domain_rows[0]["canonical_key"]), "impuestos_gasto_fiscalidad")

                ledger_result = backfill_policy_event_accountability_ledger(
                    conn,
                    source_ids=("placsp_contratacion", "bdns_subvenciones"),
                )
                self.assertEqual(ledger_result["entries_upserted"], result_1["policy_events_total"])
                ledger_rows = conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM accountability_ledger_entries
                    WHERE source_id IN ('placsp_contratacion','bdns_subvenciones')
                      AND institution_id IS NOT NULL
                      AND actor_kind = 'institution'
                    """
                ).fetchone()
                self.assertEqual(int(ledger_rows["c"]), result_1["policy_events_total"])

                traceability_row = conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM policy_events
                    WHERE source_id IN ('placsp_contratacion','bdns_subvenciones')
                      AND source_url IS NOT NULL
                      AND trim(source_url) <> ''
                      AND source_record_pk IS NOT NULL
                      AND raw_payload IS NOT NULL
                      AND trim(raw_payload) <> ''
                      AND source_snapshot_date IS NOT NULL
                      AND trim(source_snapshot_date) <> ''
                    """
                ).fetchone()
                total_row = conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM policy_events
                    WHERE source_id IN ('placsp_contratacion','bdns_subvenciones')
                    """
                ).fetchone()
                self.assertEqual(int(traceability_row["c"]), int(total_row["c"]))

                result_2 = backfill_money_policy_events(conn)
                self.assertEqual(result_1["policy_events_total"], result_2["policy_events_total"])

                fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
                self.assertEqual(fk_rows, [])
            finally:
                conn.close()

    @unittest.skip(
        "No captured official BDNS concession with both amount and event date absent; synthetic rows forbidden"
    )
    def test_ambiguous_mapping_keeps_amount_null(self) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
