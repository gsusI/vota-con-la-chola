from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG as PARL_SOURCE_CONFIG
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.linking import link_senado_votes_to_initiatives
from etl.parlamentario_es.pipeline import ingest_one_source as ingest_parl_source
from etl.parlamentario_es.registry import get_connectors


class TestParlLinkingSenado(unittest.TestCase):
    def test_linking_by_legislature_and_expediente(self) -> None:
        connectors = get_connectors()
        ini_connector = connectors["senado_iniciativas"]
        vote_connector = connectors["senado_votaciones"]
        snapshot_date = "2026-02-12"

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-test.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)

                ini_sample = Path(PARL_SOURCE_CONFIG["senado_iniciativas"]["fallback_file"])
                vote_sample = Path(PARL_SOURCE_CONFIG["senado_votaciones"]["fallback_file"])
                self.assertTrue(ini_sample.exists(), f"Missing sample: {ini_sample}")
                self.assertTrue(vote_sample.exists(), f"Missing sample: {vote_sample}")

                ingest_parl_source(
                    conn=conn,
                    connector=ini_connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=ini_sample,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={},
                )
                ingest_parl_source(
                    conn=conn,
                    connector=vote_connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=vote_sample,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={},
                )

                res1 = link_senado_votes_to_initiatives(conn, dry_run=False)
                self.assertGreaterEqual(int(res1["links_written"]), 1)

                row = conn.execute(
                    """
                    SELECT vote_event_id, initiative_id, link_method
                    FROM parl_vote_event_initiatives
                    LIMIT 1
                    """
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(str(row["link_method"]), "leg_expediente_payload_exact")
                self.assertTrue(str(row["initiative_id"]).startswith("senado:leg15:exp:600/000001"))

                before = int(conn.execute("SELECT COUNT(*) AS c FROM parl_vote_event_initiatives").fetchone()["c"])
                link_senado_votes_to_initiatives(conn, dry_run=False)
                after = int(conn.execute("SELECT COUNT(*) AS c FROM parl_vote_event_initiatives").fetchone()["c"])
                self.assertEqual(before, after)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
