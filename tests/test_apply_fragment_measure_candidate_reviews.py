from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.apply_fragment_measure_candidate_reviews import apply_fragment_review_results


class TestApplyFragmentMeasureCandidateReviews(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
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
            CREATE TABLE parl_fragment_measure_reviews (
              fragment_id TEXT PRIMARY KEY,
              initiative_id TEXT NOT NULL,
              initiative_text_version_id TEXT NOT NULL,
              source_id TEXT NOT NULL,
              status TEXT NOT NULL,
              note TEXT,
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
            CREATE TABLE parl_measure_candidate_reviews (
              candidate_review_id INTEGER PRIMARY KEY AUTOINCREMENT,
              review_key TEXT NOT NULL UNIQUE,
              measure_candidate_id TEXT NOT NULL,
              measure_cluster_id TEXT,
              review_reason TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              note TEXT,
              raw_payload_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )
        return conn

    def test_apply_fragment_result_replaces_old_fragment_candidates_and_routes_high_risk_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "fragment_apply.db"
            result_dir = Path(td) / "results"
            result_dir.mkdir()
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_text_fragments(
                      fragment_id, initiative_text_version_id, initiative_id, source_id, fragment_order,
                      fragment_kind, fragment_label, char_start, char_end, fragment_text, text_hash,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (
                      'frag-1', 'v1', 'i1', 'congreso_iniciativas', 1, 'article', 'Artículo 1', 0, 120,
                      'Artículo 1. Se podrán restringir coches diésel en zonas de bajas emisiones.',
                      'hash-1', '{}', '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_measure_candidates(
                      measure_candidate_id, initiative_id, source_id, initiative_text_version_id, fragment_id,
                      candidate_origin, extraction_method, effect_type, risk_level, measure_title,
                      citizen_summary, normalized_key, search_terms_json, primary_vote_event_ids_json,
                      support_side, evidence_json, confidence, status, raw_payload_json, created_at, updated_at
                    ) VALUES (
                      'old-cand', 'i1', 'congreso_iniciativas', 'v1', 'frag-1',
                      'fragment_model', 'fragment_worker_v1', 'unknown', 'low', 'Medida vieja',
                      'Texto viejo', 'medida vieja|unknown', '[]', '[]', 'unknown', '[]', 0.5, 'candidate',
                      '{}', '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_measure_clusters(
                      measure_cluster_id, cluster_slug, canonical_title, canonical_summary, normalized_key,
                      effect_type, risk_level, aliases_json, search_terms_json, confidence, publish_status,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (
                      'old-cluster', 'medida-vieja-12345678', 'Medida vieja', 'Texto viejo', 'medida vieja|unknown',
                      'unknown', 'low', '["Medida vieja"]', '["Medida vieja"]', 0.5, 'candidate', '{}',
                      '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_measure_candidate_cluster_links(
                      measure_candidate_id, measure_cluster_id, link_method, confidence, is_primary,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (
                      'old-cand', 'old-cluster', 'title_norm_exact', 0.5, 1, '{}',
                      '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00'
                    )
                    """
                )
                conn.commit()

                (result_dir / "frag-1.json").write_text(
                    json.dumps(
                        {
                            "task_id": "frag-1",
                            "review_status": "resolved",
                            "review_note": "usable fragment",
                            "reviewer": "worker-frag",
                            "candidates": [
                                {
                                    "measure_title": "Restricciones a coches diésel en zonas de bajas emisiones",
                                    "citizen_summary": "Permite limitar la circulación de coches diésel en áreas urbanas con bajas emisiones.",
                                    "effect_type": "restriction",
                                    "risk_level": "high",
                                    "affected_groups": "conductores",
                                    "policy_area": "movilidad",
                                    "measure_kind": "restricción urbana",
                                    "primary_vote_event_ids": ["vote-1"],
                                    "support_side": "yes",
                                    "search_terms": ["coches diésel", "bajas emisiones"],
                                    "evidence": [
                                        {
                                            "quote": "Se podrán restringir coches diésel en zonas de bajas emisiones.",
                                            "fragment_id": "frag-1",
                                            "fragment_label": "Artículo 1"
                                        }
                                    ]
                                }
                            ]
                        },
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )

                result = apply_fragment_review_results(
                    conn,
                    result_files=[result_dir / "frag-1.json"],
                    source_id="congreso_iniciativas",
                    dry_run=False,
                )
                self.assertEqual(result["fragments_updated"], 1)
                self.assertEqual(result["candidates_written"], 1)
                self.assertEqual(result["candidate_reviews_written"], 1)
                self.assertEqual(result["purge_summary"]["candidates_deleted"], 1)

                old_candidate = conn.execute(
                    "SELECT 1 FROM parl_measure_candidates WHERE measure_candidate_id='old-cand'"
                ).fetchone()
                self.assertIsNone(old_candidate)

                fragment_status = conn.execute(
                    "SELECT status, note FROM parl_fragment_measure_reviews WHERE fragment_id='frag-1'"
                ).fetchone()
                self.assertEqual(str(fragment_status["status"]), "resolved")
                self.assertEqual(str(fragment_status["note"]), "usable fragment")

                candidate = conn.execute(
                    """
                    SELECT candidate_origin, effect_type, risk_level, fragment_id, status
                    FROM parl_measure_candidates
                    WHERE fragment_id='frag-1'
                    """
                ).fetchone()
                self.assertEqual(str(candidate["candidate_origin"]), "fragment_model")
                self.assertEqual(str(candidate["effect_type"]), "restriction")
                self.assertEqual(str(candidate["risk_level"]), "high")
                self.assertEqual(str(candidate["fragment_id"]), "frag-1")
                self.assertEqual(str(candidate["status"]), "candidate")

                cluster = conn.execute(
                    """
                    SELECT publish_status, canonical_title
                    FROM parl_measure_clusters
                    """
                ).fetchone()
                self.assertEqual(str(cluster["publish_status"]), "review_required")
                self.assertIn("diésel", str(cluster["canonical_title"]).lower())

                review_row = conn.execute(
                    """
                    SELECT review_reason, status
                    FROM parl_measure_candidate_reviews
                    """
                ).fetchone()
                self.assertEqual(str(review_row["review_reason"]), "high_risk")
                self.assertEqual(str(review_row["status"]), "pending")
            finally:
                conn.close()

    def test_apply_fragment_result_accepts_filesystem_safe_pfrag_evidence_ids(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "fragment_apply.db"
            result_dir = Path(td) / "results"
            result_dir.mkdir()
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_text_fragments(
                      fragment_id, initiative_text_version_id, initiative_id, source_id, fragment_order,
                      fragment_kind, fragment_label, char_start, char_end, fragment_text, text_hash,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (
                      'pfrag:abc123', 'v1', 'i1', 'parl_initiative_docs', 1, 'article', 'Artículo 1', 0, 120,
                      'Artículo 1. Se reducen impuestos autonómicos.',
                      'hash-1', '{}', '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00'
                    )
                    """
                )
                conn.commit()

                (result_dir / "pfrag-abc123.json").write_text(
                    json.dumps(
                        {
                            "task_id": "pfrag:abc123",
                            "review_status": "resolved",
                            "review_note": "usable fragment",
                            "reviewer": "worker-frag",
                            "candidates": [
                                {
                                    "measure_title": "Reduccion de impuestos autonomicos",
                                    "citizen_summary": "Permite bajar impuestos de la comunidad autonoma.",
                                    "effect_type": "tax",
                                    "risk_level": "low",
                                    "affected_groups": "contribuyentes",
                                    "policy_area": "hacienda",
                                    "measure_kind": "article",
                                    "primary_vote_event_ids": ["vote-1"],
                                    "support_side": "yes",
                                    "search_terms": ["impuestos autonomicos"],
                                    "evidence": [
                                        {
                                            "quote": "Se reducen impuestos autonómicos.",
                                            "fragment_id": "pfrag-abc123",
                                            "fragment_label": "Artículo 1"
                                        }
                                    ]
                                }
                            ]
                        },
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )

                result = apply_fragment_review_results(
                    conn,
                    result_files=[result_dir / "pfrag-abc123.json"],
                    source_id="parl_initiative_docs",
                    dry_run=False,
                )
                self.assertEqual(result["fragments_updated"], 1)
                self.assertEqual(result["skipped_invalid_candidate"], 0)

                candidate = conn.execute(
                    """
                    SELECT fragment_id, evidence_json
                    FROM parl_measure_candidates
                    WHERE fragment_id='pfrag:abc123'
                    """
                ).fetchone()
                self.assertIsNotNone(candidate)
                self.assertEqual(str(candidate["fragment_id"]), "pfrag:abc123")
                evidence = json.loads(str(candidate["evidence_json"]))
                self.assertEqual(evidence[0]["fragment_id"], "pfrag:abc123")
            finally:
                conn.close()

    def test_apply_fragment_result_recovers_sibling_fragment_from_quote_match(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "fragment_apply.db"
            result_dir = Path(td) / "results"
            result_dir.mkdir()
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_text_fragments(
                      fragment_id, initiative_text_version_id, initiative_id, source_id, fragment_order,
                      fragment_kind, fragment_label, char_start, char_end, fragment_text, text_hash,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (
                      'pfrag:main', 'v1', 'i1', 'parl_initiative_docs', 1, 'chunk', 'Chunk 1', 0, 120,
                      'Texto base sobre la norma.', 'hash-1', '{}',
                      '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_text_fragments(
                      fragment_id, initiative_text_version_id, initiative_id, source_id, fragment_order,
                      fragment_kind, fragment_label, char_start, char_end, fragment_text, text_hash,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (
                      'pfrag:sibling', 'v1', 'i1', 'parl_initiative_docs', 2, 'chunk', 'Chunk 2', 121, 260,
                      'La informacion anterior debera constar tambien en las condiciones generales del contrato.',
                      'hash-2', '{}', '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00'
                    )
                    """
                )
                conn.commit()

                (result_dir / "pfrag-main.json").write_text(
                    json.dumps(
                        {
                            "task_id": "pfrag:main",
                            "review_status": "resolved",
                            "review_note": "usable fragment",
                            "reviewer": "worker-frag",
                            "candidates": [
                                {
                                    "measure_title": "Informacion obligatoria en el contrato",
                                    "citizen_summary": "La empresa debe incluir esta informacion en el contrato.",
                                    "effect_type": "obligation",
                                    "risk_level": "low",
                                    "affected_groups": "consumidores",
                                    "policy_area": "consumo",
                                    "measure_kind": "chunk",
                                    "primary_vote_event_ids": ["vote-1"],
                                    "support_side": "yes",
                                    "search_terms": ["contrato", "informacion"],
                                    "evidence": [
                                        {
                                            "quote": "La informacion anterior debera constar tambien en las condiciones generales del contrato.",
                                            "fragment_id": "pfrag:siblign",
                                            "fragment_label": "Chunk 2"
                                        }
                                    ]
                                }
                            ]
                        },
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )

                result = apply_fragment_review_results(
                    conn,
                    result_files=[result_dir / "pfrag-main.json"],
                    source_id="parl_initiative_docs",
                    dry_run=False,
                )
                self.assertEqual(result["fragments_updated"], 1)
                self.assertEqual(result["skipped_invalid_candidate"], 0)

                candidate = conn.execute(
                    """
                    SELECT evidence_json
                    FROM parl_measure_candidates
                    WHERE fragment_id='pfrag:main'
                    """
                ).fetchone()
                self.assertIsNotNone(candidate)
                evidence = json.loads(str(candidate["evidence_json"]))
                self.assertEqual(evidence[0]["fragment_id"], "pfrag:sibling")
            finally:
                conn.close()

    def test_apply_fragment_result_recovers_sibling_fragment_from_label_match(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "fragment_apply.db"
            result_dir = Path(td) / "results"
            result_dir.mkdir()
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_text_fragments(
                      fragment_id, initiative_text_version_id, initiative_id, source_id, fragment_order,
                      fragment_kind, fragment_label, char_start, char_end, fragment_text, text_hash,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (
                      'pfrag:main', 'v1', 'i1', 'parl_initiative_docs', 1, 'chunk', 'Chunk 1', 0, 120,
                      'Texto base sobre la norma.', 'hash-1', '{}',
                      '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_text_fragments(
                      fragment_id, initiative_text_version_id, initiative_id, source_id, fragment_order,
                      fragment_kind, fragment_label, char_start, char_end, fragment_text, text_hash,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (
                      'pfrag:sibling', 'v1', 'i1', 'parl_initiative_docs', 2, 'chunk', 'Chunk 8', 121, 260,
                      'Debiendo constar tambien en las condiciones generales de los contratos de compraventa o de prestacion de servicios que el empresario ofrezca al consumidor.',
                      'hash-2', '{}', '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00'
                    )
                    """
                )
                conn.commit()

                (result_dir / "pfrag-main.json").write_text(
                    json.dumps(
                        {
                            "task_id": "pfrag:main",
                            "review_status": "resolved",
                            "review_note": "usable fragment",
                            "reviewer": "worker-frag",
                            "candidates": [
                                {
                                    "measure_title": "Informacion obligatoria en el contrato",
                                    "citizen_summary": "La empresa debe incluir esta informacion en el contrato.",
                                    "effect_type": "obligation",
                                    "risk_level": "low",
                                    "affected_groups": "consumidores",
                                    "policy_area": "consumo",
                                    "measure_kind": "chunk",
                                    "primary_vote_event_ids": ["vote-1"],
                                    "support_side": "yes",
                                    "search_terms": ["contrato", "informacion"],
                                    "evidence": [
                                        {
                                            "quote": "Debera constar tambien en las condiciones generales de los contratos de compraventa o de prestacion de servicios que el empresario ofrezca al consumidor.",
                                            "fragment_id": "pfrag:siblign",
                                            "fragment_label": "Chunk 8"
                                        }
                                    ]
                                }
                            ]
                        },
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )

                result = apply_fragment_review_results(
                    conn,
                    result_files=[result_dir / "pfrag-main.json"],
                    source_id="parl_initiative_docs",
                    dry_run=False,
                )
                self.assertEqual(result["fragments_updated"], 1)
                self.assertEqual(result["skipped_invalid_candidate"], 0)

                candidate = conn.execute(
                    """
                    SELECT evidence_json
                    FROM parl_measure_candidates
                    WHERE fragment_id='pfrag:main'
                    """
                ).fetchone()
                self.assertIsNotNone(candidate)
                evidence = json.loads(str(candidate["evidence_json"]))
                self.assertEqual(evidence[0]["fragment_id"], "pfrag:sibling")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
