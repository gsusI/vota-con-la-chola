from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from etl.politicos_es.db import apply_schema, seed_dimensions, seed_sources
from publicdata_core.blobstore import StoredBlob
from publicdata_core.util import now_utc_iso, sha256_bytes
from publicdata_ops import heartbeat_work_items
from publicdata_policy_es.eurostat_bulk import (
    inspect_eurostat_jsonstat,
    iter_eurostat_jsonstat_series,
    load_eurostat_source_records,
)
from publicdata_policy_es.indicator_backfill import backfill_indicator_harmonization
from publicdata_sqlite import open_db
from scripts.ingest_eurostat_indicator_registry import (
    DEFAULT_MAXIMUM_CUBE_CELLS,
    _maximum_cube_cells,
    enqueue_registry,
    load_registry,
    run_worker,
)


def _cube(*, changed_value: float | None = None) -> dict[str, object]:
    values = {"0": 10.0, "1": 11.0, "2": 12.0, "3": 13.0}
    if changed_value is not None:
        values["3"] = changed_value
    return {
        "version": "2.0",
        "class": "dataset",
        "label": "Population test cube",
        "extension": {"updated": "2026-08-11T00:00:00+0200"},
        "id": ["freq", "sex", "geo", "time"],
        "size": [1, 2, 1, 2],
        "dimension": {
            "freq": {
                "label": "Frequency",
                "category": {"index": {"A": 0}, "label": {"A": "Annual"}},
            },
            "sex": {
                "label": "Sex",
                "category": {
                    "index": {"T": 0, "F": 1},
                    "label": {"T": "Total", "F": "Females"},
                },
            },
            "geo": {
                "label": "Geography",
                "category": {"index": {"ES": 0}, "label": {"ES": "Spain"}},
            },
            "time": {
                "label": "Time",
                "category": {
                    "index": {"2024": 0, "2025": 1},
                    "label": {"2024": "2024", "2025": "2025"},
                },
            },
        },
        "value": values,
    }


