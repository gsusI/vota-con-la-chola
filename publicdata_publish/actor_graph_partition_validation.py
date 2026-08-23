"""Independent, full-row validation for lossless actor-graph Parquet."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .actor_graph_partitions import (
    ACTOR_GRAPH_BUCKETS,
    ACTOR_GRAPH_LANE,
    ACTOR_GRAPH_MAX_FILE_ROWS,
    ACTOR_GRAPH_MAX_ROW_GROUP_ROWS,
    ACTOR_GRAPH_TABLE_SPECS,
    ACTOR_GRAPH_TRANSFORMER_VERSION,
    ActorGraphTableSpec,
    actor_graph_schema_sha256,
    actor_partition_bucket,
    load_actor_graph_contracts,
    non_public_source_url_findings,
    non_real_marker_findings,
)
from .semantic_contracts import (
    MANIFEST_SCHEMA_VERSION,
    SemanticLaneContract,
    peak_rss_mb,
    private_token_findings,
    safe_child,
    safe_component,
    sha256_file,
)

VALIDATION_SCHEMA_VERSION = "actor_graph_partition_validation_v1"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _connect_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA temp_store = FILE")
    connection.create_function(
        "actor_partition_bucket", 1, actor_partition_bucket, deterministic=True
    )
    return connection


def _bucket_sql(spec: ActorGraphTableSpec) -> str:
    return f"actor_partition_bucket({spec.bucket_token_sql})"


def _iter_source_rows(
    connection: sqlite3.Connection,
    spec: ActorGraphTableSpec,
    contract: SemanticLaneContract,
    *,
    fetch_rows: int,
    telemetry: dict[str, int],
) -> Iterator[tuple[dict[str, Any], str, str]]:
    """Second implementation of the source scan used by the validator."""
    if fetch_rows <= 0:
        raise ValueError("source-fetch-rows must be positive")
    table = _quote_identifier(spec.name)
    primary_key = _quote_identifier(spec.primary_key)
    bucket = _bucket_sql(spec)
    base = f"""
        SELECT t.*, {spec.release_sql} AS __release_id,
               {bucket} AS __partition_bucket
        FROM {table} AS t
        {spec.joins_sql}
    """
    ordering = f" ORDER BY {spec.release_sql}, {bucket}, CAST(t.{primary_key} AS TEXT)"
    cursor = connection.execute(base + ordering)
    telemetry["source_ordered_query_executions"] += 1
    last: tuple[str, str, str] | None = None
    while True:
        page = cursor.fetchmany(int(fetch_rows))
        if not page:
            break
        telemetry["source_cursor_batches"] += 1
        for source_row in page:
            row = {name: source_row[name] for name in contract.columns}
            key = (
                str(source_row["__release_id"] or ""),
                str(source_row["__partition_bucket"] or ""),
                str(row[spec.primary_key] or ""),
            )
            if not all(key):
                raise RuntimeError(
                    f"{spec.name} has an empty release, bucket, or primary key"
                )
            if last is not None and key <= last:
                raise RuntimeError(f"{spec.name} source ordered cursor drift")
            last = key
            yield row, key[0], key[1]


def _partition_id(table: str, release_id: str, bucket: str) -> str:
    return f"{table}|{release_id}|{bucket}"


def _expected_relative_dir(
    *, snapshot_date: str, table: str, release_id: str, bucket: str
) -> str:
    return Path(
        f"lane={ACTOR_GRAPH_LANE}",
        f"snapshot_date={safe_component(snapshot_date)}",
        f"table={safe_component(table)}",
        f"release={safe_component(release_id)}",
        f"bucket={safe_component(bucket)}",
    ).as_posix()


def _identity_metrics(table: str, row: dict[str, Any]) -> tuple[int, int, int]:
    labels = int(
        table == "actor_graph_node_versions"
        and bool(str(row.get("canonical_label") or "").strip())
    )
    identifiers = int(
        table == "actor_graph_identifier_versions"
        and bool(str(row.get("namespace") or "").strip())
        and bool(str(row.get("value") or "").strip())
    )
    aliases = int(
        table == "actor_graph_alias_versions"
        and bool(str(row.get("alias") or "").strip())
    )
    return labels, identifiers, aliases


def _empty_partition_state() -> dict[str, Any]:
    return {
        "rows": 0,
        "min_id": None,
        "max_id": None,
        "public_label_rows": 0,
        "public_identifier_rows": 0,
        "private_token_findings": 0,
        "non_real_marker_findings": 0,
        "non_public_source_url_findings": 0,
        "_digest": hashlib.sha256(),
    }


def _finalize_partition_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **{key: value for key, value in state.items() if key != "_digest"},
        "input_sha256": state["_digest"].hexdigest(),
    }


def _scan_source_database(
    *,
    db_path: Path,
    contracts: dict[str, SemanticLaneContract],
    fetch_rows: int,
) -> dict[str, Any]:
    telemetry = {
        "source_cursor_batches": 0,
        "source_ordered_query_executions": 0,
    }
    partitions: dict[str, dict[str, Any]] = {}
    table_rows = {spec.name: 0 for spec in ACTOR_GRAPH_TABLE_SPECS}
    table_min_ids: dict[str, str | None] = {
        spec.name: None for spec in ACTOR_GRAPH_TABLE_SPECS
    }
    table_max_ids: dict[str, str | None] = {
        spec.name: None for spec in ACTOR_GRAPH_TABLE_SPECS
    }
    table_hashes: dict[str, str] = {}
    pk_duplicates = 0
    join_balance = True
    source_fk_errors = 0
    private_findings = 0
    non_real_findings = 0
    non_public_url_findings = 0
    public_label_rows = 0
    public_identifier_rows = 0
    public_alias_rows = 0
    release_rows = 0
    real_data_release_rows = 0
    public_identity_release_rows = 0
    source_mapping_rows = 0
    connection = _connect_readonly(db_path)
    try:
        connection.execute("BEGIN")
        for spec in ACTOR_GRAPH_TABLE_SPECS:
            quoted_table = _quote_identifier(spec.name)
            quoted_pk = _quote_identifier(spec.primary_key)
            source_count, distinct_count = connection.execute(
                f"SELECT COUNT(*), COUNT(DISTINCT {quoted_pk}) FROM {quoted_table}"
            ).fetchone()
            pk_duplicates += int(source_count) - int(distinct_count)
            table_digest = hashlib.sha256()
            current_key: tuple[str, str] | None = None
            current_state: dict[str, Any] | None = None
            streamed_rows = 0
            previous_id: str | None = None
            for row, release_id, bucket in _iter_source_rows(
                connection,
                spec,
                contracts[spec.name],
                fetch_rows=fetch_rows,
                telemetry=telemetry,
            ):
                key = (release_id, bucket)
                if key != current_key:
                    if current_state is not None and current_key is not None:
                        partitions[_partition_id(spec.name, *current_key)] = (
                            _finalize_partition_state(current_state)
                        )
                    current_key = key
                    current_state = _empty_partition_state()
                    previous_id = None
                assert current_state is not None
                row_id = str(row[spec.primary_key])
                if previous_id is not None and row_id <= previous_id:
                    raise RuntimeError(
                        f"{spec.name} source primary keys are not ordered"
                    )
                previous_id = row_id
                canonical = contracts[spec.name].canonical_row_bytes(row)
                current_state["_digest"].update(canonical)
                table_digest.update(canonical)
                current_state["rows"] += 1
                current_state["min_id"] = (
                    row_id
                    if current_state["min_id"] is None
                    else min(str(current_state["min_id"]), row_id)
                )
                current_state["max_id"] = (
                    row_id
                    if current_state["max_id"] is None
                    else max(str(current_state["max_id"]), row_id)
                )
                labels, identifiers, aliases = _identity_metrics(spec.name, row)
                current_state["public_label_rows"] += labels
                current_state["public_identifier_rows"] += identifiers
                public_label_rows += labels
                public_identifier_rows += identifiers
                public_alias_rows += aliases
                row_private = private_token_findings(row)
                row_non_real = non_real_marker_findings(row)
                row_non_public_url = non_public_source_url_findings(row)
                current_state["private_token_findings"] += row_private
                current_state["non_real_marker_findings"] += row_non_real
                current_state["non_public_source_url_findings"] += row_non_public_url
                private_findings += row_private
                non_real_findings += row_non_real
                non_public_url_findings += row_non_public_url
                streamed_rows += 1
                table_min_ids[spec.name] = (
                    row_id
                    if table_min_ids[spec.name] is None
                    else min(str(table_min_ids[spec.name]), row_id)
                )
                table_max_ids[spec.name] = (
                    row_id
                    if table_max_ids[spec.name] is None
                    else max(str(table_max_ids[spec.name]), row_id)
                )
                if spec.name == "actor_graph_releases":
                    release_rows += 1
                    real_data_release_rows += int(int(row["real_data_only"]) == 1)
                    public_identity_release_rows += int(
                        int(row["public_identity_retained"]) == 1
                    )
                elif spec.name == "actor_graph_source_mappings":
                    source_mapping_rows += 1
            if current_state is not None and current_key is not None:
                partitions[_partition_id(spec.name, *current_key)] = (
                    _finalize_partition_state(current_state)
                )
            table_rows[spec.name] = streamed_rows
            table_hashes[spec.name] = table_digest.hexdigest()
            join_balance = join_balance and streamed_rows == int(source_count)
            source_fk_errors += len(
                list(connection.execute(f"PRAGMA foreign_key_check({quoted_table})"))
            )
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()
    aggregate = hashlib.sha256()
    for spec in ACTOR_GRAPH_TABLE_SPECS:
        aggregate.update(spec.name.encode("utf-8") + b"\0")
        aggregate.update(table_hashes[spec.name].encode("ascii") + b"\n")
    return {
        "partitions": partitions,
        "table_rows": table_rows,
        "table_min_ids": table_min_ids,
        "table_max_ids": table_max_ids,
        "table_content_sha256": table_hashes,
        "content_sha256": aggregate.hexdigest(),
        "rows": sum(table_rows.values()),
        "pk_duplicates": pk_duplicates,
        "join_balance": join_balance,
        "source_fk_errors": source_fk_errors,
        "private_token_findings": private_findings,
        "non_real_marker_findings": non_real_findings,
        "non_public_source_url_findings": non_public_url_findings,
        "public_label_rows": public_label_rows,
        "public_identifier_rows": public_identifier_rows,
        "public_alias_rows": public_alias_rows,
        "release_rows": release_rows,
        "real_data_release_rows": real_data_release_rows,
        "public_identity_release_rows": public_identity_release_rows,
        "source_mapping_rows": source_mapping_rows,
        **telemetry,
    }


def _new_key_index(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        PRAGMA journal_mode = OFF;
        PRAGMA synchronous = OFF;
        PRAGMA temp_store = FILE;
        CREATE TABLE exported_keys (
          table_name TEXT NOT NULL,
          row_id TEXT NOT NULL,
          PRIMARY KEY (table_name, row_id)
        ) WITHOUT ROWID;
        CREATE TABLE exported_refs (
          child_table TEXT NOT NULL,
          child_column TEXT NOT NULL,
          child_id TEXT NOT NULL,
          parent_table TEXT NOT NULL,
          parent_id TEXT NOT NULL
        );
        """
    )
    return connection


