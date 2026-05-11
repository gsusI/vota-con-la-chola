from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.export_liberty_delegated_person_window_scrape_targets import build_scrape_targets
from scripts.export_liberty_delegated_person_window_review_queue import build_review_rows
from scripts.import_liberty_delegated_enforcement_seed import import_seed as import_delegated_seed
from scripts.import_liberty_restrictions_seed import import_seed as import_liberty_seed
from scripts.import_sanction_norms_seed import import_seed as import_norm_seed
from scripts.report_liberty_delegated_person_window_queue import (
    DEFAULT_INSTITUTION_HINT_TERMS,
    _parse_csv_list,
    build_queue_report,
)


class TestExportLibertyDelegatedPersonWindowScrapeTargets(unittest.TestCase):
    def test_build_scrape_targets_from_seeded_queue(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "delegated_scrape_targets.db"
            root = Path(__file__).resolve().parents[1]
            delegated_seed = json.loads(
                (root / "etl" / "data" / "seeds" / "liberty_delegated_enforcement_seed_v1.json").read_text(encoding="utf-8")
            )
            norm_seed_doc = json.loads((root / "etl" / "data" / "seeds" / "sanction_norms_seed_v1.json").read_text(encoding="utf-8"))
            liberty_seed_doc = json.loads(
                (root / "etl" / "data" / "seeds" / "liberty_restrictions_seed_v1.json").read_text(encoding="utf-8")
            )

            conn = open_db(db_path)
            try:
                apply_schema(conn, root / "etl" / "load" / "sqlite_schema.sql")
                import_norm_seed(conn, seed_doc=norm_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_liberty_seed(conn, seed_doc=liberty_seed_doc, source_id="", snapshot_date="2026-02-23")
                import_delegated_seed(conn, seed_doc=delegated_seed, source_id="", snapshot_date="2026-02-23")
                queue_report = build_queue_report(
                    conn,
                    limit=0,
                    institution_hint_terms=_parse_csv_list(DEFAULT_INSTITUTION_HINT_TERMS),
                    max_actionable_rows=-1,
                )
            finally:
                conn.close()

        review_rows, _ = build_review_rows(queue_report=queue_report, seed_doc=delegated_seed, only_actionable=True)
        targets, summary = build_scrape_targets(review_rows=review_rows, min_priority_score=1)

        self.assertEqual(int(summary["targets_total"]), 0)
        self.assertEqual(int(summary["packets_total"]), 0)
        self.assertEqual(int(summary["top_priority_score"]), 0)

    def test_build_scrape_targets_prioritizes_actionable_review_rows(self) -> None:
        targets, summary = build_scrape_targets(
            review_rows=[
                {
                    "link_key": "link-1",
                    "fragment_id": "frag-1",
                    "norm_id": "norm-1",
                    "boe_id": "BOE-A-2024-1",
                    "delegating_actor_label": "Ministerio",
                    "delegated_institution_label": "AEAT",
                    "designated_role_title": "Director",
                    "current_designated_actor_label": "",
                    "current_appointment_start_date": "",
                    "current_enforcement_evidence_date": "",
                    "current_source_url": "https://www.boe.es/boe/dias/2024/01/02/",
                    "chain_confidence": 0.5,
                    "reasons_csv": "missing_designated_actor|missing_appointment_start_date|missing_enforcement_evidence_date",
                }
            ],
            min_priority_score=1,
        )

        self.assertEqual(int(summary["targets_total"]), 1)
        self.assertEqual(int(summary["packets_total"]), 1)
        self.assertIn("missing_designated_actor", dict(summary["by_reason"]))
        self.assertEqual(int(summary["top_priority_score"]), 75)

        first = targets[0]
        self.assertIn('site:boe.es "AEAT"', str(first["search_query_primary"]))
        self.assertIn("review_status", first)
        self.assertEqual(str(first["review_status"]), "pending")
        self.assertEqual(int(first["priority_rank"]), 1)


if __name__ == "__main__":
    unittest.main()
