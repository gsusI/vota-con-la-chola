"""Typed, revision-preserving Parquet publication for indicator observations."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from itertools import groupby
from pathlib import Path
from typing import Any

from .semantic_contracts import (
    MANIFEST_SCHEMA_VERSION,
    SemanticLaneContract,
    peak_rss_mb,
    private_token_findings,
    public_http_url,
    safe_component,
    sha256_file,
)
from .semantic_parquet_io import (
    PartitionWriter,
    reusable_partition,
    reuse_partition_files,
)

INDICATOR_OBSERVATION_CONTRACT = SemanticLaneContract(
    lane="indicator_observations",
    transformer_version="indicator_observations_public_v1",
    id_column="observation_id",
    year_column="point_year",
    schema=(
        {"name": "observation_id", "type": "string", "nullable": False},
        {"name": "observation_group_id", "type": "string", "nullable": False},
        {"name": "revision_ordinal", "type": "int64", "nullable": False},
        {"name": "revision_count", "type": "int64", "nullable": False},
        {"name": "revision_state", "type": "string", "nullable": False},
        {"name": "indicator_series_id", "type": "int64", "nullable": False},
        {"name": "series_canonical_key", "type": "string", "nullable": False},
        {"name": "series_code", "type": "string", "nullable": False},
        {"name": "series_label", "type": "string", "nullable": False},
        {"name": "domain_id", "type": "int64", "nullable": True},
        {"name": "domain_key", "type": "string", "nullable": True},
        {"name": "admin_level_id", "type": "int64", "nullable": True},
        {"name": "admin_level_code", "type": "string", "nullable": True},
        {"name": "territory_id", "type": "int64", "nullable": True},
        {"name": "territory_code", "type": "string", "nullable": True},
        {"name": "territory_name", "type": "string", "nullable": True},
        {"name": "geographic_scope", "type": "string", "nullable": False},
        {"name": "source_id", "type": "string", "nullable": False},
        {"name": "source_record_pk", "type": "int64", "nullable": True},
        {"name": "source_record_id", "type": "string", "nullable": True},
        {"name": "source_snapshot_date", "type": "string", "nullable": True},
        {"name": "source_url", "type": "string", "nullable": False},
        {"name": "source_url_scope", "type": "string", "nullable": False},
        {"name": "lineage_state", "type": "string", "nullable": False},
        {"name": "point_date", "type": "string", "nullable": False},
        {"name": "point_year", "type": "string", "nullable": False},
        {"name": "value", "type": "float64", "nullable": True},
        {"name": "value_text", "type": "string", "nullable": True},
        {"name": "observation_state", "type": "string", "nullable": False},
        {"name": "unit", "type": "string", "nullable": True},
        {"name": "unit_state", "type": "string", "nullable": False},
        {"name": "frequency", "type": "string", "nullable": True},
        {"name": "frequency_state", "type": "string", "nullable": False},
        {"name": "methodology_version", "type": "string", "nullable": True},
        {"name": "methodology_state", "type": "string", "nullable": False},
        {"name": "dimensions_json", "type": "string", "nullable": False},
        {"name": "dimensions_sha256", "type": "string", "nullable": False},
    ),
)

INDICATOR_OBSERVATION_SQL = """
SELECT
  o.observation_record_id,
  o.indicator_series_id,
  o.source_id,
  o.source_record_pk,
  o.source_record_id,
  o.source_snapshot_date,
  o.source_url AS observation_source_url,
  o.series_code,
  o.point_date,
  o.value,
  o.value_text,
  o.unit,
  o.frequency,
  COALESCE(o.dimensions_json, series.dimensions_json) AS dimensions_json,
  o.methodology_version,
  series.canonical_key AS series_canonical_key,
  series.label AS series_label,
  series.domain_id,
  domain.canonical_key AS domain_key,
  series.admin_level_id,
  admin.code AS admin_level_code,
  series.territory_id,
  territory.code AS territory_code,
  territory.name AS territory_name,
  series.source_url AS series_source_url,
  series.source_record_pk AS series_source_record_pk,
  source.default_url AS source_default_url
