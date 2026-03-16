from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_senado_retry_packet_only_dedup import main


class ExportSenadoRetryPacketOnlyDedupTests(unittest.TestCase):
    def _write_csv(self, path: Path, *, rows: list[dict[str, str]]) -> None:
        fieldnames = [
            "initiative_id",
            "doc_kind",
            "doc_url",
            "last_http_status",
            "attempts",
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in fieldnames})

    def test_packet_only_dedup_builds_fresh_packet(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pool_csv = root / "pool.csv"
            packet_a = root / "old" / "packet_a.csv"
            packet_b = root / "old" / "packet_b.csv"
            refs = root / "refs.txt"
            out_json = root / "summary.json"
            out_csv = root / "fresh.csv"
            used_urls_out = root / "used_urls.txt"
            used_refs_out = root / "used_refs.txt"

            self._write_csv(
                pool_csv,
                rows=[
                    {"initiative_id": "i1", "doc_kind": "bocg", "doc_url": "https://senado.es/u1", "last_http_status": "403"},
                    {"initiative_id": "i2", "doc_kind": "bocg", "doc_url": "https://senado.es/u2", "last_http_status": "403"},
                    {"initiative_id": "i3", "doc_kind": "bocg", "doc_url": "https://senado.es/u3", "last_http_status": "403"},
                    {"initiative_id": "i4", "doc_kind": "bocg", "doc_url": "https://senado.es/u4", "last_http_status": "404"},
                    {"initiative_id": "i5", "doc_kind": "bocg", "doc_url": "https://senado.es/u5", "last_http_status": "404"},
                ],
            )
            self._write_csv(
                packet_a,
                rows=[
                    {"initiative_id": "x1", "doc_kind": "bocg", "doc_url": "https://senado.es/u1"},
                    {"initiative_id": "x2", "doc_kind": "bocg", "doc_url": "https://senado.es/u5"},
                ],
            )
            self._write_csv(
                packet_b,
                rows=[
                    {"initiative_id": "x3", "doc_kind": "bocg", "doc_url": "https://senado.es/u2"},
                    {"initiative_id": "x4", "doc_kind": "bocg", "doc_url": "https://senado.es/u2"},
                ],
            )
            refs.write_text(str(packet_a) + "\n", encoding="utf-8")

            rc = main(
                [
                    "--pool-csv",
                    str(pool_csv),
                    "--packet-csv-refs-file",
                    str(refs),
                    "--packet-csv-glob",
                    str(root / "old" / "*.csv"),
                    "--max-rows",
                    "2",
                    "--strict-min-fresh-rows",
                    "1",
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                    "--used-urls-out",
                    str(used_urls_out),
                    "--used-packet-refs-out",
                    str(used_refs_out),
                    "--strict",
                ]
            )
            self.assertEqual(rc, 0)

            report = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(str(report.get("status") or ""), "ok")
            totals = report.get("totals") or {}
            self.assertEqual(int(totals.get("pool_rows_total") or 0), 5)
            self.assertEqual(int(totals.get("used_packet_files_total") or 0), 2)
            self.assertEqual(int(totals.get("used_urls_total") or 0), 3)
            self.assertEqual(int(totals.get("excluded_used_urls_total") or 0), 3)
            self.assertEqual(int(totals.get("fresh_rows_total") or 0), 2)

            with out_csv.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)
            urls = [str(r.get("doc_url") or "") for r in rows]
            self.assertEqual(urls, ["https://senado.es/u3", "https://senado.es/u4"])

            used_urls_lines = [x.strip() for x in used_urls_out.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(used_urls_lines, ["https://senado.es/u1", "https://senado.es/u2", "https://senado.es/u5"])

            used_refs_lines = [x.strip() for x in used_refs_out.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(len(used_refs_lines), 2)

    def test_strict_fails_when_canonical_dedupe_exhausts_pool(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pool_csv = root / "pool.csv"
            packet_a = root / "packet_a.csv"
            out_json = root / "summary.json"
            out_csv = root / "fresh.csv"

            self._write_csv(
                pool_csv,
                rows=[
                    {"initiative_id": "i1", "doc_kind": "bocg", "doc_url": "https://senado.es/u1"},
                    {"initiative_id": "i2", "doc_kind": "bocg", "doc_url": "https://senado.es/u2"},
                ],
            )
            self._write_csv(
                packet_a,
                rows=[
                    {"initiative_id": "x1", "doc_kind": "bocg", "doc_url": "https://senado.es/u1"},
                    {"initiative_id": "x2", "doc_kind": "bocg", "doc_url": "https://senado.es/u2"},
                ],
            )

            rc = main(
                [
                    "--pool-csv",
                    str(pool_csv),
                    "--packet-csv",
                    str(packet_a),
                    "--strict-min-fresh-rows",
                    "1",
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                    "--strict",
                ]
            )
            self.assertEqual(rc, 4)
            report = json.loads(out_json.read_text(encoding="utf-8"))
            self.assertEqual(str(report.get("status") or ""), "degraded")
            reasons = report.get("strict_fail_reasons") or []
            self.assertIn("fresh_rows_below_min", reasons)
            self.assertIn("packet_exhausted_by_canonical_dedupe", reasons)

    def test_refs_file_only_limits_dedupe_scope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pool_csv = root / "pool.csv"
            packet_a = root / "old" / "packet_a.csv"
            packet_b = root / "old" / "packet_b.csv"
            refs = root / "refs.txt"
            out_json = root / "summary.json"
            out_csv = root / "fresh.csv"

            self._write_csv(
                pool_csv,
                rows=[
                    {"initiative_id": "i1", "doc_kind": "bocg", "doc_url": "https://senado.es/u1"},
                    {"initiative_id": "i2", "doc_kind": "bocg", "doc_url": "https://senado.es/u2"},
                    {"initiative_id": "i3", "doc_kind": "bocg", "doc_url": "https://senado.es/u3"},
                ],
            )
            self._write_csv(
                packet_a,
                rows=[
                    {"initiative_id": "x1", "doc_kind": "bocg", "doc_url": "https://senado.es/u1"},
                ],
            )
            self._write_csv(
                packet_b,
                rows=[
                    {"initiative_id": "x2", "doc_kind": "bocg", "doc_url": "https://senado.es/u2"},
                ],
            )
            refs.write_text(str(packet_a) + "\n", encoding="utf-8")

            rc = main(
                [
                    "--pool-csv",
                    str(pool_csv),
                    "--packet-csv-refs-file",
                    str(refs),
                    "--packet-csv-refs-file-only",
                    "--packet-csv-glob",
                    str(root / "old" / "*.csv"),
                    "--strict-min-fresh-rows",
                    "1",
                    "--out",
                    str(out_json),
                    "--csv-out",
                    str(out_csv),
                    "--strict",
                ]
            )
            self.assertEqual(rc, 0)
            report = json.loads(out_json.read_text(encoding="utf-8"))
            totals = report.get("totals") or {}
            self.assertEqual(int(totals.get("used_packet_files_total") or 0), 1)
            self.assertEqual(int(totals.get("used_urls_total") or 0), 1)

            with out_csv.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            urls = [str(r.get("doc_url") or "") for r in rows]
            self.assertEqual(urls, ["https://senado.es/u2", "https://senado.es/u3"])


if __name__ == "__main__":
    unittest.main()
