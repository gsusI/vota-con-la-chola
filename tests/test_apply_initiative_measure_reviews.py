from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.apply_initiative_measure_reviews import apply_review_results
from scripts.measure_scale_layer import candidate_id_from_measure_point_id, cluster_id_from_normalized_key


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
            CREATE TABLE parl_initiative_text_versions (
              initiative_text_version_id TEXT PRIMARY KEY,
              initiative_id TEXT NOT NULL,
              published_date TEXT,
              version_order INTEGER
            );
            CREATE TABLE parl_vote_event_text_versions (
              parl_vote_event_text_version_id INTEGER PRIMARY KEY AUTOINCREMENT,
              vote_event_id TEXT NOT NULL,
              initiative_id TEXT NOT NULL,
              initiative_text_version_id TEXT NOT NULL,
              link_method TEXT NOT NULL,
              confidence REAL,
              is_primary INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE parl_text_fragments (
              fragment_id TEXT PRIMARY KEY,
              initiative_text_version_id TEXT NOT NULL,
              initiative_id TEXT NOT NULL,
              source_id TEXT NOT NULL,
              source_record_pk INTEGER,
              fragment_order INTEGER NOT NULL,
              fragment_kind TEXT NOT NULL,
              fragment_label TEXT,
              char_start INTEGER,
              char_end INTEGER,
              fragment_text TEXT NOT NULL,
              text_hash TEXT,
              raw_payload_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE parl_measure_candidates (
              measure_candidate_id TEXT PRIMARY KEY,
              initiative_id TEXT NOT NULL,
              source_id TEXT NOT NULL,
              initiative_text_version_id TEXT,
              fragment_id TEXT,
              source_measure_point_id TEXT,
              candidate_origin TEXT NOT NULL,
              extraction_method TEXT,
              effect_type TEXT NOT NULL,
              risk_level TEXT NOT NULL,
              measure_title TEXT NOT NULL,
              citizen_summary TEXT NOT NULL,
              normalized_key TEXT NOT NULL,
              affected_groups TEXT,
              policy_area TEXT,
              measure_kind TEXT,
              search_terms_json TEXT NOT NULL DEFAULT '[]',
              primary_vote_event_ids_json TEXT NOT NULL DEFAULT '[]',
              support_side TEXT,
              evidence_json TEXT NOT NULL DEFAULT '[]',
              confidence REAL,
              status TEXT NOT NULL DEFAULT 'candidate',
              raw_payload_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE parl_measure_clusters (
              measure_cluster_id TEXT PRIMARY KEY,
              cluster_slug TEXT NOT NULL UNIQUE,
              canonical_title TEXT NOT NULL,
              canonical_summary TEXT NOT NULL,
              normalized_key TEXT NOT NULL,
              effect_type TEXT NOT NULL,
              risk_level TEXT NOT NULL,
              policy_area TEXT,
              measure_kind TEXT,
              aliases_json TEXT NOT NULL DEFAULT '[]',
              search_terms_json TEXT NOT NULL DEFAULT '[]',
              confidence REAL,
              publish_status TEXT NOT NULL DEFAULT 'candidate',
              raw_payload_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE parl_measure_candidate_cluster_links (
              candidate_cluster_link_id INTEGER PRIMARY KEY AUTOINCREMENT,
              measure_candidate_id TEXT NOT NULL,
              measure_cluster_id TEXT NOT NULL,
              link_method TEXT NOT NULL,
              confidence REAL,
              is_primary INTEGER NOT NULL DEFAULT 1,
              raw_payload_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE (measure_candidate_id, measure_cluster_id)
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
                conn.execute(
                    """
                    INSERT INTO parl_initiative_text_versions(
                      initiative_text_version_id, initiative_id, published_date, version_order
                    ) VALUES ('v1', 'i1', '2026-03-01', 1)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_event_text_versions(
                      vote_event_id, initiative_id, initiative_text_version_id, link_method, confidence, is_primary
                    ) VALUES ('v1', 'i1', 'v1', 'single_version', 1.0, 1)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_text_fragments(
                      fragment_id, initiative_text_version_id, initiative_id, source_id, fragment_order,
                      fragment_kind, fragment_label, char_start, char_end, fragment_text, text_hash,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (
                      'f1', 'v1', 'i1', 'congreso_iniciativas', 1, 'article', 'Artículo 1', 0, 120,
                      'Artículo 1. Se permiten zonas de bajas emisiones con restricciones de acceso para vehículos más contaminantes.',
                      'hash1', '{}', '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_measure_points(
                      measure_point_id, task_id, initiative_id, source_id, measure_rank, measure_title,
                      citizen_summary, search_terms_json, primary_vote_event_ids_json, support_side,
                      evidence_json, created_at, updated_at
                    ) VALUES (
                      'old-point', 'i1', 'i1', 'congreso_iniciativas', 1,
                      'Medida antigua',
                      'Texto viejo.',
                      '[]',
                      '["v1"]',
                      'yes',
                      '[]',
                      '2026-03-12T00:00:00+00:00',
                      '2026-03-12T00:00:00+00:00'
                    )
                    """
                )
                old_cluster_id = cluster_id_from_normalized_key("medida antigua|unknown")
                conn.execute(
                    """
                    INSERT INTO parl_measure_candidates(
                      measure_candidate_id, initiative_id, source_id, initiative_text_version_id, fragment_id,
                      source_measure_point_id, candidate_origin, extraction_method, effect_type, risk_level,
                      measure_title, citizen_summary, normalized_key, search_terms_json, primary_vote_event_ids_json,
                      support_side, evidence_json, confidence, status, raw_payload_json, created_at, updated_at
                    ) VALUES (
                      ?, 'i1', 'congreso_iniciativas', 'v1', 'f1', 'old-point', 'reviewed_point',
                      'seed_reviewed_point_v1', 'unknown', 'low', 'Medida antigua', 'Texto viejo.',
                      'medida antigua|unknown', '[]', '["v1"]', 'yes', '[]', 1.0, 'promoted', '{}',
                      '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00'
                    )
                    """,
                    (candidate_id_from_measure_point_id("old-point"),),
                )
                conn.execute(
                    """
                    INSERT INTO parl_measure_clusters(
                      measure_cluster_id, cluster_slug, canonical_title, canonical_summary, normalized_key,
                      effect_type, risk_level, aliases_json, search_terms_json, confidence, publish_status,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (
                      ?, 'medida-antigua-12345678', 'Medida antigua', 'Texto viejo.', 'medida antigua|unknown',
                      'unknown', 'low', '["Medida antigua"]', '["Medida antigua"]', 1.0, 'published', '{}',
                      '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00'
                    )
                    """,
                    (old_cluster_id,),
                )
                conn.execute(
                    """
                    INSERT INTO parl_measure_candidate_cluster_links(
                      measure_candidate_id, measure_cluster_id, link_method, confidence, is_primary,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (?, ?, 'seed_exact', 1.0, 1, '{}', '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00')
                    """,
                    (candidate_id_from_measure_point_id("old-point"), old_cluster_id),
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

                old_candidate = conn.execute(
                    """
                    SELECT 1
                    FROM parl_measure_candidates
                    WHERE measure_candidate_id = ?
                    """,
                    (candidate_id_from_measure_point_id("old-point"),),
                ).fetchone()
                self.assertIsNone(old_candidate)

                candidate = conn.execute(
                    """
                    SELECT measure_title, effect_type, fragment_id, source_measure_point_id
                    FROM parl_measure_candidates
                    WHERE initiative_id='i1'
                    """
                ).fetchone()
                self.assertIn("bajas emisiones", str(candidate["measure_title"]).lower())
                self.assertEqual(str(candidate["effect_type"]), "restriction")
                self.assertEqual(str(candidate["fragment_id"]), "f1")
                self.assertNotEqual(str(candidate["source_measure_point_id"]), "old-point")

                cluster = conn.execute(
                    """
                    SELECT canonical_title, publish_status
                    FROM parl_measure_clusters
                    """
                ).fetchone()
                self.assertIn("bajas emisiones", str(cluster["canonical_title"]).lower())
                self.assertEqual(str(cluster["publish_status"]), "published")

                self.assertEqual(result["scale_layer_cleanup"]["candidates_deleted"], 1)
                self.assertEqual(result["scale_layer_sync"]["measure_points_seen"], 1)
                self.assertEqual(result["scale_layer_sync"]["fragments_matched"], 1)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