FROM indicator_observation_records AS o
JOIN indicator_series AS series
  ON series.indicator_series_id = o.indicator_series_id
 AND series.source_id = o.source_id
JOIN sources AS source ON source.source_id = o.source_id
LEFT JOIN domains AS domain ON domain.domain_id = series.domain_id
LEFT JOIN admin_levels AS admin ON admin.admin_level_id = series.admin_level_id
LEFT JOIN territories AS territory ON territory.territory_id = series.territory_id
ORDER BY
  o.source_id,
  substr(o.point_date, 1, 4),
  o.point_date,
  o.series_code,
  COALESCE(o.source_snapshot_date, ''),
  COALESCE(o.source_record_id, ''),
  o.observation_record_id
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _integer(value: Any) -> int | None:
    return None if value is None else int(value)


def _point_year(point_date: Any) -> str:
    value = str(point_date or "")
    if len(value) < 10 or value[4] != "-" or value[7] != "-":
        raise ValueError(f"indicator observation has invalid ISO date: {value!r}")
    year = value[:4]
    if not (year.isdigit() and year[0] in {"1", "2"}):
        raise ValueError(f"indicator observation has invalid year: {value!r}")
    return year


def _canonical_dimensions(value: Any) -> tuple[str, str]:
    raw = str(value or "{}").strip() or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("indicator observation has invalid dimensions_json") from exc
    if not isinstance(parsed, dict):
        raise TypeError("indicator observation dimensions_json must be an object")
    canonical = json.dumps(
        parsed,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return canonical, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _dimension_territory(value: str) -> str | None:
    payload = json.loads(value)
    queue: list[Any] = [payload]
    keys = {"geo", "geo_code", "territory", "territory_code"}
    while queue:
        item = queue.pop(0)
        if isinstance(item, dict):
            for key, nested in item.items():
                if str(key).lower() in keys and not isinstance(nested, (dict, list)):
                    territory = _text(nested)
                    if territory:
                        return territory
                queue.append(nested)
        elif isinstance(item, list):
            queue.extend(item)
    return None


def _geographic_scope(
    *, admin_level_code: str | None, territory_code: str | None
) -> str:
    admin = str(admin_level_code or "").lower()
    territory = str(territory_code or "").upper()
    if admin in {"europeo", "european", "eu"}:
        return "eu"
    if territory in {"ES", "ESP", "NACIONAL"} or admin in {"nacional", "national"}:
        return "es-national"
    if territory:
        return "es-territorial"
    return "unspecified"


def _base_public_row(row: sqlite3.Row) -> dict[str, Any]:
    point_date = str(row["point_date"])
    dimensions_json, dimensions_sha256 = _canonical_dimensions(row["dimensions_json"])
    territory_code = _text(row["territory_code"]) or _dimension_territory(
        dimensions_json
    )
    observation_url = public_http_url(row["observation_source_url"])
    series_url = public_http_url(row["series_source_url"])
    default_url = public_http_url(row["source_default_url"])
    source_url = observation_url or series_url or default_url
    if source_url is None:
        raise ValueError(
            "indicator observation has no public source URL: "
            f"{row['observation_record_id']}"
        )
    source_url_scope = (
        "observation"
        if observation_url
        else "series"
        if series_url
        else "source_default"
    )
    value = None if row["value"] is None else float(row["value"])
    value_text = _text(row["value_text"])
    if value is not None:
        value_text = None
        observation_state = "numeric"
    elif value_text is not None:
        observation_state = "text_only"
    else:
        observation_state = "missing"
    source_record_pk = _integer(row["source_record_pk"])
    source_record_id = _text(row["source_record_id"])
    series_source_record_pk = _integer(row["series_source_record_pk"])
    lineage_state = (
        "observation_source_record"
        if source_record_pk is not None and source_record_id
        else "observation_source_record_id"
        if source_record_id
        else "series_source_record"
        if series_source_record_pk is not None
        else "source_url"
    )
    unit = _text(row["unit"])
    frequency = _text(row["frequency"])
    methodology_version = _text(row["methodology_version"])
    return {
        "observation_id": (
            f"indicator_observation:{int(row['observation_record_id']):020d}"
        ),
        "observation_group_id": "",
        "revision_ordinal": 0,
        "revision_count": 0,
        "revision_state": "",
        "indicator_series_id": int(row["indicator_series_id"]),
        "series_canonical_key": str(row["series_canonical_key"]),
        "series_code": str(row["series_code"]),
        "series_label": str(row["series_label"]),
        "domain_id": _integer(row["domain_id"]),
        "domain_key": _text(row["domain_key"]),
        "admin_level_id": _integer(row["admin_level_id"]),
        "admin_level_code": _text(row["admin_level_code"]),
        "territory_id": _integer(row["territory_id"]),
        "territory_code": territory_code,
        "territory_name": _text(row["territory_name"]),
        "geographic_scope": _geographic_scope(
            admin_level_code=_text(row["admin_level_code"]),
            territory_code=territory_code,
        ),
        "source_id": str(row["source_id"]),
        "source_record_pk": source_record_pk,
        "source_record_id": source_record_id,
        "source_snapshot_date": _text(row["source_snapshot_date"]),
        "source_url": source_url,
        "source_url_scope": source_url_scope,
        "lineage_state": lineage_state,
        "point_date": point_date,
        "point_year": _point_year(point_date),
        "value": value,
        "value_text": value_text,
        "observation_state": observation_state,
        "unit": unit,
        "unit_state": "present" if unit else "missing",
        "frequency": frequency,
        "frequency_state": "present" if frequency else "missing",
        "methodology_version": methodology_version,
        "methodology_state": "present" if methodology_version else "missing",
        "dimensions_json": dimensions_json,
        "dimensions_sha256": dimensions_sha256,
    }


def _raw_group_key(row: sqlite3.Row) -> tuple[str, str, str]:
    return (str(row["source_id"]), str(row["series_code"]), str(row["point_date"]))


def _iter_rows(db_path: Path) -> Iterator[dict[str, Any]]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        raw_rows = conn.execute(INDICATOR_OBSERVATION_SQL)
        for key, grouped in groupby(raw_rows, key=_raw_group_key):
            rows = [_base_public_row(row) for row in grouped]
            revision_count = len(rows)
            group_digest = hashlib.sha256(
                json.dumps(key, ensure_ascii=True, separators=(",", ":")).encode(
                    "utf-8"
                )
            ).hexdigest()
            for ordinal, public_row in enumerate(rows, start=1):
                public_row["observation_group_id"] = group_digest
                public_row["revision_ordinal"] = ordinal
                public_row["revision_count"] = revision_count
                public_row["revision_state"] = (
                    "sole"
                    if revision_count == 1
                    else "latest"
                    if ordinal == revision_count
                    else "superseded"
                )
                yield public_row
    finally:
        conn.close()


def _partition_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row["source_id"]),
        str(row["geographic_scope"]),
        str(row["point_year"]),
    )


