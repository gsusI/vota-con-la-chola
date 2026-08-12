from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from etl.politicos_es.config import DEFAULT_SCHEMA
from etl.politicos_es.db import apply_schema, open_db, seed_dimensions, seed_sources
from etl.politicos_es.indicator_backfill import backfill_indicator_harmonization
from etl.politicos_es.pipeline import ingest_one_source
from etl.politicos_es.registry import get_connectors


EUROSTAT_OFFICIAL_CAPTURE = Path(
    "etl/data/object-origin/eurostat-indicators/fc/a5/"
    "fca5f0c54754173cab1048a6ca52e2e9f7094ca8fa1220f2c29babd9a3911018.json"
)
EUROSTAT_OFFICIAL_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "ilc_peps11n?lang=EN&sinceTimePeriod=2015"
)
BDE_OFFICIAL_CAPTURE = Path(
    "etl/data/raw/bde_series_api/2026/05/11/bde_series_api_20260511T175659Z.json"
)

REAL_INDICATOR_CAPTURES = (
    ("eurostat_sdmx", EUROSTAT_OFFICIAL_CAPTURE, EUROSTAT_OFFICIAL_URL),
    ("bde_series_api", BDE_OFFICIAL_CAPTURE, None),
)
REAL_INDICATOR_SOURCE_IDS = tuple(item[0] for item in REAL_INDICATOR_CAPTURES)


def _ingest_real_indicator_captures(conn, raw_dir: Path) -> None:  # type: ignore[no-untyped-def]
    connectors = get_connectors()
    for source_id, capture_path, source_url in REAL_INDICATOR_CAPTURES:
        if not capture_path.exists():
            raise AssertionError(f"Missing official capture for {source_id}: {capture_path}")
        ingest_one_source(
            conn=conn,
            connector=connectors[source_id],
            raw_dir=raw_dir,
            timeout=5,
            from_file=capture_path,
            url_override=source_url,
            snapshot_date="2026-08-12",
            strict_network=True,
        )


