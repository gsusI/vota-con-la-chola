from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.export_liberty_person_identity_official_upgrade_review_queue import build_review_rows
from scripts.import_liberty_indirect_accountability_seed import import_seed as import_indirect_seed
from scripts.import_liberty_person_identity_resolution_seed import import_seed as import_identity_seed
from scripts.import_liberty_restrictions_seed import import_seed as import_liberty_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed
from scripts.report_liberty_person_identity_resolution_queue import build_report


def _seed_rights(conn, root: Path) -> None:
    norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
    liberty_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8"))
    indirect_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_indirect_accountability_seed_v1.json").read_text(encoding="utf-8"))
    identity_seed_doc = json.loads(
        (root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(encoding="utf-8")
    )
    import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
    import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
    import_indirect_seed(conn, seed_doc=indirect_seed_doc, source_id="", snapshot_date="2026-02-23")
    import_identity_seed(conn, seed_doc=identity_seed_doc, source_id="", snapshot_date="2026-02-23")


class TestExportLibertyPersonIdentityOfficialUpgradeReviewQueue(unittest.TestCase):
    def test_build_review_rows_from_manual_upgrade_backlog(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "identity_upgrade_review_queue.db"
            root = Path(__file__).resolve().parents[1]
            seed_doc = json.loads(
                (root / "etl" / "data" / "seeds" / "liberty_person_identity_resolution_seed_v1.json").read_text(
                    encoding="utf-8"
                )
            )
            conn = open_db(db_path)
            try:
                apply_schema(conn, root / "etl" / "load" / "sqlite_schema.sql")
                _seed_rights(conn, root)
                report_doc = build_report(conn)
                rows, summary = build_review_rows(report_doc=report_doc, seed_doc=seed_doc)
            finally:
                conn.close()

        self.assertEqual(int(summary["rows_total"]), 9)
        self.assertEqual(int(summary["manual_upgrade_rows_total"]), 9)
        self.assertEqual(int(summary["official_evidence_gap_rows_total"]), 0)
        self.assertEqual(int(summary["official_source_record_gap_rows_total"]), 0)
        self.assertEqual(int(summary["missing_seed_mapping_total"]), 0)
        self.assertEqual(int(summary["source_record_pk_lookup_keys_total"]), 0)
        self.assertEqual(int(summary["source_record_pk_lookup_prefilled_total"]), 0)
        self.assertEqual(int(summary["source_record_pk_lookup_miss_total"]), 0)
        self.assertEqual(int(summary["actionable_rows_total"]), 0)
        self.assertEqual(int(summary["likely_not_actionable_rows_total"]), 9)
        self.assertEqual(len(rows), 9)
        first_row = rows[0]
        self.assertIn("manual_upgrade", str(first_row["gap_flags_csv"]))
        self.assertEqual(str(first_row["current_source_kind"]), "manual_seed")
        self.assertEqual(str(first_row["proposed_source_kind"]), "official_nombramiento")
        self.assertEqual(str(first_row["decision"]), "")
        self.assertEqual(str(first_row["source_record_pk_lookup_status"]), "not_applicable")
        self.assertEqual(str(first_row["actionability"]), "likely_not_actionable_seed_placeholder")
        self.assertEqual(str(first_row["actionability_reason"]), "actor_person_name_seed_prefix")

    def test_build_review_rows_prefills_source_record_pk_from_lookup(self) -> None:
        seed_doc = {
            "schema_version": "liberty_person_identity_resolution_seed_v1",
            "generated_at": "2026-02-23T00:00:00+00:00",
            "methodology": {"method_version": "v1", "method_label": "test"},
            "mappings": [
                {
                    "actor_person_name": "Persona Lookup Demo",
                    "person_full_name": "Persona Lookup Demo",
                    "source_kind": "official_nombramiento",
                    "source_url": "https://www.boe.es/boe/dias/2024/01/02/",
                    "evidence_date": "2024-01-02",
                    "evidence_quote": "Nombramiento oficial publicado en BOE.",
                    "source_id": "boe_api_legal",
                    "source_record_id": "boe_ref:BOE-A-2026-3482",
                }
            ],
        }
        report_doc = {
            "manual_alias_upgrade_queue_rows": [],
            "official_alias_evidence_upgrade_queue_rows": [],
            "official_alias_source_record_upgrade_queue_rows": [
                {
                    "queue_key": "official_source_record:test",
                    "actor_person_name": "Persona Lookup Demo",
                    "person_name": "Persona Lookup Demo",
                    "source_kind": "official_nombramiento",
                    "edges_total": 3,
                    "fragments_total": 2,
                    "first_evidence_date": "2024-01-02",
                    "last_evidence_date": "2024-01-10",
                }
            ],
        }

        rows, summary = build_review_rows(
            report_doc=report_doc,
            seed_doc=seed_doc,
            source_record_lookup={("boe_api_legal", "boe_ref:boe-a-2026-3482"): "125908"},
        )
        self.assertEqual(int(summary["rows_total"]), 1)
        self.assertEqual(int(summary["source_record_pk_lookup_keys_total"]), 1)
        self.assertEqual(int(summary["source_record_pk_lookup_prefilled_total"]), 1)
        self.assertEqual(int(summary["source_record_pk_lookup_miss_total"]), 0)
        self.assertEqual(int(summary["actionable_rows_total"]), 1)
        self.assertEqual(int(summary["likely_not_actionable_rows_total"]), 0)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(str(row["source_record_pk"]), "125908")
        self.assertEqual(str(row["source_record_pk_lookup_status"]), "prefilled_from_db")
        self.assertEqual(str(row["actionability"]), "actionable")
        self.assertEqual(str(row["actionability_reason"]), "")


if __name__ == "__main__":
    unittest.main()
