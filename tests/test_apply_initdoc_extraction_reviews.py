from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.apply_initdoc_extraction_reviews import apply_review_decisions


class TestApplyInitdocExtractionReviews(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE parl_initiative_doc_extractions (
              source_record_pk INTEGER PRIMARY KEY,
              source_id TEXT,
              extracted_subject TEXT,
              extracted_title TEXT,
              confidence REAL,
              needs_review INTEGER,
              analysis_payload_json TEXT,
              updated_at TEXT
            );
            """
        )
        return conn

    def test_apply_resolved_updates_fields_and_clears_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "apply.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_initiative_doc_extractions(
                      source_record_pk, source_id, extracted_subject, extracted_title,
                      confidence, needs_review, analysis_payload_json, updated_at
                    ) VALUES (1, 'parl_initiative_docs', 'old subject', 'old title', 0.5, 1, '{}', '2026-02-22T00:00:00Z')
                    """
                )
                conn.commit()

                result = apply_review_decisions(
                    conn,
                    source_id="parl_initiative_docs",
                    rows=[
                        {
                            "source_record_pk": "1",
                            "review_status": "resolved",
                            "final_subject": "new subject",
                            "final_title": "new title",
                            "final_confidence": "0.93",
                            "review_note": "looks good",
                            "reviewer": "agent-l2",
                        }
                    ],
                    dry_run=False,
                )

                self.assertEqual(int(result["updated"]), 1)
                row = conn.execute(
                    "SELECT extracted_subject, extracted_title, confidence, needs_review, analysis_payload_json FROM parl_initiative_doc_extractions WHERE source_record_pk = 1"
                ).fetchone()
                self.assertEqual(str(row["extracted_subject"]), "new subject")
                self.assertEqual(str(row["extracted_title"]), "new title")
                self.assertAlmostEqual(float(row["confidence"]), 0.93, places=6)
                self.assertEqual(int(row["needs_review"]), 0)
                payload = json.loads(str(row["analysis_payload_json"]))
                self.assertEqual(str(payload.get("review_status")), "resolved")
            finally:
                conn.close()

    def test_apply_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "apply_dry.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_initiative_doc_extractions(
                      source_record_pk, source_id, extracted_subject, extracted_title,
                      confidence, needs_review, analysis_payload_json, updated_at
                    ) VALUES (2, 'parl_initiative_docs', 'old', 'old', 0.5, 1, '{}', '2026-02-22T00:00:00Z')
                    """
                )
                conn.commit()

                result = apply_review_decisions(
                    conn,
                    source_id="parl_initiative_docs",
                    rows=[
                        {
                            "source_record_pk": "2",
                            "review_status": "ignored",
                            "review_note": "skip",
                        }
                    ],
                    dry_run=True,
                )
                self.assertEqual(int(result["updated"]), 1)

                row = conn.execute(
                    "SELECT needs_review, extracted_subject FROM parl_initiative_doc_extractions WHERE source_record_pk = 2"
                ).fetchone()
                self.assertEqual(int(row["needs_review"]), 1)
                self.assertEqual(str(row["extracted_subject"]), "old")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
