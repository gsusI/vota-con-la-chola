from __future__ import annotations

import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.report_programas_unclear_tail_dedupe import build_report, fetch_unclear_rows, main


class TestReportProgramasUnclearTailDedupe(unittest.TestCase):
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
              excerpt TEXT,
              stance TEXT
            );
            """
        )
        return conn

    def test_build_report_dedupes_and_profiles(self) -> None:
        rows = [
            {"party_name": "VOX", "source_url": "https://vox/programa.pdf", "evidence_id": 10, "excerpt": "A B C"},
            {"party_name": "VOX", "source_url": "https://vox/programa.pdf", "evidence_id": 11, "excerpt": "a   b   c"},
            {"party_name": "VOX", "source_url": "https://vox/programa.pdf", "evidence_id": 12, "excerpt": "D E F"},
            {"party_name": "BNG", "source_url": "https://bng/eu.pdf", "evidence_id": 20, "excerpt": "X Y Z"},
        ]
        report, queue_rows, profile_rows = build_report(
            source_id="programas_partidos",
            parties=["BNG", "VOX"],
            rows=rows,
            max_duplicate_share=1.0,
        )
        self.assertEqual(int(report["raw_unclear_rows_total"]), 4)
        self.assertEqual(int(report["unclear_unique_excerpt_rows_total"]), 3)
        self.assertEqual(int(report["unclear_duplicate_rows_total"]), 1)
        self.assertAlmostEqual(float(report["duplicate_share"]), 0.25, places=6)
        self.assertEqual(str(report["status"]), "ok")
        self.assertEqual(len(queue_rows), 3)
        self.assertEqual(len(profile_rows), 2)
        self.assertEqual(int(profile_rows[0]["unclear_duplicate_rows"]), 1)
        self.assertEqual(str(profile_rows[0]["party_name"]), "VOX")

    def test_fetch_unclear_rows_filters_party_and_stance(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "unclear-tail.db"
            conn = self._open_db(db_path)
            try:
                conn.executemany(
                    "INSERT INTO persons(person_id, full_name) VALUES (?, ?)",
                    [(1, "BNG"), (2, "VOX"), (3, "PP")],
                )
                conn.executemany(
                    """
                    INSERT INTO topic_evidence(evidence_id, person_id, source_id, source_url, excerpt, stance)
                    VALUES (?, ?, 'programas_partidos', ?, ?, ?)
                    """,
                    [
                        (1, 1, "https://bng/1", "bng unclear", "unclear"),
                        (2, 1, "https://bng/1", "bng support", "support"),
                        (3, 2, "https://vox/1", "vox unclear", "unclear"),
                        (4, 3, "https://pp/1", "pp unclear", "unclear"),
                    ],
                )
                conn.commit()

                got = fetch_unclear_rows(
                    conn,
                    source_id="programas_partidos",
                    parties=["BNG", "VOX"],
                    excerpt_len=120,
                )
                ids = [int(r["evidence_id"]) for r in got]
                self.assertEqual(ids, [1, 3])
            finally:
                conn.close()

    def test_main_strict_fails_when_duplicate_share_above_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            db_path = td_path / "strict-fail.db"
            out_json = td_path / "report.json"
            out_csv = td_path / "queue.csv"

            conn = self._open_db(db_path)
            try:
                conn.execute("INSERT INTO persons(person_id, full_name) VALUES (1, 'VOX')")
                conn.executemany(
                    """
                    INSERT INTO topic_evidence(evidence_id, person_id, source_id, source_url, excerpt, stance)
                    VALUES (?, 1, 'programas_partidos', 'https://vox/programa.pdf', ?, 'unclear')
                    """,
                    [
                        (100, "texto repetido"),
                        (101, "texto repetido"),
                        (102, "texto unico"),
                    ],
                )
                conn.commit()
            finally:
                conn.close()

            rc = main(
                [
                    "--db",
                    str(db_path),
                    "--source-id",
                    "programas_partidos",
                    "--parties",
                    "VOX",
                    "--max-duplicate-share",
                    "0.1",
                    "--out",
                    str(out_json),
                    "--queue-out",
                    str(out_csv),
                    "--strict",
                ]
            )
            self.assertEqual(rc, 4)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(str(payload["status"]), "degraded")
            self.assertIn("duplicate_share_above_threshold", list(payload["strict_fail_reasons"]))
            with out_csv.open("r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