class TestEurostatIndicatorRegistry(unittest.TestCase):
    source_url = (
        "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/"
        "data/demo_test?lang=EN"
    )

    def _write_cube(self, root: Path, name: str, payload: dict[str, object]) -> Path:
        path = root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _database(self, root: Path) -> sqlite3.Connection:
        conn = open_db(root / "indicators.db")
        apply_schema(conn, Path("etl/load/sqlite_schema.sql"))
        seed_sources(conn)
        seed_dimensions(conn)
        return conn

    def _acquisition(
        self,
        conn: sqlite3.Connection,
        *,
        item_key: str,
        snapshot_date: str,
        payload_path: Path,
    ) -> int:
        now_iso = now_utc_iso()
        payload_sha = sha256_bytes(payload_path.read_bytes())
        row = conn.execute(
            """
            INSERT INTO indicator_bulk_acquisitions (
              pipeline_id, item_key, source_id, dataset_code, source_url,
              source_snapshot_date, transport_security, raw_content_sha256,
              raw_path, raw_bytes, status, created_at, updated_at
            ) VALUES (
              'test-pipeline', ?, 'eurostat_sdmx', 'demo_test', ?, ?,
              'verified_ca', ?, ?, ?, 'running', ?, ?
            ) RETURNING indicator_bulk_acquisition_id
            """,
            (
                item_key,
                self.source_url,
                snapshot_date,
                payload_sha,
                str(payload_path),
                payload_path.stat().st_size,
                now_iso,
                now_iso,
            ),
        ).fetchone()
        conn.commit()
        assert row is not None
        return int(row[0])

    def test_registry_is_official_bounded_and_unique(self) -> None:
        registry = load_registry(
            Path("etl/data/seeds/eurostat_indicator_registry_v1.json")
        )
        self.assertEqual(registry["source_id"], "eurostat_sdmx")
        self.assertEqual(len(registry["queries"]), 4)
        self.assertEqual(
            len({query["query_id"] for query in registry["queries"]}),
            len(registry["queries"]),
        )
        self.assertTrue(
            all(
                query["source_url"].startswith("https://ec.europa.eu/")
                for query in registry["queries"]
            )
        )
        self.assertTrue(
            all(
                query["maximum_bytes"] <= 64 * 1024 * 1024
                for query in registry["queries"]
            )
        )
        self.assertTrue(
            all(
                query["maximum_cube_cells"] >= query["minimum_observations"]
                for query in registry["queries"]
            )
        )

    def test_cube_cell_ceiling_fails_before_sparse_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = self._write_cube(root, "cube.json", _cube())
            with self.assertRaisesRegex(RuntimeError, "cube-cell ceiling exceeded"):
                inspect_eurostat_jsonstat(
                    path,
                    source_url=self.source_url,
                    maximum_cube_cells=3,
                )

    def test_legacy_queued_query_gets_bounded_cube_ceiling(self) -> None:
        self.assertEqual(_maximum_cube_cells({}), DEFAULT_MAXIMUM_CUBE_CELLS)
        self.assertEqual(_maximum_cube_cells({"maximum_cube_cells": 42}), 42)
        with self.assertRaisesRegex(RuntimeError, "must be >= 1"):
            _maximum_cube_cells({"maximum_cube_cells": 0})

    def test_worker_heartbeats_download_parse_load_and_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload_path = self._write_cube(root, "cube.json", _cube())
            payload_sha = sha256_bytes(payload_path.read_bytes())
            conn = self._database(root)
            try:
                enqueue_registry(
                    conn,
                    registry={
                        "queries": [
                            {
                                "query_id": "test-query",
                                "dataset_code": "demo_test",
                                "domain_key": "demografia_contexto",
                                "source_url": self.source_url,
                                "minimum_observations": 4,
                                "maximum_bytes": 1_000_000,
                                "maximum_cube_cells": 4,
                                "priority": 1,
                                "max_attempts": 2,
                            }
                        ]
                    },
                    pipeline_id="test-worker-pipeline",
                    snapshot_date="2026-08-11",
                )

                def fake_load(*args: object, **kwargs: object) -> dict[str, int]:
                    progress_callback = kwargs.get("progress_callback")
                    assert callable(progress_callback)
                    progress_callback()
                    return {"series_loaded": 2, "observations_discovered": 4}

                stored = StoredBlob(
                    content_sha256=payload_sha,
                    bytes=payload_path.stat().st_size,
                    path=payload_path,
                    content_type="application/json",
                    etag=None,
                    last_modified=None,
                    deduplicated=False,
                )
                with (
                    patch(
                        "scripts.ingest_eurostat_indicator_registry.download_to_content_addressed_store",
                        return_value=stored,
                    ),
                    patch(
                        "scripts.ingest_eurostat_indicator_registry.inspect_eurostat_jsonstat",
                        return_value={"observations": 4},
                    ),
                    patch(
                        "scripts.ingest_eurostat_indicator_registry.load_eurostat_source_records",
                        side_effect=fake_load,
                    ),
                    patch(
                        "scripts.ingest_eurostat_indicator_registry.heartbeat_work_items",
                        wraps=heartbeat_work_items,
                    ) as heartbeat_mock,
                ):
                    result = run_worker(
                        conn,
                        pipeline_id="test-worker-pipeline",
                        worker_id="test-worker",
                        store_root=root / "store",
                        timeout=1,
                        ca_bundle=None,
                        insecure_ssl=False,
                        max_items=1,
                        source_record_batch_size=1,
                    )

                self.assertEqual(result["succeeded"], 1)
                self.assertEqual(result["failed"], 0)
                self.assertGreaterEqual(heartbeat_mock.call_count, 3)
                self.assertEqual(result["queue"]["state_counts"].get("succeeded"), 1)
                self.assertEqual(result["queue"]["unfinished_total"], 0)
            finally:
                conn.close()

    def test_streams_compact_series_and_preserves_changed_series_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_path = self._write_cube(root, "first.json", _cube())
            preflight = inspect_eurostat_jsonstat(
                first_path,
                source_url=self.source_url,
                expected_dataset_code="demo_test",
            )
            self.assertEqual(preflight["series_with_values"], 2)
            self.assertEqual(preflight["observations"], 4)
            series = list(
                iter_eurostat_jsonstat_series(
                    first_path,
                    source_url=self.source_url,
                    domain_key="demografia_contexto",
                )
            )
            self.assertEqual([record["points_count"] for record in series], [2, 2])
            self.assertTrue(
                all("dimension_codelists" not in record for record in series)
            )

            conn = self._database(root)
            try:
                first_acquisition = self._acquisition(
                    conn,
                    item_key="first",
                    snapshot_date="2026-08-11",
                    payload_path=first_path,
                )
                progress_calls = 0

                def record_progress() -> None:
                    nonlocal progress_calls
                    progress_calls += 1

                first = load_eurostat_source_records(
                    conn,
                    blob_path=first_path,
                    source_url=self.source_url,
                    snapshot_date="2026-08-11",
                    raw_content_sha256=sha256_bytes(first_path.read_bytes()),
                    acquisition_id=first_acquisition,
                    domain_key="demografia_contexto",
                    batch_size=1,
                    progress_callback=record_progress,
                )
                self.assertEqual(
                    first, {"series_loaded": 2, "observations_discovered": 4}
                )
                self.assertEqual(progress_calls, 2)

                second_path = self._write_cube(
                    root, "second.json", _cube(changed_value=14.0)
                )
                second_acquisition = self._acquisition(
                    conn,
                    item_key="second",
                    snapshot_date="2026-08-12",
                    payload_path=second_path,
                )
                second = load_eurostat_source_records(
                    conn,
                    blob_path=second_path,
                    source_url=self.source_url,
                    snapshot_date="2026-08-12",
                    raw_content_sha256=sha256_bytes(second_path.read_bytes()),
                    acquisition_id=second_acquisition,
                    domain_key="demografia_contexto",
                    batch_size=2,
                )
                self.assertEqual(
                    second, {"series_loaded": 2, "observations_discovered": 4}
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM source_records WHERE source_id='eurostat_sdmx'"
                    ).fetchone()[0],
                    3,
                )

                result = backfill_indicator_harmonization(
                    conn,
                    source_ids=("eurostat_sdmx",),
                )
                self.assertEqual(result["indicator_observation_records_total"], 6)
                revised = conn.execute(
                    """
                    SELECT series_code, point_date, COUNT(*) AS revisions
                    FROM indicator_observation_records
                    GROUP BY series_code, point_date
                    HAVING COUNT(*) > 1
                    ORDER BY series_code, point_date
                    """
                ).fetchall()
                self.assertEqual(len(revised), 2)
                self.assertTrue(all(int(row["revisions"]) == 2 for row in revised))
                latest = conn.execute(
                    """
                    SELECT value
                    FROM indicator_points AS point
                    JOIN indicator_series AS series
                      ON series.indicator_series_id=point.indicator_series_id
                    WHERE series.source_id='eurostat_sdmx'
                      AND series.canonical_key LIKE '%sex=F%'
                      AND point.date='2025-01-01'
                    """
                ).fetchone()
                self.assertIsNotNone(latest)
                self.assertEqual(float(latest["value"]), 14.0)
                self.assertEqual(
                    conn.execute("PRAGMA foreign_key_check").fetchall(), []
                )
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