def _insert_keys(connection: sqlite3.Connection, rows: list[tuple[str, str]]) -> int:
    before = connection.total_changes
    connection.executemany(
        "INSERT OR IGNORE INTO exported_keys(table_name, row_id) VALUES (?, ?)",
        rows,
    )
    inserted = connection.total_changes - before
    return len(rows) - inserted


def _critical_fk_report(connection: sqlite3.Connection) -> dict[str, Any]:
    missing_rows = list(
        connection.execute(
            """
            SELECT r.child_table, r.child_column, r.parent_table, COUNT(*)
            FROM exported_refs AS r
            LEFT JOIN exported_keys AS parent
              ON parent.table_name = r.parent_table
             AND parent.row_id = r.parent_id
            WHERE parent.row_id IS NULL
            GROUP BY r.child_table, r.child_column, r.parent_table
            ORDER BY r.child_table, r.child_column, r.parent_table
            """
        )
    )
    refs = int(connection.execute("SELECT COUNT(*) FROM exported_refs").fetchone()[0])
    keys = int(connection.execute("SELECT COUNT(*) FROM exported_keys").fetchone()[0])
    return {
        "keys": keys,
        "references": refs,
        "missing": sum(int(row[3]) for row in missing_rows),
        "missing_by_constraint": [
            {
                "child_table": str(row[0]),
                "child_column": str(row[1]),
                "parent_table": str(row[2]),
                "rows": int(row[3]),
            }
            for row in missing_rows
        ],
    }


