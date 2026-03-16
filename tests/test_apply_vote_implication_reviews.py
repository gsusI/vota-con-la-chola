from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.apply_vote_implication_reviews import apply_review_decisions


class TestApplyVoteImplicationReviews(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE parl_vote_implication_reviews (
              review_id INTEGER PRIMARY KEY AUTOINCREMENT,
              review_key TEXT NOT NULL UNIQUE,
              vote_event_id TEXT NOT NULL,
              initiative_id TEXT,
              source_id TEXT NOT NULL,
              review_reason TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              priority INTEGER NOT NULL DEFAULT 50,
              heuristic_subject TEXT,
              heuristic_implication_kind TEXT,
              heuristic_binding_strength TEXT,
              citizen_title TEXT,
              citizen_question TEXT,
              citizen_summary TEXT,
              impact_if_approved TEXT,
              impact_if_rejected TEXT,
              affected_groups TEXT,
              evidence_quote TEXT,
              final_implication_kind TEXT,
              final_binding_strength TEXT,
              confidence REAL,
              extractor_version TEXT,
              note TEXT,
              raw_payload_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        return conn

    def test_apply_review_decisions_updates_row_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "apply_vote_queue.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_vote_implication_reviews(
                      review_key, vote_event_id, initiative_id, source_id, review_reason, status,
                      priority, heuristic_subject, heuristic_implication_kind, heuristic_binding_strength,
                      extractor_version, raw_payload_json, created_at, updated_at
                    ) VALUES (
                      'v1|i1', 'v1', 'i1', 'congreso_votaciones', 'split_vote_point', 'pending',
                      95, 'Tema vivienda', 'non_binding_motion', 'non_binding',
                      'citizen_vote_implication_v1', '{}', '2026-03-08T00:00:00+00:00', '2026-03-08T00:00:00+00:00'
                    )
                    """
                )
                conn.commit()

                result = apply_review_decisions(
                    conn,
                    rows=[
                        {
                            "review_key": "v1|i1",
                            "review_status": "resolved",
                            "final_implication_kind": "non_binding_motion",
                            "final_binding_strength": "non_binding",
                            "citizen_title": "Más presión pública sobre vivienda",
                            "citizen_question": "¿Debe el Congreso pedir más intervención pública en vivienda?",
                            "citizen_summary": "No cambia la ley por sí solo, pero fija una posición política clara.",
                            "impact_if_approved": "Refuerza la presión parlamentaria a favor de esa línea.",
                            "impact_if_rejected": "Deja sin apoyo esa dirección política específica.",
                            "affected_groups": "Hogares con problemas de acceso a vivienda",
                            "evidence_quote": "medidas fiscales, regulatorias y de adquisición pública",
                            "final_confidence": "0.91",
                            "review_note": "ok",
                            "reviewer": "agent-test",
                        }
                    ],
                    source_id="congreso_votaciones",
                    dry_run=False,
                )
                self.assertEqual(result["updated"], 1)

                row = conn.execute(
                    """
                    SELECT status, citizen_title, final_implication_kind, final_binding_strength,
                           confidence, note, raw_payload_json
                    FROM parl_vote_implication_reviews
                    WHERE review_key = 'v1|i1'
                    """
                ).fetchone()
                self.assertEqual(str(row["status"]), "resolved")
                self.assertEqual(str(row["citizen_title"]), "Más presión pública sobre vivienda")
                self.assertEqual(str(row["final_implication_kind"]), "non_binding_motion")
                self.assertEqual(str(row["final_binding_strength"]), "non_binding")
                self.assertAlmostEqual(float(row["confidence"]), 0.91, places=2)
                self.assertEqual(str(row["note"]), "ok")
                self.assertIn("review_history", str(row["raw_payload_json"]))
            finally:
                conn.close()

    def test_apply_review_decisions_requires_resolved_text(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "apply_vote_queue_invalid.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_vote_implication_reviews(
                      review_key, vote_event_id, initiative_id, source_id, review_reason, status,
                      priority, extractor_version, raw_payload_json, created_at, updated_at
                    ) VALUES (
                      'v1|', 'v1', NULL, 'congreso_votaciones', 'generic_title', 'pending',
                      70, 'citizen_vote_implication_v1', '{}', '2026-03-08T00:00:00+00:00', '2026-03-08T00:00:00+00:00'
                    )
                    """
                )
                conn.commit()

                result = apply_review_decisions(
                    conn,
                    rows=[
                        {
                            "review_key": "v1|",
                            "review_status": "resolved",
                            "final_implication_kind": "unknown",
                            "final_binding_strength": "unknown",
                        }
                    ],
                    source_id="congreso_votaciones",
                    dry_run=False,
                )
                self.assertEqual(result["updated"], 0)
                row = conn.execute(
                    "SELECT status FROM parl_vote_implication_reviews WHERE review_key='v1|'"
                ).fetchone()
                self.assertEqual(str(row["status"]), "pending")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
