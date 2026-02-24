from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.export_sanction_norms_seed_source_record_upgrade_queue import build_queue_report
from scripts.import_sanction_norms_seed import import_seed


class TestExportSanctionNormsSeedSourceRecordUpgradeQueue(unittest.TestCase):
    def _seed_doc(self) -> dict[str, object]:
        return {
            "schema_version": "sanction_norms_seed_v1",
            "norms": [
                {
                    "norm_id": "es:boe-a-2015-11722",
                    "boe_id": "BOE-A-2015-11722",
                    "title": "Ley trafico",
                    "scope": "nacional",
                    "organismo_competente": "DGT",
                    "incidence_hypothesis": "alta",
                    "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                    "evidence_required": ["base_legal_fragment"],
                    "key_fragments": [
                        {
                            "fragment_type": "articulo",
                            "fragment_label": "Bloque principal",
                            "conducta_sancionada": "Incumplimientos",
                            "organo_competente": "DGT",
                            "via_recurso": "Reposicion",
                        }
                    ],
                    "responsibility_hints": [
                        {
                            "role": "propose",
                            "actor_label": "Gobierno",
                            "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                            "evidence_date": "2015-10-31",
                            "evidence_quote": "Fuente BOE del marco normativo publicado.",
                            "evidence_items": [
                                {
                                    "evidence_type": "boe_publicacion",
                                    "source_id": "boe_api_legal",
                                    "source_record_id": "BOE-A-2015-11722",
                                    "source_url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11722",
                                    "evidence_date": "2015-10-31",
                                    "evidence_quote": "Referencia BOE del texto legal publicado.",
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    def _insert_source(self, conn: object) -> None:
        ts = "2026-02-24T00:00:00+00:00"
        conn.execute(
            """
            INSERT INTO sources (
              source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "boe_api_legal",
                "BOE API Legal",
                "nacional",
                "https://www.boe.es/",
                "json",
                1,
                ts,
                ts,
            ),
        )
        conn.commit()

    def test_queue_is_empty_when_source_record_is_non_seed(self) -> None:
        seed_doc = self._seed_doc()
        with TemporaryDirectory() as td:
            db_path = Path(td) / "queue_non_seed.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._insert_source(conn)
                ts = "2026-02-24T00:00:00+00:00"
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date,
                      raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "boe_api_legal",
                        "BOE-A-2015-11722",
                        "2026-02-24",
                        '{"upstream":"boe_api_legal"}',
                        "non-seed-sha",
                        ts,
                        ts,
                    ),
                )
                conn.commit()
                import_seed(conn, seed_doc=seed_doc, source_id="boe_api_legal", snapshot_date="2026-02-23")
                got = build_queue_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertTrue(bool(got["checks"]["queue_empty"]))
        self.assertFalse(bool(got["checks"]["queue_visible"]))
        self.assertEqual(int(got["totals"]["queue_rows_total"]), 0)
        self.assertEqual(len(got["queue_rows"]), 0)

    def test_queue_has_seed_backed_rows(self) -> None:
        seed_doc = self._seed_doc()
        with TemporaryDirectory() as td:
            db_path = Path(td) / "queue_seed.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._insert_source(conn)
                import_seed(conn, seed_doc=seed_doc, source_id="boe_api_legal", snapshot_date="2026-02-23")
                got = build_queue_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "degraded")
        self.assertTrue(bool(got["checks"]["queue_visible"]))
        self.assertFalse(bool(got["checks"]["queue_empty"]))
        self.assertEqual(int(got["totals"]["queue_rows_total"]), 1)
        self.assertEqual(int(got["totals"]["queue_norms_total"]), 1)
        self.assertEqual(int(got["totals"]["queue_fragments_total"]), 1)
        self.assertEqual(int(got["totals"]["queue_responsibilities_total"]), 1)
        self.assertEqual(int(got["totals"]["queue_evidence_types_total"]), 1)
        row0 = got["queue_rows"][0]
        self.assertEqual(str(row0["norm_id"]), "es:boe-a-2015-11722")
        self.assertEqual(str(row0["boe_id"]), "BOE-A-2015-11722")
        self.assertTrue(str(row0["queue_key"]).startswith("responsibility_evidence_id:"))


if __name__ == "__main__":
    unittest.main()
