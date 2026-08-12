"""Independent full-row validation for indicator-observation Parquet."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .indicator_partitions import INDICATOR_OBSERVATION_CONTRACT
from .semantic_contracts import (
    MANIFEST_SCHEMA_VERSION,
    peak_rss_mb,
    private_token_findings,
    safe_child,
    safe_component,
    sha256_file,
)

VALIDATION_SCHEMA_VERSION = "indicator_observation_partition_validation_v1"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _is_public_url(value: Any) -> bool:
    try:
        parsed = urlsplit(str(value or ""))
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _expected_relative_dir(manifest: dict[str, Any], values: dict[str, Any]) -> str:
    return Path(
        f"lane={INDICATOR_OBSERVATION_CONTRACT.lane}",
        f"snapshot_date={safe_component(str(manifest.get('snapshot_date') or ''))}",
        f"source_id={safe_component(str(values.get('source_id') or ''))}",
        f"geographic_scope={safe_component(str(values.get('geographic_scope') or ''))}",
        f"year={safe_component(str(values.get('year') or ''))}",
    ).as_posix()


def _expected_observation_state(row: dict[str, Any]) -> str:
    if row["value"] is not None:
        return "numeric"
    if row["value_text"] not in (None, ""):
        return "text_only"
    return "missing"


def _expected_metadata_state(value: Any) -> str:
    return "present" if value not in (None, "") else "missing"


def _expected_group_id(row: dict[str, Any]) -> str:
    key = (str(row["source_id"]), str(row["series_code"]), str(row["point_date"]))
    return hashlib.sha256(
        json.dumps(key, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _expected_revision_state(ordinal: int, count: int) -> str:
    if count == 1:
        return "sole"
    if ordinal == count:
        return "latest"
    return "superseded"


def validate_indicator_partitions(
    *,
    root: Path,
    manifest_path: Path | None = None,
    batch_rows: int = 10_000,
    min_rows: int = 1,
    max_peak_rss_mb: float = 1024.0,
) -> dict[str, Any]:
    try:
        import pyarrow.parquet as pq  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pyarrow is required; install the project parquet extra"
        ) from exc
    if batch_rows <= 0:
        raise ValueError("batch-rows must be positive")
    root = Path(root)
    manifest_path = Path(manifest_path) if manifest_path else root / "manifest.json"
    if not root.is_dir():
        raise FileNotFoundError(root)
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_schema = INDICATOR_OBSERVATION_CONTRACT.arrow_schema()

    expected_paths: set[str] = set()
    seen_ids: set[str] = set()
    duplicate_paths = 0
    duplicate_ids = 0
    files_present = True
    checksums_valid = True
    schemas_valid = True
    file_rows_valid = True
    file_minmax_valid = True
    partition_rows_valid = True
    partition_hashes_valid = True
    partition_values_valid = True
    rows_ordered = True
    urls_public = True
    row_semantics_valid = True
    revision_groups_valid = True
    dimensions_valid = True
    rows_total = 0
    files_total = 0
    bytes_total = 0
    source_url_rows = 0
    source_record_rows = 0
    lineage_rows = 0
    numeric_rows = 0
    text_rows = 0
    missing_rows = 0
    unit_rows = 0
    frequency_rows = 0
    methodology_rows = 0
    sole_rows = 0
    latest_revision_rows = 0
    superseded_revision_rows = 0
    revision_groups = 0
    revised_groups = 0
    private_findings = 0
    current_group: str | None = None
    current_group_count = 0
    current_group_last_ordinal = 0
    partition_reports: list[dict[str, Any]] = []

    for partition in list(manifest.get("partitions") or []):
        digest = hashlib.sha256()
        partition_rows = 0
        partition_min_id: str | None = None
        partition_max_id: str | None = None
        previous_order: tuple[str, str, str, str, str] | None = None
        values = dict(partition.get("values") or {})
        expected_relative_dir = _expected_relative_dir(manifest, values)
        expected_partition_id = "|".join(
            str(values.get(key) or "")
            for key in ("source_id", "geographic_scope", "year")
        )
        if str(partition.get("relative_dir") or "") != expected_relative_dir:
            partition_values_valid = False
        if str(partition.get("partition_id") or "") != expected_partition_id:
            partition_values_valid = False
        if str(values.get("snapshot_date") or "") != str(
            manifest.get("snapshot_date") or ""
        ):
            partition_values_valid = False
        partition_file_reports: list[dict[str, Any]] = []

        for file_meta in list(partition.get("files") or []):
            relative = str(file_meta.get("path") or "")
            if relative in expected_paths:
                duplicate_paths += 1
            expected_paths.add(relative)
            if Path(relative).parent.as_posix() != expected_relative_dir:
                partition_values_valid = False
            file_path = safe_child(root, relative)
            files_total += 1
            if file_path is None or not file_path.is_file():
                files_present = False
                continue
            actual_bytes = int(file_path.stat().st_size)
            actual_sha256 = sha256_file(file_path)
            bytes_total += actual_bytes
            if actual_bytes != int(file_meta.get("bytes") or -1):
                checksums_valid = False
            if actual_sha256 != str(file_meta.get("sha256") or ""):
                checksums_valid = False
            parquet_file = pq.ParquetFile(file_path)
            if not parquet_file.schema_arrow.equals(
                expected_schema, check_metadata=True
            ):
                schemas_valid = False
            expected_file_rows = int(file_meta.get("rows") or 0)
            if int(parquet_file.metadata.num_rows) != expected_file_rows:
                file_rows_valid = False
            file_rows = 0
            file_min_id: str | None = None
            file_max_id: str | None = None
            for batch in parquet_file.iter_batches(batch_size=batch_rows):
                columns = {
                    name: batch.column(index).to_pylist()
                    for index, name in enumerate(INDICATOR_OBSERVATION_CONTRACT.columns)
                }
                for row_index in range(batch.num_rows):
                    row = {
                        name: columns[name][row_index]
                        for name in INDICATOR_OBSERVATION_CONTRACT.columns
                    }
                    observation_id = str(row["observation_id"])
                    if observation_id in seen_ids:
                        duplicate_ids += 1
                    seen_ids.add(observation_id)
                    file_min_id = (
                        observation_id
                        if file_min_id is None
                        else min(file_min_id, observation_id)
                    )
                    file_max_id = (
                        observation_id
                        if file_max_id is None
                        else max(file_max_id, observation_id)
                    )
                    partition_min_id = (
                        observation_id
                        if partition_min_id is None
                        else min(partition_min_id, observation_id)
                    )
                    partition_max_id = (
                        observation_id
                        if partition_max_id is None
                        else max(partition_max_id, observation_id)
                    )
                    order_key = (
                        str(row["point_date"]),
                        str(row["series_code"]),
                        str(row["source_snapshot_date"] or ""),
                        str(row["source_record_id"] or ""),
                        observation_id,
                    )
                    if previous_order is not None and order_key < previous_order:
                        rows_ordered = False
                    previous_order = order_key
                    if str(row["source_id"]) != str(values.get("source_id")):
                        partition_values_valid = False
                    if str(row["geographic_scope"]) != str(
                        values.get("geographic_scope")
                    ):
                        partition_values_valid = False
                    if str(row["point_year"]) != str(values.get("year")):
                        partition_values_valid = False
                    if not str(row["point_date"]).startswith(
                        str(row["point_year"]) + "-"
                    ):
                        row_semantics_valid = False
                    if _is_public_url(row["source_url"]):
                        source_url_rows += 1
                    else:
                        urls_public = False
                    if row["source_record_pk"] is not None:
                        source_record_rows += 1
                    if str(row["lineage_state"]) != "missing":
                        lineage_rows += 1
                    expected_state = _expected_observation_state(row)
                    if row["observation_state"] != expected_state:
                        row_semantics_valid = False
                    if expected_state == "numeric":
                        numeric_rows += 1
                        if row["value_text"] not in (None, ""):
                            row_semantics_valid = False
                    elif expected_state == "text_only":
                        text_rows += 1
                    else:
                        missing_rows += 1
                    for field, state_field, metric in (
                        ("unit", "unit_state", "unit"),
                        ("frequency", "frequency_state", "frequency"),
                        (
                            "methodology_version",
                            "methodology_state",
                            "methodology",
                        ),
                    ):
                        if row[state_field] != _expected_metadata_state(row[field]):
                            row_semantics_valid = False
                        if row[field] not in (None, ""):
                            if metric == "unit":
                                unit_rows += 1
                            elif metric == "frequency":
                                frequency_rows += 1
                            else:
                                methodology_rows += 1
                    try:
                        parsed_dimensions = json.loads(str(row["dimensions_json"]))
                    except (json.JSONDecodeError, TypeError):
                        dimensions_valid = False
                    else:
                        canonical = json.dumps(
                            parsed_dimensions,
                            ensure_ascii=True,
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                        if not isinstance(parsed_dimensions, dict):
                            dimensions_valid = False
                        if canonical != row["dimensions_json"]:
                            dimensions_valid = False
                        if (
                            hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                            != row["dimensions_sha256"]
                        ):
                            dimensions_valid = False
                    group_id = str(row["observation_group_id"])
                    if group_id != _expected_group_id(row):
                        revision_groups_valid = False
                    ordinal = int(row["revision_ordinal"])
                    count = int(row["revision_count"])
                    if group_id != current_group:
                        if (
                            current_group is not None
                            and current_group_last_ordinal != current_group_count
                        ):
                            revision_groups_valid = False
                        current_group = group_id
                        current_group_count = count
                        current_group_last_ordinal = 0
                        revision_groups += 1
                        if count > 1:
                            revised_groups += 1
                    if (
                        count != current_group_count
                        or ordinal != current_group_last_ordinal + 1
                    ):
                        revision_groups_valid = False
                    current_group_last_ordinal = ordinal
                    expected_revision_state = _expected_revision_state(ordinal, count)
                    if row["revision_state"] != expected_revision_state:
                        revision_groups_valid = False
                    if expected_revision_state == "sole":
                        sole_rows += 1
                    elif expected_revision_state == "latest":
                        latest_revision_rows += 1
                    else:
                        superseded_revision_rows += 1
                    private_findings += private_token_findings(row)
                    digest.update(
                        INDICATOR_OBSERVATION_CONTRACT.canonical_row_bytes(row)
                    )
                    file_rows += 1
                    partition_rows += 1
                    rows_total += 1
            if file_rows != expected_file_rows:
                file_rows_valid = False
            if file_min_id != file_meta.get("min_id"):
                file_minmax_valid = False
            if file_max_id != file_meta.get("max_id"):
                file_minmax_valid = False
            partition_file_reports.append(
                {
                    "path": relative,
                    "rows": file_rows,
                    "bytes": actual_bytes,
                    "sha256": actual_sha256,
                }
            )
        if partition_rows != int(partition.get("rows") or 0):
            partition_rows_valid = False
        if partition_min_id != partition.get("min_id"):
            partition_rows_valid = False
        if partition_max_id != partition.get("max_id"):
            partition_rows_valid = False
        actual_input_sha256 = digest.hexdigest()
        if actual_input_sha256 != str(partition.get("input_sha256") or ""):
            partition_hashes_valid = False
        partition_reports.append(
            {
                "partition_id": partition.get("partition_id"),
                "rows": partition_rows,
                "files": partition_file_reports,
                "input_sha256": actual_input_sha256,
            }
        )

    if current_group is not None and current_group_last_ordinal != current_group_count:
        revision_groups_valid = False
    actual_paths = {
        path.relative_to(root).as_posix() for path in root.rglob("*.parquet")
    }
    peak_rss = peak_rss_mb()
    totals = dict(manifest.get("totals") or {})
    checks = {
        "manifest_schema": manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION,
        "lane": manifest.get("lane") == INDICATOR_OBSERVATION_CONTRACT.lane,
        "transformer_version": manifest.get("transformer_version")
        == INDICATOR_OBSERVATION_CONTRACT.transformer_version,
        "schema_sha256": manifest.get("schema_sha256")
        == INDICATOR_OBSERVATION_CONTRACT.schema_sha256,
        "minimum_rows": rows_total >= int(min_rows),
        "all_files_present": files_present,
        "no_duplicate_manifest_paths": duplicate_paths == 0,
        "no_extra_parquet_files": actual_paths == expected_paths,
        "checksums_and_bytes": checksums_valid,
        "parquet_schemas": schemas_valid,
        "file_rows": file_rows_valid,
        "file_minmax": file_minmax_valid,
        "partition_rows": partition_rows_valid,
        "partition_hashes": partition_hashes_valid,
        "partition_values": partition_values_valid,
        "rows_ordered_within_partitions": rows_ordered,
        "unique_observation_ids": duplicate_ids == 0,
        "manifest_row_total": rows_total == int(totals.get("rows") or -1),
        "manifest_file_total": files_total == int(totals.get("files") or -1),
        "manifest_byte_total": bytes_total == int(totals.get("parquet_bytes") or -1),
        "source_urls_complete_and_public": urls_public
        and source_url_rows == rows_total,
        "lineage_complete": lineage_rows == rows_total,
        "row_semantics": row_semantics_valid,
        "revision_groups": revision_groups_valid
        and revision_groups == int(totals.get("revision_groups") or -1)
        and revised_groups == int(totals.get("revised_groups", -1)),
        "revision_state_balance": sole_rows
        + latest_revision_rows
        + superseded_revision_rows
        == rows_total,
        "dimensions_canonical_and_hashed": dimensions_valid,
        "no_private_tokens": private_findings == 0,
        "bounded_peak_rss": peak_rss <= float(max_peak_rss_mb),
    }
    status = "ok" if all(checks.values()) else "failed"
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "status": status,
        "manifest_file": manifest_path.name,
        "root_name": root.name,
        "checks": checks,
        "totals": {
            "rows": rows_total,
            "files": files_total,
            "parquet_bytes": bytes_total,
            "partitions": len(partition_reports),
            "source_url_rows": source_url_rows,
            "source_record_rows": source_record_rows,
            "lineage_rows": lineage_rows,
            "numeric_rows": numeric_rows,
            "text_rows": text_rows,
            "missing_rows": missing_rows,
            "unit_rows": unit_rows,
            "frequency_rows": frequency_rows,
            "methodology_rows": methodology_rows,
            "revision_groups": revision_groups,
            "revised_groups": revised_groups,
            "sole_rows": sole_rows,
            "latest_revision_rows": latest_revision_rows,
            "superseded_revision_rows": superseded_revision_rows,
            "private_token_findings": private_findings,
            "duplicate_observation_ids": duplicate_ids,
        },
        "coverage": {
            "source_url": round(source_url_rows / rows_total, 8) if rows_total else 0.0,
            "lineage": round(lineage_rows / rows_total, 8) if rows_total else 0.0,
            "unit": round(unit_rows / rows_total, 8) if rows_total else 0.0,
            "frequency": round(frequency_rows / rows_total, 8) if rows_total else 0.0,
            "methodology": round(methodology_rows / rows_total, 8)
            if rows_total
            else 0.0,
        },
        "performance": {
            "peak_rss_mb": peak_rss,
            "max_peak_rss_mb": float(max_peak_rss_mb),
            "batch_rows": int(batch_rows),
        },
        "publication_status": manifest.get("publication_status"),
        "analytical_partition_gate_passed": all(checks.values()),
        "promotion_gate_passed": bool(manifest.get("promotion_gate_passed"))
        and all(checks.values()),
        "partitions": partition_reports,
    }


__all__ = ["VALIDATION_SCHEMA_VERSION", "validate_indicator_partitions"]
