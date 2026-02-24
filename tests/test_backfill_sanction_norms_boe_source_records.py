from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.backfill_sanction_norms_boe_source_records import backfill
from scripts.import_sanction_norms_seed import import_seed


class TestBackfillSanctionNormsBoeSourceRecords(unittest.TestCase):
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
                "xml",
                1,
                ts,
                ts,
            ),
        )
        conn.commit()

    def test_backfill_inserts_canonical_boe_ref_record(self) -> None:
        xml_payload = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<documento>
  <metadatos>
    <identificador>BOE-A-2015-11722</identificador>
    <titulo>Ley trafico</titulo>
    <fecha_publicacion>20151031</fecha_publicacion>
    <url_pdf>/boe/dias/2015/10/31/pdfs/BOE-A-2015-11722.pdf</url_pdf>
    <url_eli>https://www.boe.es/eli/es/rdlg/2015/10/30/6</url_eli>
  </metadatos>
</documento>
"""

        seed_doc = self._seed_doc()
        with TemporaryDirectory() as td:
            db_path = Path(td) / "backfill.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._insert_source(conn)
                import_seed(conn, seed_doc=seed_doc, source_id="boe_api_legal", snapshot_date="2026-02-23")

                with mock.patch(
                    "scripts.backfill_sanction_norms_boe_source_records.http_get_bytes",
                    return_value=(xml_payload, "application/xml; charset=utf-8"),
                ):
                    got = backfill(
                        conn,
                        source_id="boe_api_legal",
                        timeout=20,
                        boe_ids=["BOE-A-2015-11722"],
                        limit=0,
                        seed_schema_version="sanction_norms_seed_v1",
                        strict_network=True,
                    )

                row = conn.execute(
                    """
                    SELECT source_record_id, raw_payload
                    FROM source_records
                    WHERE source_id = ? AND source_record_id = ?
                    """,
                    ("boe_api_legal", "boe_ref:BOE-A-2015-11722"),
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(int(got["counts"]["targets_total"]), 1)
        self.assertEqual(int(got["counts"]["records_inserted"]), 1)
        self.assertEqual(int(got["counts"]["records_fetch_failed"]), 0)
        self.assertIsNotNone(row)
        self.assertEqual(str(row["source_record_id"]), "boe_ref:BOE-A-2015-11722")
        self.assertIn("boe_document_xml", str(row["raw_payload"]))
        self.assertNotIn('"seed_schema_version": "sanction_norms_seed_v1"', str(row["raw_payload"]))


if __name__ == "__main__":
    unittest.main()
