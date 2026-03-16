from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.export_liberty_delegated_person_window_review_queue import build_review_rows
from scripts.import_liberty_delegated_enforcement_seed import import_seed as import_delegated_seed
from scripts.import_liberty_restrictions_seed import import_seed as import_liberty_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed
from scripts.report_liberty_delegated_person_window_queue import (
    DEFAULT_INSTITUTION_HINT_TERMS,
    _parse_csv_list,
    build_queue_report,
)


class TestExportLibertyDelegatedPersonWindowReviewQueue(unittest.TestCase):
    def test_build_review_rows_from_seeded_queue(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "delegated_review_queue.db"
            root = Path(__file__).resolve().parents[1]
            seed_doc = json.loads((root / "etl" / "data" / "seeds" / "liberty_delegated_enforcement_seed_v1.json").read_text(encoding="utf-8"))
            if isinstance(seed_doc.get("links"), list) and seed_doc["links"]:
                seed_doc["links"][0]["designated_actor_label"] = ""
                seed_doc["links"][0]["enforcement_evidence_date"] = ""

            conn = open_db(db_path)
            try:
                apply_schema(conn, root / "etl" / "load" / "sqlite_schema.sql")
                norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
                liberty_seed_doc = json.loads(
                    (root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8")
                )
                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_delegated_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-23")
                queue_report = build_queue_report(
                    conn,
                    limit=0,
                    institution_hint_terms=_parse_csv_list(DEFAULT_INSTITUTION_HINT_TERMS),
                    max_actionable_rows=-1,
                    dedupe_fragment_latest=True,
                )
            finally:
                conn.close()

        rows, summary = build_review_rows(
            queue_report=queue_report,
            seed_doc=seed_doc,
            only_actionable=False,
        )
        self.assertGreater(int(summary["rows_total"]), 0)
        self.assertGreater(int(summary["actionable_rows_total"]), 0)
        self.assertEqual(int(summary["missing_seed_links_total"]), 0)
        self.assertIn("missing_designated_actor", dict(summary["by_reason"]))
        self.assertEqual(len(rows), int(summary["rows_total"]))
        first = rows[0]
        self.assertIn("decision", first)
        self.assertEqual(str(first["decision"]), "")
        self.assertIn("reasons_csv", first)


if __name__ == "__main__":
    unittest.main()