def _partition_id(key: tuple[str, str, str]) -> str:
    return "|".join(key)


def _partition_dir(snapshot_date: str, key: tuple[str, str, str]) -> Path:
    return Path(
        f"lane={INDICATOR_OBSERVATION_CONTRACT.lane}",
        f"snapshot_date={safe_component(snapshot_date)}",
        f"source_id={safe_component(key[0])}",
        f"geographic_scope={safe_component(key[1])}",
        f"year={safe_component(key[2])}",
    )


def _new_partition(snapshot_date: str, key: tuple[str, str, str]) -> dict[str, Any]:
    return {
        "partition_id": _partition_id(key),
        "values": {
            "snapshot_date": snapshot_date,
            "source_id": key[0],
            "geographic_scope": key[1],
            "year": key[2],
        },
        "relative_dir": _partition_dir(snapshot_date, key).as_posix(),
        "rows": 0,
        "min_id": None,
        "max_id": None,
        "source_url_rows": 0,
        "lineage_rows": 0,
        "numeric_rows": 0,
        "text_rows": 0,
        "missing_rows": 0,
        "unit_rows": 0,
        "frequency_rows": 0,
        "methodology_rows": 0,
        "sole_rows": 0,
        "latest_revision_rows": 0,
        "superseded_revision_rows": 0,
        "private_token_findings": 0,
        "_digest": hashlib.sha256(),
    }


