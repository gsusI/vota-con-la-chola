from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG as PARL_SOURCE_CONFIG
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.linking import link_congreso_votes_to_initiatives, link_senado_votes_to_initiatives
from etl.parlamentario_es.pipeline import ingest_one_source as ingest_parl_source
from etl.parlamentario_es.publish import build_votaciones_snapshot
from etl.parlamentario_es.registry import get_connectors


class TestPublishParlamentarioVotaciones(unittest.TestCase):
    def test_publish_snapshot_is_deterministic_and_traceable(self) -> None:
        connectors = get_connectors()
        snapshot_date = "2026-02-12"
        source_ids = [
            "congreso_votaciones",
            "congreso_iniciativas",
            "senado_iniciativas",
            "senado_votaciones",
        ]
        for sid in source_ids:
            self.assertIn(sid, connectors, f"Missing connector: {sid}")

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-test.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)

                for sid in source_ids:
                    connector = connectors[sid]
                    sample_path = Path(PARL_SOURCE_CONFIG[sid]["fallback_file"])
                    self.assertTrue(sample_path.exists(), f"Missing sample for {sid}: {sample_path}")
                    ingest_parl_source(
                        conn=conn,
                        connector=connector,
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=sample_path,
                        url_override=None,
                        snapshot_date=snapshot_date,
                        strict_network=True,
                        options={},
                    )

                link_congreso_votes_to_initiatives(conn, dry_run=False)
                link_senado_votes_to_initiatives(conn, dry_run=False)

                snap1 = build_votaciones_snapshot(conn, snapshot_date=snapshot_date)
                snap2 = build_votaciones_snapshot(conn, snapshot_date=snapshot_date)
                self.assertEqual(snap1, snap2)

                items = snap1.get("items")
                self.assertIsInstance(items, list)
                self.assertGreater(len(items), 0)

                tot = snap1.get("totales") or {}
                self.assertGreater(int(tot.get("eventos") or 0), 0)
                self.assertGreater(int(tot.get("votos_nominales") or 0), 0)

                self.assertTrue(any((it.get("initiatives") or []) for it in items))
                self.assertTrue(any((it.get("member_votes") or []) for it in items))

                for it in items[:10]:
                    self.assertIn("event", it)
                    self.assertIn("source", it)
                    self.assertIn("initiatives", it)
                    self.assertIn("member_votes", it)
                    src = it["source"]
                    self.assertTrue(src.get("source_id"))
                    self.assertTrue(src.get("source_url"))
                    self.assertTrue(src.get("source_hash"))
                    self.assertTrue(src.get("source_record_id"))

                    for link in (it.get("initiatives") or [])[:3]:
                        self.assertIn("initiative", link)
                        self.assertIn("link", link)
                        self.assertIn("source", link)
                        lsrc = link["source"]
                        self.assertTrue(lsrc.get("source_id"))
                        self.assertTrue(lsrc.get("source_url"))
                        self.assertTrue(lsrc.get("source_hash"))
                        self.assertTrue(lsrc.get("source_record_id"))

                    for mv in (it.get("member_votes") or [])[:3]:
                        self.assertIn("vote_choice", mv)
                        self.assertIn("source", mv)
                        msrc = mv["source"]
                        self.assertTrue(msrc.get("source_id"))
                        self.assertTrue(msrc.get("source_url"))
                        self.assertTrue(msrc.get("source_hash"))
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
