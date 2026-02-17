from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources, upsert_source_record
from etl.politicos_es.pipeline import ingest_one_source
from etl.politicos_es.policy_events import backfill_money_policy_events
from etl.politicos_es.registry import get_connectors
from etl.politicos_es.util import now_utc_iso, sha256_bytes, stable_json


class TestPolicyMoneyMapping(unittest.TestCase):
    def test_backfill_money_policy_events_is_idempotent_and_traceable(self) -> None:
        snapshot_date = "2026-02-16"
        sample_placsp = Path("etl/data/raw/samples/placsp_sindicacion_sample.xml")
        sample_bdns = Path("etl/data/raw/samples/bdns_api_subvenciones_sample.json")
        self.assertTrue(sample_placsp.exists(), f"Missing sample: {sample_placsp}")
        self.assertTrue(sample_bdns.exists(), f"Missing sample: {sample_bdns}")

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "money-policy-events.db"
            raw_dir = Path(td) / "raw"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                connectors = get_connectors()
                for source_id, sample in (
                    ("placsp_sindicacion", sample_placsp),
                    ("bdns_api_subvenciones", sample_bdns),
                ):
                    ingest_one_source(
                        conn=conn,
                        connector=connectors[source_id],
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=sample,
                        url_override=None,
                        snapshot_date=snapshot_date,
                        strict_network=True,
                    )

                result_1 = backfill_money_policy_events(conn)
                self.assertGreater(result_1["policy_events_total"], 0)
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

    def test_ambiguous_mapping_keeps_amount_null(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "money-policy-events-ambiguous.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)
                now_iso = now_utc_iso()

                payload = {
                    "record_kind": "bdns_subsidy_record",
                    "source_url": "https://www.pap.hacienda.gob.es/bdnstrans/GE/es/convocatorias/ambigua-1",
                    "convocatoria_id": "BDNS-AMB-001",
                    "concesion_id": None,
                    "beneficiario": "Entidad no identificada",
                    "beneficiario_id": None,
                    "importe_eur": None,
                    "published_at_iso": "2026-02-16T10:00:00+00:00",
                    "organo_convocante": "Organo de prueba",
                }
                raw_payload = stable_json(payload)
                srpk = upsert_source_record(
                    conn=conn,
                    source_id="bdns_api_subvenciones",
                    source_record_id="conv:bdns_amb_001",
                    snapshot_date="2026-02-16",
                    raw_payload=raw_payload,
                    content_sha256=sha256_bytes(raw_payload.encode("utf-8")),
                    now_iso=now_iso,
                )
                self.assertGreater(srpk, 0)
                conn.commit()

                result = backfill_money_policy_events(conn, source_ids=("bdns_api_subvenciones",))
                self.assertGreater(result["policy_events_total"], 0)

                row = conn.execute(
                    """
                    SELECT amount_eur, currency, event_date, published_date
                    FROM policy_events
                    WHERE source_id='bdns_subvenciones'
                      AND source_record_pk=?
                    """,
                    (srpk,),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertIsNone(row["amount_eur"])
                self.assertIsNone(row["currency"])
                self.assertIsNone(row["event_date"])
                self.assertEqual(row["published_date"], "2026-02-16")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()

