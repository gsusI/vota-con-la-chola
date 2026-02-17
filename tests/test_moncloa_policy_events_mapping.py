from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources, upsert_source_record
from etl.politicos_es.pipeline import ingest_one_source
from etl.politicos_es.policy_events import backfill_moncloa_policy_events
from etl.politicos_es.registry import get_connectors
from etl.politicos_es.util import now_utc_iso, sha256_bytes, stable_json


class TestMoncloaPolicyEventsMapping(unittest.TestCase):
    def test_backfill_moncloa_policy_events_is_idempotent_and_traceable(self) -> None:
        snapshot_date = "2026-02-12"
        sample_refs = Path("etl/data/raw/samples/moncloa_referencias_sample.html")
        sample_rss = Path("etl/data/raw/samples/moncloa_rss_referencias_sample.xml")
        self.assertTrue(sample_refs.exists(), f"Missing sample: {sample_refs}")
        self.assertTrue(sample_rss.exists(), f"Missing sample: {sample_rss}")

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "moncloa-policy-events.db"
            raw_dir = Path(td) / "raw"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)

                connectors = get_connectors()
                for source_id, sample_path in (
                    ("moncloa_referencias", sample_refs),
                    ("moncloa_rss_referencias", sample_rss),
                ):
                    ingest_one_source(
                        conn=conn,
                        connector=connectors[source_id],
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=sample_path,
                        url_override=None,
                        snapshot_date=snapshot_date,
                        strict_network=True,
                    )

                result_1 = backfill_moncloa_policy_events(conn)
                self.assertGreater(result_1["policy_events_total"], 0)
                self.assertEqual(
                    result_1["policy_events_total"],
                    result_1["policy_events_with_source_url"],
                )

                instruments = {
                    row["code"]: row["label"]
                    for row in conn.execute(
                        "SELECT code, label FROM policy_instruments ORDER BY code"
                    ).fetchall()
                }
                self.assertIn("exec_reference", instruments)
                self.assertIn("exec_rss_reference", instruments)

                traceability_row = conn.execute(
                    """
                    SELECT COUNT(*) AS c
                    FROM policy_events
                    WHERE source_id LIKE 'moncloa_%'
                      AND source_url IS NOT NULL
                      AND trim(source_url) <> ''
                      AND source_record_pk IS NOT NULL
                      AND raw_payload IS NOT NULL
                      AND trim(raw_payload) <> ''
                    """
                ).fetchone()
                total_row = conn.execute(
                    "SELECT COUNT(*) AS c FROM policy_events WHERE source_id LIKE 'moncloa_%'"
                ).fetchone()
                self.assertEqual(int(traceability_row["c"]), int(total_row["c"]))

                result_2 = backfill_moncloa_policy_events(conn)
                self.assertEqual(result_1["policy_events_total"], result_2["policy_events_total"])

                fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
                self.assertEqual(fk_rows, [])
            finally:
                conn.close()

    def test_missing_event_date_keeps_published_date(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "moncloa-policy-events-dates.db"
            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)
                now_iso = now_utc_iso()

                payload = {
                    "source_feed": "tipo15",
                    "stable_id_slug": "100226-rueda-de-prensa-ministros.aspx",
                    "title": "Resumen del Consejo de Ministros",
                    "source_url": "https://www.lamoncloa.gob.es/consejodeministros/resumenes/paginas/2026/100226-rueda-de-prensa-ministros.aspx",
                    "event_date_iso": None,
                    "published_at_iso": "2026-02-10T15:00:00+00:00",
                    "summary_text": "Resumen de acuerdos",
                }
                raw_payload = stable_json(payload)
                srpk = upsert_source_record(
                    conn=conn,
                    source_id="moncloa_rss_referencias",
                    source_record_id="tipo15:100226-rueda-de-prensa-ministros.aspx",
                    snapshot_date="2026-02-12",
                    raw_payload=raw_payload,
                    content_sha256=sha256_bytes(raw_payload.encode("utf-8")),
                    now_iso=now_iso,
                )
                self.assertGreater(srpk, 0)
                conn.commit()

                result = backfill_moncloa_policy_events(conn)
                self.assertGreater(result["policy_events_total"], 0)

                row = conn.execute(
                    """
                    SELECT event_date, published_date
                    FROM policy_events
                    WHERE source_id = 'moncloa_rss_referencias'
                      AND source_record_pk = ?
                    """,
                    (srpk,),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertIsNone(row["event_date"])
                self.assertEqual(row["published_date"], "2026-02-10")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
