"""Independent full-corpus validation for semantic Parquet partitions."""

from __future__ import annotations

import hashlib
import json
import resource
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .semantic_partitions import (
    LANE,
    MANIFEST_SCHEMA_VERSION,
    MEMBER_VOTE_COLUMNS,
    PRIVATE_TOKENS,
    _arrow_schema,
    _canonical_row_bytes,
    _schema_sha256,
    _sha256_file,
)


VALIDATION_SCHEMA_VERSION = "semantic_partition_validation_v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _peak_rss_mb() -> float:
    raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return round(raw / (1024 * 1024), 3)
    return round(raw / 1024, 3)


def _safe_child(root: Path, relative: str) -> Path | None:
    candidate = root / relative
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _public_http_url(value: Any) -> bool:
    if value in (None, ""):
        return True
    try:
        parsed = urlsplit(str(value))
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_semantic_partitions(
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

    root = Path(root)
    manifest_path = Path(manifest_path) if manifest_path else root / "manifest.json"
    if not root.is_dir():
        raise FileNotFoundError(root)
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_schema = _arrow_schema()
    expected_paths: set[str] = set()
    duplicate_paths = 0
    checksums_valid = True
    files_present = True
    schemas_valid = True
    file_rows_valid = True
    file_minmax_valid = True
    partition_rows_valid = True
    partition_hashes_valid = True
    partition_values_valid = True
    member_ids_sorted = True
    urls_public = True
    private_findings = 0
    rows_total = 0
    files_total = 0
    bytes_total = 0
    source_url_rows = 0
    source_record_url_rows = 0
    source_default_url_rows = 0
    person_id_rows = 0
    lineage_rows = 0
    unknown_year_rows = 0
    partition_reports: list[dict[str, Any]] = []

    for partition in list(manifest.get("partitions") or []):
        digest = hashlib.sha256()
        partition_rows = 0
        partition_min_id: int | None = None
        partition_max_id: int | None = None
        partition_previous_id: int | None = None
        values = dict(partition.get("values") or {})
        partition_file_reports: list[dict[str, Any]] = []
        for file_meta in list(partition.get("files") or []):
            relative = str(file_meta.get("path") or "")
            if relative in expected_paths:
                duplicate_paths += 1
            expected_paths.add(relative)
            file_path = _safe_child(root, relative)
            files_total += 1
            if file_path is None or not file_path.is_file():
                files_present = False
                continue
            actual_bytes = int(file_path.stat().st_size)
            actual_sha256 = _sha256_file(file_path)
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
            metadata_rows = int(parquet_file.metadata.num_rows)
            expected_file_rows = int(file_meta.get("rows") or 0)
            if metadata_rows != expected_file_rows:
                file_rows_valid = False
            file_rows = 0
            file_min_id: int | None = None
            file_max_id: int | None = None
            for batch in parquet_file.iter_batches(batch_size=batch_rows):
                columns = {
                    name: batch.column(index).to_pylist()
                    for index, name in enumerate(MEMBER_VOTE_COLUMNS)
                }
                for row_index in range(batch.num_rows):
                    row = {
                        name: columns[name][row_index]
                        for name in MEMBER_VOTE_COLUMNS
                    }
                    member_vote_id = int(row["member_vote_id"])
                    if (
                        partition_previous_id is not None
                        and member_vote_id <= partition_previous_id
                    ):
                        member_ids_sorted = False
                    partition_previous_id = member_vote_id
                    file_min_id = (
                        member_vote_id
                        if file_min_id is None
                        else min(file_min_id, member_vote_id)
                    )
                    file_max_id = (
                        member_vote_id
                        if file_max_id is None
                        else max(file_max_id, member_vote_id)
                    )
                    partition_min_id = (
                        member_vote_id
                        if partition_min_id is None
                        else min(partition_min_id, member_vote_id)
                    )
                    partition_max_id = (
                        member_vote_id
                        if partition_max_id is None
                        else max(partition_max_id, member_vote_id)
                    )
                    if str(row["source_id"]) != str(values.get("source_id")):
                        partition_values_valid = False
                    if str(row["jurisdiction"]) != str(
                        values.get("jurisdiction")
                    ):
                        partition_values_valid = False
                    if str(row["vote_year"]) != str(values.get("year")):
                        partition_values_valid = False
                    if not _public_http_url(row["source_url"]):
                        urls_public = False
                    if row["source_url"] not in (None, ""):
                        source_url_rows += 1
                    if row["source_url_scope"] == "record":
                        source_record_url_rows += 1
                    elif row["source_url_scope"] == "source_default":
                        source_default_url_rows += 1
                    elif row["source_url"] not in (None, ""):
                        partition_values_valid = False
                    if row["person_id"] is not None:
                        person_id_rows += 1
                    if row["event_source_record_pk"] is not None:
                        lineage_rows += 1
                    if row["vote_year"] == "unknown":
                        unknown_year_rows += 1
                    private_findings += sum(
                        1
                        for value in row.values()
                        if isinstance(value, str)
                        for token in PRIVATE_TOKENS
                        if token in value
                    )
                    digest.update(_canonical_row_bytes(row))
                    file_rows += 1
                    partition_rows += 1
                    rows_total += 1
            if file_rows != expected_file_rows:
                file_rows_valid = False
            if file_min_id != file_meta.get("min_member_vote_id"):
                file_minmax_valid = False
            if file_max_id != file_meta.get("max_member_vote_id"):
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
        if partition_min_id != partition.get("min_member_vote_id"):
            partition_rows_valid = False
        if partition_max_id != partition.get("max_member_vote_id"):
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

    actual_paths = {
        path.relative_to(root).as_posix() for path in root.rglob("*.parquet")
    }
    peak_rss = _peak_rss_mb()
    manifest_totals = dict(manifest.get("totals") or {})
    rows_match = rows_total == int(manifest_totals.get("rows") or -1)
    files_match = files_total == int(manifest_totals.get("files") or -1)
    bytes_match = bytes_total == int(manifest_totals.get("parquet_bytes") or -1)
    checks = {
        "manifest_schema": manifest.get("schema_version")
        == MANIFEST_SCHEMA_VERSION,
        "lane": manifest.get("lane") == LANE,
        "schema_sha256": manifest.get("schema_sha256") == _schema_sha256(),
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
        "member_vote_ids_sorted_within_partitions": member_ids_sorted,
        "manifest_row_total": rows_match,
        "manifest_file_total": files_match,
        "manifest_byte_total": bytes_match,
        "source_urls_public": urls_public,
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
            "source_record_url_rows": source_record_url_rows,
            "source_default_url_rows": source_default_url_rows,
            "person_id_rows": person_id_rows,
            "event_source_record_rows": lineage_rows,
            "unknown_year_rows": unknown_year_rows,
            "private_token_findings": private_findings,
        },
        "coverage": {
            "source_url": round(source_url_rows / rows_total, 8)
            if rows_total
            else 0.0,
            "person_id": round(person_id_rows / rows_total, 8)
            if rows_total
            else 0.0,
            "event_source_record": round(lineage_rows / rows_total, 8)
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


__all__ = ["VALIDATION_SCHEMA_VERSION", "validate_semantic_partitions"]
