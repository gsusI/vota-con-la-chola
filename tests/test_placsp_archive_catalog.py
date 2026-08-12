from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from publicdata_connectors_es.money.placsp_catalog import (
    build_catalog_report,
    parse_catalog_links,
)
from scripts.ingest_placsp_archives import (
    _open_runtime,
    _parse_archive_report,
    enqueue_archives,
)


def catalog_html(periods: list[str]) -> bytes:
    links = "".join(
        (
            '<a href="https://contrataciondelsectorpublico.gob.es/sindicacion/'
            "sindicacion_643/licitacionesPerfilesContratanteCompleto3_"
            f'{period}.zip">{period}</a>'
        )
        for period in periods
    )
    return f"<!doctype html><html><body>{links}</body></html>".encode()


class TestPlacspArchiveCatalog(unittest.TestCase):
    def test_selects_closed_annual_and_current_monthly_without_overlap(self) -> None:
        payload = catalog_html(
            ["2012", "2013", "2014", "2015", "201501", "201502", "201503"]
        )

        report = build_catalog_report(
            payload,
            catalog_url="https://official.example/catalog",
            as_of_date=date(2015, 3, 20),
        )

        self.assertEqual(report["status"], "ok")
        self.assertEqual(
            [row["period"] for row in report["archives"]],
            ["2012", "2013", "2014", "201501", "201502", "201503"],
        )
        self.assertEqual(report["missing"]["annual_periods"], [])
        self.assertEqual(report["missing"]["monthly_periods"], [])
        self.assertEqual(report["expected"]["selected_archives"], 6)

    def test_gap_accounting_fails_closed(self) -> None:
        report = build_catalog_report(
            catalog_html(["2012", "2014", "201501", "201503"]),
            catalog_url="https://official.example/catalog",
            as_of_date=date(2015, 3, 20),
        )

        self.assertEqual(report["status"], "degraded")
        self.assertEqual(report["missing"]["annual_periods"], ["2013"])
        self.assertEqual(report["missing"]["monthly_periods"], ["201502"])
        self.assertFalse(report["checks"]["closed_years_gap_free"])
        self.assertFalse(report["checks"]["current_year_months_gap_free"])

    def test_rejects_non_https_archive_link(self) -> None:
        html = (
            '<a href="http://official.example/'
            'licitacionesPerfilesContratanteCompleto3_2012.zip">2012</a>'
        )
        with self.assertRaisesRegex(ValueError, "non-HTTPS"):
            parse_catalog_links(html, catalog_url="https://official.example/catalog")

    def test_report_enqueue_is_idempotent_and_contract_locked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_path = root / "catalog.json"
            report_path.write_text(
                """{
                  "status": "ok",
                  "archives": [
                    {"period": "2012", "source_url": "https://official.example/2012.zip"},
                    {"period": "2013", "source_url": "https://official.example/2013.zip"}
                  ]
                }""",
                encoding="utf-8",
            )
            archives = _parse_archive_report(report_path)
            conn = _open_runtime(
                root / "catalog.db", Path("etl/load/sqlite_schema.sql")
            )
            try:
                first = enqueue_archives(
                    conn,
                    pipeline_id="history",
                    snapshot_date="2026-08-11",
                    archives=archives,
                )
                second = enqueue_archives(
                    conn,
                    pipeline_id="history",
                    snapshot_date="2026-08-11",
                    archives=archives,
                )
                self.assertEqual(len(first["archive_contract_sha256"]), 64)
                self.assertEqual(
                    first["archive_contract_sha256"], second["archive_contract_sha256"]
                )
                self.assertEqual(second["archive_queue"]["inserted_total"], 0)
                with self.assertRaisesRegex(RuntimeError, "different archive contract"):
                    enqueue_archives(
                        conn,
                        pipeline_id="history",
                        snapshot_date="2026-08-11",
                        archives=[
                            ("2012", "https://official.example/changed-2012.zip"),
                            ("2013", "https://official.example/2013.zip"),
                        ],
                    )
            finally:
                conn.close()

    def test_report_rejects_invalid_archive_row_without_silently_skipping_it(
        self,
    ) -> None:
        with TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "catalog.json"
            report_path.write_text(
                """{
                  "status": "ok",
                  "archives": [
                    {"period": "2012", "source_url": "https://official.example/2012.zip"},
                    "malformed"
                  ]
                }""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "invalid archive row"):
                _parse_archive_report(report_path)


if __name__ == "__main__":
    unittest.main()
