from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from etl.parlamentario_es.cli import main
from etl.parlamentario_es.config import DEFAULT_SCHEMA, SOURCE_CONFIG as PARL_SOURCE_CONFIG
from etl.parlamentario_es.db import apply_schema, open_db, seed_sources as seed_parl_sources
from etl.parlamentario_es.pipeline import ingest_one_source as ingest_parl_source
from etl.parlamentario_es.registry import get_connectors


class TestParlCliQualityReport(unittest.TestCase):
    def test_quality_report_json_out_is_written_and_stable(self) -> None:
        snapshot_date = "2026-02-12"
        out_file_name = f"votaciones-kpis-cli-test-{snapshot_date}.json"
        connectors = get_connectors()

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality-cli.db"
            raw_dir = Path(td) / "raw"
            out_path = Path(td) / out_file_name

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                for source_id in ("congreso_votaciones", "senado_votaciones"):
                    connector = connectors[source_id]
                    sample_path = Path(PARL_SOURCE_CONFIG[source_id]["fallback_file"])
                    ingest_parl_source(
                        conn=conn,
                        connector=connector,
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=sample_path,
                        url_override=None,
                        snapshot_date=snapshot_date,
                        strict_network=True,
                        options={},
                    )
            finally:
                conn.close()

            stdout1 = io.StringIO()
            with redirect_stdout(stdout1):
                code = main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones,senado_votaciones",
                        "--json-out",
                        str(out_path),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue(out_path.exists(), f"Missing quality json output: {out_path}")

            snapshot = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(snapshot["source_ids"], ["congreso_votaciones", "senado_votaciones"])
            self.assertIn("kpis", snapshot)
            self.assertIn("gate", snapshot)
            self.assertIn("OK wrote:", stdout1.getvalue())

            content_first = out_path.read_bytes()
            stdout2 = io.StringIO()
            with redirect_stdout(stdout2):
                code2 = main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones,senado_votaciones",
                        "--json-out",
                        str(out_path),
                    ]
                )
            self.assertEqual(code2, 0)
            self.assertEqual(content_first, out_path.read_bytes())
            self.assertIn("OK unchanged:", stdout2.getvalue())

    def test_quality_report_include_unmatched_people_preview(self) -> None:
        snapshot_date = "2026-02-12"
        out_file_name = f"votaciones-kpis-cli-unmatched-test-{snapshot_date}.json"
        connectors = get_connectors()

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality-cli-unmatched.db"
            raw_dir = Path(td) / "raw"
            out_path = Path(td) / out_file_name

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                for source_id in ("congreso_votaciones", "senado_votaciones"):
                    connector = connectors[source_id]
                    sample_path = Path(PARL_SOURCE_CONFIG[source_id]["fallback_file"])
                    ingest_parl_source(
                        conn=conn,
                        connector=connector,
                        raw_dir=raw_dir,
                        timeout=5,
                        from_file=sample_path,
                        url_override=None,
                        snapshot_date=snapshot_date,
                        strict_network=True,
                        options={},
                    )
            finally:
                conn.close()

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones,senado_votaciones",
                        "--include-unmatched",
                        "--unmatched-sample-limit",
                        "3",
                        "--json-out",
                        str(out_path),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertTrue(out_path.exists(), f"Missing quality json output: {out_path}")

            snapshot = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertIn("unmatched_vote_ids", snapshot)
            unmatched = snapshot["unmatched_vote_ids"]
            self.assertIn("dry_run", unmatched)
            self.assertTrue(unmatched["dry_run"])
            self.assertIn("total_checked", unmatched)
            self.assertIn("unmatched_by_reason", unmatched)
            self.assertLessEqual(len(unmatched.get("unmatched_sample", [])), 3)

    def test_quality_report_include_unmatched_rejects_negative_sample_limit(self) -> None:
        snapshot_date = "2026-02-12"
        connectors = get_connectors()

        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "parl-quality-cli-invalid.db"
            raw_dir = Path(td) / "raw"

            conn = open_db(db_path)
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_parl_sources(conn)
                connector = connectors["congreso_votaciones"]
                sample_path = Path(PARL_SOURCE_CONFIG["congreso_votaciones"]["fallback_file"])
                ingest_parl_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=raw_dir,
                    timeout=5,
                    from_file=sample_path,
                    url_override=None,
                    snapshot_date=snapshot_date,
                    strict_network=True,
                    options={},
                )
            finally:
                conn.close()

            with self.assertRaises(SystemExit):
                main(
                    [
                        "quality-report",
                        "--db",
                        str(db_path),
                        "--source-ids",
                        "congreso_votaciones",
                        "--include-unmatched",
                        "--unmatched-sample-limit",
                        "-1",
                    ]
                )


if __name__ == "__main__":
    unittest.main()
