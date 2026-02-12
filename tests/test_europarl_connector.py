from __future__ import annotations

import unittest

from etl.politicos_es.connectors.europarl import EuroparlMepsConnector


class TestEuroparlNormalize(unittest.TestCase):
    def setUp(self) -> None:
        self.connector = EuroparlMepsConnector()

    def test_normalize_with_name_and_surname(self) -> None:
        row = {
            "name": "Laura",
            "surname": "Sanchez",
            "country": "ES",
            "politicalGroup": "PSOE",
        }
        normalized = self.connector.normalize(row, snapshot_date="2026-02-12")
        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized["full_name"], "Laura Sanchez")
        self.assertEqual(normalized["given_name"], "Laura")
        self.assertEqual(normalized["family_name"], "Sanchez")

    def test_normalize_when_only_full_name(self) -> None:
        row = {
            "fullName": "Maria Perez",
            "country": "ES",
            "politicalGroup": "PP",
        }
        normalized = self.connector.normalize(row, snapshot_date="2026-02-12")
        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual(normalized["full_name"], "Maria Perez")
        self.assertIsNone(normalized["given_name"])
        self.assertIsNone(normalized["family_name"])

    def test_normalize_rejects_no_full_name(self) -> None:
        row = {"country": "ES"}
        normalized = self.connector.normalize(row, snapshot_date="2026-02-12")
        self.assertIsNone(normalized)


if __name__ == "__main__":
    unittest.main()