def validate_actor_graph_partitions(
    *,
    root: Path,
    source_db_path: Path,
    manifest_path: Path | None = None,
    batch_rows: int = 10_000,
    min_rows: int = 1,
    max_peak_rss_mb: float = 1024.0,
    source_fetch_rows: int = 25_000,
) -> dict[str, Any]:
    try:
        import pyarrow.parquet as pq  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pyarrow is required; install the project parquet extra"
        ) from exc
    if batch_rows <= 0 or source_fetch_rows <= 0:
        raise ValueError("batch-rows and source-fetch-rows must be positive")
    root = Path(root)
    source_db_path = Path(source_db_path)
    manifest_path = Path(manifest_path) if manifest_path else root / "manifest.json"
    if not root.is_dir():
        raise FileNotFoundError(root)
    if not source_db_path.is_file():
        raise FileNotFoundError(source_db_path)
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    partition_contract = dict(manifest.get("partition_contract") or {})
    try:
        declared_row_group_rows = int(partition_contract.get("row_group_rows") or 0)
        declared_max_file_rows = int(partition_contract.get("max_file_rows") or 0)
        declared_cursor_fetch_rows = int(
            partition_contract.get("cursor_fetch_rows") or 0
        )
    except (TypeError, ValueError):
        declared_row_group_rows = 0
        declared_max_file_rows = 0
        declared_cursor_fetch_rows = 0
    manifest_private_findings = private_token_findings({"manifest": manifest})
    manifest_non_real_findings = non_real_marker_findings(
        {
            "manifest_json": json.dumps(
                manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True
            )
        }
    )
    contracts, sqlite_schemas = load_actor_graph_contracts(source_db_path)
    expected_schema_sha256 = actor_graph_schema_sha256(contracts, sqlite_schemas)
    expected_table_names = {spec.name for spec in ACTOR_GRAPH_TABLE_SPECS}
    manifest_tables = dict(manifest.get("tables") or {})
    manifest_partitions = list(manifest.get("partitions") or [])
    manifest_partition_by_id: dict[str, dict[str, Any]] = {}
    duplicate_partition_ids = 0
    for partition in manifest_partitions:
        partition_id = str(partition.get("partition_id") or "")
        if partition_id in manifest_partition_by_id:
            duplicate_partition_ids += 1
        manifest_partition_by_id[partition_id] = partition

    source = _scan_source_database(
        db_path=source_db_path,
        contracts=contracts,
        fetch_rows=source_fetch_rows,
    )
    expected_source_partitions = dict(source["partitions"])

    expected_paths: set[str] = set()
    duplicate_paths = 0
    files_present = True
    file_hashes_valid = True
    parquet_schemas_valid = True
    file_rows_valid = True
    file_minmax_valid = True
    row_groups_bounded = True
    row_groups_match_manifest_contract = True
    zstd_only = True
    files_match_manifest_contract = True
    partition_paths_valid = True
    partition_rows_valid = True
    partition_hashes_valid = True
    partition_values_valid = True
    primary_keys_sorted = True
    rows_total = 0
    files_total = 0
    bytes_total = 0
    duplicate_primary_keys = 0
    private_findings = 0
    non_real_findings = 0
    non_public_url_findings = 0
    public_label_rows = 0
    public_identifier_rows = 0
    public_alias_rows = 0
    release_rows = 0
    real_data_release_rows = 0
    public_identity_release_rows = 0
    source_mapping_rows = 0
    parquet_table_rows = {spec.name: 0 for spec in ACTOR_GRAPH_TABLE_SPECS}
    parquet_table_min_ids: dict[str, str | None] = {
        spec.name: None for spec in ACTOR_GRAPH_TABLE_SPECS
    }
    parquet_table_max_ids: dict[str, str | None] = {
        spec.name: None for spec in ACTOR_GRAPH_TABLE_SPECS
    }
    parquet_table_digests = {
        spec.name: hashlib.sha256() for spec in ACTOR_GRAPH_TABLE_SPECS
    }
    partition_reports: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="actor-graph-validation-") as temp_dir:
        key_index_path = Path(temp_dir) / "keys.sqlite"
        key_index = _new_key_index(key_index_path)
        try:
            previous_partition_sort_key: tuple[int, str, str] | None = None
            spec_order = {
                spec.name: index for index, spec in enumerate(ACTOR_GRAPH_TABLE_SPECS)
            }
            specs_by_name = {spec.name: spec for spec in ACTOR_GRAPH_TABLE_SPECS}
            for partition in manifest_partitions:
                values = dict(partition.get("values") or {})
                table = str(values.get("table") or "")
                release_id = str(values.get("release_id") or "")
                bucket = str(values.get("bucket") or "")
                snapshot_date = str(values.get("snapshot_date") or "")
                if table not in specs_by_name:
                    partition_values_valid = False
                    continue
                spec = specs_by_name[table]
                contract = contracts[table]
                sort_key = (spec_order[table], release_id, bucket)
                if (
                    previous_partition_sort_key is not None
                    and sort_key <= previous_partition_sort_key
                ):
                    partition_values_valid = False
                previous_partition_sort_key = sort_key
                expected_partition_id = _partition_id(table, release_id, bucket)
                expected_dir = _expected_relative_dir(
                    snapshot_date=str(manifest.get("snapshot_date") or ""),
                    table=table,
                    release_id=release_id,
                    bucket=bucket,
                )
                if str(partition.get("partition_id") or "") != expected_partition_id:
                    partition_values_valid = False
                if snapshot_date != str(manifest.get("snapshot_date") or ""):
                    partition_values_valid = False
                if not bucket.startswith("b") or len(bucket) != 3:
                    partition_values_valid = False
                else:
                    try:
                        if int(bucket[1:], 16) >= ACTOR_GRAPH_BUCKETS:
                            partition_values_valid = False
                    except ValueError:
                        partition_values_valid = False
                if str(partition.get("relative_dir") or "") != expected_dir:
                    partition_paths_valid = False
                if str(partition.get("schema_sha256") or "") != contract.schema_sha256:
                    parquet_schemas_valid = False

                state = _empty_partition_state()
                previous_id: str | None = None
                file_reports: list[dict[str, Any]] = []
                for file_meta in list(partition.get("files") or []):
                    relative = str(file_meta.get("path") or "")
                    if relative in expected_paths:
                        duplicate_paths += 1
                    expected_paths.add(relative)
                    if Path(relative).parent.as_posix() != expected_dir:
                        partition_paths_valid = False
                    file_path = safe_child(root, relative)
                    files_total += 1
                    if file_path is None or not file_path.is_file():
                        files_present = False
                        continue
                    actual_bytes = int(file_path.stat().st_size)
                    actual_sha256 = sha256_file(file_path)
                    bytes_total += actual_bytes
                    if actual_bytes != int(file_meta.get("bytes") or -1):
                        file_hashes_valid = False
                    if actual_sha256 != str(file_meta.get("sha256") or ""):
                        file_hashes_valid = False
                    parquet_file = pq.ParquetFile(file_path)
                    if not parquet_file.schema_arrow.equals(
                        contract.arrow_schema(), check_metadata=True
                    ):
                        parquet_schemas_valid = False
                    expected_file_rows = int(file_meta.get("rows") or 0)
                    if int(parquet_file.metadata.num_rows) != expected_file_rows:
                        file_rows_valid = False
                    for row_group_index in range(parquet_file.metadata.num_row_groups):
                        row_group = parquet_file.metadata.row_group(row_group_index)
                        if int(row_group.num_rows) > ACTOR_GRAPH_MAX_ROW_GROUP_ROWS:
                            row_groups_bounded = False
                        if (
                            declared_row_group_rows <= 0
                            or int(row_group.num_rows) > declared_row_group_rows
                        ):
                            row_groups_match_manifest_contract = False
                        for column_index in range(row_group.num_columns):
                            if (
                                str(row_group.column(column_index).compression).upper()
                                != "ZSTD"
                            ):
                                zstd_only = False
                    file_rows = 0
                    file_min_id: str | None = None
                    file_max_id: str | None = None
                    for batch in parquet_file.iter_batches(batch_size=batch_rows):
                        columns = {
                            name: batch.column(index).to_pylist()
                            for index, name in enumerate(contract.columns)
                        }
                        keys: list[tuple[str, str]] = []
                        references: list[tuple[str, str, str, str, str]] = []
                        for row_index in range(batch.num_rows):
                            row = {
                                name: columns[name][row_index]
                                for name in contract.columns
                            }
                            row_id = str(row[spec.primary_key] or "")
                            if not row_id:
                                primary_keys_sorted = False
                            if previous_id is not None and row_id <= previous_id:
                                primary_keys_sorted = False
                            previous_id = row_id
                            file_min_id = (
                                row_id
                                if file_min_id is None
                                else min(file_min_id, row_id)
                            )
                            file_max_id = (
                                row_id
                                if file_max_id is None
                                else max(file_max_id, row_id)
                            )
                            state["min_id"] = (
                                row_id
                                if state["min_id"] is None
                                else min(str(state["min_id"]), row_id)
                            )
                            state["max_id"] = (
                                row_id
                                if state["max_id"] is None
                                else max(str(state["max_id"]), row_id)
                            )
                            canonical = contract.canonical_row_bytes(row)
                            state["_digest"].update(canonical)
                            parquet_table_digests[table].update(canonical)
                            labels, identifiers, aliases = _identity_metrics(table, row)
                            state["public_label_rows"] += labels
                            state["public_identifier_rows"] += identifiers
                            public_label_rows += labels
                            public_identifier_rows += identifiers
                            public_alias_rows += aliases
                            row_private = private_token_findings(row)
                            row_non_real = non_real_marker_findings(row)
                            row_non_public_url = non_public_source_url_findings(row)
                            state["private_token_findings"] += row_private
                            state["non_real_marker_findings"] += row_non_real
                            state["non_public_source_url_findings"] += (
                                row_non_public_url
                            )
                            private_findings += row_private
                            non_real_findings += row_non_real
                            non_public_url_findings += row_non_public_url
                            if table == "actor_graph_releases":
                                release_rows += 1
                                real_data_release_rows += int(
                                    int(row["real_data_only"]) == 1
                                )
                                public_identity_release_rows += int(
                                    int(row["public_identity_retained"]) == 1
                                )
                            elif table == "actor_graph_source_mappings":
                                source_mapping_rows += 1
                            keys.append((table, row_id))
                            for child_column, parent_table, _ in spec.foreign_keys:
                                parent_id = row.get(child_column)
                                if parent_id is not None:
                                    references.append(
                                        (
                                            table,
                                            child_column,
                                            row_id,
                                            parent_table,
                                            str(parent_id),
                                        )
                                    )
                            file_rows += 1
                            state["rows"] += 1
                            rows_total += 1
                            parquet_table_rows[table] += 1
                            parquet_table_min_ids[table] = (
                                row_id
                                if parquet_table_min_ids[table] is None
                                else min(str(parquet_table_min_ids[table]), row_id)
                            )
                            parquet_table_max_ids[table] = (
                                row_id
                                if parquet_table_max_ids[table] is None
                                else max(str(parquet_table_max_ids[table]), row_id)
                            )
                        duplicate_primary_keys += _insert_keys(key_index, keys)
                        key_index.executemany(
                            """
                            INSERT INTO exported_refs(
                              child_table, child_column, child_id,
                              parent_table, parent_id
                            ) VALUES (?, ?, ?, ?, ?)
                            """,
                            references,
                        )
                    if file_rows != expected_file_rows:
                        file_rows_valid = False
                    if file_min_id != file_meta.get("min_id"):
                        file_minmax_valid = False
                    if file_max_id != file_meta.get("max_id"):
                        file_minmax_valid = False
                    if file_rows > ACTOR_GRAPH_MAX_FILE_ROWS:
                        file_rows_valid = False
                    if (
                        declared_max_file_rows <= 0
                        or file_rows > declared_max_file_rows
                    ):
                        files_match_manifest_contract = False
                    file_reports.append(
                        {
                            "path": relative,
                            "rows": file_rows,
                            "bytes": actual_bytes,
                            "sha256": actual_sha256,
                            "min_id": file_min_id,
                            "max_id": file_max_id,
                        }
                    )
                actual_state = _finalize_partition_state(state)
                source_state = expected_source_partitions.get(expected_partition_id)
                if source_state is None:
                    partition_rows_valid = False
                    partition_hashes_valid = False
                else:
                    for key in (
                        "rows",
                        "min_id",
                        "max_id",
                        "public_label_rows",
                        "public_identifier_rows",
                        "private_token_findings",
                        "non_real_marker_findings",
                        "non_public_source_url_findings",
                    ):
                        if actual_state[key] != source_state[key]:
                            partition_rows_valid = False
                    if actual_state["input_sha256"] != source_state["input_sha256"]:
                        partition_hashes_valid = False
                for key in (
                    "rows",
                    "min_id",
                    "max_id",
                    "public_label_rows",
                    "public_identifier_rows",
                    "private_token_findings",
                    "non_real_marker_findings",
                    "non_public_source_url_findings",
                ):
                    if actual_state[key] != partition.get(key):
                        partition_rows_valid = False
                if actual_state["input_sha256"] != str(
                    partition.get("input_sha256") or ""
                ):
                    partition_hashes_valid = False
                partition_reports.append(
                    {
                        "partition_id": expected_partition_id,
                        "rows": actual_state["rows"],
                        "files": file_reports,
                        "input_sha256": actual_state["input_sha256"],
                    }
                )
            key_index.commit()
            fk_report = _critical_fk_report(key_index)
        finally:
            key_index.close()
        key_index_bytes = (
            int(key_index_path.stat().st_size) if key_index_path.exists() else 0
        )

    actual_paths = {
        path.relative_to(root).as_posix() for path in root.rglob("*.parquet")
    }
    parquet_table_hashes = {
        table: digest.hexdigest() for table, digest in parquet_table_digests.items()
    }
    parquet_aggregate = hashlib.sha256()
    for spec in ACTOR_GRAPH_TABLE_SPECS:
        parquet_aggregate.update(spec.name.encode("utf-8") + b"\0")
        parquet_aggregate.update(
            parquet_table_hashes[spec.name].encode("ascii") + b"\n"
        )
    parquet_content_sha256 = parquet_aggregate.hexdigest()
    totals = dict(manifest.get("totals") or {})
    manifest_table_rows = dict(totals.get("table_rows") or {})
    manifest_table_hashes = dict(totals.get("table_content_sha256") or {})
    source_table_rows = dict(source["table_rows"])
    source_table_hashes = dict(source["table_content_sha256"])
    source_manifest = dict(manifest.get("source") or {})
    publication_policy = dict(manifest.get("publication_policy") or {})
    peak_rss = peak_rss_mb()

    expected_table_contracts = {
        spec.name: {
            "table": spec.name,
            "primary_key": spec.primary_key,
            "foreign_keys": [
                {
                    "column": child,
                    "parent_table": parent,
                    "parent_column": parent_column,
                }
                for child, parent, parent_column in spec.foreign_keys
            ],
            "sqlite_columns": sqlite_schemas[spec.name],
            "parquet_schema": list(contracts[spec.name].schema),
            "parquet_schema_sha256": contracts[spec.name].schema_sha256,
            "rows": source_table_rows[spec.name],
            "min_id": source["table_min_ids"][spec.name],
            "max_id": source["table_max_ids"][spec.name],
            "content_sha256": source_table_hashes[spec.name],
        }
        for spec in ACTOR_GRAPH_TABLE_SPECS
    }
    checks = {
        "manifest_schema_version": manifest.get("schema_version")
        == MANIFEST_SCHEMA_VERSION,
        "manifest_lane": manifest.get("lane") == ACTOR_GRAPH_LANE,
        "transformer_version": manifest.get("transformer_version")
        == ACTOR_GRAPH_TRANSFORMER_VERSION,
        "required_table_set": set(manifest_tables) == expected_table_names,
        "table_contracts_exact": manifest_tables == expected_table_contracts,
        "aggregate_schema_exact": manifest.get("schema_sha256")
        == expected_schema_sha256,
        "partition_contract": (
            partition_contract.get("strategy")
            == "table_release_bounded_source_or_type_hash"
            and partition_contract.get("keys")
            == ["snapshot_date", "table", "release_id", "bucket"]
            and int(partition_contract.get("bucket_count") or 0) == ACTOR_GRAPH_BUCKETS
            and partition_contract.get("ordering")
            == ["table", "release_id", "bucket", "primary_key"]
            and partition_contract.get("scan")
            == "single_ordered_cursor_fetchmany_no_offset"
            and declared_cursor_fetch_rows > 0
            and 0 < declared_row_group_rows <= ACTOR_GRAPH_MAX_ROW_GROUP_ROWS
            and 0 < declared_max_file_rows <= ACTOR_GRAPH_MAX_FILE_ROWS
            and declared_row_group_rows <= declared_max_file_rows
            and str(partition_contract.get("compression") or "").casefold() == "zstd"
        ),
        "publication_policy": (
            publication_policy.get("real_records_only") is True
            and publication_policy.get(
                "official_public_domain_personal_information_retained"
            )
            is True
            and publication_policy.get(
                "canonical_labels_identifiers_aliases_not_redacted"
            )
            is True
            and publication_policy.get(
                "workstation_paths_credentials_and_sessions_forbidden"
            )
            is True
        ),
        "manifest_publication_hygiene": manifest_private_findings == 0
        and manifest_non_real_findings == 0,
        "source_database_file_is_basename": str(
            source_manifest.get("database_file") or ""
        )
        == Path(str(source_manifest.get("database_file") or "")).name,
        "source_database_sha256": source_manifest.get("database_sha256")
        == sha256_file(source_db_path),
        "source_semantic_sha256": source_manifest.get("semantic_content_sha256")
        == source["content_sha256"],
        "source_primary_keys_unique": int(source["pk_duplicates"]) == 0,
        "source_join_balance": bool(source["join_balance"]),
        "source_foreign_keys": int(source["source_fk_errors"]) == 0,
        "manifest_partition_ids_unique": duplicate_partition_ids == 0,
        "partition_set_exact": set(manifest_partition_by_id)
        == set(expected_source_partitions),
        "partition_values": partition_values_valid,
        "partition_paths": partition_paths_valid,
        "partition_rows_exact": partition_rows_valid,
        "partition_hashes_exact": partition_hashes_valid,
        "files_present": files_present,
        "file_paths_unique": duplicate_paths == 0,
        "no_unlisted_parquet_files": actual_paths == expected_paths,
        "file_hashes": file_hashes_valid,
        "parquet_schemas": parquet_schemas_valid,
        "file_rows": file_rows_valid,
        "file_minmax": file_minmax_valid,
        "zstd_compression": zstd_only,
        "row_groups_at_most_25000": row_groups_bounded,
        "row_groups_match_manifest_contract": row_groups_match_manifest_contract,
        "files_at_most_100000_rows": all(
            int(file_meta.get("rows") or 0) <= ACTOR_GRAPH_MAX_FILE_ROWS
            for partition in manifest_partitions
            for file_meta in list(partition.get("files") or [])
        ),
        "files_match_manifest_contract": files_match_manifest_contract,
        "primary_keys_sorted_within_partitions": primary_keys_sorted,
        "primary_keys_unique_across_partitions": duplicate_primary_keys == 0
        and fk_report["keys"] == rows_total,
        "critical_foreign_keys": int(fk_report["missing"]) == 0,
        "exact_source_table_row_counts": parquet_table_rows == source_table_rows,
        "manifest_table_row_counts": manifest_table_rows == source_table_rows,
        "exact_table_content_hashes": parquet_table_hashes == source_table_hashes,
        "manifest_table_content_hashes": manifest_table_hashes == source_table_hashes,
        "aggregate_content_hash": parquet_content_sha256
        == source["content_sha256"]
        == totals.get("content_sha256"),
        "manifest_row_total": rows_total
        == int(totals.get("rows") or -1)
        == int(source["rows"]),
        "manifest_partition_total": len(partition_reports)
        == int(totals.get("partitions") or -1),
        "manifest_file_total": files_total == int(totals.get("files") or -1),
        "manifest_byte_total": bytes_total == int(totals.get("parquet_bytes") or -1),
        "minimum_rows": rows_total >= int(min_rows),
        "real_data_only_release_flags": release_rows > 0
        and real_data_release_rows
        == release_rows
        == int(source["real_data_release_rows"]),
        "public_identity_release_flags": release_rows > 0
        and public_identity_release_rows
        == release_rows
        == int(source["public_identity_release_rows"]),
        "source_mappings_retained": source_mapping_rows > 0
        and source_mapping_rows == int(source["source_mapping_rows"]),
        "public_labels_retained": public_label_rows
        == int(source["public_label_rows"])
        == source_table_rows["actor_graph_node_versions"],
        "public_identifiers_retained": public_identifier_rows
        == int(source["public_identifier_rows"])
        == source_table_rows["actor_graph_identifier_versions"],
        "public_aliases_retained": public_alias_rows
        == int(source["public_alias_rows"])
        == source_table_rows["actor_graph_alias_versions"],
        "no_private_tokens": private_findings
        == 0
        == int(source["private_token_findings"]),
        "no_non_real_markers": non_real_findings
        == 0
        == int(source["non_real_marker_findings"]),
        "source_urls_public_and_credential_free": non_public_url_findings
        == 0
        == int(source["non_public_source_url_findings"]),
        "bounded_peak_rss": peak_rss <= float(max_peak_rss_mb),
    }
    status = "ok" if all(checks.values()) else "failed"
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "status": status,
        "manifest_file": manifest_path.name,
        "root_name": root.name,
        "source_database_file": source_db_path.name,
        "checks": checks,
        "totals": {
            "rows": rows_total,
            "tables": len(ACTOR_GRAPH_TABLE_SPECS),
            "table_rows": parquet_table_rows,
            "partitions": len(partition_reports),
            "files": files_total,
            "parquet_bytes": bytes_total,
            "public_label_rows": public_label_rows,
            "public_identifier_rows": public_identifier_rows,
            "public_alias_rows": public_alias_rows,
            "private_token_findings": private_findings,
            "non_real_marker_findings": non_real_findings,
            "non_public_source_url_findings": non_public_url_findings,
            "manifest_private_token_findings": manifest_private_findings,
            "manifest_non_real_marker_findings": manifest_non_real_findings,
        },
        "critical_foreign_keys": fk_report,
        "content": {
            "source_semantic_sha256": source["content_sha256"],
            "parquet_semantic_sha256": parquet_content_sha256,
            "table_content_sha256": parquet_table_hashes,
        },
        "performance": {
            "peak_rss_mb": peak_rss,
            "max_peak_rss_mb": float(max_peak_rss_mb),
            "batch_rows": int(batch_rows),
            "source_fetch_rows": int(source_fetch_rows),
            "source_cursor_batches": int(source["source_cursor_batches"]),
            "source_ordered_query_executions": int(
                source["source_ordered_query_executions"]
            ),
            "on_disk_key_index_bytes": key_index_bytes,
        },
        "analytical_partition_gate_passed": all(checks.values()),
        "promotion_gate_passed": bool(manifest.get("promotion_gate_passed"))
        and all(checks.values()),
        "partitions": partition_reports,
        "limitations": [
            "Validation uses an on-disk SQLite key/FK index; memory is bounded but temporary disk use grows linearly with exported graph edges.",
            "This proves exact equivalence to the supplied actor-graph SQLite database, not correctness of upstream official records.",
            "Durable-origin upload and a clean-room restore remain separate promotion gates.",
        ],
    }


__all__ = ["VALIDATION_SCHEMA_VERSION", "validate_actor_graph_partitions"]
