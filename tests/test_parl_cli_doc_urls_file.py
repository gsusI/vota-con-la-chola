from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.parlamentario_es.cli import _parse_doc_urls_file, _parse_http_status_csv


class TestParlCliDocUrlsFile(unittest.TestCase):
    def test_parse_http_status_csv_retry_accepts_zero_status(self) -> None:
        statuses = _parse_http_status_csv(
            "0,404,0",
            for_command="backfill-initiative-documents",
            arg_name="--retry-http-statuses",
            allow_status_zero=True,
        )
        self.assertEqual(statuses, (0, 404))

    def test_parse_http_status_csv_archive_rejects_zero_status(self) -> None:
        with self.assertRaises(SystemExit):
            _parse_http_status_csv(
                "0,404",
                for_command="backfill-initiative-documents",
                arg_name="--archive-fallback-http-statuses",
            )

    def test_parse_doc_urls_file_empty_path_returns_empty_contract(self) -> None:
        urls, status_by_url, entry_keys = _parse_doc_urls_file(
            "",
            for_command="backfill-initiative-documents",
        )
        self.assertEqual(urls, tuple())
        self.assertEqual(status_by_url, {})
        self.assertEqual(entry_keys, tuple())

    def test_parse_doc_urls_file_csv_emits_status_and_entry_keys(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "packet.csv"
            path.write_text(
                "\n".join(
                    [
                        "initiative_id,doc_kind,doc_url,last_http_status",
                        "senado:leg14:exp:621/000047,bocg,https://www.senado.es/a,403",
                        "senado:leg14:exp:621/000047,bocg,https://www.senado.es/a,403",
                        "senado:leg14:exp:621/000048,ds,https://www.senado.es/b,500",
                    ]
                ),
                encoding="utf-8",
            )
            urls, status_by_url, entry_keys = _parse_doc_urls_file(
                str(path),
                for_command="backfill-initiative-documents",
            )

            self.assertEqual(urls, ("https://www.senado.es/a", "https://www.senado.es/b"))
            self.assertEqual(status_by_url, {"https://www.senado.es/a": 403, "https://www.senado.es/b": 500})
            self.assertEqual(
                entry_keys,
                (
                    ("senado:leg14:exp:621/000047", "bocg", "https://www.senado.es/a"),
                    ("senado:leg14:exp:621/000048", "ds", "https://www.senado.es/b"),
                ),
            )

    def test_parse_doc_urls_file_csv_preserves_zero_status_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "packet.csv"
            path.write_text(
                "\n".join(
                    [
                        "initiative_id,doc_kind,doc_url,last_http_status",
                        "senado:leg15:exp:621/000111,bocg,https://www.senado.es/unknown,0",
                    ]
                ),
                encoding="utf-8",
            )
            urls, status_by_url, entry_keys = _parse_doc_urls_file(
                str(path),
                for_command="backfill-initiative-documents",
            )
            self.assertEqual(urls, ("https://www.senado.es/unknown",))
            self.assertEqual(status_by_url, {"https://www.senado.es/unknown": 0})
            self.assertEqual(
                entry_keys,
                (("senado:leg15:exp:621/000111", "bocg", "https://www.senado.es/unknown"),),
            )


if __name__ == "__main__":
    unittest.main()