class TestIndicatorBackfill(unittest.TestCase):
    def test_indicator_backfill_seeds_domains_for_real_official_series(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            conn = open_db(td_path / "indicator-domain-linkage.db")
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)
                _ingest_real_indicator_captures(conn, td_path / "raw")

                result = backfill_indicator_harmonization(conn)
                self.assertEqual(
                    result["indicator_series_with_domain_id"]
                    + result["indicator_series_unresolved_domain"],
                    result["indicator_series_total"],
                )

                placeholders = ",".join("?" for _ in REAL_INDICATOR_SOURCE_IDS)
                unresolved_row = conn.execute(
                    f"""
                    SELECT COUNT(*) AS c
                    FROM indicator_series
                    WHERE source_id IN ({placeholders})
                      AND domain_id IS NULL
                    """,
                    REAL_INDICATOR_SOURCE_IDS,
                ).fetchone()
                self.assertEqual(
                    int(unresolved_row["c"]),
                    result["indicator_series_unresolved_domain"],
                )

                domain_keys = {
                    str(row["canonical_key"])
                    for row in conn.execute("SELECT canonical_key FROM domains").fetchall()
                }
                self.assertIn("proteccion_social_pensiones", domain_keys)
                self.assertIn("vivienda_urbanismo", domain_keys)
                self.assertIn("impuestos_gasto_fiscalidad", domain_keys)
            finally:
                conn.close()

    def test_indicator_backfill_is_idempotent_and_traceable_on_real_captures(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            conn = open_db(td_path / "indicator-backfill.db")
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)
                _ingest_real_indicator_captures(conn, td_path / "raw")

                result_1 = backfill_indicator_harmonization(conn)
                self.assertGreater(result_1["indicator_series_total"], 0)
                self.assertGreater(result_1["indicator_points_total"], 0)
                self.assertGreater(result_1["indicator_observation_records_total"], 0)
                self.assertEqual(
                    result_1["indicator_series_total"],
                    result_1["indicator_series_with_provenance"],
                )
                self.assertEqual(
                    result_1["indicator_observation_records_total"],
                    result_1["observation_records_with_provenance"],
                )
                for source_id in REAL_INDICATOR_SOURCE_IDS:
                    self.assertGreater(
                        result_1["indicator_series_by_source"].get(source_id, 0),
                        0,
                    )

                placeholders = ",".join("?" for _ in REAL_INDICATOR_SOURCE_IDS)
                traceability_series_row = conn.execute(
                    f"""
                    SELECT COUNT(*) AS c
                    FROM indicator_series
                    WHERE source_id IN ({placeholders})
                      AND source_record_pk IS NOT NULL
                      AND source_snapshot_date IS NOT NULL
                      AND trim(source_snapshot_date) <> ''
                      AND source_url LIKE 'https://%'
                      AND raw_payload IS NOT NULL
                      AND trim(raw_payload) <> ''
                    """,
                    REAL_INDICATOR_SOURCE_IDS,
                ).fetchone()
                total_series_row = conn.execute(
                    f"SELECT COUNT(*) AS c FROM indicator_series WHERE source_id IN ({placeholders})",
                    REAL_INDICATOR_SOURCE_IDS,
                ).fetchone()
                self.assertEqual(
                    int(traceability_series_row["c"]),
                    int(total_series_row["c"]),
                )

                traceability_obs_row = conn.execute(
                    f"""
                    SELECT COUNT(*) AS c
                    FROM indicator_observation_records
                    WHERE source_id IN ({placeholders})
                      AND source_record_pk IS NOT NULL
                      AND source_record_id IS NOT NULL
                      AND trim(source_record_id) <> ''
                      AND source_snapshot_date IS NOT NULL
                      AND trim(source_snapshot_date) <> ''
                      AND source_url LIKE 'https://%'
                      AND methodology_version IS NOT NULL
                      AND trim(methodology_version) <> ''
                      AND raw_payload IS NOT NULL
                      AND trim(raw_payload) <> ''
                    """,
                    REAL_INDICATOR_SOURCE_IDS,
                ).fetchone()
                total_obs_row = conn.execute(
                    f"""
                    SELECT COUNT(*) AS c
                    FROM indicator_observation_records
                    WHERE source_id IN ({placeholders})
                    """,
                    REAL_INDICATOR_SOURCE_IDS,
                ).fetchone()
                self.assertEqual(int(traceability_obs_row["c"]), int(total_obs_row["c"]))

                linked_obs_row = conn.execute(
                    f"""
                    SELECT COUNT(*) AS c
                    FROM indicator_observation_records AS o
                    JOIN indicator_series AS s
                      ON s.indicator_series_id = o.indicator_series_id
                     AND s.source_id = o.source_id
                    WHERE o.source_id IN ({placeholders})
                    """,
                    REAL_INDICATOR_SOURCE_IDS,
                ).fetchone()
                self.assertEqual(int(linked_obs_row["c"]), int(total_obs_row["c"]))

                result_2 = backfill_indicator_harmonization(conn)
                for key in (
                    "indicator_series_total",
                    "indicator_points_total",
                    "indicator_observation_records_total",
                ):
                    self.assertEqual(result_1[key], result_2[key])

                self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            finally:
                conn.close()

    def test_real_bde_series_map_to_accountability_domains(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            conn = open_db(td_path / "indicator-bde-domains.db")
            try:
                apply_schema(conn, DEFAULT_SCHEMA)
                seed_sources(conn)
                seed_dimensions(conn)
                connector = get_connectors()["bde_series_api"]
                ingest_one_source(
                    conn=conn,
                    connector=connector,
                    raw_dir=td_path / "raw",
                    timeout=5,
                    from_file=BDE_OFFICIAL_CAPTURE,
                    url_override=None,
                    snapshot_date="2026-05-11",
                    strict_network=True,
                )
                result = backfill_indicator_harmonization(
                    conn,
                    source_ids=("bde_series_api",),
                )
                self.assertGreaterEqual(result["indicator_series_with_domain_id"], 2)

                rows = {
                    str(row["label"]): str(row["canonical_key"])
                    for row in conn.execute(
                        """
                        SELECT s.label, d.canonical_key
                        FROM indicator_series AS s
                        JOIN domains AS d ON d.domain_id = s.domain_id
                        WHERE s.source_id='bde_series_api'
                          AND s.label IN (
                            'Euribor a un año',
                            'MERCADO SECUNDARIO DE DEUDA PUBLICA RENDIMIENTOS EN EL AREA DEL EURO BENCHMARK A 10 AÑOS'
                          )
                        """
                    ).fetchall()
                }
                self.assertEqual(rows["Euribor a un año"], "vivienda_urbanismo")
                self.assertEqual(
                    rows[
                        "MERCADO SECUNDARIO DE DEUDA PUBLICA RENDIMIENTOS EN EL AREA DEL EURO BENCHMARK A 10 AÑOS"
                    ],
                    "impuestos_gasto_fiscalidad",
                )
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
