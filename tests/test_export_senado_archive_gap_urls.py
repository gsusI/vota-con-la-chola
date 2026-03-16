from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_senado_archive_gap_urls import main


class ExportSenadoArchiveGapUrlsTests(unittest.TestCase):
    def test_export_aggregates_archive_no_snapshot_failures(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            in1 = root / "r1.json"
            in2 = root / "r2.json"
            out_json = root / "summary.json"
            out_csv = root / "rows.csv"

            url1 = "https://www.senado.es/web/ficopendataservlet?legis=14&tipoFich=3&tipoEx=622&numEx=000064"
            url2 = "https://www.senado.es/web/actividadparlamentaria/iniciativas/detalleiniciativa/index.html?legis=14&id1=626&id2=000008"

            in1.write_text(
                json.dumps(
                    {
                        "failures": [
                            f"url={url1} -> HTTPStatusError: archive fallback: no snapshot candidates",
                            f"url={url2} -> HTTPStatusError: archive fallback: no snapshot candidates",
                            "url=https://example.com -> HTTPStatusError: HTTP Error 500",
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            in2.write_text(
                json.dumps(
                    {
                        "failures": [
                            f"url={url1} -> HTTPStatusError: archive fallback: no snapshot candidates",
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            rc = main(
                [
                    "--retry-json",
                    str(in1),
                    "--retry-json",
                    str(in2),
                    "--strict-min-rows",
                    "1",
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                    "--strict",
                ]
            )
            self.assertEqual(rc, 0)

            summary = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(str(summary.get("status") or ""), "ok")
            totals = summary.get("totals") or {}
            self.assertEqual(int(totals.get("archive_no_snapshot_failures_total") or 0), 3)
            self.assertEqual(int(totals.get("unique_urls_total") or 0), 2)

            with out_csv.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)
            by_url = {str(r.get("url") or ""): r for r in rows}
            self.assertEqual(str(by_url[url1].get("failures") or ""), "2")
            self.assertEqual(str(by_url[url1].get("url_kind") or ""), "ficopendataservlet")
            self.assertEqual(str(by_url[url1].get("legis") or ""), "14")
            self.assertEqual(str(by_url[url1].get("tipo_ex") or ""), "622")
            self.assertEqual(str(by_url[url1].get("num_ex") or ""), "000064")
            self.assertEqual(str(by_url[url2].get("failures") or ""), "1")
            self.assertEqual(str(by_url[url2].get("url_kind") or ""), "detalleiniciativa")

    def test_strict_fails_when_rows_below_min(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            in1 = root / "r1.json"
            out_json = root / "summary.json"
            out_csv = root / "rows.csv"

            in1.write_text(json.dumps({"failures": ["url=https://x -> HTTP 500"]}), encoding="utf-8")

            rc = main(
                [
                    "--retry-json",
                    str(in1),
                    "--strict-min-rows",
                    "1",
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                    "--strict",
                ]
            )
            self.assertEqual(rc, 4)
            summary = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(str(summary.get("status") or ""), "degraded")
            reasons = summary.get("strict_fail_reasons") or []
            self.assertIn("rows_below_min", reasons)


if __name__ == "__main__":
    unittest.main()
