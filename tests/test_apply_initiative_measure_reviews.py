from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.apply_initiative_measure_reviews import apply_review_results


class TestApplyInitiativeMeasureReviews(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE parl_initiative_measure_review_tasks (
              task_id TEXT PRIMARY KEY,
              initiative_id TEXT NOT NULL UNIQUE,
              source_id TEXT NOT NULL,
              review_reason TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              priority INTEGER NOT NULL DEFAULT 50,
              evidence_bundle_dir TEXT,
              note TEXT,
              raw_payload_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE parl_initiative_measure_points (
              measure_point_id TEXT PRIMARY KEY,
              task_id TEXT NOT NULL,
              initiative_id TEXT NOT NULL,
              source_id TEXT NOT NULL,
              measure_rank INTEGER NOT NULL DEFAULT 1,
              measure_title TEXT NOT NULL,
              citizen_summary TEXT NOT NULL,
              affected_groups TEXT,
              policy_area TEXT,
              measure_kind TEXT,
              measure_status TEXT,
              search_terms_json TEXT NOT NULL DEFAULT '[]',
              primary_vote_event_ids_json TEXT NOT NULL DEFAULT '[]',
              support_side TEXT,
              support_explanation TEXT,
              evidence_json TEXT NOT NULL DEFAULT '[]',
              note TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        return conn

    def test_apply_resolved_result_inserts_measure_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "measure_apply.db"
            result_dir = Path(td) / "results"
            result_dir.mkdir()
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_initiative_measure_review_tasks(
                      task_id, initiative_id, source_id, review_reason, status, priority, raw_payload_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'pending', 90, '{}', '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00')
                    """,
                    ("i1", "i1", "congreso_iniciativas", "official_docs_bundle"),
                )
                conn.commit()

                (result_dir / "i1.json").write_text(
                    json.dumps(
                        {
                            "task_id": "i1",
                            "review_status": "resolved",
                            "review_note": "ready",
                            "reviewer": "worker-a",
                            "measures": [
                                {
                                    "measure_title": "Zonas de bajas emisiones pueden restringir vehículos más contaminantes",
                                    "citizen_summary": "La norma permite restringir la circulación de vehículos muy contaminantes en ciudades.",
                                    "search_terms": ["bajas emisiones", "diesel ciudades"],
                                    "measure_status": "approved",
                                    "support_side": "yes",
                                    "support_explanation": "Un sí apoyó la continuidad del texto.",
                                    "primary_vote_event_ids": ["v1"],
                                    "evidence": [{"doc_file": "docs/01.txt", "quote": "zonas de bajas emisiones"}]
                                }
                            ]
                        },
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )

                result = apply_review_results(
                    conn,
                    result_files=[result_dir / "i1.json"],
                    source_id="congreso_iniciativas",
                    dry_run=False,
                )
                self.assertEqual(result["tasks_updated"], 1)
                self.assertEqual(result["measures_inserted"], 1)

                task = conn.execute(
                    "SELECT status, note FROM parl_initiative_measure_review_tasks WHERE task_id='i1'"
                ).fetchone()
                self.assertEqual(str(task["status"]), "resolved")
                self.assertEqual(str(task["note"]), "ready")

                point = conn.execute(
                    """
                    SELECT measure_title, support_side, primary_vote_event_ids_json
                    FROM parl_initiative_measure_points
                    WHERE task_id='i1'
                    """
                ).fetchone()
                self.assertIn("bajas emisiones", str(point["measure_title"]).lower())
                self.assertEqual(str(point["support_side"]), "yes")
                self.assertEqual(str(point["primary_vote_event_ids_json"]), '["v1"]')
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
