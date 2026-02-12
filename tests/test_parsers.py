from __future__ import annotations

import unittest

from etl.politicos_es.parsers import parse_csv_source


class TestCsvParsing(unittest.TestCase):
    def test_parse_csv_source_reads_utf8(self) -> None:
        payload = "nombre;partido\nAna;PSOE\n".encode("utf-8")
        rows = parse_csv_source(payload)
        self.assertEqual(rows[0]["nombre"], "Ana")
        self.assertEqual(rows[0]["partido"], "PSOE")

    def test_parse_csv_source_prefers_cp1252_before_latin1(self) -> None:
        payload = "nombre;siglas\nMarta€;PSOE\n".encode("cp1252")
        rows = parse_csv_source(payload)
        self.assertEqual(rows[0]["siglas"], "PSOE")
        self.assertEqual(rows[0]["nombre"], "Marta€")


if __name__ == "__main__":
    unittest.main()
