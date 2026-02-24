from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_sanction_data_catalog_seed import import_seed as import_catalog_seed
from scripts.run_sanction_procedural_official_review_apply_from_kpi_gap_cycle import (
    main as gap_cycle_main,
)


class TestRunSanctionProceduralOfficialReviewApplyFromKpiGapCycle(unittest.TestCase):
    def _insert_source(self, conn: object, source_id: str = "boe_api_legal") -> None:
        ts = "2026-02-24T00:00:00+00:00"
        conn.execute(
            """
            INSERT INTO sources (
              source_id, name, scope, default_url, data_format, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                "BOE API Legal",
                "nacional",
                "https://www.boe.es/",
                "json",
                1,
                ts,
                ts,
            ),
        )
        conn.commit()

    def _seed_catalog(self, conn: object) -> None:
        seed_path = (
            Path(__file__).resolve().parents[1]
            / "etl"
            / "data"
            / "seeds"
            / "sanction_data_catalog_seed_v1.json"
        )
        seed_doc = json.loads(seed_path.read_text(encoding="utf-8"))
        import_catalog_seed(conn, seed_doc=seed_doc, source_id="", snapshot_date="2026-02-24")

    def _setup_db(self, db_path: Path) -> None:
        conn = open_db(db_path)
        try:
            schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
            apply_schema(conn, schema_path)
            self._insert_source(conn)
            self._seed_catalog(conn)
        finally:
            conn.close()

    def _insert_missing_source_record_metric(self, db_path: Path) -> None:
        conn = open_db(db_path)
        try:
            conn.execute(
                """
                INSERT INTO sanction_procedural_metrics (
                  metric_key, kpi_id, sanction_source_id, period_date, period_granularity,
                  value, numerator, denominator, source_id, source_url, source_record_pk,
                  evidence_date, evidence_quote, raw_payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "kpi:formal_annulment_rate|es:sanctions:teac_resolutions|2025-12-31|year",
                    "kpi:formal_annulment_rate",
                    "es:sanctions:teac_resolutions",
                    "2025-12-31",
                    "year",
                    0.05,
                    5.0,
                    100.0,
                    None,
                    "https://sede.agenciatributaria.gob.es/",
                    None,
                    "2025-12-31",
                    "Memoria oficial TEAC 2025 con datos de anulaciones formales.",
                    "{}",
                    "2026-02-24T00:00:00+00:00",
                    "2026-02-24T00:00:00+00:00",
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _run_gap_cycle(self, argv: list[str]) -> int:
        import sys

        old = sys.argv[:]
        try:
            sys.argv = argv
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return int(gap_cycle_main())
        finally:
            sys.argv = old

    def test_strict_actionable_blocks_when_no_matching_rows(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "gap_cycle_block.db"
            out_path = Path(td) / "out.json"
            self._setup_db(db_path)

            rc = self._run_gap_cycle(
                [
                    "run_sanction_procedural_official_review_apply_from_kpi_gap_cycle.py",
                    "--db",
                    str(db_path),
                    "--period-date",
                    "2025-12-31",
                    "--period-granularity",
                    "year",
                    "--statuses",
                    "missing_source_record",
                    "--strict-actionable",
                    "--out",
                    str(out_path),
                ]
            )

            payload = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(rc, 4)
        self.assertEqual(int(payload["gap_export"]["rows_emitted_total"]), 0)
        self.assertTrue(bool(payload["cycle"]["apply"]["skipped"]))
        self.assertEqual(str(payload["cycle"]["apply"]["skip_reason"]), "no_actionable_rows")

    def test_dry_run_fixes_missing_source_record_gap_without_writes(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "gap_cycle_dry_run.db"
            out_path = Path(td) / "out.json"
            self._setup_db(db_path)
            self._insert_missing_source_record_metric(db_path)

            rc = self._run_gap_cycle(
                [
                    "run_sanction_procedural_official_review_apply_from_kpi_gap_cycle.py",
                    "--db",
                    str(db_path),
                    "--period-date",
                    "2025-12-31",
                    "--period-granularity",
                    "year",
                    "--statuses",
                    "missing_source_record",
                    "--strict-actionable",
                    "--strict-readiness",
                    "--dry-run",
                    "--snapshot-date",
                    "2026-02-24",
                    "--out",
                    str(out_path),
                ]
            )

            payload = json.loads(out_path.read_text(encoding="utf-8"))
            conn = open_db(db_path)
            try:
                metric_count = int(conn.execute("SELECT COUNT(*) AS n FROM sanction_procedural_metrics").fetchone()["n"])
                source_record_count = int(conn.execute("SELECT COUNT(*) AS n FROM source_records").fetchone()["n"])
            finally:
                conn.close()

        self.assertEqual(rc, 0)
        self.assertEqual(int(payload["gap_export"]["rows_emitted_total"]), 1)
        self.assertEqual(str(payload["cycle"]["readiness"]["status"]), "ok")
        self.assertFalse(bool(payload["cycle"]["apply"]["skipped"]))
        self.assertEqual(int(payload["cycle"]["apply"]["counts"]["rows_ready"]), 1)
        self.assertEqual(int(payload["cycle"]["apply"]["counts"]["source_record_pk_would_create"]), 1)
        self.assertEqual(metric_count, 1)
        self.assertEqual(source_record_count, 0)

    def test_non_dry_run_creates_source_record_and_updates_metric(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "gap_cycle_apply.db"
            out_path = Path(td) / "out.json"
            self._setup_db(db_path)
            self._insert_missing_source_record_metric(db_path)

            rc = self._run_gap_cycle(
                [
                    "run_sanction_procedural_official_review_apply_from_kpi_gap_cycle.py",
                    "--db",
                    str(db_path),
                    "--period-date",
                    "2025-12-31",
                    "--period-granularity",
                    "year",
                    "--statuses",
                    "missing_source_record",
                    "--strict-actionable",
                    "--strict-readiness",
                    "--snapshot-date",
                    "2026-02-24",
                    "--out",
                    str(out_path),
                ]
            )

            payload = json.loads(out_path.read_text(encoding="utf-8"))
            conn = open_db(db_path)
            try:
                metric = conn.execute(
                    """
                    SELECT source_record_pk, source_id
                    FROM sanction_procedural_metrics
                    WHERE metric_key = ?
                    """,
                    ("kpi:formal_annulment_rate|es:sanctions:teac_resolutions|2025-12-31|year",),
                ).fetchone()
                source_record_count = int(conn.execute("SELECT COUNT(*) AS n FROM source_records").fetchone()["n"])
            finally:
                conn.close()

        self.assertEqual(rc, 0)
        self.assertEqual(str(payload["cycle"]["readiness"]["status"]), "ok")
        self.assertFalse(bool(payload["cycle"]["apply"]["skipped"]))
        self.assertEqual(int(payload["cycle"]["apply"]["counts"]["rows_upserted"]), 1)
        self.assertIsNotNone(metric)
        self.assertIsNotNone(metric["source_record_pk"])
        self.assertEqual(str(metric["source_id"]), "boe_api_legal")
        self.assertEqual(source_record_count, 1)


if __name__ == "__main__":
    unittest.main()
