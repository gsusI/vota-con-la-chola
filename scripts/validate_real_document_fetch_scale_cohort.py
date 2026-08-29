#!/usr/bin/env python3
"""Independently validate bounded real-document acquisition cohorts."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import resource
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


EXPECTED_HOST_ROWS = {
    "www.boe.es": 914,
    "www.parlamentodeandalucia.es": 86,
}
EXPECTED_MODES = {
    "boe_document_identifier": 800,
    "boe_summary_structure": 114,
    "parliament_html_semantic": 51,
    "parliament_pdf_signature": 35,
}
MAX_MANIFEST_ROWS = 100_000_000
MAX_MANIFEST_PARTITIONS = 100_000
MAX_PARTITION_ROWS = 250_000
MAX_PARTITION_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
PLANNER_SCHEMA_VERSION = "real_document_fetch_disk_planner_v1"
MAX_EMBEDDED_ROWS = 25_000


class BoundedErrors:
    def __init__(self, limit: int = 100) -> None:
        self.limit = max(1, int(limit))
        self.samples: list[str] = []
        self.total = 0

    def append(self, value: object) -> None:
        self.total += 1
        if len(self.samples) < self.limit:
            self.samples.append(str(value))

    def extend(self, values: list[str]) -> None:
        for value in values:
            self.append(value)

    def __bool__(self) -> bool:
        return self.total > 0


def validation_performance(*, started: float, cpu_started: float) -> dict[str, Any]:
    rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return {
        "elapsed_seconds": round(max(0.000001, time.monotonic() - started), 6),
        "cpu_seconds": round(max(0.0, time.process_time() - cpu_started), 6),
        "peak_rss_bytes": rss if sys.platform == "darwin" else rss * 1024,
    }


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"path is outside repository: {path}") from exc


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def safe_repo_file(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe repository path: {value}")
    resolved = (Path.cwd() / path).resolve()
    try:
        resolved.relative_to(Path.cwd().resolve())
    except ValueError as exc:
        raise ValueError(f"repository path escapes root: {value}") from exc
    return resolved


def safe_fresh_path(raw_root: Path, stored_path: str) -> Path:
    path = Path(stored_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    resolved = path.resolve()
    try:
        resolved.relative_to(raw_root.resolve())
    except ValueError as exc:
        raise ValueError(f"stored raw path escapes cohort root: {stored_path}") from exc
    return resolved


def semantic_projection(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        "source_pipeline_id",
        "source_id",
        "source_url",
        "source_host",
        "document_kind",
        "validation_mode",
        "size_decile",
        "expected_bytes",
        "expected_content_sha256",
    )
    return [{field: row.get(field) for field in fields} for row in rows]


def semantic_sha256(rows: list[dict[str, Any]]) -> str:
    encoded = json.dumps(
        semantic_projection(rows),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_projection_line(row: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            semantic_projection([row])[0],
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def execution_contract_line(
    row: dict[str, Any], *, queue_priority: int
) -> bytes:
    fields = (
        "source_pipeline_id",
        "source_id",
        "provenance_source_id",
        "source_url",
        "source_host",
        "document_kind",
        "validation_mode",
        "size_decile",
        "expected_bytes",
        "expected_content_sha256",
        "captured_raw_path",
        "partition_key",
        "queue_priority",
        "payload",
    )
    projected = {field: row.get(field) for field in fields}
    projected["queue_priority"] = queue_priority
    return (
        json.dumps(
            projected,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def validate_exact_provenance_reference_edges(payload: dict[str, Any]) -> None:
    provenance = payload.get("provenance") or {}
    if not isinstance(provenance, dict):
        raise ValueError("Parliament provenance is not an object")
    reference_edges = provenance.get("reference_edges") or []
    if not isinstance(reference_edges, list) or not 1 <= len(reference_edges) <= 10_000:
        raise ValueError("Parliament provenance reference-edge count is invalid")
    pairs: list[tuple[str, str]] = []
    for edge in reference_edges:
        if not isinstance(edge, dict) or set(edge) != {"db_ref", "table_name"}:
            raise ValueError("Parliament provenance reference edge is invalid")
        pair = (str(edge.get("db_ref") or ""), str(edge.get("table_name") or ""))
        if not all(pair):
            raise ValueError("Parliament provenance reference edge is empty")
        pairs.append(pair)
    if pairs != sorted(set(pairs)):
        raise ValueError("Parliament provenance reference edges are not sorted unique")
    if provenance.get("db_refs") != sorted({pair[0] for pair in pairs}):
        raise ValueError("Parliament provenance db-ref projection mismatch")
    if provenance.get("table_names") != sorted({pair[1] for pair in pairs}):
        raise ValueError("Parliament provenance table-name projection mismatch")


def expected_partition_filename(
    *, source_pipeline_id: str, size_decile: int, shard_ordinal: int
) -> str:
    safe_pipeline = "".join(
        character if character.isalnum() else "-"
        for character in source_pipeline_id.lower()
    ).strip("-")
    pipeline_hash = hashlib.sha256(source_pipeline_id.encode("utf-8")).hexdigest()[:10]
    return (
        f"{safe_pipeline}-{pipeline_hash}-size-decile-{size_decile:02d}-"
        f"part-{shard_ordinal:06d}.jsonl.gz"
    )


def iter_manifest_rows(
    *, manifest: dict[str, Any], manifest_path: Path
):
    schema_version = manifest.get("schema_version")
    if schema_version == "real_document_fetch_scale_cohort_v2":
        rows = manifest.get("rows") or []
        if not isinstance(rows, list):
            raise ValueError("embedded manifest rows are not a list")
        yield from rows
        return
    if schema_version not in {
        "real_document_fetch_scale_cohort_v3",
        "real_document_fetch_scale_cohort_v4",
    }:
        raise ValueError("manifest schema mismatch")
    row_manifest = manifest.get("row_manifest") or {}
    expected_layout = (
        "partitioned_jsonl_gzip_v2"
        if schema_version == "real_document_fetch_scale_cohort_v4"
        else "partitioned_jsonl_gzip_v1"
    )
    if row_manifest.get("layout") != expected_layout:
        raise ValueError("partitioned manifest layout mismatch")
    if (
        row_manifest.get("semantic_identity_contract")
        != "sha256_concatenated_canonical_projection_jsonl_v1"
    ):
        raise ValueError("partitioned semantic identity contract mismatch")
    descriptors = row_manifest.get("partitions") or []
    if not isinstance(descriptors, list) or not descriptors:
        raise ValueError("partitioned manifest has no partitions")
    declared_total_rows = int(row_manifest.get("rows") or 0)
    if declared_total_rows < 1 or declared_total_rows > MAX_MANIFEST_ROWS:
        raise ValueError("partitioned manifest total rows exceed validation bounds")
    if len(descriptors) > MAX_MANIFEST_PARTITIONS:
        raise ValueError("partitioned manifest has too many partitions")
    seen_paths: set[str] = set()
    total_rows = 0
    previous_descriptor_key: tuple[str, int, int] | None = None
    previous_group_key: tuple[str, int] | None = None
    previous_group_last_url = ""
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            raise ValueError("partition descriptor is not an object")
        stored_path = str(descriptor.get("path") or "")
        if stored_path in seen_paths:
            raise ValueError(f"duplicate manifest partition: {stored_path}")
        seen_paths.add(stored_path)
        partition_path = safe_repo_file(stored_path)
        if not partition_path.is_file():
            raise ValueError(f"manifest partition is missing: {stored_path}")
        if descriptor.get("compression") != "gzip":
            raise ValueError(f"manifest partition compression mismatch: {stored_path}")
        declared_rows = int(descriptor.get("rows") or 0)
        declared_uncompressed_bytes = int(
            descriptor.get("uncompressed_bytes") or 0
        )
        if declared_rows < 1 or declared_rows > MAX_PARTITION_ROWS:
            raise ValueError(f"manifest partition row bound exceeded: {stored_path}")
        if (
            declared_uncompressed_bytes < 1
            or declared_uncompressed_bytes > MAX_PARTITION_UNCOMPRESSED_BYTES
        ):
            raise ValueError(
                f"manifest partition expanded-byte bound exceeded: {stored_path}"
            )
        if partition_path.stat().st_size != int(descriptor.get("bytes") or 0):
            raise ValueError(f"manifest partition byte mismatch: {stored_path}")
        if sha256_path(partition_path) != str(descriptor.get("sha256") or ""):
            raise ValueError(f"manifest partition hash mismatch: {stored_path}")
        rows = 0
        uncompressed_bytes = 0
        first_source_url = ""
        last_source_url = ""
        previous_source_url = ""
        descriptor_pipeline = str(descriptor.get("source_pipeline_id") or "")
        descriptor_decile = int(descriptor.get("size_decile") or 0)
        if schema_version == "real_document_fetch_scale_cohort_v4":
            shard_ordinal = int(descriptor.get("shard_ordinal") or 0)
            descriptor_key = (
                descriptor_pipeline,
                descriptor_decile,
                shard_ordinal,
            )
            group_key = (descriptor_pipeline, descriptor_decile)
            if not descriptor_pipeline or not 1 <= descriptor_decile <= 10:
                raise ValueError(f"manifest partition group mismatch: {stored_path}")
            if shard_ordinal < 1:
                raise ValueError(f"manifest partition shard ordinal mismatch: {stored_path}")
            if previous_descriptor_key is not None and descriptor_key <= previous_descriptor_key:
                raise ValueError("manifest partition descriptor order mismatch")
            expected_ordinal = (
                previous_descriptor_key[2] + 1
                if previous_group_key == group_key and previous_descriptor_key is not None
                else 1
            )
            if shard_ordinal != expected_ordinal:
                raise ValueError(f"manifest partition shard sequence mismatch: {stored_path}")
            expected_filename = expected_partition_filename(
                source_pipeline_id=descriptor_pipeline,
                size_decile=descriptor_decile,
                shard_ordinal=shard_ordinal,
            )
            if partition_path.name != expected_filename:
                raise ValueError(f"manifest partition filename mismatch: {stored_path}")
        else:
            shard_ordinal = 1
            descriptor_key = (
                descriptor_pipeline,
                descriptor_decile,
                shard_ordinal,
            )
            group_key = (descriptor_pipeline, descriptor_decile)
        with gzip.open(partition_path, "rb") as handle:
            line_number = 0
            while True:
                line = handle.readline(MAX_PARTITION_UNCOMPRESSED_BYTES + 1)
                if not line:
                    break
                line_number += 1
                if len(line) > MAX_PARTITION_UNCOMPRESSED_BYTES:
                    raise ValueError(
                        f"manifest row exceeds validation byte bound: {stored_path}:{line_number}"
                    )
                if not line.strip():
                    raise ValueError(
                        f"blank manifest row: {stored_path}:{line_number}"
                    )
                uncompressed_bytes += len(line)
                if uncompressed_bytes > declared_uncompressed_bytes:
                    raise ValueError(
                        f"manifest partition exceeds declared expanded bytes: {stored_path}"
                    )
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError(
                        f"manifest row is not an object: {stored_path}:{line_number}"
                    )
                source_url = str(row.get("source_url") or "")
                if str(row.get("source_pipeline_id") or "") != descriptor_pipeline:
                    raise ValueError(
                        f"manifest partition pipeline mismatch: {stored_path}"
                    )
                if int(row.get("size_decile") or 0) != descriptor_decile:
                    raise ValueError(
                        f"manifest partition size-decile mismatch: {stored_path}"
                    )
                if previous_source_url and source_url <= previous_source_url:
                    raise ValueError(
                        f"manifest partition URL order mismatch: {stored_path}"
                    )
                if not first_source_url:
                    first_source_url = source_url
                last_source_url = source_url
                previous_source_url = source_url
                rows += 1
                if rows > declared_rows:
                    raise ValueError(
                        f"manifest partition exceeds declared rows: {stored_path}"
                    )
                yield row
        if rows != declared_rows:
            raise ValueError(f"manifest partition row mismatch: {stored_path}")
        if uncompressed_bytes != declared_uncompressed_bytes:
            raise ValueError(f"manifest partition expanded-byte mismatch: {stored_path}")
        if first_source_url != str(descriptor.get("first_source_url") or ""):
            raise ValueError(f"manifest partition first URL mismatch: {stored_path}")
        if last_source_url != str(descriptor.get("last_source_url") or ""):
            raise ValueError(f"manifest partition last URL mismatch: {stored_path}")
        if (
            schema_version == "real_document_fetch_scale_cohort_v4"
            and previous_group_key == group_key
            and previous_group_last_url
            and first_source_url <= previous_group_last_url
        ):
            raise ValueError(f"manifest cross-shard URL order mismatch: {stored_path}")
        previous_descriptor_key = descriptor_key
        previous_group_key = group_key
        previous_group_last_url = last_source_url
        total_rows += rows
    if total_rows != declared_total_rows:
        raise ValueError("partitioned manifest total row mismatch")


def stage_manifest_rows(
    *, conn: sqlite3.Connection, manifest: dict[str, Any], manifest_path: Path
) -> dict[str, Any]:
    conn.execute("PRAGMA temp_store=FILE")
    conn.execute(
        """
        CREATE TEMP TABLE expected_manifest_rows (
          source_url TEXT PRIMARY KEY,
          source_pipeline_id TEXT NOT NULL,
          source_id TEXT NOT NULL,
          source_host TEXT NOT NULL,
          document_kind TEXT NOT NULL,
          validation_mode TEXT NOT NULL,
          size_decile INTEGER NOT NULL,
          queue_priority INTEGER NOT NULL,
          expected_bytes INTEGER NOT NULL,
          expected_content_sha256 TEXT NOT NULL,
          captured_raw_path TEXT NOT NULL,
          payload_json TEXT NOT NULL
        ) WITHOUT ROWID
        """
    )
    schema_version = str(manifest.get("schema_version") or "")
    legacy_projections: list[dict[str, Any]] = []
    streaming_digest = hashlib.sha256()
    execution_digest = hashlib.sha256()
    host_counts: dict[str, int] = {}
    mode_counts: dict[str, int] = {}
    host_ranks: dict[str, int] = {}
    batch: list[tuple[Any, ...]] = []
    row_count = 0
    insert_sql = """
      INSERT INTO expected_manifest_rows (
        source_url, source_pipeline_id, source_id, source_host, document_kind,
        validation_mode, size_decile, expected_bytes, expected_content_sha256,
        queue_priority, captured_raw_path, payload_json
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    for row in iter_manifest_rows(manifest=manifest, manifest_path=manifest_path):
        payload = row.get("payload") or {}
        if not isinstance(payload, dict):
            raise ValueError("manifest payload is not an object")
        source_url = str(row.get("source_url") or "")
        source_host = str(row.get("source_host") or "")
        validation_mode = str(row.get("validation_mode") or "")
        if not source_url or not source_host or not validation_mode:
            raise ValueError("manifest row lacks URL, host, or validation mode")
        projection = semantic_projection([row])[0]
        if schema_version == "real_document_fetch_scale_cohort_v2":
            legacy_projections.append(projection)
        streaming_digest.update(canonical_projection_line(row))
        host_counts[source_host] = host_counts.get(source_host, 0) + 1
        mode_counts[validation_mode] = mode_counts.get(validation_mode, 0) + 1
        if schema_version == "real_document_fetch_scale_cohort_v4":
            if source_host == "www.parlamentodeandalucia.es":
                validate_exact_provenance_reference_edges(payload)
            queue_priority = -host_ranks.get(source_host, 0)
            host_ranks[source_host] = host_ranks.get(source_host, 0) + 1
        else:
            queue_priority = int(row.get("queue_priority") or 0)
        if schema_version == "real_document_fetch_scale_cohort_v4":
            execution_digest.update(
                execution_contract_line(row, queue_priority=queue_priority)
            )
        batch.append(
            (
                source_url,
                str(row.get("source_pipeline_id") or ""),
                str(row.get("source_id") or ""),
                source_host,
                str(row.get("document_kind") or ""),
                validation_mode,
                int(row.get("size_decile") or 0),
                int(row.get("expected_bytes") or 0),
                str(row.get("expected_content_sha256") or ""),
                queue_priority,
                str(row.get("captured_raw_path") or ""),
                json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
            )
        )
        row_count += 1
        if len(batch) >= 1000:
            conn.executemany(insert_sql, batch)
            batch.clear()
    if batch:
        conn.executemany(insert_sql, batch)
    cohort_sha256 = (
        semantic_sha256(legacy_projections)
        if schema_version == "real_document_fetch_scale_cohort_v2"
        else streaming_digest.hexdigest()
    )
    return {
        "rows": row_count,
        "hosts": dict(sorted(host_counts.items())),
        "validation_modes": dict(sorted(mode_counts.items())),
        "cohort_semantic_sha256": cohort_sha256,
        "cohort_selection_sha256": streaming_digest.hexdigest(),
        "execution_contract_sha256": (
            execution_digest.hexdigest()
            if schema_version == "real_document_fetch_scale_cohort_v4"
            else ""
        ),
        "validation_storage": "sqlite_temp_file",
    }


def validate_fresh_contract(
    *, row: dict[str, Any], content_type: str, fresh_path: Path
) -> list[str]:
    errors: list[str] = []
    source_url = str(row.get("source_url") or "")
    payload = row.get("payload") or {}
    contract = payload.get("validation_contract") or {}
    parsed = urlparse(source_url)
    if not isinstance(contract, dict):
        return [f"validation contract is not an object: {source_url}"]
    if contract.get("require_https") is True and parsed.scheme != "https":
        errors.append(f"validation contract HTTPS mismatch: {source_url}")
    expected_host = str(contract.get("expected_host") or "").lower()
    if expected_host and (parsed.hostname or "").lower() != expected_host:
        errors.append(f"validation contract host mismatch: {source_url}")
    minimum_bytes = int(contract.get("minimum_bytes") or 0)
    if fresh_path.stat().st_size < minimum_bytes:
        errors.append(f"validation contract minimum bytes mismatch: {source_url}")
    allowed_types = contract.get("allowed_content_types")
    if allowed_types is not None:
        normalized_type = content_type.split(";", 1)[0].strip().lower()
        normalized_allowed = {
            str(value).strip().lower() for value in allowed_types if str(value).strip()
        }
        if normalized_type not in normalized_allowed:
            errors.append(f"validation contract content type mismatch: {source_url}")
    required = contract.get("required_ascii_casefolded") or []
    forbidden = contract.get("forbidden_ascii_casefolded") or []
    if required or forbidden:
        with fresh_path.open("rb") as handle:
            body = handle.read(1024 * 1024).lower()
        for marker in required:
            try:
                marker_bytes = str(marker).encode("ascii").lower()
            except UnicodeEncodeError:
                errors.append(f"validation contract marker is not ASCII: {source_url}")
                continue
            if marker_bytes not in body:
                errors.append(f"required semantic marker missing: {source_url}")
        for marker in forbidden:
            try:
                marker_bytes = str(marker).encode("ascii").lower()
            except UnicodeEncodeError:
                errors.append(f"validation contract marker is not ASCII: {source_url}")
                continue
            if marker_bytes in body:
                errors.append(f"forbidden block marker present: {source_url}")
    return errors


def validate_boe_structure(*, row: dict[str, Any], fresh_path: Path) -> list[str]:
    errors: list[str] = []
    source_url = str(row.get("source_url") or "")
    mode = str(row.get("validation_mode") or "")
    parsed = urlparse(source_url)
    with fresh_path.open("rb") as handle:
        prefix = handle.read(128 * 1024).lstrip()
    if mode == "boe_summary_structure":
        if not re.fullmatch(r"/datosabiertos/api/boe/sumario/\d{8}", parsed.path):
            errors.append(f"BOE summary URL contract mismatch: {source_url}")
        is_json = prefix.startswith(b"{") and b'"sumario"' in prefix
        is_xml = (
            prefix.startswith(b"<?xml")
            and b"<response" in prefix
            and b"<sumario" in prefix
        )
        if not is_json and not is_xml:
            errors.append(f"BOE summary payload contract mismatch: {source_url}")
        return errors
    if mode != "boe_document_identifier":
        return errors
    expected_ids = parse_qs(parsed.query).get("id") or []
    if (
        parsed.path != "/diario_boe/xml.php"
        or len(expected_ids) != 1
        or not re.fullmatch(
            r"BOE-[A-Z]-\d{4}-\d+", expected_ids[0], flags=re.IGNORECASE
        )
    ):
        errors.append(f"BOE document URL contract mismatch: {source_url}")
        return errors
    identifier_match = re.search(
        rb"<identificador>\s*(BOE-[A-Z]-\d{4}-\d+)\s*</identificador>",
        prefix,
        flags=re.IGNORECASE,
    )
    if not prefix.startswith(b"<?xml") or identifier_match is None:
        errors.append(f"BOE document XML contract mismatch: {source_url}")
    elif identifier_match.group(1).decode("ascii").upper() != expected_ids[0].upper():
        errors.append(f"BOE document identifier mismatch: {source_url}")
    return errors


def expected_policy_contract() -> dict[str, Any]:
    return {
        "official_real_documents_only": True,
        "synthetic_or_mock_records_counted": False,
        "official_public_domain_personal_information_retained": True,
        "known_blocked_rows_selected": 0,
        "dynamic_official_html_requires_semantic_contract": True,
        "official_content_revisions_preserved_and_measured": True,
    }


def validate_planning_contract(
    *,
    manifest: dict[str, Any],
    errors: BoundedErrors,
    max_peak_rss_bytes: int = 0,
) -> bool:
    planning = manifest.get("planning") or {}
    before = errors.total
    expected = {
        "schema_version": PLANNER_SCHEMA_VERSION,
        "backend": "disk_backed_sqlite",
        "candidate_deduplication": "sqlite_primary_key",
        "selected_row_iteration": "ordered_sqlite_cursor",
        "source_query_temp_store": "file",
        "queue_insertion": "streamed_executemany",
        "queue_priority": "deterministic_negative_host_rank_db_only",
        "partition_writes": "streamed_bounded_shards",
        "full_cohort_materialized_in_memory": False,
        "partition_members_materialized_in_memory": False,
        "embedded_compatibility_max_rows": MAX_EMBEDDED_ROWS,
        "partition_max_rows": MAX_PARTITION_ROWS,
        "partition_max_uncompressed_bytes": MAX_PARTITION_UNCOMPRESSED_BYTES,
        "output_locking": "sorted_per_target_kernel_flock_v1",
        "output_publication": "journaled_manifest_last_bundle_v1",
        "input_immutability": "sha256_before_after_checkpointed_sqlite_v1",
        "provenance_reference_edges": (
            "exact_db_ref_table_name_pairs_bounded_10000_v1"
        ),
    }
    for key, value in expected.items():
        if planning.get(key) != value:
            errors.append(f"planning.{key} mismatch")
    if int(planning.get("planner_store_bytes") or 0) < 1:
        errors.append("planning.planner_store_bytes is not positive")
    source_snapshot = (manifest.get("inputs") or {}).get(
        "source_sqlite_snapshot"
    ) or {}
    if source_snapshot != {
        "transaction": "read_only_snapshot",
        "wal_required_empty": True,
    }:
        errors.append("inputs.source_sqlite_snapshot mismatch")
    peak_rss_bytes = int(planning.get("peak_rss_bytes") or 0)
    if peak_rss_bytes < 1:
        errors.append("planning.peak_rss_bytes is not positive")
    if max_peak_rss_bytes > 0 and peak_rss_bytes > max_peak_rss_bytes:
        errors.append("planning.peak_rss_bytes exceeds configured bound")
    return errors.total == before


def validate_execution_contract(
    *, manifest: dict[str, Any], staged_sha256: str, errors: BoundedErrors
) -> bool:
    contract = manifest.get("execution_contract") or {}
    before = errors.total
    if contract.get("schema_version") != "real_document_fetch_execution_contract_v1":
        errors.append("execution_contract.schema_version mismatch")
    if contract.get("includes_payload_and_queue_priority") is not True:
        errors.append("execution_contract payload/priority scope mismatch")
    if str(contract.get("sha256") or "") != staged_sha256:
        errors.append("execution_contract.sha256 mismatch")
    return errors.total == before


def validate_selection_identity(
    *, manifest: dict[str, Any], staged_sha256: str, errors: BoundedErrors
) -> bool:
    before = errors.total
    if (
        manifest.get("selection_identity_contract")
        != "sha256_concatenated_canonical_projection_jsonl_v1"
    ):
        errors.append("selection_identity_contract mismatch")
    if str(manifest.get("cohort_selection_sha256") or "") != staged_sha256:
        errors.append("cohort_selection_sha256 mismatch")
    return errors.total == before


def prior_content_type(*, mode: str, path: Path) -> str:
    if mode == "boe_summary_structure":
        with path.open("rb") as handle:
            prefix = handle.read(64).lstrip()
        return "application/json" if prefix.startswith(b"{") else "application/xml"
    if mode == "boe_document_identifier":
        return "application/xml"
    if mode == "parliament_html_semantic":
        return "text/html"
    if mode == "parliament_pdf_signature":
        return "application/pdf"
    return "application/octet-stream"


def validate_preflight(
    *,
    manifest_path: Path,
    db_path: Path,
    max_planner_peak_rss_bytes: int = 0,
) -> dict[str, Any]:
    started = time.monotonic()
    cpu_started = time.process_time()
    errors = BoundedErrors()
    manifest = read_json(manifest_path)
    manifest_schema = str(manifest.get("schema_version") or "")
    if manifest_schema not in {
        "real_document_fetch_scale_cohort_v3",
        "real_document_fetch_scale_cohort_v4",
    }:
        errors.append("preflight requires partitioned cohort schema v3 or v4")
    planning_contract_validated = False
    execution_contract_validated = False
    selection_identity_validated = False
    if manifest_schema == "real_document_fetch_scale_cohort_v4":
        planning_contract_validated = validate_planning_contract(
            manifest=manifest,
            errors=errors,
            max_peak_rss_bytes=max_planner_peak_rss_bytes,
        )
    policy = manifest.get("policy") or {}
    expected_policy = expected_policy_contract()
    for key, expected in expected_policy.items():
        if policy.get(key) != expected:
            errors.append(f"policy.{key} mismatch")
    selection = manifest.get("selection") or {}
    conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        stage = stage_manifest_rows(
            conn=conn,
            manifest=manifest,
            manifest_path=manifest_path,
        )
        if manifest_schema == "real_document_fetch_scale_cohort_v4":
            selection_identity_validated = validate_selection_identity(
                manifest=manifest,
                staged_sha256=str(stage["cohort_selection_sha256"]),
                errors=errors,
            )
            execution_contract_validated = validate_execution_contract(
                manifest=manifest,
                staged_sha256=str(stage["execution_contract_sha256"]),
                errors=errors,
            )
        row_count = int(stage["rows"])
        expected_host_rows = {
            str(key): int(value)
            for key, value in (selection.get("hosts") or {}).items()
        }
        expected_mode_rows = {
            str(key): int(value)
            for key, value in (selection.get("validation_modes") or {}).items()
        }
        if row_count != int(selection.get("rows") or 0):
            errors.append("manifest row count mismatch")
        if stage["hosts"] != expected_host_rows:
            errors.append("manifest host allocation mismatch")
        if stage["validation_modes"] != expected_mode_rows:
            errors.append("manifest validation-mode allocation mismatch")
        if manifest.get("cohort_semantic_sha256") != stage["cohort_semantic_sha256"]:
            errors.append("cohort semantic hash mismatch")
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        queue_state_rows = conn.execute(
            """
            SELECT state, COUNT(*) AS rows, SUM(attempts) AS attempts
            FROM pipeline_work_items
            WHERE pipeline_id = ?
            GROUP BY state
            ORDER BY state
            """,
            (str(manifest.get("pipeline_id") or ""),),
        ).fetchall()
        queue_states = {
            str(row["state"]): {
                "rows": int(row["rows"] or 0),
                "attempts": int(row["attempts"] or 0),
            }
            for row in queue_state_rows
        }
        fetch_rows = int(
            conn.execute("SELECT COUNT(*) FROM document_fetches").fetchone()[0]
        )
        document_rows = int(
            conn.execute("SELECT COUNT(*) FROM text_documents").fetchone()[0]
        )
        prior_files_rehashed = 0
        prior_bytes_reconciled = 0
        source_contract_rows = 0
        real_policy_rows = 0
        public_information_rows = 0
        blocked_host_rows = 0
        for row in conn.execute(
            """
            SELECT e.*, q.item_key AS q_item_key, q.state AS q_state,
                   q.priority AS q_priority,
                   q.attempts AS q_attempts
            FROM expected_manifest_rows e
            LEFT JOIN pipeline_work_items q
              ON q.pipeline_id = ? AND q.item_key = e.source_url
            ORDER BY e.source_url
            """,
            (str(manifest.get("pipeline_id") or ""),),
        ):
            source_url = str(row["source_url"])
            payload = json.loads(str(row["payload_json"]))
            expected = {
                "source_url": source_url,
                "validation_mode": str(row["validation_mode"]),
                "payload": payload,
            }
            if row["q_item_key"] is None or str(row["q_state"]) != "pending":
                errors.append(f"queue row is not pristine pending: {source_url}")
            if int(row["q_attempts"] or 0) != 0:
                errors.append(f"queue row has preflight attempts: {source_url}")
            if int(row["q_priority"] or 0) != int(row["queue_priority"] or 0):
                errors.append(f"queue priority mismatch: {source_url}")
            if payload.get("synthetic_or_mock_records_counted") is False:
                real_policy_rows += 1
            else:
                errors.append(f"real-data policy mismatch: {source_url}")
            if payload.get("official_public_domain_personal_information_retained") is True:
                public_information_rows += 1
            else:
                errors.append(f"public-information policy mismatch: {source_url}")
            host = (urlparse(source_url).hostname or "").lower()
            if host in {
                "contrataciondelestado.es",
                "parlamentodenavarra.es",
                "www.congreso.es",
                "www.senado.es",
            }:
                blocked_host_rows += 1
            prior_path = safe_repo_file(str(row["captured_raw_path"] or ""))
            if not prior_path.is_file():
                errors.append(f"prior captured file missing: {source_url}")
                continue
            actual_bytes = prior_path.stat().st_size
            actual_sha256 = sha256_path(prior_path)
            prior_files_rehashed += 1
            prior_bytes_reconciled += actual_bytes
            if actual_bytes != int(row["expected_bytes"] or 0):
                errors.append(f"prior captured file byte mismatch: {source_url}")
            if actual_sha256 != str(row["expected_content_sha256"] or ""):
                errors.append(f"prior captured file hash mismatch: {source_url}")
            mode = str(row["validation_mode"])
            contract_errors = validate_fresh_contract(
                row=expected,
                content_type=prior_content_type(mode=mode, path=prior_path),
                fresh_path=prior_path,
            )
            if mode.startswith("boe_"):
                contract_errors.extend(
                    validate_boe_structure(row=expected, fresh_path=prior_path)
                )
            source_contract_rows += 1
            errors.extend(contract_errors)
    finally:
        conn.close()
    if integrity != "ok" or foreign_keys:
        errors.append("cohort database integrity or foreign keys failed")
    if queue_states != {"pending": {"rows": row_count, "attempts": 0}}:
        errors.append("prepared queue is not exactly pristine pending")
    if fetch_rows != 0 or document_rows != 0:
        errors.append("prepared cohort database already contains fetch outputs")
    if prior_files_rehashed != row_count:
        errors.append("prior file rehash count mismatch")
    if prior_bytes_reconciled != int(selection.get("expected_prior_bytes") or 0):
        errors.append("prior byte total mismatch")
    if source_contract_rows != row_count:
        errors.append("prior source-contract row count mismatch")
    if real_policy_rows != row_count or public_information_rows != row_count:
        errors.append("real/public-information policy row count mismatch")
    if blocked_host_rows:
        errors.append("known blocked host rows were selected")
    row_manifest = manifest.get("row_manifest") or {}
    partitions = row_manifest.get("partitions") or []
    compressed_bytes = sum(int(row.get("bytes") or 0) for row in partitions)
    uncompressed_bytes = sum(
        int(row.get("uncompressed_bytes") or 0) for row in partitions
    )
    return {
        "schema_version": "real_document_fetch_scale_cohort_preflight_validation_v1",
        "status": "ok" if not errors else "error",
        "cohort_id": str(manifest.get("cohort_id") or ""),
        "cohort_semantic_sha256": str(stage["cohort_semantic_sha256"]),
        "policy": expected_policy,
        "planning": manifest.get("planning") or {},
        "inputs": {
            "manifest": {
                "path": repo_path(manifest_path),
                "bytes": manifest_path.stat().st_size,
                "sha256": sha256_path(manifest_path),
            },
            "database": {
                "path": repo_path(db_path),
                "bytes": db_path.stat().st_size,
                "sha256": sha256_path(db_path),
            },
        },
        "checks": {
            "cohort_rows": row_count,
            "manifest_partitions": len(partitions),
            "manifest_compressed_bytes": compressed_bytes,
            "manifest_uncompressed_bytes": uncompressed_bytes,
            "manifest_validation_storage": str(stage["validation_storage"]),
            "disk_planning_contract_validated": planning_contract_validated,
            "execution_contract_validated": execution_contract_validated,
            "selection_identity_validated": selection_identity_validated,
            "prior_files_rehashed": prior_files_rehashed,
            "prior_bytes_reconciled": prior_bytes_reconciled,
            "source_contract_rows": source_contract_rows,
            "real_policy_rows": real_policy_rows,
            "official_public_information_rows": public_information_rows,
            "known_blocked_host_rows": blocked_host_rows,
            "queue_states": queue_states,
            "database_integrity": integrity,
            "foreign_key_violations": len(foreign_keys),
            "preexisting_fetch_rows": fetch_rows,
            "preexisting_document_rows": document_rows,
        },
        "hosts": expected_host_rows,
        "validation_modes": expected_mode_rows,
        "validation_performance": validation_performance(
            started=started,
            cpu_started=cpu_started,
        ),
        "error_count": errors.total,
        "errors_truncated": errors.total > len(errors.samples),
        "errors": errors.samples,
    }


def validate(
    *,
    manifest_path: Path,
    run_report_path: Path,
    db_path: Path,
    raw_root: Path,
    max_planner_peak_rss_bytes: int = 0,
) -> dict[str, Any]:
    validation_started = time.monotonic()
    validation_cpu_started = time.process_time()
    errors = BoundedErrors()
    manifest = read_json(manifest_path)
    run_report = read_json(run_report_path)
    manifest_schema = str(manifest.get("schema_version") or "")
    if manifest_schema not in {
        "real_document_fetch_scale_cohort_v2",
        "real_document_fetch_scale_cohort_v3",
        "real_document_fetch_scale_cohort_v4",
    }:
        errors.append("manifest schema mismatch")
    planning_contract_validated = False
    execution_contract_validated = False
    selection_identity_validated = False
    if manifest_schema == "real_document_fetch_scale_cohort_v4":
        planning_contract_validated = validate_planning_contract(
            manifest=manifest,
            errors=errors,
            max_peak_rss_bytes=max_planner_peak_rss_bytes,
        )
    if run_report.get("schema_version") != "document_fetch_queue_run_v3":
        errors.append("run report schema mismatch")
    if run_report.get("status") != "ok":
        errors.append("run status is not ok")
    expected_policy = expected_policy_contract()
    policy = manifest.get("policy") or {}
    for key, expected in expected_policy.items():
        if policy.get(key) != expected:
            errors.append(f"policy.{key} mismatch")

    selection = manifest.get("selection") or {}
    conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        stage = stage_manifest_rows(
            conn=conn,
            manifest=manifest,
            manifest_path=manifest_path,
        )
        if manifest_schema == "real_document_fetch_scale_cohort_v4":
            selection_identity_validated = validate_selection_identity(
                manifest=manifest,
                staged_sha256=str(stage["cohort_selection_sha256"]),
                errors=errors,
            )
            execution_contract_validated = validate_execution_contract(
                manifest=manifest,
                staged_sha256=str(stage["execution_contract_sha256"]),
                errors=errors,
            )
        row_count = int(stage["rows"])
        cohort_semantic_sha256 = str(stage["cohort_semantic_sha256"])
        expected_host_rows = {
            str(key): int(value)
            for key, value in (selection.get("hosts") or {}).items()
        }
        expected_mode_rows = {
            str(key): int(value)
            for key, value in (selection.get("validation_modes") or {}).items()
        }
        if row_count != int(selection.get("rows") or 0):
            errors.append("manifest row count mismatch")
        if stage["hosts"] != expected_host_rows:
            errors.append("manifest host allocation mismatch")
        if stage["validation_modes"] != expected_mode_rows:
            errors.append("manifest validation-mode allocation mismatch")
        if manifest_schema == "real_document_fetch_scale_cohort_v2":
            if expected_host_rows != EXPECTED_HOST_ROWS:
                errors.append("legacy manifest host allocation mismatch")
            if expected_mode_rows != EXPECTED_MODES:
                errors.append("legacy manifest validation-mode allocation mismatch")
        if manifest.get("cohort_semantic_sha256") != cohort_semantic_sha256:
            errors.append("cohort semantic hash mismatch")
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        queue_row_count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM pipeline_work_items
                WHERE pipeline_id = ?
                """,
                (str(manifest.get("pipeline_id") or ""),),
            ).fetchone()[0]
        )
        fetch_row_count = int(
            conn.execute("SELECT COUNT(*) FROM document_fetches").fetchone()[0]
        )
        document_row_count = int(
            conn.execute("SELECT COUNT(*) FROM text_documents").fetchone()[0]
        )
        joined_rows = conn.execute(
            """
            SELECT
              e.*,
              q.item_key AS q_item_key,
              q.state AS q_state,
              q.priority AS q_priority,
              q.attempts AS q_attempts,
              q.last_error AS q_last_error,
              f.doc_url AS f_doc_url,
              f.source_id AS f_source_id,
              f.fetched_ok AS f_fetched_ok,
              f.last_http_status AS f_last_http_status,
              f.content_type AS f_content_type,
              f.content_sha256 AS f_content_sha256,
              f.bytes AS f_bytes,
              f.raw_path AS f_raw_path,
              d.source_url AS d_source_url,
              d.source_id AS d_source_id,
              d.content_type AS d_content_type,
              d.content_sha256 AS d_content_sha256,
              d.bytes AS d_bytes,
              d.raw_path AS d_raw_path
            FROM expected_manifest_rows e
            LEFT JOIN pipeline_work_items q
              ON q.pipeline_id = ? AND q.item_key = e.source_url
            LEFT JOIN document_fetches f ON f.doc_url = e.source_url
            LEFT JOIN text_documents d ON d.source_url = e.source_url
            ORDER BY e.source_url
            """
            ,
            (str(manifest.get("pipeline_id") or ""),),
        )
        prior_files_rehashed = 0
        fresh_files_rehashed = 0
        fresh_bytes = 0
        exact_matches = 0
        drifted_rows = 0
        source_contract_rows = 0
        source_contract_parity = True
        prior_capture_integrity = True
        fresh_content_integrity = True
        host_actual_rows: dict[str, int] = {}
        host_actual_bytes: dict[str, int] = {}
        drift_by_kind: dict[str, int] = {}
        for joined in joined_rows:
            source_url = str(joined["source_url"])
            expected = {
                "source_url": source_url,
                "source_id": str(joined["source_id"]),
                "source_host": str(joined["source_host"]),
                "document_kind": str(joined["document_kind"]),
                "validation_mode": str(joined["validation_mode"]),
                "expected_bytes": int(joined["expected_bytes"]),
                "expected_content_sha256": str(
                    joined["expected_content_sha256"]
                ),
                "captured_raw_path": str(joined["captured_raw_path"]),
                "payload": json.loads(str(joined["payload_json"])),
            }
            if joined["q_item_key"] is None or str(joined["q_state"]) != "succeeded":
                errors.append(f"queue row not succeeded: {source_url}")
                fresh_content_integrity = False
                continue
            if int(joined["q_priority"] or 0) != int(
                joined["queue_priority"] or 0
            ):
                errors.append(f"queue priority mismatch: {source_url}")
            if joined["f_doc_url"] is None or joined["d_source_url"] is None:
                errors.append(f"fetch or text document row missing: {source_url}")
                fresh_content_integrity = False
                continue
            if (
                int(joined["f_fetched_ok"] or 0) != 1
                or int(joined["f_last_http_status"] or 0) != 200
            ):
                errors.append(f"fetch terminal status mismatch: {source_url}")
                fresh_content_integrity = False
            for label, prefix in (("fetch", "f"), ("document", "d")):
                if str(joined[f"{prefix}_source_id"] or "") != expected["source_id"]:
                    errors.append(f"{label} source mismatch: {source_url}")
                if str(joined[f"{prefix}_content_sha256"] or "") != str(
                    joined["f_content_sha256"] or ""
                ):
                    errors.append(f"{label} fresh hash inconsistency: {source_url}")
                    fresh_content_integrity = False
                if int(joined[f"{prefix}_bytes"] or 0) != int(
                    joined["f_bytes"] or 0
                ):
                    errors.append(f"{label} fresh byte inconsistency: {source_url}")
                    fresh_content_integrity = False
            try:
                prior_path = safe_repo_file(expected["captured_raw_path"])
                fresh_path = safe_fresh_path(
                    raw_root, str(joined["f_raw_path"] or "")
                )
            except ValueError as exc:
                errors.append(str(exc))
                prior_capture_integrity = False
                fresh_content_integrity = False
                continue
            expected_bytes = int(expected["expected_bytes"])
            expected_sha256 = str(expected["expected_content_sha256"])
            if not prior_path.is_file():
                errors.append(f"prior captured file missing: {source_url}")
                prior_capture_integrity = False
                continue
            prior_files_rehashed += 1
            if (
                prior_path.stat().st_size != expected_bytes
                or sha256_path(prior_path) != expected_sha256
            ):
                errors.append(f"prior captured file drift: {source_url}")
                prior_capture_integrity = False
            if not fresh_path.is_file():
                errors.append(f"fresh raw file missing: {source_url}")
                fresh_content_integrity = False
                continue
            actual_bytes = fresh_path.stat().st_size
            actual_sha256 = sha256_path(fresh_path)
            fresh_files_rehashed += 1
            fresh_bytes += actual_bytes
            host = str(expected["source_host"])
            host_actual_rows[host] = host_actual_rows.get(host, 0) + 1
            host_actual_bytes[host] = host_actual_bytes.get(host, 0) + actual_bytes
            if actual_sha256 != str(joined["f_content_sha256"] or ""):
                errors.append(f"fresh raw hash differs from database: {source_url}")
                fresh_content_integrity = False
            if actual_bytes != int(joined["f_bytes"] or 0):
                errors.append(f"fresh raw bytes differ from database: {source_url}")
                fresh_content_integrity = False
            if actual_sha256 == expected_sha256 and actual_bytes == expected_bytes:
                exact_matches += 1
            else:
                drifted_rows += 1
                kind = str(expected["document_kind"] or "unknown")
                drift_by_kind[kind] = drift_by_kind.get(kind, 0) + 1
            mode = str(expected["validation_mode"])
            if mode not in expected_mode_rows:
                errors.append(f"unknown validation mode: {source_url}")
                continue
            source_contract_rows += 1
            contract_errors = validate_fresh_contract(
                row=expected,
                content_type=str(joined["f_content_type"] or ""),
                fresh_path=fresh_path,
            )
            if mode.startswith("boe_"):
                contract_errors.extend(
                    validate_boe_structure(row=expected, fresh_path=fresh_path)
                )
            if contract_errors:
                source_contract_parity = False
                errors.extend(contract_errors)
    finally:
        conn.close()

    totals = run_report.get("totals") or {}
    performance = run_report.get("performance") or {}
    run_host_slos = run_report.get("host_slos") or []
    durable_telemetry = run_report.get("durable_request_telemetry") or {}
    uses_durable_request_telemetry = (
        durable_telemetry.get("storage")
        == "sqlite_document_fetch_request_events_v1"
    )
    if uses_durable_request_telemetry:
        host_slos = [
            {
                "host": row.get("host"),
                "requests_started": row.get("network_requests_started"),
                "successes": row.get("succeeded_attempts"),
                "failures": row.get("failed_attempts"),
                "bytes_received": row.get("bytes_received"),
            }
            for row in durable_telemetry.get("hosts") or []
        ]
    else:
        host_slos = run_host_slos
    requests_started = sum(int(row.get("requests_started") or 0) for row in host_slos)
    host_successes = sum(int(row.get("successes") or 0) for row in host_slos)
    host_failures = sum(int(row.get("failures") or 0) for row in host_slos)
    host_bytes = sum(int(row.get("bytes_received") or 0) for row in host_slos)
    host_request_counts = {
        str(row.get("host") or ""): int(row.get("requests_started") or 0)
        for row in host_slos
    }
    host_success_counts = {
        str(row.get("host") or ""): int(row.get("successes") or 0)
        for row in host_slos
    }
    succeeded = row_count if uses_durable_request_telemetry else int(
        totals.get("succeeded") or 0
    )
    if (
        uses_durable_request_telemetry
        and host_successes != row_count
    ) or (
        not uses_durable_request_telemetry
        and (
            int(totals.get("claimed") or 0) != row_count
            or succeeded != row_count
        )
    ):
        errors.append("run claimed/succeeded totals do not match cohort")
    if int(totals.get("dead") or 0) != 0:
        errors.append("fresh cohort has retries or dead rows")
    if (
        int(durable_telemetry.get("bytes_received") or 0)
        if uses_durable_request_telemetry
        else int(totals.get("bytes_received") or 0)
    ) != fresh_bytes:
        errors.append("run bytes do not match fresh files")
    if not uses_durable_request_telemetry and requests_started != int(
        performance.get("network_requests_started") or 0
    ):
        errors.append("network request telemetry does not reconcile")
    host_policy = run_report.get("host_policy") or {}
    explicit_host_budgets = {
        str(key): int(value)
        for key, value in (host_policy.get("request_budgets") or {}).items()
    }
    explicit_host_budgets_enforced = (
        host_policy.get("require_explicit_host_budget") is True
    )
    if explicit_host_budgets_enforced:
        if set(explicit_host_budgets) != set(expected_host_rows):
            errors.append("explicit host request budget coverage mismatch")
        for host, requests in host_request_counts.items():
            if requests > int(explicit_host_budgets.get(host) or 0):
                errors.append(f"host request budget exceeded: {host}")
    if run_report.get("budget_exhausted_hosts") or run_report.get("unbudgeted_hosts"):
        errors.append("host request budget blocked the acquisition")
    if uses_durable_request_telemetry:
        network_request_upper_bound = int(
            durable_telemetry.get("queue_attempt_events") or 0
        ) * int(host_policy.get("download_attempts_per_queue_attempt") or 0)
    else:
        network_request_upper_bound = int(
            performance.get("network_request_upper_bound") or 0
        )
    if (
        requests_started < row_count
        or requests_started > network_request_upper_bound
        or host_successes != row_count
        or host_failures != requests_started - host_successes
    ):
        errors.append("host request outcomes exceed the bounded retry envelope")
    if host_failures > max(1, row_count // 50):
        errors.append("network-attempt failure rate exceeds two percent")
    if host_bytes != fresh_bytes:
        errors.append("host bytes do not reconcile with fresh files")
    if host_success_counts != expected_host_rows:
        errors.append("host success allocation mismatch")
    if host_actual_rows != expected_host_rows:
        errors.append("fresh-file host allocation mismatch")
    if int(host_policy.get("per_host_min_interval_ms") or 0) < 500:
        errors.append("per-host minimum interval is below 500ms")
    for row in run_host_slos:
        if int(row.get("peak_inflight") or 0) > int(
            host_policy.get("per_host_workers") or 0
        ):
            errors.append(f"host peak inflight exceeds limit: {row.get('host')}")
    for key in ("elapsed_seconds", "cpu_seconds", "peak_rss_bytes"):
        if float(performance.get(key) or 0) <= 0:
            errors.append(f"performance.{key} is not positive")
    if integrity != "ok" or foreign_keys:
        errors.append("cohort database integrity or foreign keys failed")
    if (
        queue_row_count != row_count
        or fetch_row_count != row_count
        or document_row_count != row_count
    ):
        errors.append("cohort database row totals do not reconcile")
    if source_contract_rows != row_count:
        errors.append("source-contract validation row count mismatch")

    denominator = succeeded or 1
    return {
        "schema_version": (
            "real_document_fetch_scale_cohort_validation_v4"
            if manifest_schema == "real_document_fetch_scale_cohort_v4"
            else (
                "real_document_fetch_scale_cohort_validation_v3"
                if manifest_schema == "real_document_fetch_scale_cohort_v3"
                else "real_document_fetch_scale_cohort_validation_v2"
            )
        ),
        "status": "ok" if not errors else "error",
        "cohort_id": str(manifest.get("cohort_id") or ""),
        "cohort_semantic_sha256": cohort_semantic_sha256,
        "policy": expected_policy,
        "planning": manifest.get("planning") or {},
        "inputs": {
            "manifest": {
                "path": repo_path(manifest_path),
                "bytes": manifest_path.stat().st_size,
                "sha256": sha256_path(manifest_path),
            },
            "run_report": {
                "path": repo_path(run_report_path),
                "bytes": run_report_path.stat().st_size,
                "sha256": sha256_path(run_report_path),
            },
            "database": {
                "path": repo_path(db_path),
                "bytes": db_path.stat().st_size,
                "sha256": sha256_path(db_path),
            },
        },
        "checks": {
            "cohort_rows": row_count,
            "manifest_validation_storage": str(stage["validation_storage"]),
            "disk_planning_contract_validated": planning_contract_validated,
            "execution_contract_validated": execution_contract_validated,
            "selection_identity_validated": selection_identity_validated,
            "manifest_partitions": len(
                ((manifest.get("row_manifest") or {}).get("partitions") or [])
            ),
            "prior_files_rehashed": prior_files_rehashed,
            "fresh_files_rehashed": fresh_files_rehashed,
            "fresh_bytes_reconciled": fresh_bytes,
            "network_requests_started": requests_started,
            "network_request_telemetry_storage": (
                "sqlite_document_fetch_request_events_v1"
                if uses_durable_request_telemetry
                else "run_report_host_slos"
            ),
            "host_request_budget_policy": (
                "explicit_cli_host_budgets"
                if explicit_host_budgets_enforced
                else "manifest_rows_times_download_attempt_bound"
            ),
            "network_retry_attempts": max(0, requests_started - row_count),
            "network_request_upper_bound": network_request_upper_bound,
            "host_successes": host_successes,
            "host_failures": host_failures,
            "database_integrity": integrity,
            "foreign_key_violations": len(foreign_keys),
            "prior_capture_byte_hash_integrity": prior_capture_integrity,
            "source_contract_rows": source_contract_rows,
            "fresh_source_contract_parity": source_contract_parity,
            "fresh_content_hash_self_consistency": fresh_content_integrity,
        },
        "content_drift": {
            "exact_matches": exact_matches,
            "drifted_rows": drifted_rows,
            "drift_by_document_kind": dict(sorted(drift_by_kind.items())),
            "drift_is_allowed_when_fresh_source_contract_passes": True,
        },
        "hosts": {
            host: {
                "rows": host_actual_rows.get(host, 0),
                "bytes": host_actual_bytes.get(host, 0),
                "network_requests": host_request_counts.get(host, 0),
                "network_successes": host_success_counts.get(host, 0),
            }
            for host in sorted(expected_host_rows)
        },
        "per_1000_succeeded": {
            "network_requests_started": round(requests_started * 1000 / denominator, 6),
            "bytes_received": round(fresh_bytes * 1000 / denominator, 6),
            "elapsed_seconds": round(
                float(performance.get("elapsed_seconds") or 0) * 1000 / denominator,
                6,
            ),
            "cpu_seconds": round(
                float(performance.get("cpu_seconds") or 0) * 1000 / denominator,
                6,
            ),
            "failures": round(host_failures * 1000 / denominator, 6),
        },
        "performance": {
            "elapsed_seconds": float(performance.get("elapsed_seconds") or 0),
            "cpu_seconds": float(performance.get("cpu_seconds") or 0),
            "peak_rss_bytes": int(performance.get("peak_rss_bytes") or 0),
            "workers": int(run_report.get("workers") or 0),
            "per_host_workers": int(run_report.get("per_host_workers") or 0),
            "per_host_min_interval_ms": int(
                host_policy.get("per_host_min_interval_ms") or 0
            ),
            "validation": validation_performance(
                started=validation_started,
                cpu_started=validation_cpu_started,
            ),
        },
        "error_count": errors.total,
        "errors_truncated": errors.total > len(errors.samples),
        "errors": errors.samples,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("acquisition", "preflight"), default="acquisition"
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--run-report", default="")
    parser.add_argument("--db", required=True)
    parser.add_argument("--raw-root", default="")
    parser.add_argument("--max-planner-peak-rss-mb", type=float, default=0.0)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        max_planner_peak_rss_bytes = int(
            max(0.0, float(args.max_planner_peak_rss_mb)) * 1024 * 1024
        )
        if args.mode == "preflight":
            report = validate_preflight(
                manifest_path=Path(args.manifest),
                db_path=Path(args.db),
                max_planner_peak_rss_bytes=max_planner_peak_rss_bytes,
            )
        else:
            if not args.run_report or not args.raw_root:
                raise ValueError(
                    "acquisition mode requires --run-report and --raw-root"
                )
            report = validate(
                manifest_path=Path(args.manifest),
                run_report_path=Path(args.run_report),
                db_path=Path(args.db),
                raw_root=Path(args.raw_root),
                max_planner_peak_rss_bytes=max_planner_peak_rss_bytes,
            )
        write_json_atomic(Path(args.out), report)
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"ERROR real document fetch scale cohort validation: {exc}")
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
