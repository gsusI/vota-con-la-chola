from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources, upsert_source_record
from etl.politicos_es.pipeline import ingest_one_source
from etl.politicos_es.policy_events import backfill_boe_policy_events
from etl.politicos_es.registry import get_connectors
from etl.politicos_es.util import now_utc_iso, sha256_bytes, stable_json


class TestBoePolicyEventsMapping(unittest.TestCase):
    def test_backfill_boe_policy_events_is_idempotent_and_traceable(self) -> None:
        snapshot_date = "2026-02-16"
        sample_xml = Path("etl/data/raw/samples/boe_api_legal_sample.xml")
        self.assertTrue(sample_xml.exists(), f"Missing sample: {sample_xml}")

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "boe-policy-events.db"
            raw_dir = Path(td) / "raw"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                connectors = get_connectors()
                ingest_one_source(
                    conn=conn,
                    connector=connectors["boe_api_legal"],
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=sample_xml,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                )

                result_1 = backfill_boe_policy_events(conn)
                self.assertGreater(result_1["policy_events_total"], 0)
                self.assertEqual(
                    result_1["policy_events_total"],
                    result_1["policy_events_with_source_url"],
                )
                self.assertEqual(
                    result_1["policy_events_total"],
                    result_1["policy_events_null_event_date_with_published"],
                )

                instruments = {
                    row["code"]: row["label"]
                    for row in conn.execute(
                        "SELECT code, label FROM policy_instruments WHERE code LIKE 'boe_%' ORDER BY code"
                    ).fetchall()
                }
                self.assertIn("boe_daily_summary", instruments)
                self.assertIn("boe_legal_document", instruments)

                traceability_row = conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM policy_events
                    WHERE source_id LIKE 'boe_%'
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
                    "SELECT COUNT(*) AS c FROM policy_events WHERE source_id LIKE 'boe_%'"
                ).fetchone()
                self.assertEqual(int(traceability_row["c"]), int(total_row["c"]))

                result_2 = backfill_boe_policy_events(conn)
                self.assertEqual(result_1["policy_events_total"], result_2["policy_events_total"])

                fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
                self.assertEqual(fk_rows, [])
            finally:
                conn.close()

    def test_ambiguous_dates_keep_event_date_null_and_use_published_date(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "boe-policy-events-dates.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)
                now_iso = now_utc_iso()

                payload = {
                    "record_kind": "boe_rss_item",
                    "title": "Orden sobre administracion y censo electoral",
                    "description": "Referencia: BOE-A-2026-9999",
                    "boe_ref": "BOE-A-2026-9999",
                    "source_url": "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-9999",
                    "published_at_iso": "2026-02-14T09:00:00+01:00",
                    "event_date_iso": "2026-02-10T00:00:00+01:00",
                }
                raw_payload = stable_json(payload)
                srpk = upsert_source_record(
                    conn=conn,
                    source_id="boe_api_legal",
                    source_record_id="boe_ref:BOE-A-2026-9999",
                    snapshot_date="2026-02-16",
                    raw_payload=raw_payload,
                    content_sha256=sha256_bytes(raw_payload.encode("utf-8")),
                    now_iso=now_iso,
                )
                self.assertGreater(srpk, 0)
                conn.commit()

                result = backfill_boe_policy_events(conn)
                self.assertGreater(result["policy_events_total"], 0)

                row = conn.execute(
                    """
                    SELECT event_date, published_date
                    FROM policy_events
                    WHERE source_id = 'boe_api_legal'
                      AND source_record_pk = ?
                    """,
                    (srpk,),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertIsNone(row["event_date"])
                self.assertEqual(row["published_date"], "2026-02-14")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
