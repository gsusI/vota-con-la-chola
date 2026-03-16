from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.export_fragment_measure_candidate_queue import fetch_fragment_review_rows, write_fragment_bundle


class TestExportFragmentMeasureCandidateQueue(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE parl_initiatives (
              initiative_id TEXT PRIMARY KEY,
              source_id TEXT NOT NULL,
              expediente TEXT,
              title TEXT,
              type TEXT,
              supertype TEXT,
              procedure_type TEXT,
              current_status TEXT,
              source_url TEXT
            );
            CREATE TABLE parl_initiative_text_versions (
              initiative_text_version_id TEXT PRIMARY KEY,
              initiative_id TEXT NOT NULL,
              chamber TEXT,
              doc_kind TEXT,
              document_code TEXT,
              doc_series TEXT,
              doc_number TEXT,
              version_order INTEGER,
              published_date TEXT,
              stage_kind TEXT,
              stage_label TEXT
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
              fragment_id TEXT
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
            CREATE TABLE parl_vote_events (
              vote_event_id TEXT PRIMARY KEY,
              vote_date TEXT,
              source_id TEXT,
              title TEXT,
              subgroup_title TEXT,
              subgroup_text TEXT,
              expediente_text TEXT,
              totals_yes INTEGER,
              totals_no INTEGER,
              totals_abstain INTEGER
            );
            CREATE TABLE parl_vote_event_initiatives (
              parl_vote_event_initiative_id INTEGER PRIMARY KEY AUTOINCREMENT,
              vote_event_id TEXT,
              initiative_id TEXT
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
            CREATE TABLE parl_initiative_measure_points (
              measure_point_id TEXT PRIMARY KEY,
              initiative_id TEXT NOT NULL,
              measure_rank INTEGER NOT NULL DEFAULT 1,
              measure_title TEXT NOT NULL,
              citizen_summary TEXT NOT NULL,
              primary_vote_event_ids_json TEXT NOT NULL DEFAULT '[]'
            );
            """
        )
        return conn

    def test_exporter_filters_claimed_fragments_and_writes_high_effort_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "fragment_queue.db"
            evidence_root = Path(td) / "evidence"
            conn = self._open_db(db_path)
            try:
                conn.execute(
                    """
                    INSERT INTO parl_initiatives(
                      initiative_id, source_id, expediente, title, type, supertype, procedure_type, current_status, source_url
                    ) VALUES (
                      'i1', 'congreso_iniciativas', '121/000009/0000',
                      'Proyecto de Ley de movilidad sostenible.', 'Proyecto de ley', 'Función legislativa',
                      'Normal', 'Cerrado', 'https://example.org/i1'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_text_versions(
                      initiative_text_version_id, initiative_id, chamber, doc_kind, document_code, doc_series,
                      doc_number, version_order, published_date, stage_kind, stage_label
                    ) VALUES (
                      'v1', 'i1', 'congreso', 'bocg', 'BOCG-15-A-9-1', 'A', '9', 1,
                      '2026-01-10', 'initial_text', 'Texto inicial'
                    )
                    """
                )
                conn.executemany(
                    """
                    INSERT INTO parl_text_fragments(
                      fragment_id, initiative_text_version_id, initiative_id, source_id, fragment_order,
                      fragment_kind, fragment_label, char_start, char_end, fragment_text, text_hash,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (?, 'v1', 'i1', 'congreso_iniciativas', ?, ?, ?, 0, 100, ?, ?, '{}',
                              '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00')
                    """,
                    [
                        (
                            "frag-open",
                            1,
                            "article",
                            "Artículo 1",
                            "Artículo 1. Se podrán restringir vehículos diésel en zonas de bajas emisiones urbanas.",
                            "hash-1",
                        ),
                        (
                            "frag-claimed",
                            2,
                            "article",
                            "Artículo 2",
                            "Artículo 2. Se crea una comisión técnica de seguimiento.",
                            "hash-2",
                        ),
                        (
                            "frag-ignored",
                            3,
                            "article",
                            "Artículo 3",
                            "Artículo 3. Se regulan permisos de circulación excepcionales.",
                            "hash-3",
                        ),
                    ],
                )
                conn.execute(
                    "INSERT INTO parl_measure_candidates(measure_candidate_id, fragment_id) VALUES ('cand-1', 'frag-claimed')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_fragment_measure_reviews(
                      fragment_id, initiative_id, initiative_text_version_id, source_id, status, note,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (
                      'frag-ignored', 'i1', 'v1', 'congreso_iniciativas', 'ignored', 'not useful', '{}',
                      '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_events(
                      vote_event_id, vote_date, source_id, title, subgroup_title, subgroup_text,
                      expediente_text, totals_yes, totals_no, totals_abstain
                    ) VALUES (
                      'vote-1', '2026-02-20', 'congreso_votaciones', 'Proyecto de Ley de movilidad sostenible.',
                      'Votación final sobre el conjunto', '', 'Proyecto de Ley de movilidad sostenible.', 180, 150, 10
                    )
                    """
                )
                conn.execute(
                    "INSERT INTO parl_vote_event_initiatives(vote_event_id, initiative_id) VALUES ('vote-1', 'i1')"
                )
                conn.execute(
                    """
                    INSERT INTO parl_vote_event_text_versions(
                      vote_event_id, initiative_id, initiative_text_version_id, link_method, confidence, is_primary
                    ) VALUES ('vote-1', 'i1', 'v1', 'single_version', 1.0, 1)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO parl_initiative_measure_points(
                      measure_point_id, initiative_id, measure_rank, measure_title, citizen_summary, primary_vote_event_ids_json
                    ) VALUES (
                      'mp1', 'i1', 1, 'Medida ya revisada', 'Resumen previo', '["vote-1"]'
                    )
                    """
                )
                conn.commit()

                rows = fetch_fragment_review_rows(
                    conn,
                    initiative_source_ids=("congreso_iniciativas",),
                    fragment_kinds=("article", "disposition", "chunk"),
                    contains_terms=["diésel"],
                    contains_any_terms=[],
                    only_unclaimed=True,
                    min_fragment_chars=40,
                    max_fragment_chars=400,
                    min_priority=0,
                    limit=0,
                    offset=0,
                )
                self.assertEqual(len(rows), 1)
                self.assertEqual(str(rows[0]["fragment_id"]), "frag-open")
                self.assertEqual(int(rows[0]["priority"]) > 0, True)

                bundle_dir = write_fragment_bundle(conn, rows[0], evidence_root=evidence_root)
                bundle = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
                self.assertEqual(bundle["task_id"], "frag-open")
                self.assertEqual(bundle["subagent_hint"]["reasoning_effort"], "high")
                self.assertEqual(bundle["subagent_hint"]["do_not_use_reasoning_effort"], "xhigh")
                self.assertEqual(bundle["recommended_primary_vote_event_ids"], ["vote-1"])
                self.assertEqual(bundle["fragment"]["fragment_id"], "frag-open")
                self.assertEqual(len(bundle["existing_initiative_measures"]), 1)
            finally:
                conn.close()

    def test_exporter_supports_contains_any_min_priority_and_skips_low_signal_fragments(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "fragment_queue.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    """
                    INSERT INTO parl_initiatives(
                      initiative_id, source_id, expediente, title, type, supertype, procedure_type, current_status, source_url
                    ) VALUES (?, 'congreso_iniciativas', ?, ?, 'Proyecto de ley', 'Función legislativa',
                              'Normal', 'Cerrado', 'https://example.org/x')
                    """,
                    [
                        ("i-energy", "121/1", "Medidas sobre energia y movilidad"),
                        ("i-tax", "121/2", "Reforma fiscal para carburantes"),
                        ("i-plan", "121/4", "Plan de movilidad e indicadores"),
                        ("i-treaty", "121/3", "Adenda del convenio internacional"),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_initiative_text_versions(
                      initiative_text_version_id, initiative_id, chamber, doc_kind, document_code, doc_series,
                      doc_number, version_order, published_date, stage_kind, stage_label
                    ) VALUES (?, ?, 'congreso', 'bocg', ?, 'A', ?, 1, '2026-01-10', 'initial_text', 'Texto inicial')
                    """,
                    [
                        ("v-energy", "i-energy", "DOC-1", "1"),
                        ("v-tax", "i-tax", "DOC-2", "2"),
                        ("v-plan", "i-plan", "DOC-4", "4"),
                        ("v-treaty", "i-treaty", "DOC-3", "3"),
                    ],
                )
                conn.executemany(
                    """
                    INSERT INTO parl_text_fragments(
                      fragment_id, initiative_text_version_id, initiative_id, source_id, fragment_order,
                      fragment_kind, fragment_label, char_start, char_end, fragment_text, text_hash,
                      raw_payload_json, created_at, updated_at
                    ) VALUES (?, ?, ?, 'congreso_iniciativas', ?, 'article', ?, 0, 100, ?, ?, '{}',
                              '2026-03-12T00:00:00+00:00', '2026-03-12T00:00:00+00:00')
                    """,
                    [
                        (
                            "frag-energy",
                            "v-energy",
                            "i-energy",
                            1,
                            "Artículo 10",
                            "Artículo 10. Se reduce el coste energético y se flexibilizan contratos eléctricos domésticos.",
                            "hash-energy",
                        ),
                        (
                            "frag-tax",
                            "v-tax",
                            "i-tax",
                            1,
                            "Artículo 20",
                            "Artículo 20. Se incrementa el impuesto sobre carburantes fósiles.",
                            "hash-tax",
                        ),
                        (
                            "frag-treaty",
                            "v-treaty",
                            "i-treaty",
                            1,
                            "Disposición final única",
                            "Se autoriza el texto de la adenda del convenio internacional sobre la sede.",
                            "hash-treaty",
                        ),
                        (
                            "frag-plan",
                            "v-plan",
                            "i-plan",
                            1,
                            "Artículo 5",
                            "Artículo 5. El ministerio aprobará sendas, hitos e indicadores de movilidad y publicará un informe anual.",
                            "hash-plan",
                        ),
                    ],
                )
                conn.commit()

                rows = fetch_fragment_review_rows(
                    conn,
                    initiative_source_ids=("congreso_iniciativas",),
                    fragment_kinds=("article",),
                    contains_terms=[],
                    contains_any_terms=["energ", "impuesto"],
                    only_unclaimed=True,
                    min_fragment_chars=20,
                    max_fragment_chars=400,
                    min_priority=55,
                    limit=0,
                    offset=0,
                )
                self.assertEqual({str(row["fragment_id"]) for row in rows}, {"frag-tax", "frag-energy"})
                self.assertTrue(all(int(row["priority"]) >= 55 for row in rows))
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
