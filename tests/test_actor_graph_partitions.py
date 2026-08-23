from __future__ import annotations

import itertools
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from publicdata_publish.actor_graph_partition_validation import (
    validate_actor_graph_partitions,
)
from publicdata_publish.actor_graph_partitions import (
    ACTOR_GRAPH_BUCKETS,
    ACTOR_GRAPH_TABLE_SPECS,
    _connect_readonly,
    _iter_table_rows,
    _previous_partitions,
    actor_graph_schema_sha256,
    actor_partition_bucket,
    export_actor_graph_partitions,
    load_actor_graph_contracts,
    non_real_marker_findings,
)

try:
    import pyarrow
except ModuleNotFoundError:
    pyarrow = None


REAL_GRAPH_DB = Path("etl/data/staging/actor-graph-v1.db")


def _has_complete_real_graph(path: Path) -> bool:
    if not path.is_file():
        return False
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    try:
        available = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        return {spec.name for spec in ACTOR_GRAPH_TABLE_SPECS}.issubset(available)
    finally:
        connection.close()


@unittest.skipUnless(
    _has_complete_real_graph(REAL_GRAPH_DB),
    "current real actor graph with mandatory source mappings is absent",
)
class TestActorGraphPartitionsAgainstRealDatabase(unittest.TestCase):
    def test_dynamic_contract_covers_every_required_real_table(self) -> None:
        contracts, sqlite_schemas = load_actor_graph_contracts(REAL_GRAPH_DB)
        self.assertEqual(
            set(contracts), {spec.name for spec in ACTOR_GRAPH_TABLE_SPECS}
        )
        self.assertEqual(set(sqlite_schemas), set(contracts))
        self.assertEqual(len(actor_graph_schema_sha256(contracts, sqlite_schemas)), 64)
        for spec in ACTOR_GRAPH_TABLE_SPECS:
            self.assertGreater(len(contracts[spec.name].columns), 0)
            self.assertEqual(contracts[spec.name].id_column, spec.primary_key)

    def test_single_ordered_cursor_batches_match_real_sqlite_rows(self) -> None:
        contracts, _ = load_actor_graph_contracts(REAL_GRAPH_DB)
        spec = next(
            item
            for item in ACTOR_GRAPH_TABLE_SPECS
            if item.name == "actor_graph_node_versions"
        )
        connection = _connect_readonly(REAL_GRAPH_DB)
        telemetry = {"cursor_batches": 0, "ordered_query_executions": 0}
        try:
            actual = list(
                itertools.islice(
                    _iter_table_rows(
                        connection,
                        spec,
                        contracts[spec.name],
                        fetch_rows=2,
                        telemetry=telemetry,
                    ),
                    5,
                )
            )
            expected = list(
                connection.execute(
                    """
                    SELECT node_version_id, release_id,
                           actor_partition_bucket('source:' || source_id)
                    FROM actor_graph_node_versions
                    ORDER BY release_id,
                             actor_partition_bucket('source:' || source_id),
                             CAST(node_version_id AS TEXT)
                    LIMIT 5
                    """
                )
            )
        finally:
            connection.close()
        self.assertEqual(len(actual), len(expected))
        self.assertEqual(
            [(row[0]["node_version_id"], row[1], row[2]) for row in actual],
            [tuple(row) for row in expected],
        )
        self.assertEqual(telemetry["ordered_query_executions"], 1)
        self.assertEqual(telemetry["cursor_batches"], 3)

    def test_real_release_flags_do_not_trigger_non_real_marker_gate(self) -> None:
        connection = sqlite3.connect(
            f"file:{REAL_GRAPH_DB.resolve()}?mode=ro", uri=True
        )
        connection.row_factory = sqlite3.Row
        try:
            row = dict(
                connection.execute(
                    "SELECT * FROM actor_graph_releases ORDER BY release_id LIMIT 1"
                ).fetchone()
            )
        finally:
            connection.close()
        self.assertEqual(int(row["real_data_only"]), 1)
        self.assertEqual(non_real_marker_findings(row), 0)

    def test_bucket_space_is_fixed(self) -> None:
        connection = sqlite3.connect(
            f"file:{REAL_GRAPH_DB.resolve()}?mode=ro", uri=True
        )
        try:
            values = [
                str(row[0])
                for row in connection.execute(
                    "SELECT DISTINCT source_scope_id FROM actor_graph_nodes"
                )
            ]
        finally:
            connection.close()
        buckets = {actor_partition_bucket(value) for value in values}
        self.assertLessEqual(len(buckets), ACTOR_GRAPH_BUCKETS)
        self.assertTrue(
            all(len(value) == 3 and value.startswith("b") for value in buckets)
        )

    @unittest.skipUnless(
        pyarrow is not None
        and os.environ.get("RUN_REAL_ACTOR_GRAPH_PARTITION_E2E") == "1",
        "set RUN_REAL_ACTOR_GRAPH_PARTITION_E2E=1 with pyarrow for the full real export",
    )
    def test_full_lossless_export_and_validation_on_real_graph(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "actor-graph"
            manifest = export_actor_graph_partitions(
                db_path=REAL_GRAPH_DB,
                output_root=output_root,
                snapshot_date="2026-08-20",
                enforce=True,
            )
            self.assertEqual(
                manifest["totals"]["rows"],
                sum(manifest["totals"]["table_rows"].values()),
            )
            reusable, _ = _previous_partitions(
                output_root / "manifest.json",
                schema_sha256=manifest["schema_sha256"],
                compression="zstd",
                row_group_rows=25_000,
                max_file_rows=100_000,
            )
            self.assertEqual(len(reusable), manifest["totals"]["partitions"])
            incompatible, _ = _previous_partitions(
                output_root / "manifest.json",
                schema_sha256=manifest["schema_sha256"],
                compression="zstd",
                row_group_rows=5_000,
                max_file_rows=10_000,
            )
            self.assertEqual(incompatible, {})
            validation = validate_actor_graph_partitions(
                root=output_root,
                source_db_path=REAL_GRAPH_DB,
                min_rows=manifest["totals"]["rows"],
            )
            self.assertEqual(validation["status"], "ok")
            self.assertTrue(validation["checks"]["partition_contract"])
            self.assertTrue(validation["checks"]["row_groups_match_manifest_contract"])
            self.assertTrue(validation["checks"]["files_match_manifest_contract"])


if __name__ == "__main__":
    unittest.main()
