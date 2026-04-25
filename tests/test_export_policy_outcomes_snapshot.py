from __future__ import annotations

import sqlite3
import unittest
from argparse import Namespace

from scripts import export_policy_outcomes_snapshot as policy_outcomes


def make_args() -> Namespace:
    return Namespace(
        db=":memory:",
        out="",
        snapshot_date="2026-02-12",
        max_series=120,
        min_points=2,
        max_points_per_series=36,
        max_events=500,
        max_associations_per_series=6,
        max_associations=500,
        pre_window_days=120,
        post_window_days=120,
    )


class TestExportPolicyOutcomesSnapshot(unittest.TestCase):
    def test_build_payload_returns_empty_snapshot_when_base_tables_are_missing(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            payload = policy_outcomes.build_payload(conn, make_args())
        finally:
            conn.close()

        self.assertEqual(payload["meta"]["snapshot_date"], "2026-02-12")
        self.assertEqual(
            payload["coverage"],
            {
                "indicator_series_total": 0,
                "indicator_points_total": 0,
                "interventions_total": 0,
                "intervention_events_total": 0,
                "causal_estimates_total": 0,
                "policy_events_total": 0,
                "series_loaded": 0,
                "events_loaded": 0,
                "events_in_association": 0,
                "associations_total": 0,
                "series_in_association": 0,
                "series_by_source": {},
                "series_coverage_by_point_count": {
                    "min_points_included": 0,
                    "max_points_included": 0,
                },
            },
        )
        self.assertEqual(payload["series"], [])
        self.assertEqual(payload["policy_events"], [])
        self.assertEqual(payload["associations"], [])
        self.assertIn(
            "La DB actual no incluye todas las tablas base de policy outcomes; se exporta un snapshot parcial o vacio segun cobertura.",
            payload["limitations"]["description"],
        )

    def test_load_series_handles_missing_dimension_tables(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript(
                """
                CREATE TABLE indicator_series (
                  indicator_series_id INTEGER PRIMARY KEY,
                  canonical_key TEXT,
                  label TEXT,
                  unit TEXT,
                  frequency TEXT,
                  domain_id INTEGER,
                  admin_level_id INTEGER,
                  territory_id INTEGER,
                  source_id TEXT,
                  source_url TEXT,
                  source_snapshot_date TEXT
                );
                CREATE TABLE indicator_points (
                  indicator_point_id INTEGER PRIMARY KEY,
                  indicator_series_id INTEGER,
                  date TEXT,
                  value REAL,
                  value_text TEXT
                );
                INSERT INTO indicator_series(
                  indicator_series_id, canonical_key, label, unit, frequency, domain_id,
                  admin_level_id, territory_id, source_id, source_url, source_snapshot_date
                )
                VALUES
                  (1, 'paro_total', 'Paro total', '%', 'monthly', 7, 3, 9, 'eurostat_sdmx', 'https://data.test/paro', '2026-02-11');
                INSERT INTO indicator_points(indicator_point_id, indicator_series_id, date, value, value_text)
                VALUES
                  (1, 1, '2025-12-01', 11.5, ''),
                  (2, 1, '2026-01-01', 11.2, '');
                """
            )

            series, points_by_series = policy_outcomes.load_series(conn, max_series=10, min_points=2)
        finally:
            conn.close()

        self.assertEqual(len(series), 1)
        self.assertEqual(series[0]["indicator_series_id"], 1)
        self.assertEqual(series[0]["domain_label"], "")
        self.assertEqual(series[0]["domain_key"], "")
        self.assertEqual(series[0]["admin_level_label"], "")
        self.assertEqual(series[0]["territory_label"], "")
        self.assertEqual(series[0]["territory_code"], "")
        self.assertEqual(series[0]["point_count"], 2)
        self.assertEqual(len(points_by_series[1]), 2)


if __name__ == "__main__":
    unittest.main()
