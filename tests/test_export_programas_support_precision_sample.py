from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.export_programas_support_precision_sample import build_summary, fetch_support_rows


class TestExportProgramasSupportPrecisionSample(unittest.TestCase):
    def _open_db(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE persons (
              person_id INTEGER PRIMARY KEY,
              full_name TEXT
            );
            CREATE TABLE topic_evidence (
              evidence_id INTEGER PRIMARY KEY,
              person_id INTEGER,
              source_id TEXT,
              source_url TEXT,
              source_record_pk INTEGER,
              excerpt TEXT,
              stance TEXT
            );
            CREATE TABLE source_records (
              source_record_pk INTEGER PRIMARY KEY,
              content_sha256 TEXT
            );
            """
        )
        return conn

    def test_fetch_support_rows_stratified_per_party(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "sample.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO persons(person_id, full_name) VALUES (?, ?)",
                    [(1, "BNG"), (2, "VOX"), (3, "PP")],
                )
                conn.executemany(
                    """
                    INSERT INTO topic_evidence(evidence_id, person_id, source_id, source_url, source_record_pk, excerpt, stance)
                    VALUES (?, ?, 'programas_partidos', ?, NULL, ?, ?)
                    """,
                    [
                        (10, 1, "https://bng/1", "bng support 1", "support"),
                        (11, 1, "https://bng/1", "bng support 2", "support"),
                        (12, 1, "https://bng/2", "bng unclear", "unclear"),
                        (20, 2, "https://vox/1", "vox support 1", "support"),
                        (21, 2, "https://vox/2", "vox support 2", "support"),
                        (22, 2, "https://vox/3", "vox support 3", "support"),
                        (30, 3, "https://pp/1", "pp support 1", "support"),
                    ],
                )
                conn.commit()

                rows, _meta = fetch_support_rows(
                    conn,
                    source_id="programas_partidos",
                    parties=["BNG", "VOX"],
                    per_party_limit=2,
                    limit=0,
                    excerpt_len=50,
                    dedupe_key="none",
                    excerpt_window_words=0,
                    excerpt_window_stride=0,
                    excerpt_window_min_words=12,
                )
                self.assertEqual(len(rows), 4)
                by_party = [str(r["party_name"]) for r in rows]
                self.assertEqual(by_party.count("BNG"), 2)
                self.assertEqual(by_party.count("VOX"), 2)
                ids = [int(r["evidence_id"]) for r in rows]
                self.assertEqual(ids, [10, 11, 20, 21])
            finally:
                conn.close()

    def test_build_summary_tracks_missing_parties(self) -> None:
        rows = [
            {"party_name": "BNG"},
            {"party_name": "BNG"},
            {"party_name": "VOX"},
        ]
        summary = build_summary(
            rows=rows,
            parties=["BNG", "VOX", "PP"],
            source_id="programas_partidos",
            dedupe_key="none",
            min_unique_per_party=0,
            candidate_total_before_dedupe=3,
            dropped_duplicates_total=0,
            dropped_duplicates_by_party={},
            available_unique_by_party={"BNG": 2, "VOX": 1, "PP": 0},
            excerpt_window_words=0,
            excerpt_window_stride=0,
            excerpt_window_min_words=12,
            windowed_rows_total=0,
        )
        self.assertEqual(int(summary["sample_total"]), 3)
        self.assertEqual(int(summary["by_party"]["BNG"]), 2)
        self.assertEqual(int(summary["by_party"]["VOX"]), 1)
        self.assertEqual(int(summary["by_party"]["PP"]), 0)
        self.assertEqual(summary["missing_parties"], ["PP"])

    def test_fetch_support_rows_dedupes_excerpt_plus_url(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "sample-dedupe.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO persons(person_id, full_name) VALUES (?, ?)",
                    [(1, "PP")],
                )
                conn.executemany(
                    """
                    INSERT INTO topic_evidence(evidence_id, person_id, source_id, source_url, source_record_pk, excerpt, stance)
                    VALUES (?, ?, 'programas_partidos', ?, NULL, ?, 'support')
                    """,
                    [
                        (100, 1, "https://pp/dup", "Same Excerpt"),
                        (101, 1, "https://pp/dup", "same  excerpt"),
                        (102, 1, "https://pp/uniq", "Unique Excerpt"),
                    ],
                )
                conn.commit()

                rows, meta = fetch_support_rows(
                    conn,
                    source_id="programas_partidos",
                    parties=["PP"],
                    per_party_limit=0,
                    limit=0,
                    excerpt_len=120,
                    dedupe_key="excerpt_norm+source_url",
                    excerpt_window_words=0,
                    excerpt_window_stride=0,
                    excerpt_window_min_words=12,
                )
                self.assertEqual(len(rows), 2)
                kept_ids = [int(r["evidence_id"]) for r in rows]
                self.assertEqual(kept_ids, [100, 102])
                self.assertEqual(int(meta["candidate_total_before_dedupe"]), 3)
                self.assertEqual(int(meta["dropped_duplicates_total"]), 1)
                self.assertEqual(int(meta["dropped_duplicates_by_party"]["PP"]), 1)
                self.assertEqual(int(meta["available_unique_by_party"]["PP"]), 2)
                self.assertEqual(int(meta["windowed_rows_total"]), 0)
            finally:
                conn.close()

    def test_build_summary_flags_min_unique_party(self) -> None:
        rows = [
            {"party_name": "BNG"},
            {"party_name": "VOX"},
        ]
        summary = build_summary(
            rows=rows,
            parties=["BNG", "VOX", "PP"],
            source_id="programas_partidos",
            dedupe_key="excerpt_norm+source_url",
            min_unique_per_party=1,
            candidate_total_before_dedupe=3,
            dropped_duplicates_total=1,
            dropped_duplicates_by_party={"PP": 1},
            available_unique_by_party={"BNG": 1, "VOX": 1, "PP": 0},
            excerpt_window_words=0,
            excerpt_window_stride=0,
            excerpt_window_min_words=12,
            windowed_rows_total=0,
        )
        self.assertEqual(summary["status"], "degraded")
        self.assertIn("PP", summary["parties_below_min_unique"])
        self.assertNotIn("PP", summary["parties_below_effective_min_unique"])
        self.assertIn("PP", summary["parties_capped_by_available_unique"])
        self.assertIn("missing_parties", summary["strict_fail_reasons"])

    def test_build_summary_allows_cap_when_available_below_target(self) -> None:
        rows = [
            {"party_name": "VOX"},
            {"party_name": "VOX"},
            {"party_name": "VOX"},
            {"party_name": "VOX"},
            {"party_name": "VOX"},
        ]
        summary = build_summary(
            rows=rows,
            parties=["VOX"],
            source_id="programas_partidos",
            dedupe_key="excerpt_norm+source_url",
            min_unique_per_party=10,
            candidate_total_before_dedupe=16,
            dropped_duplicates_total=11,
            dropped_duplicates_by_party={"VOX": 11},
            available_unique_by_party={"VOX": 5},
            excerpt_window_words=0,
            excerpt_window_stride=0,
            excerpt_window_min_words=12,
            windowed_rows_total=0,
        )
        self.assertEqual(summary["status"], "ok")
        self.assertEqual(summary["checks"]["min_unique_per_party_met"], False)
        self.assertEqual(summary["checks"]["min_unique_per_party_effective_met"], True)
        self.assertEqual(summary["parties_capped_by_available_unique"], ["VOX"])
        self.assertEqual(summary["strict_fail_reasons"], [])

    def test_fetch_support_rows_windowed_excerpt_diversifies_same_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "sample-window.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO persons(person_id, full_name) VALUES (?, ?)",
                    [(1, "VOX")],
                )
                base_excerpt = " ".join(
                    [
                        "proponemos",
                        "vivienda",
                        "asequible",
                        "empleo",
                        "juvenil",
                        "sanidad",
                        "publica",
                        "agua",
                        "agricultura",
                        "energia",
                    ]
                    * 8
                )
                conn.executemany(
                    """
                    INSERT INTO topic_evidence(evidence_id, person_id, source_id, source_url, source_record_pk, excerpt, stance)
                    VALUES (?, ?, 'programas_partidos', ?, NULL, ?, 'support')
                    """,
                    [
                        (200, 1, "https://vox/programa.pdf", base_excerpt),
                        (201, 1, "https://vox/programa.pdf", base_excerpt),
                        (202, 1, "https://vox/programa.pdf", base_excerpt),
                    ],
                )
                conn.commit()

                rows, meta = fetch_support_rows(
                    conn,
                    source_id="programas_partidos",
                    parties=["VOX"],
                    per_party_limit=0,
                    limit=0,
                    excerpt_len=220,
                    dedupe_key="excerpt_norm+source_url",
                    excerpt_window_words=24,
                    excerpt_window_stride=12,
                    excerpt_window_min_words=12,
                )
                self.assertGreaterEqual(len(rows), 2)
                self.assertGreater(int(meta["windowed_rows_total"]), 0)
                windows = {(int(r["window_index"]), int(r["window_count"])) for r in rows}
                self.assertGreaterEqual(len(windows), 2)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
