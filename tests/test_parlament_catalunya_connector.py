from __future__ import annotations

import unittest

from etl.politicos_es.connectors.parlament_catalunya import parse_alta_date


class TestParlamentCatalunyaAltaDate(unittest.TestCase):
    def test_parse_alta_date_supports_alt_punctuation(self) -> None:
        self.assertEqual(parse_alta_date("Alta: 10.06.2024."), "2024-06-10")
        self.assertEqual(parse_alta_date("Alta  10-07-24"), "2024-07-10")

    def test_parse_alta_date_supports_iso_like_around_alta(self) -> None:
        self.assertEqual(parse_alta_date("Alta: data 2024/08/15 en vigor"), "2024-08-15")


if __name__ == "__main__":
    unittest.main()
