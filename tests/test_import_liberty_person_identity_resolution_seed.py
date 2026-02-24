from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_liberty_indirect_accountability_seed import import_seed as import_indirect_seed
from scripts.import_liberty_person_identity_resolution_seed import import_seed as import_identity_seed
from scripts.import_liberty_restrictions_seed import import_seed as import_liberty_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed
from scripts.report_liberty_person_identity_resolution_queue import build_report


class TestImportLibertyPersonIdentityResolutionSeed(unittest.TestCase):
    def test_import_is_idempotent(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "identity_alias_import.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(encoding="utf-8"))
                got1 = import_identity_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-23")
                got2 = import_identity_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-23")

                self.assertEqual(str(got1["status"]), "ok")
                self.assertEqual(int(got1["counts"]["mappings_total"]), 9)
                self.assertEqual(int(got1["counts"]["aliases_inserted"]), 9)
                self.assertEqual(int(got1["counts"]["persons_created"]), 5)
                self.assertEqual(int(got1["counts"]["manual_mappings_total"]), 9)
                self.assertEqual(int(got1["counts"]["official_mappings_total"]), 0)
                self.assertEqual(int(got1["counts"]["official_mappings_with_source_record_total"]), 0)
                self.assertEqual(int(got1["counts"]["official_mappings_missing_source_record_total"]), 0)
                self.assertEqual(int(got1["totals"]["manual_aliases_total"]), 9)
                self.assertEqual(int(got1["totals"]["official_aliases_total"]), 0)
                self.assertEqual(int(got1["totals"]["official_aliases_with_source_record_total"]), 0)
                self.assertEqual(int(got1["totals"]["official_aliases_missing_source_record_total"]), 0)

                self.assertEqual(str(got2["status"]), "ok")
                self.assertEqual(int(got2["counts"]["aliases_updated"]), 9)
                self.assertEqual(int(got2["counts"]["persons_created"]), 0)
                self.assertEqual(int(got2["totals"]["aliases_total"]), 9)
                self.assertEqual(int(got2["counts"]["aliases_source_kind_downgrade_prevented"]), 0)
                self.assertEqual(int(got2["counts"]["aliases_retarget_downgrade_prevented"]), 0)
                self.assertEqual(int(got2["counts"]["source_record_pk_resolved_total"]), 0)
                self.assertEqual(int(got2["counts"]["source_record_pk_unresolved_total"]), 0)
            finally:
                conn.close()

    def test_import_resolves_official_source_record_reference(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "identity_alias_source_record_resolution.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                ts = "2026-02-23T00:00:00+00:00"
                conn.execute(
                    """
                    INSERT INTO sources (
                      source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    ("boe_api_legal", "BOE API legal", "nacional", "https://www.boe.es", "json", ts, ts),
                )
                conn.execute(
                    """
                    INSERT INTO source_records (
                      source_id, source_record_id, source_snapshot_date, raw_payload, content_sha256, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "boe_api_legal",
                        "boe:A-2024-00001",
                        "2026-02-23",
                        "{\"id\": \"boe:A-2024-00001\"}",
                        "sha256-demo",
                        ts,
                        ts,
                    ),
                )
                source_record_pk = int(
                    conn.execute(
                        """
                        SELECT source_record_pk
                        FROM source_records
                        WHERE source_id = ? AND source_record_id = ?
                        """,
                        ("boe_api_legal", "boe:A-2024-00001"),
                    ).fetchone()[0]
                )

                seed = {
                    "schema_version": "liberty_person_identity_resolution_seed_v1",
                    "generated_at": "2026-02-23T00:00:00Z",
                    "methodology": {
                        "method_version": "identity_resolution_v1",
                        "method_label": "Resolucion manual persona-cargo v1",
                    },
                    "mappings": [
                        {
                            "actor_person_name": "Persona Seed Oficial",
                            "person_full_name": "Alicia Martin Gomez",
                            "source_kind": "official_nombramiento",
                            "source_id": "boe_api_legal",
                            "source_record_id": "boe:A-2024-00001",
                            "source_url": "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-00001",
                            "evidence_date": "2024-01-02",
                            "evidence_quote": "Nombramiento oficial publicado en BOE.",
                            "confidence": 0.9,
                        }
                    ],
                }
                got = import_identity_seed(conn, seed_doc=seed, source_id="boe_api_legal", snapshot_date="2026-02-23")
                alias_row = conn.execute(
                    """
                    SELECT source_record_pk, source_kind
                    FROM person_name_aliases
                    WHERE canonical_alias = ?
                    """,
                    ("persona seed oficial",),
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertEqual(int(got["counts"]["official_mappings_total"]), 1)
        self.assertEqual(int(got["counts"]["official_mappings_with_source_record_total"]), 1)
        self.assertEqual(int(got["counts"]["official_mappings_missing_source_record_total"]), 0)
        self.assertEqual(int(got["counts"]["source_record_pk_resolved_total"]), 1)
        self.assertEqual(int(got["counts"]["source_record_pk_unresolved_total"]), 0)
        self.assertEqual(int(got["totals"]["official_aliases_total"]), 1)
        self.assertEqual(int(got["totals"]["official_aliases_with_source_record_total"]), 1)
        self.assertEqual(int(got["totals"]["official_aliases_missing_source_record_total"]), 0)
        self.assertEqual(int(alias_row["source_record_pk"]), source_record_pk)
        self.assertEqual(str(alias_row["source_kind"]), "official_nombramiento")

    def test_import_resolves_identity_queue(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "identity_alias_queue.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
                indirect_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_indirect_accountability_seed_v1.json").read_text(encoding="utf-8"))
                identity_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(encoding="utf-8"))

                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_indirect_seed(conn, seed_doc=indirect_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_identity_seed(conn, seed_doc=identity_seed_doc, source_id="", snapshot_date="2026-02-23")

                got = build_report(conn)
            finally:
                conn.close()

        self.assertEqual(str(got["status"]), "ok")
        self.assertEqual(int(got["totals"]["indirect_person_edges_valid_window_total"]), 9)
        self.assertEqual(int(got["totals"]["indirect_person_edges_identity_resolved_total"]), 9)
        self.assertEqual(int(got["totals"]["indirect_person_edges_unresolved_total"]), 0)
        self.assertEqual(int(got["totals"]["queue_rows_total"]), 0)
        self.assertEqual(float(got["coverage"]["indirect_identity_resolution_pct"]), 1.0)

    def test_manual_seed_import_does_not_downgrade_existing_official_alias(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "identity_alias_no_downgrade.db"
            conn = open_db(db_path)
            try:
                root = Path(__file__).resolve().parents[1]
                schema_path = root / "etl" / "load" / "sqlite_schema.sql"
                apply_schema(conn, schema_path)

                base_seed = json.loads(
                    (root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(
                        encoding="utf-8"
                    )
                )
                import_identity_seed(conn, seed_doc=base_seed, source_id="", snapshot_date="2026-02-23")

                upgraded_seed = json.loads(json.dumps(base_seed))
                upgraded_seed["mappings"][0]["source_kind"] = "official_nombramiento"
                upgraded_seed["mappings"][0]["source_url"] = "https://www.boe.es/boe/dias/2024/01/02/"
                upgraded_seed["mappings"][0]["evidence_date"] = "2024-01-02"
                upgraded_seed["mappings"][0]["evidence_quote"] = "Nombramiento oficial publicado en BOE."
                got_upgrade = import_identity_seed(conn, seed_doc=upgraded_seed, source_id="", snapshot_date="2026-02-23")
                manual_retarget_seed = json.loads(json.dumps(base_seed))
                manual_retarget_seed["mappings"][0]["person_full_name"] = "Persona Manual Distinta"
                manual_retarget_seed["mappings"][0]["person_canonical_key"] = "liberty_person_demo:persona_manual_distinta"
                got_replay_manual = import_identity_seed(
                    conn,
                    seed_doc=manual_retarget_seed,
                    source_id="",
                    snapshot_date="2026-02-23",
                )

                alias_row = conn.execute(
                    """
                    SELECT pna.source_kind, pna.source_url, pna.evidence_date, pna.evidence_quote, p.full_name
                    FROM person_name_aliases pna
                    JOIN persons p ON p.person_id = pna.person_id
                    WHERE pna.canonical_alias = ?
                    """,
                    ("persona seed empleo nombramientos",),
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(str(got_upgrade["status"]), "ok")
        self.assertEqual(str(got_replay_manual["status"]), "ok")
        self.assertEqual(int(got_replay_manual["counts"]["aliases_source_kind_downgrade_prevented"]), 1)
        self.assertEqual(int(got_replay_manual["counts"]["aliases_retarget_downgrade_prevented"]), 1)
        self.assertEqual(int(got_replay_manual["counts"]["aliases_retargeted"]), 0)
        self.assertEqual(str(alias_row["source_kind"]), "official_nombramiento")
        self.assertEqual(str(alias_row["source_url"]), "https://www.boe.es/boe/dias/2024/01/02/")
        self.assertEqual(str(alias_row["evidence_date"]), "2024-01-02")
        self.assertEqual(str(alias_row["evidence_quote"]), "Nombramiento oficial publicado en BOE.")
        self.assertEqual(str(alias_row["full_name"]), "Alicia Martin Gomez")


if __name__ == "__main__":
    unittest.main()
