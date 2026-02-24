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
from scripts.run_sanction_procedural_official_review_prepare_apply_cycle import (
    main as prepare_cycle_main,
)


class TestRunSanctionProceduralOfficialReviewPrepareApplyCycle(unittest.TestCase):
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

    def _run_prepare_cycle(self, argv: list[str]) -> int:
        import sys

        old = sys.argv[:]
        try:
            sys.argv = argv
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                return int(prepare_cycle_main())
        finally:
            sys.argv = old

    def test_partial_template_applies_kept_rows(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "prepare_cycle_ok.db"
            csv_path = Path(td) / "partial.csv"
            prepared_path = Path(td) / "prepared.csv"
            rejected_path = Path(td) / "rejected.csv"
            out_path = Path(td) / "out.json"
            self._setup_db(db_path)

            with csv_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "sanction_source_id",
                        "kpi_id",
                        "period_date",
                        "period_granularity",
                        "value",
                        "numerator",
                        "denominator",
                        "source_url",
                        "evidence_date",
                        "evidence_quote",
                        "source_id",
                        "source_record_id",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "sanction_source_id": "es:sanctions:teac_resolutions",
                        "kpi_id": "kpi:recurso_estimation_rate",
                        "period_date": "2025-12-31",
                        "period_granularity": "year",
                        "value": "0.2",
                        "numerator": "20",
                        "denominator": "100",
                        "source_url": "https://example.org/teac/2025",
                        "evidence_date": "2025-12-31",
                        "evidence_quote": "Memoria oficial TEAC 2025, tabla anual consolidada de recursos.",
                        "source_id": "boe_api_legal",
                        "source_record_id": "teac:2025:recurso_estimation_rate",
                    }
                )
                writer.writerow(
                    {
                        "sanction_source_id": "es:sanctions:tear_resolutions",
                        "kpi_id": "kpi:recurso_estimation_rate",
                        "period_date": "2025-12-31",
                        "period_granularity": "year",
                        "value": "",
                        "numerator": "",
                        "denominator": "",
                        "source_url": "https://example.org/tear/2025",
                        "evidence_date": "2025-12-31",
                        "evidence_quote": "Memoria oficial TEAR 2025, fila pendiente de completar valor.",
                        "source_id": "boe_api_legal",
                        "source_record_id": "tear:2025:recurso_estimation_rate",
                    }
                )

            rc = self._run_prepare_cycle(
                [
                    "run_sanction_procedural_official_review_prepare_apply_cycle.py",
                    "--db",
                    str(db_path),
                    "--in",
                    str(csv_path),
                    "--prepare-out",
                    str(prepared_path),
                    "--prepare-rejected-csv-out",
                    str(rejected_path),
                    "--strict-prepare",
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
                n = int(conn.execute("SELECT COUNT(*) AS n FROM sanction_procedural_metrics").fetchone()["n"])
            finally:
                conn.close()

            with prepared_path.open("r", encoding="utf-8", newline="") as fh:
                prepared_rows = list(csv.DictReader(fh))
            with rejected_path.open("r", encoding="utf-8", newline="") as fh:
                rejected_rows = list(csv.DictReader(fh))

        self.assertEqual(rc, 0)
        self.assertEqual(str(payload["prepare"]["status"]), "ok")
        self.assertEqual(int(payload["prepare"]["totals"]["rows_kept"]), 1)
        self.assertEqual(int(payload["prepare"]["totals"]["rows_rejected"]), 1)
        self.assertEqual(int(payload["cycle"]["apply"]["counts"]["rows_upserted"]), 1)
        self.assertEqual(n, 1)
        self.assertEqual(len(prepared_rows), 1)
        self.assertEqual(len(rejected_rows), 1)

    def test_strict_prepare_blocks_when_no_rows_kept(self) -> None:
        with TemporaryDirectory() as td:
            db_path = Path(td) / "prepare_cycle_block.db"
            csv_path = Path(td) / "empty.csv"
            out_path = Path(td) / "out.json"
            self._setup_db(db_path)

            with csv_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=[
                        "sanction_source_id",
                        "kpi_id",
                        "period_date",
                        "period_granularity",
                        "value",
                        "numerator",
                        "denominator",
                        "source_url",
                        "evidence_date",
                        "evidence_quote",
                        "source_id",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "sanction_source_id": "es:sanctions:teac_resolutions",
                        "kpi_id": "kpi:recurso_estimation_rate",
                        "period_date": "2025-12-31",
                        "period_granularity": "year",
                        "value": "",
                        "numerator": "",
                        "denominator": "",
                        "source_url": "https://example.org/teac/2025",
                        "evidence_date": "2025-12-31",
                        "evidence_quote": "Memoria oficial TEAC 2025, fila sin valor para probar bloqueo.",
                        "source_id": "boe_api_legal",
                    }
                )

            rc = self._run_prepare_cycle(
                [
                    "run_sanction_procedural_official_review_prepare_apply_cycle.py",
                    "--db",
                    str(db_path),
                    "--in",
                    str(csv_path),
                    "--strict-prepare",
                    "--strict-readiness",
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
        self.assertEqual(str(payload["prepare"]["status"]), "degraded")
        self.assertTrue(bool(payload["cycle"]["apply"]["skipped"]))
        self.assertEqual(str(payload["cycle"]["apply"]["skip_reason"]), "prepare_not_ok")
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
