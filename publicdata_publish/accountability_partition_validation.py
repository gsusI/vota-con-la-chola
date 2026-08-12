"""Independent full-row validation for accountability-ledger Parquet."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .accountability_partitions import ACCOUNTABILITY_LEDGER_CONTRACT
from .semantic_contracts import (
    MANIFEST_SCHEMA_VERSION,
    peak_rss_mb,
    private_token_findings,
    safe_child,
    sha256_file,
)

VALIDATION_SCHEMA_VERSION = "accountability_partition_validation_v1"


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


def _expected_actor_state(row: dict[str, Any]) -> str:
    actor_kind = str(row["actor_kind"])
    key_by_kind = {
        "person": "person_id",
        "party": "party_id",
        "group": "parliamentary_group_id",
        "institution": "institution_id",
        "org_unit": "org_unit_id",
        "position": "position_id",
    }
    key = key_by_kind.get(actor_kind)
    if key and row[key] is not None:
        return "resolved_" + actor_kind
    return "unresolved_" + actor_kind


def _expected_lineage_state(row: dict[str, Any]) -> str:
    if row["source_record_pk"] is not None:
        return "source_record"
    if row["policy_event_id"] not in (None, ""):
        return "policy_event"
    if row["topic_evidence_id"] is not None:
        return "topic_evidence"
    if row["legal_fragment_id"] not in (None, ""):
        return "legal_fragment"
    if row["linked_object_type"] not in (None, "") and row["linked_object_id"] not in (
        None,
        "",
    ):
        return "linked_object"
    if _is_public_url(row["source_url"]):
        return "source_url"
    return "missing"


def validate_accountability_partitions(
    *,
    root: Path,
    manifest_path: Path | None = None,
    batch_rows: int = 10_000,
    min_rows: int = 100_000,
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
    expected_schema = ACCOUNTABILITY_LEDGER_CONTRACT.arrow_schema()
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
    actor_states_explicit = True
    actor_states_consistent = True
    lineage_states_consistent = True
    rows_total = 0
    files_total = 0
    bytes_total = 0
    source_url_rows = 0
    source_record_url_rows = 0
    source_default_url_rows = 0
    source_record_rows = 0
    lineage_rows = 0
    resolved_actor_rows = 0
    unresolved_actor_rows = 0
    unknown_year_rows = 0
    private_findings = 0
    partition_reports: list[dict[str, Any]] = []

    for partition in list(manifest.get("partitions") or []):
        digest = hashlib.sha256()
        partition_rows = 0
        partition_min_id: str | None = None
        partition_max_id: str | None = None
        partition_previous_id: str | None = None
        values = dict(partition.get("values") or {})
        partition_file_reports: list[dict[str, Any]] = []
        for file_meta in list(partition.get("files") or []):
            relative = str(file_meta.get("path") or "")
            if relative in expected_paths:
                duplicate_paths += 1
            expected_paths.add(relative)
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
                    for index, name in enumerate(ACCOUNTABILITY_LEDGER_CONTRACT.columns)
                }
                for row_index in range(batch.num_rows):
                    row = {
                        name: columns[name][row_index]
                        for name in ACCOUNTABILITY_LEDGER_CONTRACT.columns
                    }
                    entry_id = str(row["entry_id"])
                    if (
                        partition_previous_id is not None
                        and entry_id <= partition_previous_id
                    ):
                        ids_sorted = False
                    partition_previous_id = entry_id
                    file_min_id = (
                        entry_id if file_min_id is None else min(file_min_id, entry_id)
                    )
                    file_max_id = (
                        entry_id if file_max_id is None else max(file_max_id, entry_id)
                    )
                    partition_min_id = (
                        entry_id
                        if partition_min_id is None
                        else min(partition_min_id, entry_id)
                    )
                    partition_max_id = (
                        entry_id
                        if partition_max_id is None
                        else max(partition_max_id, entry_id)
                    )
                    if str(row["source_id"]) != str(values.get("source_id")):
                        partition_values_valid = False
                    if str(row["jurisdiction"]) != str(values.get("jurisdiction")):
                        partition_values_valid = False
                    if str(row["entry_year"]) != str(values.get("year")):
                        partition_values_valid = False
                    if _is_public_url(row["source_url"]):
                        source_url_rows += 1
                    else:
                        urls_public = False
                    if row["source_url_scope"] == "record":
                        source_record_url_rows += 1
                    elif row["source_url_scope"] == "source_default":
                        source_default_url_rows += 1
                    else:
                        partition_values_valid = False
                    if row["source_record_pk"] is not None:
                        source_record_rows += 1
                    if row["lineage_state"] != "missing":
                        lineage_rows += 1
                    if row["lineage_state"] != _expected_lineage_state(row):
                        lineage_states_consistent = False
                    state = str(row["actor_resolution_state"])
                    if state.startswith("resolved_"):
                        resolved_actor_rows += 1
                    elif state.startswith("unresolved_"):
                        unresolved_actor_rows += 1
                    else:
                        actor_states_explicit = False
                    if state != _expected_actor_state(row):
                        actor_states_consistent = False
                    if row["entry_year"] == "unknown":
                        unknown_year_rows += 1
                    private_findings += private_token_findings(row)
                    digest.update(
                        ACCOUNTABILITY_LEDGER_CONTRACT.canonical_row_bytes(row)
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

    actual_paths = {
        path.relative_to(root).as_posix() for path in root.rglob("*.parquet")
    }
    peak_rss = peak_rss_mb()
    totals = dict(manifest.get("totals") or {})
    checks = {
        "manifest_schema": manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION,
        "lane": manifest.get("lane") == ACCOUNTABILITY_LEDGER_CONTRACT.lane,
        "transformer_version": manifest.get("transformer_version")
        == ACCOUNTABILITY_LEDGER_CONTRACT.transformer_version,
        "schema_sha256": manifest.get("schema_sha256")
        == ACCOUNTABILITY_LEDGER_CONTRACT.schema_sha256,
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
        "entry_ids_sorted_within_partitions": ids_sorted,
        "manifest_row_total": rows_total == int(totals.get("rows") or -1),
        "manifest_file_total": files_total == int(totals.get("files") or -1),
        "manifest_byte_total": bytes_total == int(totals.get("parquet_bytes") or -1),
        "source_urls_complete_and_public": urls_public
        and source_url_rows == rows_total,
        "lineage_complete": lineage_rows == rows_total,
        "lineage_states_consistent": lineage_states_consistent,
        "actor_resolution_states_explicit": actor_states_explicit
        and resolved_actor_rows + unresolved_actor_rows == rows_total,
        "actor_resolution_states_consistent": actor_states_consistent,
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
            "source_record_rows": source_record_rows,
            "lineage_rows": lineage_rows,
            "resolved_actor_rows": resolved_actor_rows,
            "unresolved_actor_rows": unresolved_actor_rows,
            "unknown_year_rows": unknown_year_rows,
            "private_token_findings": private_findings,
        },
        "coverage": {
            "source_url": round(source_url_rows / rows_total, 8) if rows_total else 0.0,
            "source_record": round(source_record_rows / rows_total, 8)
            if rows_total
            else 0.0,
            "lineage": round(lineage_rows / rows_total, 8) if rows_total else 0.0,
            "resolved_actor": round(resolved_actor_rows / rows_total, 8)
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


__all__ = ["VALIDATION_SCHEMA_VERSION", "validate_accountability_partitions"]
