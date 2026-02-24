from __future__ import annotations

import csv
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.parlamentario_es.db import apply_schema, open_db
from scripts.import_sanction_data_catalog_seed import import_seed as import_catalog_seed
from scripts.run_sanction_procedural_official_review_raw_prepare_apply_cycle import (
    main as raw_cycle_main,
)


class TestRunSanctionProceduralOfficialReviewRawPrepareApplyCycle(unittest.TestCase):
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

    def _run_raw_cycle(self, argv: list[str]) -> int:
        import sys

        old = sys.argv[:]
        try:
            sys.argv = argv
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return int(raw_cycle_main())
        finally:
            sys.argv = old

    def test_strict_raw_blocks_before_prepare_cycle(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "raw_cycle_block.db"
            raw_csv = Path(td) / "raw_bad.csv"
            out_path = Path(td) / "out.json"
            self._setup_db(db_path)

            with raw_csv.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "sanction_source_id",
                        "period_date",
                        "period_granularity",
                        "source_url",
                        "evidence_date",
                        "evidence_quote",
                        "recurso_presentado_count",
                        "recurso_estimado_count",
                        "anulaciones_formales_count",
                        "resolution_delay_p90_days",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "sanction_source_id": "es:sanctions:teac_resolutions",
                        "period_date": "2025-12-31",
                        "period_granularity": "year",
                        "source_url": "https://example.org/teac/2025",
                        "evidence_date": "31-12-2025",
                        "evidence_quote": "short",
                        "recurso_presentado_count": "0",
                        "recurso_estimado_count": "1",
                        "anulaciones_formales_count": "0",
                        "resolution_delay_p90_days": "120",
                    }
                )

            rc = self._run_raw_cycle(
                [
                    "run_sanction_procedural_official_review_raw_prepare_apply_cycle.py",
                    "--db",
                    str(db_path),
                    "--raw-in",
                    str(raw_csv),
                    "--strict-raw",
                    "--out",
                    str(out_path),
                ]
            )

            payload = json.loads(out_path.read_text(encoding="utf-8"))
            conn = open_db(db_path)
            try:
                n = int(conn.execute("SELECT COUNT(*) AS n FROM sanction_procedural_metrics").fetchone()["n"])
            finally:
                conn.close()

        self.assertEqual(rc, 4)
        self.assertEqual(str(payload["raw"]["status"]), "degraded")
        self.assertEqual(payload["prepare"], {})
        self.assertTrue(bool(payload["cycle"]["apply"]["skipped"]))
        self.assertEqual(str(payload["cycle"]["apply"]["skip_reason"]), "raw_not_ok")
        self.assertEqual(n, 0)

    def test_raw_cycle_dry_run_ok(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "raw_cycle_ok.db"
            raw_csv = Path(td) / "raw_ok.csv"
            out_path = Path(td) / "out.json"
            self._setup_db(db_path)

            with raw_csv.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "sanction_source_id",
                        "period_date",
                        "period_granularity",
                        "source_url",
                        "evidence_date",
                        "evidence_quote",
                        "recurso_presentado_count",
                        "recurso_estimado_count",
                        "anulaciones_formales_count",
                        "resolution_delay_p90_days",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "sanction_source_id": "es:sanctions:tear_resolutions",
                        "period_date": "2025-12-31",
                        "period_granularity": "year",
                        "source_url": "https://example.org/tear/2025",
                        "evidence_date": "2025-12-31",
                        "evidence_quote": "Memoria oficial TEAR 2025, consolidado anual para validar ciclo raw estricto.",
                        "recurso_presentado_count": "1200",
                        "recurso_estimado_count": "300",
                        "anulaciones_formales_count": "90",
                        "resolution_delay_p90_days": "160",
                    }
                )
                writer.writerow(
                    {
                        "sanction_source_id": "es:sanctions:teac_resolutions",
                        "period_date": "2025-12-31",
                        "period_granularity": "year",
                        "source_url": "https://example.org/teac/2025",
                        "evidence_date": "2025-12-31",
                        "evidence_quote": "Memoria oficial TEAC 2025, consolidado anual para validar ciclo raw estricto.",
                        "recurso_presentado_count": "900",
                        "recurso_estimado_count": "270",
                        "anulaciones_formales_count": "72",
                        "resolution_delay_p90_days": "145",
                    }
                )

            rc = self._run_raw_cycle(
                [
                    "run_sanction_procedural_official_review_raw_prepare_apply_cycle.py",
                    "--db",
                    str(db_path),
                    "--raw-in",
                    str(raw_csv),
                    "--strict-raw",
                    "--strict-prepare",
                    "--strict-readiness",
                    "--dry-run",
                    "--out",
                    str(out_path),
                ]
            )

            payload = json.loads(out_path.read_text(encoding="utf-8"))
            conn = open_db(db_path)
            try:
                n = int(conn.execute("SELECT COUNT(*) AS n FROM sanction_procedural_metrics").fetchone()["n"])
            finally:
                conn.close()

        self.assertEqual(rc, 0)
        self.assertEqual(str(payload["raw"]["status"]), "ok")
        self.assertEqual(int(payload["raw"]["totals"]["kpi_rows_emitted"]), 6)
        self.assertEqual(str(payload["prepare"]["status"]), "ok")
        self.assertEqual(str(payload["cycle"]["readiness"]["status"]), "ok")
        self.assertEqual(int(payload["cycle"]["apply"]["counts"]["rows_ready"]), 6)
        self.assertEqual(int(payload["cycle"]["apply"]["counts"]["source_record_pk_would_create"]), 6)
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