def scan_indicator_partitions(
    db_path: Path, *, snapshot_date: str
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    metric_fields = {
        "numeric_rows": ("observation_state", "numeric"),
        "text_rows": ("observation_state", "text_only"),
        "missing_rows": ("observation_state", "missing"),
        "sole_rows": ("revision_state", "sole"),
        "latest_revision_rows": ("revision_state", "latest"),
        "superseded_revision_rows": ("revision_state", "superseded"),
    }
    totals = {
        "rows": 0,
        "revision_groups": 0,
        "revised_groups": 0,
        "source_url_rows": 0,
        "lineage_rows": 0,
        "numeric_rows": 0,
        "text_rows": 0,
        "missing_rows": 0,
        "unit_rows": 0,
        "frequency_rows": 0,
        "methodology_rows": 0,
        "sole_rows": 0,
        "latest_revision_rows": 0,
        "superseded_revision_rows": 0,
        "private_token_findings": 0,
    }
    partitions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_key: tuple[str, str, str] | None = None
    previous_group: str | None = None
    for row in _iter_rows(db_path):
        key = _partition_key(row)
        if current_key != key:
            if current is not None:
                current["input_sha256"] = current.pop("_digest").hexdigest()
                partitions.append(current)
            current_key = key
            current = _new_partition(snapshot_date, key)
        assert current is not None
        row_id = str(row["observation_id"])
        current["rows"] += 1
        current["min_id"] = (
            row_id if current["min_id"] is None else min(str(current["min_id"]), row_id)
        )
        current["max_id"] = (
            row_id if current["max_id"] is None else max(str(current["max_id"]), row_id)
        )
        if row["source_url"]:
            current["source_url_rows"] += 1
            totals["source_url_rows"] += 1
        if row["lineage_state"] != "missing":
            current["lineage_rows"] += 1
            totals["lineage_rows"] += 1
        for metric, (field, expected) in metric_fields.items():
            if row[field] == expected:
                current[metric] += 1
                totals[metric] += 1
        for metric, field in (
            ("unit_rows", "unit"),
            ("frequency_rows", "frequency"),
            ("methodology_rows", "methodology_version"),
        ):
            if row[field] not in (None, ""):
                current[metric] += 1
                totals[metric] += 1
        group_id = str(row["observation_group_id"])
        if group_id != previous_group:
            totals["revision_groups"] += 1
            if int(row["revision_count"]) > 1:
                totals["revised_groups"] += 1
            previous_group = group_id
        findings = private_token_findings(row)
        current["private_token_findings"] += findings
        totals["private_token_findings"] += findings
        current["_digest"].update(
            INDICATOR_OBSERVATION_CONTRACT.canonical_row_bytes(row)
        )
        totals["rows"] += 1
    if current is not None:
        current["input_sha256"] = current.pop("_digest").hexdigest()
        partitions.append(current)
    return partitions, totals


def _database_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        observation_rows = int(
            conn.execute(
                "SELECT COUNT(*) FROM indicator_observation_records"
            ).fetchone()[0]
        )
        joined_rows = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM indicator_observation_records AS o
                JOIN indicator_series AS s
                  ON s.indicator_series_id = o.indicator_series_id
                 AND s.source_id = o.source_id
                JOIN sources AS source ON source.source_id = o.source_id
                """
            ).fetchone()[0]
        )
        distinct_ids = int(
            conn.execute(
                "SELECT COUNT(DISTINCT observation_record_id) "
                "FROM indicator_observation_records"
            ).fetchone()[0]
        )
        series_rows = int(
            conn.execute("SELECT COUNT(*) FROM indicator_series").fetchone()[0]
        )
        return {
            "observation_table_rows": observation_rows,
            "joined_rows": joined_rows,
            "distinct_observation_ids": distinct_ids,
            "series_table_rows": series_rows,
        }
    finally:
        conn.close()


def _previous_partitions(
    manifest_path: Path | None,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    if manifest_path is None:
        return {}, None
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    valid = (
        payload.get("schema_version") == MANIFEST_SCHEMA_VERSION
        and payload.get("lane") == INDICATOR_OBSERVATION_CONTRACT.lane
        and payload.get("transformer_version")
        == INDICATOR_OBSERVATION_CONTRACT.transformer_version
        and payload.get("schema_sha256") == INDICATOR_OBSERVATION_CONTRACT.schema_sha256
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


def export_indicator_partitions(
    *,
    db_path: Path,
    output_root: Path,
    snapshot_date: str,
    compression: str = "zstd",
    row_group_rows: int = 25_000,
    max_file_rows: int = 100_000,
    previous_manifest_path: Path | None = None,
    previous_root: Path | None = None,
    min_rows: int = 1,
    max_peak_rss_mb: float = 1024.0,
    enforce: bool = False,
) -> dict[str, Any]:
    db_path = Path(db_path)
    output_root = Path(output_root)
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    if output_root.exists():
        raise FileExistsError(output_root)
    if row_group_rows <= 0 or max_file_rows <= 0:
        raise ValueError("row-group-rows and max-file-rows must be positive")
    if row_group_rows > max_file_rows:
        raise ValueError("row-group-rows cannot exceed max-file-rows")
    if (previous_manifest_path is None) != (previous_root is None):
        raise ValueError(
            "previous-manifest and previous-root must be provided together"
        )

    started = time.monotonic()
    scan_started = time.monotonic()
    partitions, scan_totals = scan_indicator_partitions(
        db_path, snapshot_date=snapshot_date
    )
    scan_seconds = time.monotonic() - scan_started
    database_counts = _database_counts(db_path)
    previous_by_id, previous_sha256 = _previous_partitions(previous_manifest_path)
    reusable: dict[str, dict[str, Any]] = {}
    for partition in partitions:
        eligible = reusable_partition(
            partition=partition,
            previous=previous_by_id.get(str(partition["partition_id"])),
            previous_root=previous_root,
        )
        if eligible is not None:
            reusable[str(partition["partition_id"])] = eligible

    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.staging-", dir=output_root.parent)
    )
    partition_by_id = {str(item["partition_id"]): item for item in partitions}
    hardlinks = 0
    copies = 0
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
        active_id: str | None = None
        active_writer: PartitionWriter | None = None
        if len(reusable) < len(partitions):
            for row in _iter_rows(db_path):
                partition_id = _partition_id(_partition_key(row))
                if partition_id != active_id:
                    if active_writer is not None:
                        partition_by_id[str(active_id)]["files"] = active_writer.close()
                        partition_by_id[str(active_id)]["materialization"] = "rebuilt"
                    active_id = partition_id
                    active_writer = (
                        None
                        if partition_id in reusable
                        else PartitionWriter(
                            root=staging_root,
                            partition=partition_by_id[partition_id],
                            contract=INDICATOR_OBSERVATION_CONTRACT,
                            compression=compression,
                            row_group_rows=row_group_rows,
                            max_file_rows=max_file_rows,
                        )
                    )
                if active_writer is not None:
                    active_writer.append(row)
            if active_writer is not None:
                partition_by_id[str(active_id)]["files"] = active_writer.close()
                partition_by_id[str(active_id)]["materialization"] = "rebuilt"
        export_seconds = time.monotonic() - export_started

        rows = int(scan_totals["rows"])
        files = sum(len(list(item.get("files") or [])) for item in partitions)
        parquet_bytes = sum(
            int(file_meta["bytes"])
            for partition in partitions
            for file_meta in list(partition.get("files") or [])
        )
        peak_rss = peak_rss_mb()
        checks = {
            "minimum_rows": rows >= int(min_rows),
            "database_join_balance": database_counts["observation_table_rows"]
            == database_counts["joined_rows"]
            == rows,
            "distinct_observation_ids": database_counts["distinct_observation_ids"]
            == rows,
            "source_url_complete": scan_totals["source_url_rows"] == rows,
            "lineage_complete": scan_totals["lineage_rows"] == rows,
            "observation_state_complete": scan_totals["numeric_rows"]
            + scan_totals["text_rows"]
            + scan_totals["missing_rows"]
            == rows,
            "revision_state_complete": scan_totals["sole_rows"]
            + scan_totals["latest_revision_rows"]
            + scan_totals["superseded_revision_rows"]
            == rows,
            "revision_pairs_balanced": scan_totals["latest_revision_rows"]
            == scan_totals["revised_groups"],
            "metadata_states_complete": all(
                0 <= scan_totals[key] <= rows
                for key in ("unit_rows", "frequency_rows", "methodology_rows")
            ),
            "no_private_tokens": scan_totals["private_token_findings"] == 0,
            "bounded_peak_rss": peak_rss <= float(max_peak_rss_mb),
            "bounded_file_rows": all(
                int(file_meta["rows"]) <= int(max_file_rows)
                for partition in partitions
                for file_meta in list(partition.get("files") or [])
            ),
        }
        analytical_gate_passed = all(checks.values())
        promotion_checks = {
            "analytical_partition_gate": analytical_gate_passed,
            "representative_real_observations": False,
            "official_source_totals_reconciled": False,
            "durable_public_origin_verified": False,
            "published_artifact_restore_verified": False,
        }
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "snapshot_date": snapshot_date,
            "lane": INDICATOR_OBSERVATION_CONTRACT.lane,
            "transformer_version": INDICATOR_OBSERVATION_CONTRACT.transformer_version,
            "schema": INDICATOR_OBSERVATION_CONTRACT.schema,
            "schema_sha256": INDICATOR_OBSERVATION_CONTRACT.schema_sha256,
            "partition_contract": {
                "strategy": "semantic_hive",
                "keys": ["snapshot_date", "source_id", "geographic_scope", "year"],
                "ordering": [
                    "source_id",
                    "point_year",
                    "point_date",
                    "series_code",
                    "source_snapshot_date",
                    "source_record_id",
                    "observation_id",
                ],
                "row_group_rows": int(row_group_rows),
                "max_file_rows": int(max_file_rows),
                "compression": compression,
            },
            "incremental_contract": {
                "input_fingerprint": "sha256_canonical_public_rows",
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
                "table": "indicator_observation_records",
                "series_table": "indicator_series",
                "raw_payload_published": False,
                "dimensions_published_as_canonical_json": True,
            },
            "totals": {
                **database_counts,
                **scan_totals,
                "partitions": len(partitions),
                "files": files,
                "parquet_bytes": parquet_bytes,
            },
            "coverage": {
                "source_url": round(scan_totals["source_url_rows"] / rows, 8)
                if rows
                else 0.0,
                "lineage": round(scan_totals["lineage_rows"] / rows, 8)
                if rows
                else 0.0,
                "unit": round(scan_totals["unit_rows"] / rows, 8) if rows else 0.0,
                "frequency": round(scan_totals["frequency_rows"] / rows, 8)
                if rows
                else 0.0,
                "methodology": round(scan_totals["methodology_rows"] / rows, 8)
                if rows
                else 0.0,
            },
            "checks": checks,
            "analytical_partition_gate_passed": analytical_gate_passed,
            "promotion_checks": promotion_checks,
            "promotion_gate_passed": all(promotion_checks.values()),
            "publication_status": "local_generated_not_published",
            "performance": {
                "fingerprint_seconds": round(scan_seconds, 6),
                "materialize_seconds": round(export_seconds, 6),
                "total_seconds": round(time.monotonic() - started, 6),
                "rows_per_second": round(
                    rows / max(time.monotonic() - started, 0.000001), 3
                ),
                "peak_rss_mb": peak_rss,
                "max_peak_rss_mb": float(max_peak_rss_mb),
            },
            "partitions": partitions,
            "limitations": [
                "Capacity validation does not establish representative real-world indicator coverage.",
                "Revision order is deterministic by snapshot, source-record identity, and observation id; it does not infer upstream publication chronology beyond those fields.",
                "Missing units, frequencies, methodologies, domains, and territories remain explicit rather than imputed.",
                "Local materialization does not prove durable publication or restore.",
            ],
        }
        if enforce and not analytical_gate_passed:
            failed = [key for key, value in checks.items() if not value]
            raise RuntimeError("analytical partition gate failed: " + ", ".join(failed))
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
    "INDICATOR_OBSERVATION_CONTRACT",
    "INDICATOR_OBSERVATION_SQL",
    "export_indicator_partitions",
    "scan_indicator_partitions",
]
