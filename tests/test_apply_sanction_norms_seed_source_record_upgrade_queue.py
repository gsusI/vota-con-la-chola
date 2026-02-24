from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.db import upsert_source_record
from etl.politicos_es.util import sha256_bytes
from scripts.apply_sanction_norms_seed_source_record_upgrade_queue import apply_upgrades
from scripts.import_sanction_norms_seed import import_seed


class TestApplySanctionNormsSeedSourceRecordUpgradeQueue(unittest.TestCase):
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

    def test_apply_upgrades_repoints_to_non_seed_alias_record(self) -> None:
        seed_doc = self._seed_doc()

        with TemporaryDirectory() as td:
            db_path = Path(td) / "apply_upgrade.db"
            conn = open_db(db_path)
            try:
                schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)
                self._insert_source(conn)
                import_seed(conn, seed_doc=seed_doc, source_id="boe_api_legal", snapshot_date="2026-02-23")

                before = conn.execute(
                    "SELECT source_record_pk FROM legal_fragment_responsibility_evidence LIMIT 1"
                ).fetchone()
                self.assertIsNotNone(before)
                before_pk = int(before["source_record_pk"])

                now_iso = "2026-02-24T00:00:00+00:00"
                payload = json.dumps(
                    {
                        "record_kind": "boe_document_xml",
                        "boe_ref": "BOE-A-2015-11722",
                        "title": "Ley trafico",
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                candidate_pk = upsert_source_record(
                    conn,
                    "boe_api_legal",
                    "boe_ref:BOE-A-2015-11722",
                    "2026-02-24",
                    payload,
                    sha256_bytes(payload.encode("utf-8")),
                    now_iso,
                )

                got = apply_upgrades(conn, seed_schema_version="sanction_norms_seed_v1", dry_run=False)

                after = conn.execute(
                    "SELECT source_record_pk FROM legal_fragment_responsibility_evidence LIMIT 1"
                ).fetchone()
                self.assertIsNotNone(after)
                after_pk = int(after["source_record_pk"])
            finally:
                conn.close()

        self.assertNotEqual(before_pk, candidate_pk)
        self.assertEqual(after_pk, candidate_pk)
        self.assertEqual(int(got["counts"]["queue_rows_seen"]), 1)
        self.assertEqual(int(got["counts"]["upgraded_rows"]), 1)
        self.assertEqual(int(got["counts"]["missing_candidate_rows"]), 0)
        self.assertEqual(len(got["upgraded_samples"]), 1)


if __name__ == "__main__":
    unittest.main()
