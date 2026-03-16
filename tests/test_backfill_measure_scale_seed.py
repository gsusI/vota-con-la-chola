from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.measure_scale_layer import seed_measure_scale_layer


class TestBackfillMeasureScaleSeed(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
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
              note TEXT
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

    def test_seed_scale_layer_creates_candidate_cluster_and_link(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "scale_seed.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_initiative_measure_points(
                      measure_point_id, task_id, initiative_id, source_id, measure_rank, measure_title,
                      citizen_summary, affected_groups, policy_area, measure_kind, measure_status,
                      search_terms_json, primary_vote_event_ids_json, support_side, support_explanation,
                      evidence_json, note
                    ) VALUES (
                      'mp1', 'task-1', 'i1', 'congreso_iniciativas', 1,
                      'Restricciones de acceso en zonas de bajas emisiones',
                      'La ley permite limitar la circulación de vehículos contaminantes en la ciudad.',
                      'conductores', 'movilidad', 'restricciones urbanas', 'approved',
                      '["bajas emisiones", "restriccion de acceso"]',
                      '["vote-1"]',
                      'yes',
                      'Un sí mantiene el texto.',
                      '[{"quote":"zona de bajas emisiones"}]',
                      'seed'
                    )
                    """
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
                    ) VALUES ('vote-1', 'i1', 'v1', 'single_version', 1.0, 1)
                    """
                )
                conn.executemany(
                    """
                    INSERT INTO parl_text_fragments(
                      fragment_id, initiative_text_version_id, initiative_id, source_id, fragment_order,
                      fragment_kind, fragment_label, char_start, char_end, fragment_text, text_hash,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (?, 'v1', 'i1', 'congreso_iniciativas', ?, 'article', ?, 0, 100, ?, ?, '{}',
                              '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00')
                    """,
                    [
                        (
                            "frag-1",
                            1,
                            "Artículo 1",
                            "Artículo 1. Los ayuntamientos podrán restringir el acceso en zonas de bajas emisiones.",
                            "hash-1",
                        ),
                        (
                            "frag-2",
                            2,
                            "Artículo 2",
                            "Artículo 2. Se regula la financiación del transporte público.",
                            "hash-2",
                        ),
                    ],
                )
                conn.commit()

                with conn:
                    result = seed_measure_scale_layer(
                        conn,
                        measure_point_ids=("mp1",),
                        dry_run=False,
                    )

                self.assertTrue(result["schema_ready"])
                self.assertEqual(result["measure_points_seen"], 1)
                self.assertEqual(result["candidate_rows_inserted"], 1)
                self.assertEqual(result["cluster_rows_inserted"], 1)
                self.assertEqual(result["versions_resolved"], 1)
                self.assertEqual(result["fragments_matched"], 1)

                candidate = conn.execute(
                    """
                    SELECT effect_type, risk_level, fragment_id, initiative_text_version_id, status
                    FROM parl_measure_candidates
                    WHERE source_measure_point_id='mp1'
                    """
                ).fetchone()
                self.assertEqual(str(candidate["effect_type"]), "restriction")
                self.assertEqual(str(candidate["risk_level"]), "high")
                self.assertEqual(str(candidate["fragment_id"]), "frag-1")
                self.assertEqual(str(candidate["initiative_text_version_id"]), "v1")
                self.assertEqual(str(candidate["status"]), "promoted")

                cluster = conn.execute(
                    """
                    SELECT canonical_title, publish_status, aliases_json
                    FROM parl_measure_clusters
                    """
                ).fetchone()
                self.assertIn("bajas emisiones", str(cluster["canonical_title"]).lower())
                self.assertEqual(str(cluster["publish_status"]), "published")
                self.assertIn("Restricciones de acceso", str(cluster["aliases_json"]))

                link = conn.execute(
                    """
                    SELECT link_method, is_primary
                    FROM parl_measure_candidate_cluster_links
                    """
                ).fetchone()
                self.assertEqual(str(link["link_method"]), "seed_exact")
                self.assertEqual(int(link["is_primary"]), 1)
            finally:
                conn.close()

    def test_seed_scale_layer_uses_evidence_quotes_to_match_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "scale_seed_quotes.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_initiative_measure_points(
                      measure_point_id, task_id, initiative_id, source_id, measure_rank, measure_title,
                      citizen_summary, affected_groups, policy_area, measure_kind, measure_status,
                      search_terms_json, primary_vote_event_ids_json, support_side, support_explanation,
                      evidence_json, note
                    ) VALUES (
                      'mpq1', 'task-q1', 'iq1', 'senado_iniciativas', 1,
                      'Impuesto sobre servicios digitales',
                      'La medida grava determinados servicios digitales de grandes empresas.',
                      '', 'tributaria', 'ley tributaria', 'approved',
                      '[]',
                      '["vote-q1"]',
                      'yes',
                      '',
                      '[{"quote":"prestacion de determinados servicios digitales en territorio espanol"}]',
                      'seed'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_text_versions(
                      initiative_text_version_id, initiative_id, published_date, version_order
                    ) VALUES ('vq1', 'iq1', '2026-03-01', 1)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_event_text_versions(
                      vote_event_id, initiative_id, initiative_text_version_id, link_method, confidence, is_primary
                    ) VALUES ('vote-q1', 'iq1', 'vq1', 'single_version', 1.0, 1)
                    """
                )
                conn.executemany(
                    """
                    INSERT INTO parl_text_fragments(
                      fragment_id, initiative_text_version_id, initiative_id, source_id, fragment_order,
                      fragment_kind, fragment_label, char_start, char_end, fragment_text, text_hash,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (?, 'vq1', 'iq1', 'senado_iniciativas', ?, 'article', ?, 0, 100, ?, ?, '{}',
                              '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00')
                    """,
                    [
                        (
                            "frag-q1-a",
                            1,
                            "Artículo 1",
                            "Artículo 1. Este título regula la prestación de determinados servicios digitales en territorio español.",
                            "hash-q1-a",
                        ),
                        (
                            "frag-q1-b",
                            2,
                            "Artículo 2",
                            "Artículo 2. Disposición general sobre coordinación administrativa.",
                            "hash-q1-b",
                        ),
                    ],
                )
                conn.commit()

                with conn:
                    result = seed_measure_scale_layer(
                        conn,
                        measure_point_ids=("mpq1",),
                        dry_run=False,
                    )

                self.assertEqual(result["versions_resolved"], 1)
                self.assertEqual(result["fragments_matched"], 1)
                candidate = conn.execute(
                    """
                    SELECT fragment_id
                    FROM parl_measure_candidates
                    WHERE source_measure_point_id='mpq1'
                    """
                ).fetchone()
                self.assertEqual(str(candidate["fragment_id"]), "frag-q1-a")
            finally:
                conn.close()

    def test_seed_scale_layer_can_fallback_to_other_initiative_version_for_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "scale_seed_fragment_fallback.db"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_initiative_measure_points(
                      measure_point_id, task_id, initiative_id, source_id, measure_rank, measure_title,
                      citizen_summary, affected_groups, policy_area, measure_kind, measure_status,
                      search_terms_json, primary_vote_event_ids_json, support_side, support_explanation,
                      evidence_json, note
                    ) VALUES (
                      'mpf1', 'task-f1', 'if1', 'senado_iniciativas', 1,
                      'Gravamen temporal en el sector energético',
                      'La medida crea un gravamen temporal sobre ingresos extraordinarios del sector energético.',
                      '', 'tributaria', 'ley tributaria', 'approved',
                      '["gravamen temporal", "sector energetico"]',
                      '["vote-f1"]',
                      'yes',
                      '',
                      '[]',
                      'seed'
                    )
                    """
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_text_versions(
                      initiative_text_version_id, initiative_id, published_date, version_order
                    ) VALUES (?, 'if1', ?, ?)
                    """,
                    [
                        ("vf1-amend", "2022-12-21", 2),
                        ("vf1-text", "2022-12-01", 1),
                    ],
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_event_text_versions(
                      vote_event_id, initiative_id, initiative_text_version_id, link_method, confidence, is_primary
                    ) VALUES ('vote-f1', 'if1', 'vf1-amend', 'single_version', 0.75, 1)
                    """
                )
                conn.executemany(
                    """
                    INSERT INTO parl_text_fragments(
                      fragment_id, initiative_text_version_id, initiative_id, source_id, fragment_order,
                      fragment_kind, fragment_label, char_start, char_end, fragment_text, text_hash,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (?, ?, 'if1', 'senado_iniciativas', ?, 'chunk', ?, 0, 100, ?, ?, '{}',
                              '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00')
                    """,
                    [
                        (
                            "frag-f1-a",
                            "vf1-amend",
                            1,
                            "Chunk 1",
                            "Propuestas de veto y total de enmiendas.",
                            "hash-f1-a",
                        ),
                        (
                            "frag-f1-b",
                            "vf1-text",
                            1,
                            "Chunk 1",
                            "Artículo 1. Se establece un gravamen temporal sobre los ingresos extraordinarios del sector energético.",
                            "hash-f1-b",
                        ),
                    ],
                )
                conn.commit()

                with conn:
                    result = seed_measure_scale_layer(
                        conn,
                        measure_point_ids=("mpf1",),
                        dry_run=False,
                    )

                self.assertEqual(result["versions_resolved"], 1)
                self.assertEqual(result["fragments_matched"], 1)
                candidate = conn.execute(
                    """
                    SELECT initiative_text_version_id, fragment_id, raw_payload_json
                    FROM parl_measure_candidates
                    WHERE source_measure_point_id='mpf1'
                    """
                ).fetchone()
                self.assertEqual(str(candidate["initiative_text_version_id"]), "vf1-amend")
                self.assertEqual(str(candidate["fragment_id"]), "frag-f1-b")
                payload = json.loads(str(candidate["raw_payload_json"] or "{}"))
                self.assertEqual(str(payload.get("fragment_match_scope")), "initiative_fallback")
                self.assertEqual(str(payload.get("fragment_initiative_text_version_id")), "vf1-text")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
