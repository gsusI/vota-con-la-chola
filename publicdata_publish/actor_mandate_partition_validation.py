"""Independent full-row validation for actor-mandate Parquet."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .actor_mandate_partitions import ACTOR_MANDATE_CONTRACT
from .semantic_contracts import (
    MANIFEST_SCHEMA_VERSION,
    peak_rss_mb,
    private_token_findings,
    safe_child,
    safe_component,
    sha256_file,
)

VALIDATION_SCHEMA_VERSION = "actor_mandate_partition_validation_v1"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _is_public_url(value: Any) -> bool:
    if value in (None, ""):
        return False
    try:
        parsed = urlsplit(str(value))
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _expected_identity_state(row: dict[str, Any]) -> str:
    if row["source_identifiers"]:
        return "source_identifier_present"
    if row["source_record_pk"] is not None:
        return "source_record_present"
    if row["aliases"]:
        return "alias_only"
    return "observed_label_only"


def _expected_lineage_state(row: dict[str, Any]) -> str:
    if row["source_record_pk"] is not None:
        return "source_record"
    if row["source_record_id"] not in (None, ""):
        return "source_scoped_record_id"
    if _is_public_url(row["source_url"]):
        return "source_default_url"
    return "missing"


def _expected_jurisdiction(level: str) -> str:
    normalized = level.strip().lower()
    known = {
        "europeo": "eu",
        "nacional": "es-national",
        "autonomico": "es-autonomic",
        "municipal": "es-municipal",
    }
    return known.get(normalized, "es-" + safe_component(normalized))


def _expected_relative_dir(manifest: dict[str, Any], values: dict[str, Any]) -> str:
    return Path(
        f"lane={ACTOR_MANDATE_CONTRACT.lane}",
        f"snapshot_date={safe_component(str(manifest.get('snapshot_date') or ''))}",
        f"source_id={safe_component(str(values.get('source_id') or ''))}",
        f"jurisdiction={safe_component(str(values.get('jurisdiction') or ''))}",
        f"year={safe_component(str(values.get('year') or ''))}",
    ).as_posix()


def validate_actor_mandate_partitions(
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
    expected_schema = ACTOR_MANDATE_CONTRACT.arrow_schema()

    expected_paths: set[str] = set()
    duplicate_paths = 0
    files_present = True
    checksums_valid = True
    schemas_valid = True
    file_rows_valid = True
    file_minmax_valid = True
    partition_rows_valid = True
    partition_hashes_valid = True
    partition_values_valid = True
    ids_sorted = True
    urls_public = True
    identity_states_consistent = True
    lineage_states_consistent = True
    list_fields_valid = True
    jurisdiction_consistent = True
    rows_total = 0
    files_total = 0
    bytes_total = 0
    source_url_rows = 0
    source_record_rows = 0
    lineage_rows = 0
    source_identifier_rows = 0
    source_record_identity_rows = 0
    alias_only_rows = 0
    observed_label_only_rows = 0
    rows_with_aliases = 0
    source_identifiers_total = 0
    aliases_total = 0
    active_rows = 0
    unknown_year_rows = 0
    private_findings = 0
    partition_reports: list[dict[str, Any]] = []
    seen_mandate_ids: set[int] = set()
    seen_person_ids: set[int] = set()
    duplicate_mandate_ids = 0

    state_metrics = {
        "source_identifier_present": "source_identifier_rows",
        "source_record_present": "source_record_identity_rows",
        "alias_only": "alias_only_rows",
        "observed_label_only": "observed_label_only_rows",
    }
    identity_counts = {key: 0 for key in state_metrics.values()}

    for partition in list(manifest.get("partitions") or []):
        digest = hashlib.sha256()
        partition_rows = 0
        partition_min_id: int | None = None
        partition_max_id: int | None = None
        partition_previous_id: int | None = None
        values = dict(partition.get("values") or {})
        expected_relative_dir = _expected_relative_dir(manifest, values)
        expected_partition_id = "|".join(
            str(values.get(key) or "") for key in ("source_id", "jurisdiction", "year")
        )
        if str(partition.get("relative_dir") or "") != expected_relative_dir:
            partition_values_valid = False
        if str(partition.get("partition_id") or "") != expected_partition_id:
            partition_values_valid = False
        if str(values.get("snapshot_date") or "") != str(
            manifest.get("snapshot_date") or ""
        ):
            partition_values_valid = False
        partition_metrics = {
            "source_url_rows": 0,
            "source_record_rows": 0,
            "lineage_rows": 0,
            "source_identifier_rows": 0,
            "source_record_identity_rows": 0,
            "alias_only_rows": 0,
            "observed_label_only_rows": 0,
            "rows_with_aliases": 0,
            "active_rows": 0,
            "private_token_findings": 0,
        }
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
            file_min_id: int | None = None
            file_max_id: int | None = None
            for batch in parquet_file.iter_batches(batch_size=batch_rows):
                columns = {
                    name: batch.column(index).to_pylist()
                    for index, name in enumerate(ACTOR_MANDATE_CONTRACT.columns)
                }
                for row_index in range(batch.num_rows):
                    row = {
                        name: columns[name][row_index]
                        for name in ACTOR_MANDATE_CONTRACT.columns
                    }
                    mandate_id = int(row["mandate_id"])
                    if mandate_id in seen_mandate_ids:
                        duplicate_mandate_ids += 1
                    seen_mandate_ids.add(mandate_id)
                    seen_person_ids.add(int(row["person_id"]))
                    if (
                        partition_previous_id is not None
                        and mandate_id <= partition_previous_id
                    ):
                        ids_sorted = False
                    partition_previous_id = mandate_id
                    file_min_id = (
                        mandate_id
                        if file_min_id is None
                        else min(file_min_id, mandate_id)
                    )
                    file_max_id = (
                        mandate_id
                        if file_max_id is None
                        else max(file_max_id, mandate_id)
                    )
                    partition_min_id = (
                        mandate_id
                        if partition_min_id is None
                        else min(partition_min_id, mandate_id)
                    )
                    partition_max_id = (
                        mandate_id
                        if partition_max_id is None
                        else max(partition_max_id, mandate_id)
                    )
                    if str(row["source_id"]) != str(values.get("source_id")):
                        partition_values_valid = False
                    if str(row["jurisdiction"]) != str(values.get("jurisdiction")):
                        partition_values_valid = False
                    if str(row["mandate_year"]) != str(values.get("year")):
                        partition_values_valid = False
                    if row["jurisdiction"] != _expected_jurisdiction(str(row["level"])):
                        jurisdiction_consistent = False
                    if _is_public_url(row["source_url"]):
                        source_url_rows += 1
                        partition_metrics["source_url_rows"] += 1
                    else:
                        urls_public = False
                    if row["source_url_scope"] != "source_default":
                        partition_values_valid = False
                    if row["source_record_pk"] is not None:
                        source_record_rows += 1
                        partition_metrics["source_record_rows"] += 1
                    if row["lineage_state"] != "missing":
                        lineage_rows += 1
                        partition_metrics["lineage_rows"] += 1
                    if row["lineage_state"] != _expected_lineage_state(row):
                        lineage_states_consistent = False
                    identifiers = row["source_identifiers"]
                    aliases = row["aliases"]
                    if not isinstance(identifiers, list) or not all(
                        isinstance(item, str) for item in identifiers
                    ):
                        list_fields_valid = False
                        identifiers = []
                    if not isinstance(aliases, list) or not all(
                        isinstance(item, str) for item in aliases
                    ):
                        list_fields_valid = False
                        aliases = []
                    if len(identifiers) != len(set(identifiers)):
                        list_fields_valid = False
                    if len(aliases) != len(set(aliases)):
                        list_fields_valid = False
                    source_identifiers_total += len(identifiers)
                    aliases_total += len(aliases)
                    if aliases:
                        rows_with_aliases += 1
                        partition_metrics["rows_with_aliases"] += 1
                    state = str(row["identity_state"])
                    metric = state_metrics.get(state)
                    if metric is None:
                        identity_states_consistent = False
                    else:
                        identity_counts[metric] += 1
                        partition_metrics[metric] += 1
                    if state != _expected_identity_state(row):
                        identity_states_consistent = False
                    if int(row["is_active"]):
                        active_rows += 1
                        partition_metrics["active_rows"] += 1
                    if row["mandate_year"] == "unknown":
                        unknown_year_rows += 1
                    row_private_findings = private_token_findings(row)
                    private_findings += row_private_findings
                    partition_metrics["private_token_findings"] += row_private_findings
                    digest.update(ACTOR_MANDATE_CONTRACT.canonical_row_bytes(row))
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
        if any(
            key not in partition or int(partition.get(key) or 0) != value
            for key, value in partition_metrics.items()
        ):
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

    source_identifier_rows = identity_counts["source_identifier_rows"]
    source_record_identity_rows = identity_counts["source_record_identity_rows"]
    alias_only_rows = identity_counts["alias_only_rows"]
    observed_label_only_rows = identity_counts["observed_label_only_rows"]
    actual_paths = {
        path.relative_to(root).as_posix() for path in root.rglob("*.parquet")
    }
    peak_rss = peak_rss_mb()
    totals = dict(manifest.get("totals") or {})
    calculated_totals = {
        "rows": rows_total,
        "mandate_rows": rows_total,
        "joined_rows": rows_total,
        "distinct_mandate_ids": len(seen_mandate_ids),
        "distinct_people": len(seen_person_ids),
        "files": files_total,
        "parquet_bytes": bytes_total,
        "partitions": len(partition_reports),
        "source_url_rows": source_url_rows,
        "source_record_rows": source_record_rows,
        "lineage_rows": lineage_rows,
        "source_identifier_rows": source_identifier_rows,
        "source_record_identity_rows": source_record_identity_rows,
        "alias_only_rows": alias_only_rows,
        "observed_label_only_rows": observed_label_only_rows,
        "rows_with_aliases": rows_with_aliases,
        "source_identifiers_total": source_identifiers_total,
        "aliases_total": aliases_total,
        "active_rows": active_rows,
        "unknown_year_rows": unknown_year_rows,
        "private_token_findings": private_findings,
    }
    expected_coverage = {
        "source_url": round(source_url_rows / rows_total, 8) if rows_total else 0.0,
        "source_record": round(source_record_rows / rows_total, 8)
        if rows_total
        else 0.0,
        "lineage": round(lineage_rows / rows_total, 8) if rows_total else 0.0,
        "source_identifier": round(source_identifier_rows / rows_total, 8)
        if rows_total
        else 0.0,
    }
    checks = {
        "manifest_schema": manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION,
        "lane": manifest.get("lane") == ACTOR_MANDATE_CONTRACT.lane,
        "transformer_version": manifest.get("transformer_version")
        == ACTOR_MANDATE_CONTRACT.transformer_version,
        "schema_sha256": manifest.get("schema_sha256")
        == ACTOR_MANDATE_CONTRACT.schema_sha256,
        "manifest_schema_definition": manifest.get("schema")
        == list(ACTOR_MANDATE_CONTRACT.schema),
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
        "mandate_ids_sorted_within_partitions": ids_sorted,
        "mandate_ids_unique_across_partitions": duplicate_mandate_ids == 0
        and len(seen_mandate_ids) == rows_total,
        "jurisdiction_consistent": jurisdiction_consistent,
        "manifest_row_total": rows_total == int(totals.get("rows") or -1),
        "manifest_file_total": files_total == int(totals.get("files") or -1),
        "manifest_byte_total": bytes_total == int(totals.get("parquet_bytes") or -1),
        "manifest_metric_totals": all(
            key in totals and int(totals.get(key) or 0) == value
            for key, value in calculated_totals.items()
        ),
        "manifest_coverage": manifest.get("coverage") == expected_coverage,
        "source_urls_complete_and_public": urls_public
        and source_url_rows == rows_total,
        "lineage_complete": lineage_rows == rows_total,
        "lineage_states_consistent": lineage_states_consistent,
        "identity_states_consistent": identity_states_consistent,
        "identity_lists_valid": list_fields_valid,
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
        "totals": calculated_totals,
        "coverage": expected_coverage,
        "performance": {
            "peak_rss_mb": peak_rss,
            "max_peak_rss_mb": float(max_peak_rss_mb),
            "batch_rows": int(batch_rows),
        },
        "identity_assurance": manifest.get("identity_assurance"),
        "publication_status": manifest.get("publication_status"),
        "analytical_partition_gate_passed": all(checks.values()),
        "promotion_gate_passed": bool(manifest.get("promotion_gate_passed"))
        and all(checks.values()),
        "partitions": partition_reports,
    }


__all__ = ["VALIDATION_SCHEMA_VERSION", "validate_actor_mandate_partitions"]
