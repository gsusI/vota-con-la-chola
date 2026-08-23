"""Lossless, bounded Parquet publication for the time-aware actor graph.

The actor graph is a normalized multi-table product.  This lane therefore
publishes every graph table without flattening or dropping public identity
fields.  Partition metadata is derived from release plus a fixed 64-way hash
of the table's natural source/type discriminator.  Each table uses one ordered
SQLite cursor and bounded ``fetchmany`` batches; no repeated sort, OFFSET scan,
or whole-table Python materialization is used.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .semantic_contracts import (
    MANIFEST_SCHEMA_VERSION,
    SemanticLaneContract,
    peak_rss_mb,
    private_token_findings,
    safe_component,
    sha256_file,
)
from .semantic_parquet_io import (
    PartitionWriter,
    reusable_partition,
    reuse_partition_files,
)

ACTOR_GRAPH_LANE = "actor_graph"
ACTOR_GRAPH_TRANSFORMER_VERSION = "actor_graph_lossless_public_v1"
ACTOR_GRAPH_BUCKETS = 64
ACTOR_GRAPH_MAX_ROW_GROUP_ROWS = 25_000
ACTOR_GRAPH_MAX_FILE_ROWS = 100_000


@dataclass(frozen=True)
class ActorGraphTableSpec:
    name: str
    primary_key: str
    release_sql: str
    bucket_token_sql: str
    joins_sql: str = ""
    foreign_keys: tuple[tuple[str, str, str], ...] = ()


# Order is parent-before-child for restore and audit consumers.
ACTOR_GRAPH_TABLE_SPECS: tuple[ActorGraphTableSpec, ...] = (
    ActorGraphTableSpec(
        "actor_graph_releases",
        "release_id",
        "t.release_id",
        "'type:release'",
    ),
    ActorGraphTableSpec(
        "actor_graph_source_mappings",
        "source_mapping_id",
        "t.release_id",
        "'source:' || t.upstream_source_id",
        foreign_keys=(("release_id", "actor_graph_releases", "release_id"),),
    ),
    ActorGraphTableSpec(
        "actor_graph_nodes",
        "actor_id",
        "t.first_release_id",
        "'type:' || t.actor_kind",
        foreign_keys=(("first_release_id", "actor_graph_releases", "release_id"),),
    ),
    ActorGraphTableSpec(
        "actor_graph_node_versions",
        "node_version_id",
        "t.release_id",
        "'source:' || t.source_id",
        foreign_keys=(
            ("actor_id", "actor_graph_nodes", "actor_id"),
            ("release_id", "actor_graph_releases", "release_id"),
            (
                "supersedes_node_version_id",
                "actor_graph_node_versions",
                "node_version_id",
            ),
        ),
    ),
    ActorGraphTableSpec(
        "actor_graph_identifier_versions",
        "identifier_version_id",
        "t.release_id",
        "'source:' || t.source_id",
        foreign_keys=(
            ("actor_id", "actor_graph_nodes", "actor_id"),
            ("release_id", "actor_graph_releases", "release_id"),
        ),
    ),
    ActorGraphTableSpec(
        "actor_graph_alias_versions",
        "alias_version_id",
        "t.release_id",
        "'source:' || t.source_id",
        foreign_keys=(
            ("actor_id", "actor_graph_nodes", "actor_id"),
            ("release_id", "actor_graph_releases", "release_id"),
        ),
    ),
    ActorGraphTableSpec(
        "actor_graph_relationships",
        "relationship_id",
        "t.created_release_id",
        "'type:' || t.relationship_type",
        foreign_keys=(
            ("subject_actor_id", "actor_graph_nodes", "actor_id"),
            ("object_actor_id", "actor_graph_nodes", "actor_id"),
            ("created_release_id", "actor_graph_releases", "release_id"),
        ),
    ),
    ActorGraphTableSpec(
        "actor_graph_relationship_versions",
        "relationship_version_id",
        "t.release_id",
        "'source:' || t.source_id",
        foreign_keys=(
            (
                "relationship_id",
                "actor_graph_relationships",
                "relationship_id",
            ),
            ("release_id", "actor_graph_releases", "release_id"),
            (
                "supersedes_relationship_version_id",
                "actor_graph_relationship_versions",
                "relationship_version_id",
            ),
        ),
    ),
    ActorGraphTableSpec(
        "actor_graph_relationship_evidence",
        "relationship_evidence_id",
        "parent_version.release_id",
        "'source:' || t.source_id || ':kind:' || t.evidence_kind",
        joins_sql=(
            "JOIN actor_graph_relationship_versions AS parent_version "
            "ON parent_version.relationship_version_id = "
            "t.relationship_version_id"
        ),
        foreign_keys=(
            (
                "relationship_version_id",
                "actor_graph_relationship_versions",
                "relationship_version_id",
            ),
        ),
    ),
    ActorGraphTableSpec(
        "actor_resolution_decisions",
        "resolution_decision_id",
        "t.release_id",
        "'type:' || t.outcome",
        foreign_keys=(
            ("release_id", "actor_graph_releases", "release_id"),
            ("source_actor_id", "actor_graph_nodes", "actor_id"),
            ("candidate_actor_id", "actor_graph_nodes", "actor_id"),
            (
                "supersedes_decision_id",
                "actor_resolution_decisions",
                "resolution_decision_id",
            ),
        ),
    ),
    ActorGraphTableSpec(
        "actor_resolution_evidence",
        "resolution_evidence_id",
        "parent_decision.release_id",
        "'source:' || t.source_id",
        joins_sql=(
            "JOIN actor_resolution_decisions AS parent_decision "
            "ON parent_decision.resolution_decision_id = "
            "t.resolution_decision_id"
        ),
        foreign_keys=(
            (
                "resolution_decision_id",
                "actor_resolution_decisions",
                "resolution_decision_id",
            ),
        ),
    ),
    ActorGraphTableSpec(
        "actor_organization_change_events",
        "organization_change_event_id",
        "t.release_id",
        "'type:' || t.event_type",
        foreign_keys=(
            ("release_id", "actor_graph_releases", "release_id"),
            ("subject_actor_id", "actor_graph_nodes", "actor_id"),
            ("object_actor_id", "actor_graph_nodes", "actor_id"),
            (
                "supersedes_event_id",
                "actor_organization_change_events",
                "organization_change_event_id",
            ),
        ),
    ),
    ActorGraphTableSpec(
        "actor_organization_change_evidence",
        "organization_change_evidence_id",
        "parent_event.release_id",
        "'type:' || parent_event.event_type",
        joins_sql=(
            "JOIN actor_organization_change_events AS parent_event "
            "ON parent_event.organization_change_event_id = "
            "t.organization_change_event_id"
        ),
        foreign_keys=(
            (
                "organization_change_event_id",
                "actor_organization_change_events",
                "organization_change_event_id",
            ),
        ),
    ),
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def actor_partition_bucket(value: Any) -> str:
    payload = str(value if value is not None else "unknown").encode("utf-8")
    ordinal = int.from_bytes(hashlib.sha256(payload).digest()[:2], "big")
    return f"b{ordinal % ACTOR_GRAPH_BUCKETS:02x}"


def _connect_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA temp_store = FILE")
    connection.create_function(
        "actor_partition_bucket", 1, actor_partition_bucket, deterministic=True
    )
    return connection


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _sqlite_arrow_type(declared_type: str) -> str:
    normalized = declared_type.strip().upper()
    if "INT" in normalized:
        return "int64"
    if any(token in normalized for token in ("REAL", "FLOA", "DOUB")):
        return "float64"
    if any(token in normalized for token in ("CHAR", "CLOB", "TEXT")):
        return "string"
    raise TypeError(f"unsupported actor-graph SQLite type: {declared_type!r}")


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _table_contract(
    connection: sqlite3.Connection, spec: ActorGraphTableSpec
) -> tuple[SemanticLaneContract, list[dict[str, Any]]]:
    if not _table_exists(connection, spec.name):
        raise RuntimeError(f"required actor-graph table is missing: {spec.name}")
    pragma_rows = list(
        connection.execute(f"PRAGMA table_info({_quote_identifier(spec.name)})")
    )
    if not pragma_rows:
        raise RuntimeError(f"actor-graph table has no columns: {spec.name}")
    sqlite_columns: list[dict[str, Any]] = []
    parquet_schema: list[dict[str, Any]] = []
    primary_keys: list[tuple[int, str]] = []
    for row in pragma_rows:
        name = str(row[1])
        declared_type = str(row[2])
        pk_ordinal = int(row[5])
        if pk_ordinal:
            primary_keys.append((pk_ordinal, name))
        sqlite_columns.append(
            {
                "name": name,
                "declared_type": declared_type,
                "not_null": bool(row[3]),
                "default_sql": row[4],
                "pk_ordinal": pk_ordinal,
            }
        )
        parquet_schema.append(
            {
                "name": name,
                "type": _sqlite_arrow_type(declared_type),
                "nullable": not (bool(row[3]) or pk_ordinal > 0),
            }
        )
    ordered_primary_keys = [name for _, name in sorted(primary_keys)]
    if ordered_primary_keys != [spec.primary_key]:
        raise RuntimeError(
            f"{spec.name} primary key drift: {ordered_primary_keys!r}, "
            f"expected {[spec.primary_key]!r}"
        )
    contract = SemanticLaneContract(
        lane=f"{ACTOR_GRAPH_LANE}.{spec.name}",
        transformer_version=ACTOR_GRAPH_TRANSFORMER_VERSION,
        id_column=spec.primary_key,
        year_column="release_id",
        schema=tuple(parquet_schema),
    )
    return contract, sqlite_columns


def load_actor_graph_contracts(
    db_path: Path,
) -> tuple[
    dict[str, SemanticLaneContract],
    dict[str, list[dict[str, Any]]],
]:
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    connection = _connect_readonly(db_path)
    try:
        return _load_actor_graph_contracts(connection)
    finally:
        connection.close()


def _load_actor_graph_contracts(
    connection: sqlite3.Connection,
) -> tuple[
    dict[str, SemanticLaneContract],
    dict[str, list[dict[str, Any]]],
]:
    contracts: dict[str, SemanticLaneContract] = {}
    sqlite_schemas: dict[str, list[dict[str, Any]]] = {}
    for spec in ACTOR_GRAPH_TABLE_SPECS:
        contract, sqlite_columns = _table_contract(connection, spec)
        contracts[spec.name] = contract
        sqlite_schemas[spec.name] = sqlite_columns
    return contracts, sqlite_schemas


def actor_graph_schema_sha256(
    contracts: dict[str, SemanticLaneContract],
    sqlite_schemas: dict[str, list[dict[str, Any]]],
) -> str:
    payload = [
        {
            "table": spec.name,
            "primary_key": spec.primary_key,
            "foreign_keys": [list(item) for item in spec.foreign_keys],
            "parquet_schema": contracts[spec.name].schema,
            "parquet_schema_sha256": contracts[spec.name].schema_sha256,
            "sqlite_columns": sqlite_schemas[spec.name],
        }
        for spec in ACTOR_GRAPH_TABLE_SPECS
    ]
    encoded = json.dumps(
        payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _bucket_sql(spec: ActorGraphTableSpec) -> str:
    return f"actor_partition_bucket({spec.bucket_token_sql})"


def _iter_table_rows(
    connection: sqlite3.Connection,
    spec: ActorGraphTableSpec,
    contract: SemanticLaneContract,
    *,
    fetch_rows: int,
    telemetry: dict[str, int] | None = None,
) -> Iterator[tuple[dict[str, Any], str, str]]:
    if fetch_rows <= 0:
        raise ValueError("fetch-rows must be positive")
    quoted_table = _quote_identifier(spec.name)
    quoted_pk = _quote_identifier(spec.primary_key)
    bucket_sql = _bucket_sql(spec)
    base_sql = f"""
        SELECT t.*, {spec.release_sql} AS __release_id,
               {bucket_sql} AS __partition_bucket
        FROM {quoted_table} AS t
        {spec.joins_sql}
    """
    order_sql = (
        f" ORDER BY {spec.release_sql}, {bucket_sql}, CAST(t.{quoted_pk} AS TEXT)"
    )
    cursor = connection.execute(base_sql + order_sql)
    if telemetry is not None:
        telemetry["ordered_query_executions"] = (
            telemetry.get("ordered_query_executions", 0) + 1
        )
    last_key: tuple[str, str, str] | None = None
    while True:
        page = cursor.fetchmany(int(fetch_rows))
        if not page:
            break
        if telemetry is not None:
            telemetry["cursor_batches"] = telemetry.get("cursor_batches", 0) + 1
        for source_row in page:
            release_id = str(source_row["__release_id"] or "")
            bucket = str(source_row["__partition_bucket"] or "")
            row = {column: source_row[column] for column in contract.columns}
            row_id = str(row[spec.primary_key] or "")
            if not release_id or not bucket or not row_id:
                raise RuntimeError(
                    f"{spec.name} has an empty release, bucket, or primary key"
                )
            key = (release_id, bucket, row_id)
            if last_key is not None and key <= last_key:
                raise RuntimeError(
                    f"{spec.name} ordered cursor is not strictly increasing"
                )
            last_key = key
            yield row, release_id, bucket


def _string_values(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _string_values(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _string_values(nested)


def _truthy_non_real_json(value: Any) -> int:
    if isinstance(value, dict):
        findings = 0
        for key, nested in value.items():
            normalized = str(key).casefold()
            if ("synthetic" in normalized or "mock" in normalized) and nested not in (
                False,
                0,
                None,
                "",
                "false",
                "0",
            ):
                findings += 1
            findings += _truthy_non_real_json(nested)
        return findings
    if isinstance(value, list):
        return sum(_truthy_non_real_json(item) for item in value)
    return 0


def non_real_marker_findings(row: dict[str, Any]) -> int:
    findings = 0
    exact_markers = (
        "example.invalid",
        "example.test",
        "synthetic sample",
        "fallback-sample",
        "network-error-fallback",
        "(synthetic)",
    )
    identifier_columns = {
        "actor_id",
        "source_scope_id",
        "stable_source_key",
        "source_id",
        "source_record_id",
        "input_database_key",
        "upstream_source_id",
        "graph_source_id",
        "context_id",
    }
    for column, value in row.items():
        for text in _string_values(value):
            folded = text.casefold()
            findings += sum(marker in folded for marker in exact_markers)
            if column in identifier_columns:
                components = {
                    component
                    for component in folded.replace("-", "_")
                    .replace(":", "_")
                    .split("_")
                    if component
                }
                if components.intersection({"mock", "synthetic", "fixture", "fake"}):
                    findings += 1
            if text[:1] in {"{", "["}:
                try:
                    parsed = json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    continue
                findings += _truthy_non_real_json(parsed)
            if column.endswith("url") and text:
                try:
                    host = (urlsplit(text).hostname or "").casefold()
                except ValueError:
                    host = ""
                if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".test"):
                    findings += 1
    return findings


def non_public_source_url_findings(row: dict[str, Any]) -> int:
    findings = 0
    for column, value in row.items():
        if not column.endswith("url") or value in (None, ""):
            continue
        try:
            parsed = urlsplit(str(value))
        except ValueError:
            findings += 1
            continue
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
        ):
            findings += 1
    return findings


def _partition_id(table: str, release_id: str, bucket: str) -> str:
    return f"{table}|{release_id}|{bucket}"


def _partition_dir(
    snapshot_date: str, table: str, release_id: str, bucket: str
) -> Path:
    return Path(
        f"lane={ACTOR_GRAPH_LANE}",
        f"snapshot_date={safe_component(snapshot_date)}",
        f"table={safe_component(table)}",
        f"release={safe_component(release_id)}",
        f"bucket={safe_component(bucket)}",
    )


def _new_partition(
    *,
    snapshot_date: str,
    table: str,
    release_id: str,
    bucket: str,
    contract: SemanticLaneContract,
) -> dict[str, Any]:
    return {
        "partition_id": _partition_id(table, release_id, bucket),
        "values": {
            "snapshot_date": snapshot_date,
            "table": table,
            "release_id": release_id,
            "bucket": bucket,
        },
        "relative_dir": _partition_dir(
            snapshot_date, table, release_id, bucket
        ).as_posix(),
        "schema_sha256": contract.schema_sha256,
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


def _identity_metrics(table: str, row: dict[str, Any]) -> tuple[int, int]:
    label_rows = int(
        table == "actor_graph_node_versions"
        and bool(str(row.get("canonical_label") or "").strip())
    )
    identifier_rows = int(
        table == "actor_graph_identifier_versions"
        and bool(str(row.get("namespace") or "").strip())
        and bool(str(row.get("value") or "").strip())
    )
    return label_rows, identifier_rows


def scan_actor_graph_partitions(
    db_path: Path,
    *,
    snapshot_date: str,
    fetch_rows: int = 25_000,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, SemanticLaneContract],
    dict[str, list[dict[str, Any]]],
]:
    totals: dict[str, Any] = {
        "rows": 0,
        "table_rows": {spec.name: 0 for spec in ACTOR_GRAPH_TABLE_SPECS},
        "table_min_ids": {spec.name: None for spec in ACTOR_GRAPH_TABLE_SPECS},
        "table_max_ids": {spec.name: None for spec in ACTOR_GRAPH_TABLE_SPECS},
        "table_content_sha256": {},
        "public_label_rows": 0,
        "public_identifier_rows": 0,
        "public_alias_rows": 0,
        "private_token_findings": 0,
        "non_real_marker_findings": 0,
        "non_public_source_url_findings": 0,
        "release_rows": 0,
        "real_data_release_rows": 0,
        "public_identity_release_rows": 0,
        "source_mapping_rows": 0,
        "cursor_batches": 0,
        "ordered_query_executions": 0,
    }
    partitions: list[dict[str, Any]] = []
    connection = _connect_readonly(Path(db_path))
    try:
        # One read transaction makes contracts, counts, hashes, and all table
        # streams describe one immutable SQLite snapshot.
        connection.execute("BEGIN")
        contracts, sqlite_schemas = _load_actor_graph_contracts(connection)
        for spec in ACTOR_GRAPH_TABLE_SPECS:
            contract = contracts[spec.name]
            table_digest = hashlib.sha256()
            current: dict[str, Any] | None = None
            current_key: tuple[str, str] | None = None
            previous_id: str | None = None
            telemetry = {"cursor_batches": 0, "ordered_query_executions": 0}
            for row, release_id, bucket in _iter_table_rows(
                connection,
                spec,
                contract,
                fetch_rows=fetch_rows,
                telemetry=telemetry,
            ):
                key = (release_id, bucket)
                if current_key != key:
                    if current is not None:
                        current["input_sha256"] = current.pop("_digest").hexdigest()
                        partitions.append(current)
                    current_key = key
                    current = _new_partition(
                        snapshot_date=snapshot_date,
                        table=spec.name,
                        release_id=release_id,
                        bucket=bucket,
                        contract=contract,
                    )
                    previous_id = None
                assert current is not None
                row_id = str(row[spec.primary_key])
                if previous_id is not None and row_id <= previous_id:
                    raise RuntimeError(
                        f"{spec.name} primary keys are not ordered within partition"
                    )
                previous_id = row_id
                canonical = contract.canonical_row_bytes(row)
                current["_digest"].update(canonical)
                table_digest.update(canonical)
                current["rows"] += 1
                current["min_id"] = (
                    row_id
                    if current["min_id"] is None
                    else min(str(current["min_id"]), row_id)
                )
                current["max_id"] = (
                    row_id
                    if current["max_id"] is None
                    else max(str(current["max_id"]), row_id)
                )
                label_rows, identifier_rows = _identity_metrics(spec.name, row)
                current["public_label_rows"] += label_rows
                current["public_identifier_rows"] += identifier_rows
                totals["public_label_rows"] += label_rows
                totals["public_identifier_rows"] += identifier_rows
                if (
                    spec.name == "actor_graph_alias_versions"
                    and str(row.get("alias") or "").strip()
                ):
                    totals["public_alias_rows"] += 1
                private_findings = private_token_findings(row)
                non_real_findings = non_real_marker_findings(row)
                non_public_url_findings = non_public_source_url_findings(row)
                current["private_token_findings"] += private_findings
                current["non_real_marker_findings"] += non_real_findings
                current["non_public_source_url_findings"] += non_public_url_findings
                totals["private_token_findings"] += private_findings
                totals["non_real_marker_findings"] += non_real_findings
                totals["non_public_source_url_findings"] += non_public_url_findings
                totals["rows"] += 1
                totals["table_rows"][spec.name] += 1
                table_min = totals["table_min_ids"][spec.name]
                table_max = totals["table_max_ids"][spec.name]
                totals["table_min_ids"][spec.name] = (
                    row_id if table_min is None else min(str(table_min), row_id)
                )
                totals["table_max_ids"][spec.name] = (
                    row_id if table_max is None else max(str(table_max), row_id)
                )
                if spec.name == "actor_graph_releases":
                    totals["release_rows"] += 1
                    totals["real_data_release_rows"] += int(
                        int(row["real_data_only"]) == 1
                    )
                    totals["public_identity_release_rows"] += int(
                        int(row["public_identity_retained"]) == 1
                    )
                elif spec.name == "actor_graph_source_mappings":
                    totals["source_mapping_rows"] += 1
            if current is not None:
                current["input_sha256"] = current.pop("_digest").hexdigest()
                partitions.append(current)
            totals["table_content_sha256"][spec.name] = table_digest.hexdigest()
            totals["cursor_batches"] += telemetry["cursor_batches"]
            totals["ordered_query_executions"] += telemetry["ordered_query_executions"]
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()
    aggregate_digest = hashlib.sha256()
    for spec in ACTOR_GRAPH_TABLE_SPECS:
        aggregate_digest.update(spec.name.encode("utf-8") + b"\0")
        aggregate_digest.update(
            str(totals["table_content_sha256"][spec.name]).encode("ascii") + b"\n"
        )
    totals["content_sha256"] = aggregate_digest.hexdigest()
    return partitions, totals, contracts, sqlite_schemas


def _previous_partitions(
    manifest_path: Path | None,
    *,
    schema_sha256: str,
    compression: str,
    row_group_rows: int,
    max_file_rows: int,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    if manifest_path is None:
        return {}, None
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    partition_contract = dict(payload.get("partition_contract") or {})
    valid = (
        payload.get("schema_version") == MANIFEST_SCHEMA_VERSION
        and payload.get("lane") == ACTOR_GRAPH_LANE
        and payload.get("transformer_version") == ACTOR_GRAPH_TRANSFORMER_VERSION
        and payload.get("schema_sha256") == schema_sha256
        and str(partition_contract.get("compression") or "").casefold()
        == compression.casefold()
        and int(partition_contract.get("row_group_rows") or 0) == int(row_group_rows)
        and int(partition_contract.get("max_file_rows") or 0) == int(max_file_rows)
    )
    partitions = (
        {
            str(item["partition_id"]): item
            for item in list(payload.get("partitions") or [])
        }
        if valid
        else {}
    )
    return partitions, sha256_file(manifest_path)


def _table_manifest(
    spec: ActorGraphTableSpec,
    contract: SemanticLaneContract,
    sqlite_schema: list[dict[str, Any]],
    totals: dict[str, Any],
) -> dict[str, Any]:
    return {
        "table": spec.name,
        "primary_key": spec.primary_key,
        "foreign_keys": [
            {"column": child, "parent_table": parent, "parent_column": parent_col}
            for child, parent, parent_col in spec.foreign_keys
        ],
        "sqlite_columns": sqlite_schema,
        "parquet_schema": contract.schema,
        "parquet_schema_sha256": contract.schema_sha256,
        "rows": int(totals["table_rows"][spec.name]),
        "min_id": totals["table_min_ids"][spec.name],
        "max_id": totals["table_max_ids"][spec.name],
        "content_sha256": totals["table_content_sha256"][spec.name],
    }


def export_actor_graph_partitions(
    *,
    db_path: Path,
    output_root: Path,
    snapshot_date: str,
    compression: str = "zstd",
    row_group_rows: int = ACTOR_GRAPH_MAX_ROW_GROUP_ROWS,
    max_file_rows: int = ACTOR_GRAPH_MAX_FILE_ROWS,
    previous_manifest_path: Path | None = None,
    previous_root: Path | None = None,
    min_rows: int = 1,
    max_peak_rss_mb: float = 1024.0,
    enforce: bool = False,
    cursor_fetch_rows: int = 25_000,
) -> dict[str, Any]:
    db_path = Path(db_path)
    output_root = Path(output_root)
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    if output_root.exists():
        raise FileExistsError(output_root)
    if compression.casefold() != "zstd":
        raise ValueError("actor_graph requires zstd compression")
    if row_group_rows <= 0 or row_group_rows > ACTOR_GRAPH_MAX_ROW_GROUP_ROWS:
        raise ValueError("actor_graph row-group-rows must be between 1 and 25000")
    if max_file_rows <= 0 or max_file_rows > ACTOR_GRAPH_MAX_FILE_ROWS:
        raise ValueError("actor_graph max-file-rows must be between 1 and 100000")
    if row_group_rows > max_file_rows:
        raise ValueError("row-group-rows cannot exceed max-file-rows")
    if cursor_fetch_rows <= 0:
        raise ValueError("cursor-fetch-rows must be positive")
    if (previous_manifest_path is None) != (previous_root is None):
        raise ValueError(
            "previous-manifest and previous-root must be provided together"
        )

    started = time.monotonic()
    scan_started = time.monotonic()
    partitions, scan_totals, contracts, sqlite_schemas = scan_actor_graph_partitions(
        db_path,
        snapshot_date=snapshot_date,
        fetch_rows=cursor_fetch_rows,
    )
    scan_seconds = time.monotonic() - scan_started
    schema_sha256 = actor_graph_schema_sha256(contracts, sqlite_schemas)
    previous_by_id, previous_sha256 = _previous_partitions(
        previous_manifest_path,
        schema_sha256=schema_sha256,
        compression=compression,
        row_group_rows=row_group_rows,
        max_file_rows=max_file_rows,
    )
    reusable: dict[str, dict[str, Any]] = {}
    for partition in partitions:
        previous = previous_by_id.get(str(partition["partition_id"]))
        eligible = reusable_partition(
            partition=partition,
            previous=previous,
            previous_root=previous_root,
        )
        if eligible is not None:
            reusable[str(partition["partition_id"])] = eligible

    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.staging-", dir=output_root.parent)
    )
    partition_by_id = {
        str(partition["partition_id"]): partition for partition in partitions
    }
    hardlinks = 0
    copies = 0
    materialize_batches = 0
    materialize_query_executions = 0
    try:
        for partition_id, previous in reusable.items():
            partition = partition_by_id[partition_id]
            files, modes = reuse_partition_files(
                previous=previous,
                previous_root=Path(previous_root),
                staging_root=staging_root,
                partition=partition,
            )
            partition["files"] = files
            partition["materialization"] = "reused"
            hardlinks += modes["hardlink"]
            copies += modes["copy"]

        export_started = time.monotonic()
        if len(reusable) < len(partitions):
            connection = _connect_readonly(db_path)
            try:
                connection.execute("BEGIN")
                for spec in ACTOR_GRAPH_TABLE_SPECS:
                    active_id: str | None = None
                    active_writer: PartitionWriter | None = None
                    active_rows = 0
                    active_digest = hashlib.sha256()
                    telemetry = {
                        "cursor_batches": 0,
                        "ordered_query_executions": 0,
                    }
                    for row, release_id, bucket in _iter_table_rows(
                        connection,
                        spec,
                        contracts[spec.name],
                        fetch_rows=cursor_fetch_rows,
                        telemetry=telemetry,
                    ):
                        partition_id = _partition_id(spec.name, release_id, bucket)
                        if partition_id != active_id:
                            if active_id is not None:
                                active_partition = partition_by_id[str(active_id)]
                                if active_rows != int(active_partition["rows"]):
                                    raise RuntimeError(
                                        f"partition {active_id} source row count changed "
                                        "between fingerprint and materialization"
                                    )
                                if (
                                    active_digest.hexdigest()
                                    != active_partition["input_sha256"]
                                ):
                                    raise RuntimeError(
                                        f"partition {active_id} source content changed "
                                        "between fingerprint and materialization"
                                    )
                                if active_writer is not None:
                                    active_partition["files"] = active_writer.close()
                                    active_partition["materialization"] = "rebuilt"
                            active_id = partition_id
                            active_rows = 0
                            active_digest = hashlib.sha256()
                            if partition_id in reusable:
                                active_writer = None
                            else:
                                active_writer = PartitionWriter(
                                    root=staging_root,
                                    partition=partition_by_id[partition_id],
                                    contract=contracts[spec.name],
                                    compression=compression,
                                    row_group_rows=row_group_rows,
                                    max_file_rows=max_file_rows,
                                )
                        active_rows += 1
                        active_digest.update(
                            contracts[spec.name].canonical_row_bytes(row)
                        )
                        if active_writer is not None:
                            active_writer.append(row)
                    if active_id is not None:
                        active_partition = partition_by_id[str(active_id)]
                        if active_rows != int(active_partition["rows"]):
                            raise RuntimeError(
                                f"partition {active_id} source row count changed "
                                "between fingerprint and materialization"
                            )
                        if (
                            active_digest.hexdigest()
                            != active_partition["input_sha256"]
                        ):
                            raise RuntimeError(
                                f"partition {active_id} source content changed "
                                "between fingerprint and materialization"
                            )
                        if active_writer is not None:
                            active_partition["files"] = active_writer.close()
                            active_partition["materialization"] = "rebuilt"
                    materialize_batches += telemetry["cursor_batches"]
                    materialize_query_executions += telemetry[
                        "ordered_query_executions"
                    ]
            finally:
                if connection.in_transaction:
                    connection.rollback()
                connection.close()
        export_seconds = time.monotonic() - export_started

        rows = int(scan_totals["rows"])
        files = sum(len(list(item.get("files") or [])) for item in partitions)
        parquet_bytes = sum(
            int(file_meta["bytes"])
            for partition in partitions
            for file_meta in list(partition.get("files") or [])
        )
        release_rows = int(scan_totals["release_rows"])
        peak_rss = peak_rss_mb()
        checks = {
            "minimum_rows": rows >= int(min_rows),
            "all_required_tables_present": len(contracts)
            == len(ACTOR_GRAPH_TABLE_SPECS),
            "release_rows_present": release_rows > 0,
            "source_mappings_present": int(scan_totals["source_mapping_rows"]) > 0,
            "real_data_only_releases": int(scan_totals["real_data_release_rows"])
            == release_rows,
            "public_identity_retained_releases": int(
                scan_totals["public_identity_release_rows"]
            )
            == release_rows,
            "public_labels_retained": int(scan_totals["public_label_rows"])
            == int(scan_totals["table_rows"]["actor_graph_node_versions"]),
            "public_identifiers_retained": int(scan_totals["public_identifier_rows"])
            == int(scan_totals["table_rows"]["actor_graph_identifier_versions"]),
            "public_aliases_retained": int(scan_totals["public_alias_rows"])
            == int(scan_totals["table_rows"]["actor_graph_alias_versions"]),
            "no_private_tokens": int(scan_totals["private_token_findings"]) == 0,
            "no_non_real_markers": int(scan_totals["non_real_marker_findings"]) == 0,
            "source_urls_public_and_credential_free": int(
                scan_totals["non_public_source_url_findings"]
            )
            == 0,
            "zstd_compression": compression.casefold() == "zstd",
            "bounded_row_groups": row_group_rows <= ACTOR_GRAPH_MAX_ROW_GROUP_ROWS,
            "bounded_file_rows": all(
                int(file_meta["rows"]) <= ACTOR_GRAPH_MAX_FILE_ROWS
                for partition in partitions
                for file_meta in list(partition.get("files") or [])
            ),
            "bounded_peak_rss": peak_rss <= float(max_peak_rss_mb),
        }
        analytical_gate_passed = all(checks.values())
        promotion_checks = {
            "analytical_partition_gate": analytical_gate_passed,
            "million_graph_records": rows >= 1_000_000,
            "million_actor_nodes": int(scan_totals["table_rows"]["actor_graph_nodes"])
            >= 1_000_000,
            "durable_public_origin_verified": False,
            "restore_drill_verified": False,
        }
        table_manifests = {
            spec.name: _table_manifest(
                spec,
                contracts[spec.name],
                sqlite_schemas[spec.name],
                scan_totals,
            )
            for spec in ACTOR_GRAPH_TABLE_SPECS
        }
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "snapshot_date": snapshot_date,
            "lane": ACTOR_GRAPH_LANE,
            "transformer_version": ACTOR_GRAPH_TRANSFORMER_VERSION,
            "schema_sha256": schema_sha256,
            "tables": table_manifests,
            "partition_contract": {
                "strategy": "table_release_bounded_source_or_type_hash",
                "keys": ["snapshot_date", "table", "release_id", "bucket"],
                "bucket_count": ACTOR_GRAPH_BUCKETS,
                "ordering": ["table", "release_id", "bucket", "primary_key"],
                "scan": "single_ordered_cursor_fetchmany_no_offset",
                "cursor_fetch_rows": int(cursor_fetch_rows),
                "row_group_rows": int(row_group_rows),
                "max_file_rows": int(max_file_rows),
                "compression": "zstd",
            },
            "incremental_contract": {
                "input_fingerprint": "sha256_canonical_lossless_table_rows",
                "reuse_key": [
                    "partition_id",
                    "input_sha256",
                    "schema_sha256",
                    "transformer_version",
                ],
                "previous_manifest_sha256": previous_sha256,
                "partitions_reused": len(reusable),
                "partitions_rebuilt": len(partitions) - len(reusable),
                "files_hardlinked": hardlinks,
                "files_copied": copies,
            },
            "source": {
                "database_file": db_path.name,
                "database_bytes": int(db_path.stat().st_size),
                "database_sha256": sha256_file(db_path),
                "semantic_content_sha256": scan_totals["content_sha256"],
                "raw_upstream_payloads_published": False,
            },
            "totals": {
                **scan_totals,
                "tables": len(ACTOR_GRAPH_TABLE_SPECS),
                "nonempty_tables": sum(
                    int(int(value) > 0) for value in scan_totals["table_rows"].values()
                ),
                "partitions": len(partitions),
                "files": files,
                "parquet_bytes": parquet_bytes,
            },
            "checks": checks,
            "analytical_partition_gate_passed": analytical_gate_passed,
            "promotion_checks": promotion_checks,
            "promotion_gate_passed": all(promotion_checks.values()),
            "publication_status": "local_generated_not_published",
            "capacity_class": (
                "s3_1m_graph_records" if rows >= 1_000_000 else "below_s3_1m"
            ),
            "publication_policy": {
                "real_records_only": True,
                "official_public_domain_personal_information_retained": True,
                "canonical_labels_identifiers_aliases_not_redacted": True,
                "workstation_paths_credentials_and_sessions_forbidden": True,
            },
            "performance": {
                "fingerprint_seconds": round(scan_seconds, 6),
                "materialize_seconds": round(export_seconds, 6),
                "total_seconds": round(time.monotonic() - started, 6),
                "rows_per_second": round(
                    rows / max(time.monotonic() - started, 0.000001), 3
                ),
                "peak_rss_mb": peak_rss,
                "max_peak_rss_mb": float(max_peak_rss_mb),
                "scan_cursor_batches": int(scan_totals["cursor_batches"]),
                "scan_ordered_query_executions": int(
                    scan_totals["ordered_query_executions"]
                ),
                "materialize_cursor_batches": int(materialize_batches),
                "materialize_ordered_query_executions": int(
                    materialize_query_executions
                ),
            },
            "partitions": partitions,
            "limitations": [
                "The lane restores the actor-graph tables, not upstream source records or document bytes.",
                "External source-registry rows referenced by source_id are not duplicated; source mappings preserve graph/upstream IDs and metadata hashes.",
                "The current corpus exceeds one million normalized graph records but does not yet contain one million actor nodes.",
                "Local Parquet materialization does not prove durable public-origin publication or disaster restore.",
            ],
        }
        if enforce and not analytical_gate_passed:
            failed = [key for key, value in checks.items() if not value]
            raise RuntimeError(
                "actor-graph partition gate failed: " + ", ".join(failed)
            )
        (staging_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staging_root.rename(output_root)
    except BaseException:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise
    return manifest


__all__ = [
    "ACTOR_GRAPH_BUCKETS",
    "ACTOR_GRAPH_LANE",
    "ACTOR_GRAPH_MAX_FILE_ROWS",
    "ACTOR_GRAPH_MAX_ROW_GROUP_ROWS",
    "ACTOR_GRAPH_TABLE_SPECS",
    "ACTOR_GRAPH_TRANSFORMER_VERSION",
    "ActorGraphTableSpec",
    "actor_graph_schema_sha256",
    "actor_partition_bucket",
    "export_actor_graph_partitions",
    "load_actor_graph_contracts",
    "non_public_source_url_findings",
    "non_real_marker_findings",
    "scan_actor_graph_partitions",
]
