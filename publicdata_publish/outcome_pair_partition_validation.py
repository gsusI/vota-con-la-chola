"""Independent full-corpus validation for C2B discovery-pair Parquet files.

This validator is deliberately fail closed.  It never delegates source-row
projection to the producer; the complete v2 implementation is kept in this
module so producer and validator defects cannot mask one another.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import stat
import time
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from .outcome_pair_identity_safety import (
    FileIdentity,
    bound_regular_file,
    exact_regular_inventory,
)
from .outcome_pair_partitions import (
    ACTION_YEAR_PARTITION_FIELD,
    BUILD_DESCRIPTOR_SCHEMA,
    CANONICAL_COMPRESSION,
    CANONICAL_COMPRESSION_LEVEL,
    CANONICAL_MAX_FILE_ROWS,
    CANONICAL_PYARROW_VERSION,
    CANONICAL_ROW_GROUP_ROWS,
    EXPECTED_MAX_PARTITION_ROWS,
    EXPECTED_MEMBER_COMPONENT_ROOT_SHA256,
    EXPECTED_MIN_PARTITION_ROWS,
    EXPECTED_PAIR_FILES,
    EXPECTED_PAIR_PARTITIONS,
    EXPECTED_SOURCE_CONTRACT_DATE,
    EXPECTED_SOURCE_COUNTS,
    IDENTITY_COMPANION_DIRECTORY,
    IDENTITY_COMPANION_VALIDATION_PATH,
    LANE,
    MAXIMUM_BATCH_ROWS,
    MAXIMUM_CHECKPOINT_BYTES,
    MAXIMUM_IDENTITY_PARQUET_BYTES,
    MAXIMUM_JSON_BYTES,
    MAXIMUM_PACKAGE_DEPTH,
    MAXIMUM_PACKAGE_DIRECTORIES,
    MAXIMUM_PACKAGE_FILES,
    MAXIMUM_PACKAGE_PATH_BYTES,
    MAXIMUM_PAIR_BATCH_BYTES,
    MAXIMUM_PAIR_COLUMN_UNCOMPRESSED_BYTES,
    MAXIMUM_PAIR_FILE_BYTES,
    MAXIMUM_PAIR_PARQUET_BYTES,
    MAXIMUM_PAIR_ROW_GROUP_UNCOMPRESSED_BYTES,
    MAXIMUM_PAIR_STRING_BYTES,
    MAXIMUM_PEAK_RSS_MB,
    MAXIMUM_PORTABLE_PARQUET_BYTES,
    MEMBER_PROJECTION_FIELDS,
    MINIMUM_REAL_PAIR_ROWS,
    OUTCOME_PAIR_CONTRACT,
    PARTITION_CHECKPOINT_SCHEMA,
    TRANSFORMER_VERSION,
    _canonical_sha256,
    _partition_checkpoint_root,
    load_identity_companion_proof,
    load_identity_resolver_audit,
    load_source_proof,
)
from .semantic_contracts import (
    MANIFEST_SCHEMA_VERSION,
    peak_rss_mb,
    private_token_findings,
)

VALIDATION_SCHEMA_VERSION = "outcome_pair_discovery_partition_validation_v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PARQUET_CREATED_BY = f"parquet-cpp-arrow version {CANONICAL_PYARROW_VERSION}"
MAX_JSON_DEPTH = 32
MAX_JSON_CONTAINER_ITEMS = 2_000
MAX_JSON_NODES = 250_000
MAX_JSON_STRING_BYTES = 1 * 1024**2

POLICY_FIELDS: dict[str, str | int] = {
    "evidence_level": "L0",
    "link_state": "internal_discovery_pair",
    "association_assessment": "not_assessed",
    "causal_assessment": "not_assessed",
    "effect_estimate_state": "not_computed",
    "political_merit_or_blame": "not_assessed",
    "corruption_assessment": "not_assessed",
    "ranking_eligible": 0,
    "publication_eligible": 0,
}

EXPECTED_MATERIALIZATION_CHECKS = {
    "source_validation_passed": True,
    "source_artifacts_unchanged": True,
    "exact_source_pair_count": True,
    "minimum_real_rows": True,
    "source_url_complete": True,
    "indicator_source_url_complete": True,
    "official_identity_reference_complete": True,
    "official_public_names_retained_at_source": True,
    "member_votes_retained_at_source": True,
    "identity_companion_validation_passed": True,
    "exact_member_votes_bundled": True,
    "exact_official_names_bundled": True,
    "exact_action_projections_bundled": True,
    "identity_companion_inventory_exact": True,
    "no_private_tokens": True,
    "association_claims_zero": True,
    "causal_claims_zero": True,
    "effect_estimates_zero": True,
    "ranking_eligible_rows_zero": True,
    "publication_eligible_rows_zero": True,
    "bounded_file_rows": True,
    "bounded_peak_rss": True,
    "hard_resource_contract": True,
    "exact_canonical_pair_layout": True,
    "hard_byte_contract": True,
    "downstream_hive_dataset_compatible": True,
}

EXPECTED_PROMOTION_CHECKS = {
    "local_package_gate": True,
    "full_l1_candidate_materialization": False,
    "real_human_review": False,
    "durable_remote_origin": False,
    "isolated_remote_restore": False,
    "publication_authorized": False,
}

EXPECTED_MANIFEST_KEYS = {
    "schema_version",
    "generated_at",
    "contract_date",
    "lane",
    "transformer_version",
    "schema",
    "schema_sha256",
    "partition_contract",
    "datasets",
    "incremental_contract",
    "restart_contract",
    "source",
    "identity_lineage",
    "policy",
    "totals",
    "semantic_root_sha256",
    "physical_inventory_root_sha256",
    "portable_package_root_sha256",
    "manifest_root_sha256",
    "checks",
    "local_package_gate_passed",
    "independent_validation_passed",
    "promotion_checks",
    "promotion_gate_passed",
    "publication_status",
    "performance",
    "partitions",
    "limitations",
}

PARTITION_KEYS = {
    "partition_id",
    "values",
    "relative_dir",
    "rows",
    "min_id",
    "max_id",
    "source_url_rows",
    "indicator_source_url_rows",
    "official_identity_reference_rows",
    "private_token_findings",
    "publication_eligible_rows",
    "ranking_eligible_rows",
    "input_sha256",
    "files",
    "materialization",
}
FILE_META_KEYS = {"path", "rows", "bytes", "sha256", "min_id", "max_id"}

# This SQL and the projection below intentionally live in the validator.  They
# must not be imported from the producer, otherwise one shared defect could make
# both sides agree on a false artifact.
SOURCE_PAIR_SQL = """
SELECT
  p.pair_plan_id,
  p.pipeline_key,
  p.base_partition_key,
  p.partition_key,
  p.pair_bucket,
  p.action_plan_pk,
  p.series_plan_pk,
  p.action_year,
  p.strict_pre_latest_date,
  p.strict_post_earliest_date,
  p.evidence_level,
  p.link_state,
  p.association_assessment,
  p.causal_assessment,
  p.effect_estimate_state,
  p.political_merit_or_blame,
  p.corruption_assessment,
  p.ranking_eligible,
  p.publication_eligible,
  p.row_semantic_sha256,
  a.action_id,
  a.action_date,
  a.action_label,
  a.source_id AS action_source_id,
  a.source_record_pk AS action_source_record_pk,
  a.source_record_id AS action_source_record_id,
  a.source_snapshot_date AS action_source_snapshot_date,
  a.official_action_url,
  a.source_page_url AS action_source_page_url,
  a.source_record_content_sha256 AS action_source_record_content_sha256,
  a.member_vote_count,
  a.official_name_count,
  a.participant_projection_sha256,
  s.indicator_series_id,
  s.canonical_key AS indicator_canonical_key,
  s.series_label AS indicator_series_label,
  s.dataset_code,
  s.country_code,
  s.geography_code,
  s.frequency_code,
  s.unit_code,
  s.dimensions_json AS indicator_dimensions_json,
  s.source_id AS indicator_source_id,
  s.source_record_pk AS indicator_source_record_pk,
  s.source_record_id AS indicator_source_record_id,
  s.source_snapshot_date AS indicator_source_snapshot_date,
  s.official_source_url AS indicator_source_url,
  s.source_record_content_sha256 AS indicator_source_record_content_sha256,
  s.origin_capture_sha256 AS indicator_origin_capture_sha256,
  s.observation_count AS indicator_observation_count,
  s.observation_years_json AS indicator_observation_years_json,
  s.observation_projection_sha256 AS indicator_observation_projection_sha256,
  s.first_observation_date,
  s.last_observation_date
FROM outcome_pair_plan_pairs AS p
JOIN outcome_pair_plan_actions AS a
  ON a.pipeline_key = p.pipeline_key
 AND a.action_plan_pk = p.action_plan_pk
JOIN outcome_pair_plan_series AS s
  ON s.pipeline_key = p.pipeline_key
 AND s.series_plan_pk = p.series_plan_pk
WHERE p.pipeline_key = ?
ORDER BY
  p.base_partition_key,
  p.pair_bucket,
  p.action_plan_pk,
  p.series_plan_pk
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _validate_json_shape(value: Any) -> None:
    stack: list[tuple[Any, int]] = [(value, 0)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise ValueError("JSON artifact exceeds its structural bound")
        if isinstance(current, dict):
            if len(current) > MAX_JSON_CONTAINER_ITEMS:
                raise ValueError("JSON object exceeds its item bound")
            stack.extend((item, depth + 1) for item in current.values())
            stack.extend((key, depth + 1) for key in current)
        elif isinstance(current, list):
            if len(current) > MAX_JSON_CONTAINER_ITEMS:
                raise ValueError("JSON list exceeds its item bound")
            stack.extend((item, depth + 1) for item in current)
        elif isinstance(current, str):
            if len(current.encode("utf-8")) > MAX_JSON_STRING_BYTES:
                raise ValueError("JSON string exceeds its byte bound")
        elif isinstance(current, float) and not math.isfinite(current):
            raise ValueError("JSON contains a non-finite number")
        elif current is not None and type(current) not in {bool, int, float}:
            raise TypeError("JSON contains an unsupported value")


def _decode_json_object(payload: bytes, *, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid UTF-8 JSON artifact: {label}") from exc
    if not isinstance(parsed, dict):
        raise TypeError(f"JSON root must be an object: {label}")
    _validate_json_shape(parsed)
    return parsed


def _file_fact(
    path: Path,
    *,
    max_bytes: int | None = None,
    database: bool = False,
) -> tuple[dict[str, Any], FileIdentity]:
    with bound_regular_file(path, database=database) as bound:
        if bound.identity.size < 1:
            raise ValueError(f"required artifact is empty: {Path(path).name}")
        if max_bytes is not None and bound.identity.size > max_bytes:
            raise ValueError(f"artifact exceeds its byte contract: {Path(path).name}")
        digest = bound.sha256()
        identity = bound.identity
    return {"bytes": identity.size, "sha256": digest}, identity


def _load_json_object(
    path: Path,
    *,
    max_bytes: int = MAXIMUM_JSON_BYTES,
) -> tuple[dict[str, Any], dict[str, Any], FileIdentity]:
    with bound_regular_file(path) as bound:
        if bound.identity.size < 1 or bound.identity.size > max_bytes:
            raise ValueError(
                f"JSON artifact exceeds its byte contract: {Path(path).name}"
            )
        payload = bound.read_bytes(max_bytes=max_bytes)
        fact = {
            "bytes": bound.identity.size,
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        identity = bound.identity
        parsed = _decode_json_object(payload, label=Path(path).name)
    return parsed, fact, identity


def _rehash_exact(
    path: Path,
    *,
    initial_fact: dict[str, Any],
    initial_identity: FileIdentity,
    max_bytes: int | None = None,
    database: bool = False,
) -> bool:
    fact, identity = _file_fact(
        path,
        max_bytes=max_bytes,
        database=database,
    )
    return fact == initial_fact and identity == initial_identity


def _complete_file_inventory(
    root: Path,
    *,
    max_files: int = MAXIMUM_PACKAGE_FILES,
    max_directories: int = MAXIMUM_PACKAGE_DIRECTORIES,
    max_depth: int = MAXIMUM_PACKAGE_DEPTH,
    max_path_bytes: int = MAXIMUM_PACKAGE_PATH_BYTES,
) -> tuple[set[str], set[str], bool]:
    """Stream the exact inventory while bounding every attacker-sized set."""

    for label, value, hard_maximum in (
        ("files", max_files, MAXIMUM_PACKAGE_FILES),
        ("directories", max_directories, MAXIMUM_PACKAGE_DIRECTORIES),
        ("depth", max_depth, MAXIMUM_PACKAGE_DEPTH),
        ("path bytes", max_path_bytes, MAXIMUM_PACKAGE_PATH_BYTES),
    ):
        if type(value) is not int or value < 1 or value > hard_maximum:
            raise ValueError(f"package inventory {label} bound is invalid")
    root = Path(root)
    files: set[str] = set()
    directories: set[str] = set()
    file_inodes: set[tuple[int, int]] = set()
    directory_inodes: set[tuple[int, int]] = set()
    unsafe = False
    try:
        root_stat = root.lstat()
    except (FileNotFoundError, OSError):
        return files, directories, True
    if root.is_symlink() or not stat.S_ISDIR(root_stat.st_mode):
        return files, directories, True
    directory_inodes.add((int(root_stat.st_dev), int(root_stat.st_ino)))
    pending: list[tuple[Path, int]] = [(root, 0)]
    try:
        while pending:
            current, depth = pending.pop()
            with os.scandir(current) as entries:
                for entry in entries:
                    path = current / entry.name
                    path_stat = entry.stat(follow_symlinks=False)
                    relative = path.relative_to(root).as_posix()
                    child_depth = depth + 1
                    if (
                        child_depth > max_depth
                        or len(relative.encode("utf-8")) > max_path_bytes
                    ):
                        raise ValueError(
                            "package inventory path exceeds depth or byte bound"
                        )
                    inode = (int(path_stat.st_dev), int(path_stat.st_ino))
                    if stat.S_ISDIR(path_stat.st_mode) and not entry.is_symlink():
                        if inode in directory_inodes:
                            raise ValueError("package directory inode is aliased")
                        if len(directories) >= max_directories:
                            raise ValueError(
                                "package directory inventory exceeds hard bound"
                            )
                        directory_inodes.add(inode)
                        directories.add(relative)
                        pending.append((path, child_depth))
                        continue
                    if (
                        not stat.S_ISREG(path_stat.st_mode)
                        or entry.is_symlink()
                        or path_stat.st_nlink != 1
                        or inode in file_inodes
                    ):
                        unsafe = True
                        continue
                    if len(files) >= max_files:
                        raise ValueError("package file inventory exceeds hard bound")
                    file_inodes.add(inode)
                    files.add(relative)
    except OSError:
        unsafe = True
    return files, directories, unsafe


def _expected_parent_directories(paths: set[str]) -> set[str]:
    directories: set[str] = set()
    for relative in paths:
        parent = PurePosixPath(relative).parent
        while parent.as_posix() != ".":
            directories.add(parent.as_posix())
            parent = parent.parent
    return directories


def _canonical_relative(value: Any) -> str:
    if type(value) is not str or not value or "\\" in value or "\x00" in value:
        raise ValueError("package path is not a canonical relative path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("package path is unsafe")
    return pure.as_posix()


def _package_child(root: Path, relative: Any) -> Path:
    canonical = _canonical_relative(relative)
    candidate = root.joinpath(*PurePosixPath(canonical).parts)
    try:
        candidate.resolve(strict=False).relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise ValueError("package path escapes the package root") from exc
    return candidate


def _safe_component(value: str) -> str:
    output = [
        char if char.isalnum() or char in {"-", "_", "."} else "_"
        for char in value.strip()
    ]
    return "".join(output).strip("._") or "unknown"


def _partition_relative_dir(
    contract_date: str,
    key: tuple[int, str, str],
) -> str:
    year, dataset_code, geography_code = key
    return PurePosixPath(
        f"lane={LANE}",
        f"contract_date={_safe_component(contract_date)}",
        "action_source=senado_votaciones",
        f"{ACTION_YEAR_PARTITION_FIELD}={year}",
        "indicator_source=eurostat_sdmx",
        f"dataset={_safe_component(dataset_code)}",
        f"geography={_safe_component(geography_code)}",
    ).as_posix()


def _exact_int(value: Any, *, label: str, minimum: int | None = None) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be an exact JSON integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} is below its hard lower bound")
    return value


def _is_sha256(value: Any) -> bool:
    return type(value) is str and bool(SHA256_RE.fullmatch(value))


def _validate_pair_parquet_decode_metadata(metadata: Any) -> tuple[int, int]:
    """Reject compressed Parquet metadata that exceeds fixed decode ceilings."""

    maximum_row_group = 0
    maximum_column = 0
    for row_group_index in range(int(metadata.num_row_groups)):
        row_group = metadata.row_group(row_group_index)
        row_group_uncompressed = 0
        for column_index in range(int(row_group.num_columns)):
            column_uncompressed = int(
                row_group.column(column_index).total_uncompressed_size
            )
            if (
                column_uncompressed < 1
                or column_uncompressed > MAXIMUM_PAIR_COLUMN_UNCOMPRESSED_BYTES
            ):
                raise ValueError("pair Parquet column exceeds uncompressed byte bound")
            maximum_column = max(maximum_column, column_uncompressed)
            row_group_uncompressed += column_uncompressed
            if row_group_uncompressed > MAXIMUM_PAIR_ROW_GROUP_UNCOMPRESSED_BYTES:
                raise ValueError(
                    "pair Parquet row group exceeds uncompressed byte bound"
                )
        maximum_row_group = max(maximum_row_group, row_group_uncompressed)
    return maximum_row_group, maximum_column


def _validate_pair_batch_decode(batch: Any) -> int:
    decoded_bytes = int(batch.nbytes)
    if decoded_bytes < 1 or decoded_bytes > MAXIMUM_PAIR_BATCH_BYTES:
        raise ValueError("pair record batch exceeds decoded byte bound")
    return decoded_bytes


def _validate_pair_string_columns(columns: dict[str, list[Any]]) -> int:
    maximum = 0
    string_fields = {
        field["name"]
        for field in OUTCOME_PAIR_CONTRACT.schema
        if field["type"] == "string"
    }
    for name in string_fields:
        for value in columns[name]:
            if type(value) is not str:
                raise TypeError("pair string field is not an exact string")
            encoded_bytes = len(value.encode("utf-8"))
            if encoded_bytes > MAXIMUM_PAIR_STRING_BYTES:
                raise ValueError("pair string exceeds decoded byte bound")
            maximum = max(maximum, encoded_bytes)
    return maximum


def _canonical_json_text(value: Any) -> str:
    parsed = json.loads(
        str(value),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_json_constant,
    )
    return json.dumps(
        parsed,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _official_url(value: Any, *, host: str, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{label} is not an exact official URL")
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise ValueError(f"{label} is malformed") from exc
    if not (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower() == host
        and parsed.username is None
        and parsed.password is None
        and not parsed.fragment
    ):
        raise ValueError(f"{label} is outside the pinned official host")
    return value


def _expected_base_partition(row: Any) -> str:
    return (
        "action_source=senado_votaciones/"
        f"year={int(row['action_year'])}/"
        "indicator_source=eurostat_sdmx/"
        f"dataset={row['dataset_code']}/"
        f"country={row['country_code']}/"
        f"geography={row['geography_code']}"
    )


def _source_pair_row(row: sqlite3.Row) -> dict[str, Any]:
    """Project one pinned SQLite row independently of the producer."""

    base_partition = _expected_base_partition(row)
    if str(row["base_partition_key"]) != base_partition:
        raise ValueError("source pair base partition drifted")
    pair_bucket = str(row["pair_bucket"])
    if str(row["partition_key"]) != f"{base_partition}/bucket={pair_bucket}":
        raise ValueError("source pair bucket partition drifted")
    if str(row["action_source_id"]) != "senado_votaciones":
        raise ValueError("source action identity drifted")
    if str(row["indicator_source_id"]) != "eurostat_sdmx":
        raise ValueError("source indicator identity drifted")
    action_url = _official_url(
        row["official_action_url"],
        host="www.senado.es",
        label="action source URL",
    )
    action_page_url = _official_url(
        row["action_source_page_url"],
        host="www.senado.es",
        label="action page URL",
    )
    indicator_url = _official_url(
        row["indicator_source_url"],
        host="ec.europa.eu",
        label="indicator source URL",
    )
    for field, expected in POLICY_FIELDS.items():
        actual = int(row[field]) if isinstance(expected, int) else str(row[field])
        if actual != expected:
            raise ValueError(f"source no-claim policy drifted: {field}")
    return {
        "pair_plan_id": str(row["pair_plan_id"]),
        "pipeline_key": str(row["pipeline_key"]),
        "base_partition_key": base_partition,
        "partition_key": str(row["partition_key"]),
        "pair_bucket": pair_bucket,
        "action_plan_pk": int(row["action_plan_pk"]),
        "series_plan_pk": int(row["series_plan_pk"]),
        "action_year": int(row["action_year"]),
        "action_id": str(row["action_id"]),
        "action_date": str(row["action_date"]),
        "action_label": str(row["action_label"]),
        "source_id": "senado_votaciones",
        "source_url": action_url,
        "action_source_record_pk": int(row["action_source_record_pk"]),
        "action_source_record_id": str(row["action_source_record_id"]),
        "action_source_snapshot_date": str(row["action_source_snapshot_date"]),
        "action_source_page_url": action_page_url,
        "action_source_record_content_sha256": str(
            row["action_source_record_content_sha256"]
        ),
        "member_vote_count": int(row["member_vote_count"]),
        "official_name_count": int(row["official_name_count"]),
        "participant_projection_sha256": str(row["participant_projection_sha256"]),
        "indicator_series_id": int(row["indicator_series_id"]),
        "indicator_canonical_key": str(row["indicator_canonical_key"]),
        "indicator_series_label": str(row["indicator_series_label"]),
        "dataset_code": str(row["dataset_code"]),
        "country_code": str(row["country_code"]),
        "geography_code": str(row["geography_code"]),
        "frequency_code": str(row["frequency_code"]),
        "unit_code": str(row["unit_code"]),
        "indicator_dimensions_json": _canonical_json_text(
            row["indicator_dimensions_json"]
        ),
        "indicator_source_id": "eurostat_sdmx",
        "indicator_source_record_pk": int(row["indicator_source_record_pk"]),
        "indicator_source_record_id": str(row["indicator_source_record_id"]),
        "indicator_source_snapshot_date": str(row["indicator_source_snapshot_date"]),
        "indicator_source_url": indicator_url,
        "indicator_source_record_content_sha256": str(
            row["indicator_source_record_content_sha256"]
        ),
        "indicator_origin_capture_sha256": str(row["indicator_origin_capture_sha256"]),
        "indicator_observation_count": int(row["indicator_observation_count"]),
        "indicator_observation_years_json": _canonical_json_text(
            row["indicator_observation_years_json"]
        ),
        "indicator_observation_projection_sha256": str(
            row["indicator_observation_projection_sha256"]
        ),
        "first_observation_date": str(row["first_observation_date"]),
        "last_observation_date": str(row["last_observation_date"]),
        "strict_pre_latest_date": str(row["strict_pre_latest_date"]),
        "strict_post_earliest_date": str(row["strict_post_earliest_date"]),
        **POLICY_FIELDS,
        "row_semantic_sha256": str(row["row_semantic_sha256"]),
        "public_identity_model": "normalized_reference_to_member_vote_corpus",
    }


class _IndependentSourceRows(Iterator[dict[str, Any]]):
    """Read the pinned source under one read transaction with plan proof."""

    def __init__(
        self,
        db_path: Path,
        *,
        pipeline_key: str,
        expected_identity: FileIdentity,
    ) -> None:
        self._bound_context = bound_regular_file(Path(db_path), database=True)
        self._bound = self._bound_context.__enter__()
        self._connection: sqlite3.Connection | None = None
        self._closed = False
        try:
            if self._bound.identity != expected_identity:
                raise RuntimeError("source database inode differs from initial proof")
            uri = f"file:/dev/fd/{self._bound.handle.fileno()}?mode=ro&immutable=1"
            self._connection = sqlite3.connect(
                uri,
                uri=True,
                isolation_level=None,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA query_only=ON")
            self._connection.execute("PRAGMA trusted_schema=OFF")
            self._connection.execute("BEGIN")
            pipelines = self._connection.execute(
                "SELECT DISTINCT pipeline_key FROM outcome_pair_plan_pairs "
                "ORDER BY pipeline_key LIMIT 2"
            ).fetchall()
            if len(pipelines) != 1 or str(pipelines[0][0]) != pipeline_key:
                raise ValueError("source must contain exactly the pinned pipeline")
            plan_rows = self._connection.execute(
                "EXPLAIN QUERY PLAN " + SOURCE_PAIR_SQL,
                (pipeline_key,),
            ).fetchall()
            self.plan = tuple(str(row[3]) for row in plan_rows)
            upper_plan = tuple(detail.upper() for detail in self.plan)
            if not any(
                "IDX_OUTCOME_PAIR_PLAN_PAIRS_PARTITION" in detail
                for detail in upper_plan
            ):
                raise ValueError("source parity query does not use the pinned index")
            if any("TEMP B-TREE" in detail for detail in upper_plan):
                raise ValueError("source parity query spills ordering to a TEMP B-TREE")
            self._cursor = self._connection.execute(
                SOURCE_PAIR_SQL,
                (pipeline_key,),
            )
        except BaseException:
            self.close()
            raise

    def __iter__(self) -> _IndependentSourceRows:
        return self

    def __next__(self) -> dict[str, Any]:
        if self._closed:
            raise StopIteration
        row = self._cursor.fetchone()
        if row is None:
            self.close()
            raise StopIteration
        return _source_pair_row(row)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._connection is not None:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            self._connection.close()
        self._bound_context.__exit__(None, None, None)


def _expected_physical_contract() -> dict[str, Any]:
    return {
        "strategy": "semantic_hive_compatible_v2",
        "semantic_keys": [
            "contract_date",
            "action_year",
            "dataset_code",
            "geography_code",
        ],
        "hive_path_keys": [
            "lane",
            "contract_date",
            "action_source",
            ACTION_YEAR_PARTITION_FIELD,
            "indicator_source",
            "dataset",
            "geography",
        ],
        "hive_field_map": {
            ACTION_YEAR_PARTITION_FIELD: "action_year",
            "dataset": "dataset_code",
            "geography": "geography_code",
        },
        "ordering": [
            "base_partition_key",
            "pair_bucket",
            "action_plan_pk",
            "series_plan_pk",
        ],
        "row_group_rows": CANONICAL_ROW_GROUP_ROWS,
        "max_file_rows": CANONICAL_MAX_FILE_ROWS,
        "compression": CANONICAL_COMPRESSION,
        "writer": {
            "library": "pyarrow",
            "library_version": CANONICAL_PYARROW_VERSION,
            "parquet_format_version": "2.6",
            "data_page_version": "1.0",
            "compression_level": CANONICAL_COMPRESSION_LEVEL,
            "use_dictionary": True,
            "write_statistics": True,
            "physical_replay": "byte_exact_only_when_checksum_reused",
            "semantic_replay": "canonical_row_root_exact",
        },
    }


def _expected_policy() -> dict[str, Any]:
    return {
        "official_real_records_only": True,
        "synthetic_or_mock_records_forbidden": True,
        "official_public_domain_personal_information_retained": True,
        "identity_storage": (
            "bundled_normalized_exact_member_vote_companion_without_pair_duplication"
        ),
        "identity_companion": "bundled_exact_public_member_vote_dimension",
        "evidence_level": "L0",
        "link_state": "internal_discovery_pair",
        "association_assessment": "not_assessed",
        "causal_assessment": "not_assessed",
        "effect_estimate_state": "not_computed",
        "political_merit_or_blame": "not_assessed",
        "corruption_assessment": "not_assessed",
        "publication_eligible_rows": 0,
    }


def _expected_identity_lineage(
    *,
    identity_companion_proof: dict[str, Any],
    identity_resolver_proof: dict[str, Any],
) -> dict[str, Any]:
    return {
        "storage_model": "bundled_normalized_exact_member_vote_identity_companion",
        "authoritative_source_table": "parl_vote_member_votes",
        "source_component_root_sha256": EXPECTED_MEMBER_COMPONENT_ROOT_SHA256,
        "source_member_vote_rows": EXPECTED_SOURCE_COUNTS[
            "member_votes_source_resolved"
        ],
        "source_distinct_official_names": EXPECTED_SOURCE_COUNTS[
            "official_names_source_resolved"
        ],
        "join_contract": {
            "pair_fields": ["source_id", "action_id"],
            "identity_companion_fields": ["source_id", "action_id"],
            "cardinality": "one_action_to_many_member_votes",
            "source_table_alias": ("parl_vote_member_votes.vote_event_id -> action_id"),
        },
        "projection_contract": {
            "version": "outcome_pair_plan_action_participant_projection_v1",
            "ordering": ["action_id", "member_vote_id"],
            "fields": MEMBER_PROJECTION_FIELDS,
            "row_encoding": "canonical_json_utf8_length_prefixed_u64_be",
            "root_encoding": ("canonical_json_of_contract_row_count_and_stream_sha256"),
            "row_reference_field": "participant_projection_sha256",
        },
        "public_name_policy": "retain_exact_official_member_name",
        "portable_exact_source_identity_dimension": True,
        "exact_source_participant_projection_bundled": True,
        "identity_companion_path": IDENTITY_COMPANION_DIRECTORY,
        "identity_companion_manifest_root_sha256": identity_companion_proof[
            "manifest_root_sha256"
        ],
        "identity_companion_semantic_root_sha256": identity_companion_proof[
            "package_semantic_root_sha256"
        ],
        "identity_companion_member_rows_root_sha256": identity_companion_proof["roots"][
            "member_rows_root_sha256"
        ],
        "identity_companion_official_names_root_sha256": (
            identity_companion_proof["roots"]["official_names_root_sha256"]
        ),
        "identity_companion_action_rows_root_sha256": identity_companion_proof["roots"][
            "action_rows_root_sha256"
        ],
        "identity_companion_member_vote_rows": identity_companion_proof["counts"][
            "member_vote_rows"
        ],
        "identity_companion_distinct_official_names": identity_companion_proof[
            "counts"
        ]["distinct_official_names"],
        "identity_companion_actions": identity_companion_proof["counts"]["actions"],
        "durable_remote_identity_origin": False,
        "durable_action_locator_available": True,
        "resolver_audit_path": "control/identity-resolver-audit.json",
        "resolver_audit_sha256": identity_resolver_proof["sha256"],
        "resolver_action_resolution_root_sha256": identity_resolver_proof["roots"][
            "action_resolution_root_sha256"
        ],
        "resolver_count_mismatch_root_sha256": identity_resolver_proof["roots"][
            "count_mismatch_root_sha256"
        ],
        "resolver_member_vote_rows": identity_resolver_proof["counts"][
            "resolver_member_votes"
        ],
        "resolver_distinct_official_names": identity_resolver_proof["counts"][
            "resolver_distinct_official_names"
        ],
        "durable_action_locator_registry": (
            "docs/etl/real-corpus-registry.json#member_votes"
        ),
        "durable_action_locator_manifest": (
            "etl/data/published/member-vote-shard-manifest-latest.json"
        ),
        "secondary_action_locator_limitation": (
            "All action IDs resolve, but 64 action member counts differ from the "
            "pinned C2B source; use the bundled exact identity companion for "
            "participant resolution."
        ),
    }


def _expected_source_metadata(
    *,
    source_db_path: Path,
    source_manifest_path: Path,
    source_validation_path: Path,
    identity_source_db_path: Path,
    identity_config_path: Path,
    source_proof: dict[str, Any],
    identity_resolver_proof: dict[str, Any],
    identity_companion_proof: dict[str, Any],
) -> dict[str, Any]:
    return {
        "database_file": source_db_path.name,
        "database_bytes": source_proof["database_bytes"],
        "database_sha256": source_proof["database_sha256"],
        "source_manifest_file": source_manifest_path.name,
        "source_manifest_sha256": source_proof["manifest_sha256"],
        "source_validation_file": source_validation_path.name,
        "source_validation_sha256": source_proof["validation_sha256"],
        "source_manifest_root_sha256": source_proof["manifest_root_sha256"],
        "source_semantic_root_sha256": source_proof["semantic_root_sha256"],
        "pipeline_key": source_proof["pipeline_key"],
        "contract_date": source_proof["contract_date"],
        "identity_resolver_audit_file": "control/identity-resolver-audit.json",
        "identity_resolver_audit_sha256": identity_resolver_proof["sha256"],
        "identity_companion_path": IDENTITY_COMPANION_DIRECTORY,
        "identity_companion_manifest_file": (
            f"{IDENTITY_COMPANION_DIRECTORY}/manifest.json"
        ),
        "identity_companion_manifest_sha256": identity_companion_proof[
            "manifest_sha256"
        ],
        "identity_companion_manifest_root_sha256": identity_companion_proof[
            "manifest_root_sha256"
        ],
        "identity_companion_validation_file": IDENTITY_COMPANION_VALIDATION_PATH,
        "identity_companion_validation_sha256": identity_companion_proof[
            "validation_sha256"
        ],
        "identity_companion_semantic_root_sha256": identity_companion_proof[
            "package_semantic_root_sha256"
        ],
        "identity_companion_inventory_root_sha256": identity_companion_proof[
            "inventory_root_sha256"
        ],
        "identity_source_database_file": identity_source_db_path.name,
        "identity_source_database_sha256": identity_companion_proof[
            "source_database_sha256"
        ],
        "identity_config_file": identity_config_path.name,
        "identity_config_sha256": identity_companion_proof["config_sha256"],
    }


def _validate_pair_dataset_interface(
    *,
    root: Path,
    manifest_dataset: Any,
    partitions: list[dict[str, Any]],
    expected_rows: int,
) -> dict[str, Any]:
    import pyarrow.dataset as ds  # type: ignore

    if not isinstance(manifest_dataset, dict):
        raise TypeError("manifest pair dataset descriptor must be an object")
    if manifest_dataset.get("path") != f"lane={LANE}":
        raise ValueError("manifest pair dataset root drifted")
    dataset_root = _package_child(root, manifest_dataset["path"])
    dataset = ds.dataset(dataset_root, format="parquet", partitioning="hive")
    required_fields = {
        *OUTCOME_PAIR_CONTRACT.columns,
        "contract_date",
        "action_source",
        ACTION_YEAR_PARTITION_FIELD,
        "indicator_source",
        "dataset",
        "geography",
    }
    if not required_fields.issubset(set(dataset.schema.names)):
        raise ValueError("ordinary Hive dataset omits declared fields")
    fragments = list(dataset.get_fragments())
    if len(fragments) != EXPECTED_PAIR_FILES:
        raise ValueError("ordinary Hive dataset fragment count is not exact")
    counted = int(dataset.count_rows())
    if counted != expected_rows:
        raise ValueError("ordinary Hive dataset row count is not exact")
    probes: list[dict[str, Any]] = []
    for index in sorted({0, len(partitions) // 2, len(partitions) - 1}):
        partition = partitions[index]
        values = partition["values"]
        expression = (
            (ds.field(ACTION_YEAR_PARTITION_FIELD) == values["action_year"])
            & (ds.field("dataset") == values["dataset_code"])
            & (ds.field("geography") == values["geography_code"])
        )
        count = int(dataset.count_rows(filter=expression))
        if count != partition["rows"]:
            raise ValueError("ordinary Hive representative filter is not exact")
        probes.append({"partition_id": partition["partition_id"], "rows": count})
    expected = {
        "path": f"lane={LANE}",
        "format": "parquet",
        "partitioning": "hive",
        "rows": counted,
        "action_year_partition_field": ACTION_YEAR_PARTITION_FIELD,
        "probes": probes,
    }
    if manifest_dataset != expected:
        raise ValueError("manifest pair dataset descriptor differs from real scan")
    return expected


def _next_or_none(iterator: Iterator[dict[str, Any]] | None) -> dict[str, Any] | None:
    """Advance an optional iterator once without hiding non-exhaustion errors."""

    if iterator is None:
        return None
    try:
        return next(iterator)
    except StopIteration:
        return None


def validate_outcome_pair_partitions(
    *,
    root: Path,
    manifest_path: Path | None = None,
    source_db_path: Path | None = None,
    source_manifest_path: Path | None = None,
    source_validation_path: Path | None = None,
    identity_source_db_path: Path,
    identity_config_path: Path,
    batch_rows: int = 5_000,
    min_rows: int = 1_000_000,
    max_peak_rss_mb: float = 1024.0,
    require_source_parity: bool = True,
) -> dict[str, Any]:
    """Validate every real v2 package row, file, control, and source artifact."""

    try:
        import pyarrow as pa  # type: ignore
        import pyarrow.parquet as pq  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pyarrow is required; install the project parquet extra"
        ) from exc
    if pa.__version__ != CANONICAL_PYARROW_VERSION:
        raise RuntimeError(
            "validator requires the exact canonical pyarrow 20.0.0 runtime"
        )
    if type(batch_rows) is not int or not 1 <= batch_rows <= MAXIMUM_BATCH_ROWS:
        raise ValueError("batch_rows exceeds the hard scale resource contract")
    if (
        type(min_rows) is not int
        or min_rows < MINIMUM_REAL_PAIR_ROWS
        or min_rows > EXPECTED_SOURCE_COUNTS["pairs"]
    ):
        raise ValueError(
            "minimum real-row gate is outside the pinned real-row contract"
        )
    if (
        type(max_peak_rss_mb) not in {int, float}
        or not math.isfinite(max_peak_rss_mb)
        or max_peak_rss_mb <= 0
        or max_peak_rss_mb > MAXIMUM_PEAK_RSS_MB
    ):
        raise ValueError("maximum peak RSS exceeds the hard scale resource contract")
    if require_source_parity is not True:
        raise ValueError("exact source parity is mandatory for the v2 contract")

    source_args = (source_db_path, source_manifest_path, source_validation_path)
    if any(value is None for value in source_args):
        raise ValueError("all pinned source artifacts are mandatory")
    assert source_db_path is not None
    assert source_manifest_path is not None
    assert source_validation_path is not None
    root = Path(root)
    source_db_path = Path(source_db_path)
    source_manifest_path = Path(source_manifest_path)
    source_validation_path = Path(source_validation_path)
    identity_source_db_path = Path(identity_source_db_path)
    identity_config_path = Path(identity_config_path)
    manifest_path = Path(manifest_path) if manifest_path else root / "manifest.json"
    started = time.monotonic()

    initial_files, initial_directories, unsafe_inventory = _complete_file_inventory(
        root,
        max_files=MAXIMUM_PACKAGE_FILES,
        max_directories=MAXIMUM_PACKAGE_DIRECTORIES,
        max_depth=MAXIMUM_PACKAGE_DEPTH,
        max_path_bytes=MAXIMUM_PACKAGE_PATH_BYTES,
    )
    if unsafe_inventory:
        raise ValueError("package contains a symlink, hardlink, or special inode")
    root_identity = FileIdentity.from_stat(root.lstat())
    root_manifest_path = root / "manifest.json"
    manifest, manifest_fact, manifest_identity = _load_json_object(
        root_manifest_path,
        max_bytes=MAXIMUM_JSON_BYTES,
    )
    package_artifacts: dict[str, tuple[dict[str, Any], FileIdentity, int | None]] = {
        "manifest.json": (manifest_fact, manifest_identity, MAXIMUM_JSON_BYTES)
    }
    external_manifest_record: (
        tuple[Path, dict[str, Any], FileIdentity, int | None, bool] | None
    ) = None
    if manifest_path.resolve(strict=True) != root_manifest_path.resolve(strict=True):
        supplied_manifest, supplied_fact, supplied_identity = _load_json_object(
            manifest_path,
            max_bytes=MAXIMUM_JSON_BYTES,
        )
        if supplied_manifest != manifest or supplied_fact != manifest_fact:
            raise ValueError("supplied manifest differs from bundled manifest")
        external_manifest_record = (
            manifest_path,
            supplied_fact,
            supplied_identity,
            MAXIMUM_JSON_BYTES,
            False,
        )
    if set(manifest) != EXPECTED_MANIFEST_KEYS:
        raise ValueError("manifest top-level inventory differs from v2 contract")
    manifest_payload = {
        key: value for key, value in manifest.items() if key != "manifest_root_sha256"
    }
    expected_manifest_root = _canonical_sha256(manifest_payload)
    if (
        not _is_sha256(manifest.get("manifest_root_sha256"))
        or manifest.get("manifest_root_sha256") != expected_manifest_root
    ):
        raise ValueError("manifest self root differs from canonical content")
    contract_date = str(manifest.get("contract_date") or "")
    if contract_date != EXPECTED_SOURCE_CONTRACT_DATE:
        raise ValueError("manifest contract date drifted")
    if manifest.get("partition_contract") != _expected_physical_contract():
        raise ValueError("manifest physical contract differs from canonical v2")

    source_specs: list[tuple[Path, int | None, bool]] = [
        (source_db_path, None, True),
        (source_manifest_path, MAXIMUM_JSON_BYTES, False),
        (source_validation_path, MAXIMUM_JSON_BYTES, False),
        (identity_source_db_path, None, True),
        (identity_config_path, MAXIMUM_JSON_BYTES, False),
        (Path(__file__).with_name("outcome_pair_partitions.py"), None, False),
        (Path(__file__).with_name("semantic_parquet_io.py"), None, False),
    ]
    source_artifacts: dict[
        Path, tuple[dict[str, Any], FileIdentity, int | None, bool]
    ] = {}
    for path, byte_cap, database in source_specs:
        resolved = path.resolve(strict=True)
        if resolved in source_artifacts:
            raise ValueError("source artifact paths must be distinct")
        fact, identity = _file_fact(
            resolved,
            max_bytes=byte_cap,
            database=database,
        )
        source_artifacts[resolved] = (fact, identity, byte_cap, database)
    if external_manifest_record is not None:
        path, fact, identity, cap, database = external_manifest_record
        resolved = path.resolve(strict=True)
        if resolved in source_artifacts:
            raise ValueError("external manifest aliases another source artifact")
        source_artifacts[resolved] = (fact, identity, cap, database)

    source_proof = load_source_proof(
        db_path=source_db_path,
        source_manifest_path=source_manifest_path,
        source_validation_path=source_validation_path,
    )
    if (
        source_artifacts[source_db_path.resolve(strict=True)][0]["sha256"]
        != source_proof["database_sha256"]
        or source_artifacts[source_db_path.resolve(strict=True)][1]
        != source_proof["database_identity"]
        or source_artifacts[source_manifest_path.resolve(strict=True)][0]["sha256"]
        != source_proof["manifest_sha256"]
        or source_artifacts[source_validation_path.resolve(strict=True)][0]["sha256"]
        != source_proof["validation_sha256"]
    ):
        raise ValueError("source proof changed during independent binding")

    bundled_audit_path = root / "control" / "identity-resolver-audit.json"
    audit_fact, audit_identity = _file_fact(
        bundled_audit_path,
        max_bytes=MAXIMUM_JSON_BYTES,
    )
    identity_resolver_proof = load_identity_resolver_audit(bundled_audit_path)
    if audit_fact["sha256"] != identity_resolver_proof["sha256"]:
        raise ValueError("bundled identity audit changed during validation")
    package_artifacts["control/identity-resolver-audit.json"] = (
        audit_fact,
        audit_identity,
        MAXIMUM_JSON_BYTES,
    )

    identity_root = root / IDENTITY_COMPANION_DIRECTORY
    identity_manifest_path = identity_root / "manifest.json"
    identity_validation_path = root / IDENTITY_COMPANION_VALIDATION_PATH
    identity_manifest_fact, identity_manifest_identity = _file_fact(
        identity_manifest_path,
        max_bytes=MAXIMUM_JSON_BYTES,
    )
    identity_validation_fact, identity_validation_identity = _file_fact(
        identity_validation_path,
        max_bytes=MAXIMUM_JSON_BYTES,
    )
    identity_companion_proof = load_identity_companion_proof(
        root=identity_root,
        manifest_path=identity_manifest_path,
        validation_path=identity_validation_path,
        source_db_path=identity_source_db_path,
        config_path=identity_config_path,
        pair_plan_db_path=source_db_path,
        max_peak_rss_mb=float(max_peak_rss_mb),
    )
    if (
        identity_manifest_fact["sha256"] != identity_companion_proof["manifest_sha256"]
        or identity_validation_fact["sha256"]
        != identity_companion_proof["validation_sha256"]
        or source_artifacts[identity_source_db_path.resolve(strict=True)][0]["sha256"]
        != identity_companion_proof["source_database_sha256"]
        or source_artifacts[identity_config_path.resolve(strict=True)][0]["sha256"]
        != identity_companion_proof["config_sha256"]
    ):
        raise ValueError("identity proof changed during independent binding")
    package_artifacts[f"{IDENTITY_COMPANION_DIRECTORY}/manifest.json"] = (
        identity_manifest_fact,
        identity_manifest_identity,
        MAXIMUM_JSON_BYTES,
    )
    package_artifacts[IDENTITY_COMPANION_VALIDATION_PATH] = (
        identity_validation_fact,
        identity_validation_identity,
        MAXIMUM_JSON_BYTES,
    )

    raw_partitions = manifest.get("partitions")
    if not isinstance(raw_partitions, list) or len(raw_partitions) != (
        EXPECTED_PAIR_PARTITIONS
    ):
        raise ValueError("manifest must contain exactly 1,205 pair partitions")
    partitions: list[dict[str, Any]] = []
    expected_pair_paths: set[str] = set()
    expected_checkpoint_paths: set[str] = set()
    seen_partition_ids: set[str] = set()
    previous_sort_key: tuple[int, str, str] | None = None
    declared_pair_bytes = 0
    declared_pair_rows = 0
    declared_partition_rows: list[int] = []
    for raw_partition in raw_partitions:
        if not isinstance(raw_partition, dict) or set(raw_partition) != PARTITION_KEYS:
            raise ValueError("partition metadata keys differ from the v2 contract")
        partition = raw_partition
        values = partition.get("values")
        if not isinstance(values, dict) or set(values) != {
            "contract_date",
            "source_id",
            "action_year",
            "indicator_source_id",
            "dataset_code",
            "geography_code",
        }:
            raise ValueError("partition values differ from the v2 contract")
        year = _exact_int(values["action_year"], label="partition action year")
        dataset_code = values["dataset_code"]
        geography_code = values["geography_code"]
        if (
            type(dataset_code) is not str
            or not dataset_code
            or type(geography_code) is not str
            or not geography_code
        ):
            raise ValueError("partition semantic key is empty or non-string")
        sort_key = (year, dataset_code, geography_code)
        partition_id = f"{year}|{dataset_code}|{geography_code}"
        relative_dir = _partition_relative_dir(contract_date, sort_key)
        if (
            partition.get("partition_id") != partition_id
            or partition_id in seen_partition_ids
            or previous_sort_key is not None
            and sort_key <= previous_sort_key
            or partition.get("relative_dir") != relative_dir
            or values
            != {
                "contract_date": contract_date,
                "source_id": "senado_votaciones",
                "action_year": year,
                "indicator_source_id": "eurostat_sdmx",
                "dataset_code": dataset_code,
                "geography_code": geography_code,
            }
        ):
            raise ValueError("partition identity, path, or ordering is not exact")
        seen_partition_ids.add(partition_id)
        previous_sort_key = sort_key
        rows = _exact_int(partition.get("rows"), label="partition rows", minimum=1)
        if rows > CANONICAL_ROW_GROUP_ROWS:
            raise ValueError("pair partition exceeds one canonical row group")
        declared_pair_rows += rows
        declared_partition_rows.append(rows)
        if not _is_sha256(partition.get("input_sha256")):
            raise ValueError("partition input digest is invalid")
        if partition.get("materialization") not in {
            "rebuilt",
            "reused",
            "checkpoint_resumed",
        }:
            raise ValueError("partition materialization state is invalid")
        for metric in (
            "source_url_rows",
            "indicator_source_url_rows",
            "official_identity_reference_rows",
            "private_token_findings",
            "publication_eligible_rows",
            "ranking_eligible_rows",
        ):
            value = _exact_int(partition.get(metric), label=f"partition {metric}")
            if value < 0 or value > rows:
                raise ValueError("partition metric exceeds its row bound")
        files = partition.get("files")
        if not isinstance(files, list) or len(files) != 1:
            raise ValueError("every pair partition must declare exactly one file")
        file_meta = files[0]
        if not isinstance(file_meta, dict) or set(file_meta) != FILE_META_KEYS:
            raise ValueError("pair file metadata differs from the v2 contract")
        expected_relative = f"{relative_dir}/part-00000.parquet"
        relative = _canonical_relative(file_meta.get("path"))
        file_rows = _exact_int(file_meta.get("rows"), label="pair file rows")
        file_bytes = _exact_int(
            file_meta.get("bytes"),
            label="pair file bytes",
            minimum=1,
        )
        if (
            relative != expected_relative
            or relative in expected_pair_paths
            or file_rows != rows
            or file_rows > CANONICAL_MAX_FILE_ROWS
            or file_bytes > MAXIMUM_PAIR_FILE_BYTES
            or not _is_sha256(file_meta.get("sha256"))
            or type(file_meta.get("min_id")) is not str
            or type(file_meta.get("max_id")) is not str
            or not file_meta["min_id"]
            or not file_meta["max_id"]
            or file_meta["min_id"] > file_meta["max_id"]
        ):
            raise ValueError("pair file metadata violates the canonical layout")
        expected_pair_paths.add(relative)
        declared_pair_bytes += file_bytes
        checkpoint_name = hashlib.sha256(partition_id.encode("utf-8")).hexdigest()
        expected_checkpoint_paths.add(f".checkpoints/{checkpoint_name}.json")
        partitions.append(partition)
    if not (
        len(expected_pair_paths) == EXPECTED_PAIR_FILES
        and declared_pair_rows == EXPECTED_SOURCE_COUNTS["pairs"]
        and min(declared_partition_rows) == EXPECTED_MIN_PARTITION_ROWS
        and max(declared_partition_rows) == EXPECTED_MAX_PARTITION_ROWS
        and declared_pair_bytes <= MAXIMUM_PAIR_PARQUET_BYTES
    ):
        raise ValueError("declared pair partition shape differs from real v2 evidence")

    identity_inventory = identity_companion_proof.get("inventory")
    if not isinstance(identity_inventory, list) or not identity_inventory:
        raise ValueError("identity companion inventory is missing")
    expected_identity_paths: set[str] = set()
    identity_parquet_paths: set[str] = set()
    identity_parquet_bytes = 0
    for raw_meta in identity_inventory:
        if not isinstance(raw_meta, dict) or set(raw_meta) != {
            "path",
            "bytes",
            "sha256",
        }:
            raise ValueError("identity inventory metadata is not exact")
        inner_relative = _canonical_relative(raw_meta.get("path"))
        overall_relative = f"{IDENTITY_COMPANION_DIRECTORY}/{inner_relative}"
        if overall_relative in expected_identity_paths:
            raise ValueError("identity inventory contains a duplicate path")
        expected_identity_paths.add(overall_relative)
        byte_count = _exact_int(
            raw_meta.get("bytes"),
            label="identity artifact bytes",
            minimum=1,
        )
        if not _is_sha256(raw_meta.get("sha256")):
            raise ValueError("identity inventory checksum is invalid")
        cap = MAXIMUM_JSON_BYTES
        if inner_relative.endswith(".parquet"):
            cap = MAXIMUM_IDENTITY_PARQUET_BYTES
            identity_parquet_paths.add(overall_relative)
            identity_parquet_bytes += byte_count
        if byte_count > cap:
            raise ValueError("identity artifact exceeds its byte contract")
        fact, identity = _file_fact(
            _package_child(root, overall_relative),
            max_bytes=cap,
        )
        if fact != {"bytes": byte_count, "sha256": raw_meta["sha256"]}:
            raise ValueError("identity inventory differs from bundled bytes")
        previous = package_artifacts.get(overall_relative)
        if previous is not None and (previous[0] != fact or previous[1] != identity):
            raise ValueError("identity control changed during proof validation")
        package_artifacts[overall_relative] = (fact, identity, cap)
    expected_identity_file_count = int(
        identity_companion_proof["counts"]["member_files"]
    ) + int(identity_companion_proof["counts"]["action_files"])
    if not (
        len(identity_parquet_paths) == expected_identity_file_count
        and identity_parquet_bytes == int(identity_companion_proof["parquet_bytes"])
        and identity_parquet_bytes <= MAXIMUM_IDENTITY_PARQUET_BYTES
        and declared_pair_bytes + identity_parquet_bytes
        <= MAXIMUM_PORTABLE_PARQUET_BYTES
    ):
        raise ValueError("portable identity byte/file contract differs from v2")

    expected_package_files = {
        ".build-descriptor.json",
        "build-checkpoint.json",
        "control/identity-resolver-audit.json",
        IDENTITY_COMPANION_VALIDATION_PATH,
        "manifest.json",
        *expected_pair_paths,
        *expected_checkpoint_paths,
        *expected_identity_paths,
    }
    expected_directories = _expected_parent_directories(expected_package_files)
    if (
        initial_files != expected_package_files
        or initial_directories != expected_directories
    ):
        raise ValueError("package has missing, extra, or empty files/directories")

    expected_schema = OUTCOME_PAIR_CONTRACT.arrow_schema()
    aggregate_digest = hashlib.sha256()
    rows_total = 0
    files_total = 0
    pair_bytes_total = 0
    source_url_rows = 0
    indicator_source_url_rows = 0
    identity_reference_rows = 0
    private_findings = 0
    publication_eligible_rows = 0
    ranking_eligible_rows = 0
    maximum_row_group_uncompressed_bytes = 0
    maximum_column_uncompressed_bytes = 0
    maximum_batch_bytes = 0
    maximum_string_bytes = 0
    action_ids: set[str] = set()
    series_ids: set[int] = set()
    dataset_counts: Counter[str] = Counter()
    partition_reports: list[dict[str, Any]] = []
    source_rows = _IndependentSourceRows(
        source_db_path,
        pipeline_key=str(source_proof["pipeline_key"]),
        expected_identity=source_artifacts[source_db_path.resolve(strict=True)][1],
    )
    source_query_plan = source_rows.plan
    exact_source_parity = True
    source_exhausted_exactly = True
    try:
        for partition in partitions:
            values = partition["values"]
            key = (
                int(values["action_year"]),
                str(values["dataset_code"]),
                str(values["geography_code"]),
            )
            file_meta = partition["files"][0]
            relative = str(file_meta["path"])
            file_path = _package_child(root, relative)
            digest = hashlib.sha256()
            partition_rows = 0
            partition_min_id: str | None = None
            partition_max_id: str | None = None
            partition_source_urls = 0
            partition_indicator_urls = 0
            partition_identity_refs = 0
            partition_private_findings = 0
            partition_publication_rows = 0
            partition_ranking_rows = 0
            previous_row_key: tuple[str, int, int] | None = None
            with bound_regular_file(file_path) as bound:
                if (
                    bound.identity.size < 1
                    or bound.identity.size > MAXIMUM_PAIR_FILE_BYTES
                ):
                    raise ValueError("pair Parquet file exceeds its byte contract")
                actual_sha256 = bound.sha256()
                actual_fact = {
                    "bytes": bound.identity.size,
                    "sha256": actual_sha256,
                }
                if actual_fact != {
                    "bytes": file_meta["bytes"],
                    "sha256": file_meta["sha256"],
                }:
                    raise ValueError("pair Parquet checksum or bytes differ")
                package_artifacts[relative] = (
                    actual_fact,
                    bound.identity,
                    MAXIMUM_PAIR_FILE_BYTES,
                )
                bound.handle.seek(0)
                parquet_file = pq.ParquetFile(bound.handle)
                metadata = parquet_file.metadata
                (
                    observed_row_group_uncompressed,
                    observed_column_uncompressed,
                ) = _validate_pair_parquet_decode_metadata(metadata)
                maximum_row_group_uncompressed_bytes = max(
                    maximum_row_group_uncompressed_bytes,
                    observed_row_group_uncompressed,
                )
                maximum_column_uncompressed_bytes = max(
                    maximum_column_uncompressed_bytes,
                    observed_column_uncompressed,
                )
                if not (
                    parquet_file.schema_arrow.equals(
                        expected_schema,
                        check_metadata=True,
                    )
                    and metadata.format_version == "2.6"
                    and metadata.created_by == PARQUET_CREATED_BY
                    and metadata.num_row_groups == 1
                    and metadata.num_rows == file_meta["rows"]
                ):
                    raise ValueError("pair Parquet physical metadata is not canonical")
                row_group = metadata.row_group(0)
                if row_group.num_rows != file_meta["rows"]:
                    raise ValueError("pair Parquet row-group size is not exact")
                for column_index in range(row_group.num_columns):
                    column = row_group.column(column_index)
                    if (
                        column.compression != "ZSTD"
                        or column.statistics is None
                        or "RLE_DICTIONARY" not in set(column.encodings)
                    ):
                        raise ValueError(
                            "pair Parquet codec/statistics/dictionary contract drifted"
                        )
                for batch in parquet_file.iter_batches(
                    batch_size=batch_rows,
                    use_threads=False,
                ):
                    maximum_batch_bytes = max(
                        maximum_batch_bytes,
                        _validate_pair_batch_decode(batch),
                    )
                    if batch.num_rows < 1 or batch.num_rows > batch_rows:
                        raise RuntimeError("Parquet reader violated the batch bound")
                    columns = {
                        name: batch.column(index).to_pylist()
                        for index, name in enumerate(OUTCOME_PAIR_CONTRACT.columns)
                    }
                    maximum_string_bytes = max(
                        maximum_string_bytes,
                        _validate_pair_string_columns(columns),
                    )
                    for row_index in range(batch.num_rows):
                        row = {
                            name: columns[name][row_index]
                            for name in OUTCOME_PAIR_CONTRACT.columns
                        }
                        pair_id = str(row["pair_plan_id"])
                        order_key = (
                            str(row["pair_bucket"]),
                            int(row["action_plan_pk"]),
                            int(row["series_plan_pk"]),
                        )
                        if (
                            previous_row_key is not None
                            and order_key <= previous_row_key
                        ):
                            raise ValueError("pair rows are not in strict source order")
                        previous_row_key = order_key
                        expected_base = _expected_base_partition(row)
                        if not (
                            int(row["action_year"]) == key[0]
                            and str(row["dataset_code"]) == key[1]
                            and str(row["geography_code"]) == key[2]
                            and str(row["base_partition_key"]) == expected_base
                            and str(row["partition_key"])
                            == f"{expected_base}/bucket={row['pair_bucket']}"
                            and row["source_id"] == "senado_votaciones"
                            and row["indicator_source_id"] == "eurostat_sdmx"
                        ):
                            raise ValueError("pair row is in the wrong Hive partition")
                        for field, expected in POLICY_FIELDS.items():
                            actual = (
                                int(row[field])
                                if isinstance(expected, int)
                                else str(row[field])
                            )
                            if actual != expected:
                                raise ValueError("pair no-claim policy drifted")
                        if not (
                            row["public_identity_model"]
                            == "normalized_reference_to_member_vote_corpus"
                            and int(row["member_vote_count"]) > 0
                            and int(row["official_name_count"]) > 0
                        ):
                            raise ValueError("pair identity reference is incomplete")
                        _official_url(
                            row["source_url"],
                            host="www.senado.es",
                            label="pair source URL",
                        )
                        _official_url(
                            row["action_source_page_url"],
                            host="www.senado.es",
                            label="pair source page URL",
                        )
                        _official_url(
                            row["indicator_source_url"],
                            host="ec.europa.eu",
                            label="pair indicator URL",
                        )
                        for field in (
                            "indicator_dimensions_json",
                            "indicator_observation_years_json",
                        ):
                            if _canonical_json_text(row[field]) != row[field]:
                                raise ValueError("pair canonical JSON field drifted")
                        for field in (
                            "row_semantic_sha256",
                            "action_source_record_content_sha256",
                            "participant_projection_sha256",
                            "indicator_source_record_content_sha256",
                            "indicator_origin_capture_sha256",
                            "indicator_observation_projection_sha256",
                        ):
                            if not _is_sha256(row[field]):
                                raise ValueError("pair SHA-256 field is invalid")
                        findings = private_token_findings(row)
                        if findings:
                            raise ValueError("pair row contains a private token")
                        row_bytes = OUTCOME_PAIR_CONTRACT.canonical_row_bytes(row)
                        expected_source_row = _next_or_none(source_rows)
                        if expected_source_row is None:
                            exact_source_parity = False
                            source_exhausted_exactly = False
                        elif (
                            OUTCOME_PAIR_CONTRACT.canonical_row_bytes(
                                expected_source_row
                            )
                            != row_bytes
                        ):
                            exact_source_parity = False
                        digest.update(row_bytes)
                        partition_rows += 1
                        rows_total += 1
                        if rows_total > EXPECTED_SOURCE_COUNTS["pairs"]:
                            raise ValueError("pair materialization exceeds pinned rows")
                        partition_min_id = (
                            pair_id
                            if partition_min_id is None
                            else min(partition_min_id, pair_id)
                        )
                        partition_max_id = (
                            pair_id
                            if partition_max_id is None
                            else max(partition_max_id, pair_id)
                        )
                        partition_source_urls += 1
                        partition_indicator_urls += 1
                        partition_identity_refs += 1
                        partition_private_findings += findings
                        partition_publication_rows += int(row["publication_eligible"])
                        partition_ranking_rows += int(row["ranking_eligible"])
                        source_url_rows += 1
                        indicator_source_url_rows += 1
                        identity_reference_rows += 1
                        private_findings += findings
                        publication_eligible_rows += int(row["publication_eligible"])
                        ranking_eligible_rows += int(row["ranking_eligible"])
                        action_ids.add(str(row["action_id"]))
                        series_ids.add(int(row["indicator_series_id"]))
                        dataset_counts[str(row["dataset_code"])] += 1
                        if (
                            len(action_ids) > EXPECTED_SOURCE_COUNTS["actions"]
                            or len(series_ids) > EXPECTED_SOURCE_COUNTS["series"]
                            or len(dataset_counts) > EXPECTED_PAIR_PARTITIONS
                        ):
                            raise ValueError(
                                "distinct-value tracking exceeded real bounds"
                            )
            if not (
                partition_rows == partition["rows"] == file_meta["rows"]
                and partition_min_id == partition["min_id"] == file_meta["min_id"]
                and partition_max_id == partition["max_id"] == file_meta["max_id"]
                and partition_source_urls == partition["source_url_rows"]
                and partition_indicator_urls == partition["indicator_source_url_rows"]
                and partition_identity_refs
                == partition["official_identity_reference_rows"]
                and partition_private_findings == partition["private_token_findings"]
                and partition_publication_rows == partition["publication_eligible_rows"]
                and partition_ranking_rows == partition["ranking_eligible_rows"]
                and digest.hexdigest() == partition["input_sha256"]
            ):
                raise ValueError("pair partition metadata differs from full row scan")
            aggregate_digest.update(
                str(partition["partition_id"]).encode("utf-8") + b"\0"
            )
            aggregate_digest.update(digest.hexdigest().encode("ascii") + b"\n")
            files_total += 1
            pair_bytes_total += int(file_meta["bytes"])
            partition_reports.append(
                {
                    "partition_id": partition["partition_id"],
                    "rows": partition_rows,
                    "files": [
                        {
                            "path": relative,
                            "rows": partition_rows,
                            "bytes": file_meta["bytes"],
                            "sha256": file_meta["sha256"],
                        }
                    ],
                    "input_sha256": digest.hexdigest(),
                }
            )
        if _next_or_none(source_rows) is not None:
            exact_source_parity = False
            source_exhausted_exactly = False
    finally:
        source_rows.close()

    if not (
        exact_source_parity
        and source_exhausted_exactly
        and rows_total == EXPECTED_SOURCE_COUNTS["pairs"]
        and files_total == EXPECTED_PAIR_FILES
        and pair_bytes_total == declared_pair_bytes
        and len(action_ids) == EXPECTED_SOURCE_COUNTS["actions"]
        and len(series_ids) == EXPECTED_SOURCE_COUNTS["series"]
    ):
        raise ValueError("full Parquet scan does not have exact source parity")

    descriptor_path = root / ".build-descriptor.json"
    descriptor, descriptor_fact, descriptor_identity = _load_json_object(
        descriptor_path,
        max_bytes=MAXIMUM_JSON_BYTES,
    )
    package_artifacts[".build-descriptor.json"] = (
        descriptor_fact,
        descriptor_identity,
        MAXIMUM_JSON_BYTES,
    )
    descriptor_sha256 = str(
        dict(manifest.get("restart_contract") or {}).get("descriptor_sha256") or ""
    )
    descriptor_payload = {
        key: value for key, value in descriptor.items() if key != "descriptor_sha256"
    }
    expected_hard_caps = {
        "pair_partitions": EXPECTED_PAIR_PARTITIONS,
        "pair_files": EXPECTED_PAIR_FILES,
        "pair_file_bytes": MAXIMUM_PAIR_FILE_BYTES,
        "pair_parquet_bytes": MAXIMUM_PAIR_PARQUET_BYTES,
        "identity_parquet_bytes": MAXIMUM_IDENTITY_PARQUET_BYTES,
        "portable_parquet_bytes": MAXIMUM_PORTABLE_PARQUET_BYTES,
        "json_bytes": MAXIMUM_JSON_BYTES,
        "checkpoint_bytes": MAXIMUM_CHECKPOINT_BYTES,
        "package_files": MAXIMUM_PACKAGE_FILES,
        "package_directories": MAXIMUM_PACKAGE_DIRECTORIES,
        "package_depth": MAXIMUM_PACKAGE_DEPTH,
        "package_path_bytes": MAXIMUM_PACKAGE_PATH_BYTES,
        "pair_row_group_uncompressed_bytes": (
            MAXIMUM_PAIR_ROW_GROUP_UNCOMPRESSED_BYTES
        ),
        "pair_column_uncompressed_bytes": (MAXIMUM_PAIR_COLUMN_UNCOMPRESSED_BYTES),
        "pair_batch_bytes": MAXIMUM_PAIR_BATCH_BYTES,
        "pair_string_bytes": MAXIMUM_PAIR_STRING_BYTES,
    }
    producer_path = (
        Path(__file__).with_name("outcome_pair_partitions.py").resolve(strict=True)
    )
    writer_path = (
        Path(__file__).with_name("semantic_parquet_io.py").resolve(strict=True)
    )
    previous_sha = descriptor.get("previous_manifest_sha256")
    if previous_sha is not None and not _is_sha256(previous_sha):
        raise ValueError("descriptor previous manifest checksum is invalid")
    if not (
        descriptor.get("schema_version") == BUILD_DESCRIPTOR_SCHEMA
        and descriptor.get("descriptor_sha256") == descriptor_sha256
        and _canonical_sha256(descriptor_payload) == descriptor_sha256
        and descriptor.get("lane") == LANE
        and descriptor.get("transformer_version") == TRANSFORMER_VERSION
        and descriptor.get("schema_sha256") == OUTCOME_PAIR_CONTRACT.schema_sha256
        and descriptor.get("source_database_sha256") == source_proof["database_sha256"]
        and descriptor.get("source_manifest_sha256") == source_proof["manifest_sha256"]
        and descriptor.get("source_validation_sha256")
        == source_proof["validation_sha256"]
        and descriptor.get("identity_resolver_audit_sha256")
        == identity_resolver_proof["sha256"]
        and descriptor.get("identity_companion_manifest_sha256")
        == identity_companion_proof["manifest_sha256"]
        and descriptor.get("identity_companion_validation_sha256")
        == identity_companion_proof["validation_sha256"]
        and descriptor.get("identity_companion_semantic_root_sha256")
        == identity_companion_proof["package_semantic_root_sha256"]
        and descriptor.get("identity_companion_inventory_root_sha256")
        == identity_companion_proof["inventory_root_sha256"]
        and descriptor.get("identity_source_database_sha256")
        == identity_companion_proof["source_database_sha256"]
        and descriptor.get("identity_config_sha256")
        == identity_companion_proof["config_sha256"]
        and descriptor.get("source_semantic_root_sha256")
        == source_proof["semantic_root_sha256"]
        and descriptor.get("partition_input_root_sha256")
        == aggregate_digest.hexdigest()
        and descriptor.get("partition_contract") == _expected_physical_contract()
        and descriptor.get("partitions") == EXPECTED_PAIR_PARTITIONS
        and descriptor.get("rows") == EXPECTED_SOURCE_COUNTS["pairs"]
        and descriptor.get("minimum_rows_gate") == min_rows
        and descriptor.get("maximum_peak_rss_mb") == float(max_peak_rss_mb)
        and descriptor.get("hard_caps") == expected_hard_caps
        and descriptor.get("implementation")
        == {
            "transformer_sha256": source_artifacts[producer_path][0]["sha256"],
            "partition_writer_sha256": source_artifacts[writer_path][0]["sha256"],
        }
    ):
        raise ValueError("restart descriptor differs from the canonical build")

    manifest_by_id = {partition["partition_id"]: partition for partition in partitions}
    for relative in sorted(expected_checkpoint_paths):
        checkpoint, checkpoint_fact, checkpoint_identity = _load_json_object(
            _package_child(root, relative),
            max_bytes=MAXIMUM_CHECKPOINT_BYTES,
        )
        package_artifacts[relative] = (
            checkpoint_fact,
            checkpoint_identity,
            MAXIMUM_CHECKPOINT_BYTES,
        )
        checkpoint_payload = {
            key: value
            for key, value in checkpoint.items()
            if key != "checkpoint_sha256"
        }
        saved_partition = checkpoint.get("partition")
        if not isinstance(saved_partition, dict):
            raise TypeError("partition checkpoint omits partition metadata")
        partition_id = str(saved_partition.get("partition_id") or "")
        expected_partition = manifest_by_id.get(partition_id)
        saved_base = {
            key: value
            for key, value in saved_partition.items()
            if key != "materialization"
        }
        expected_base = {
            key: value
            for key, value in (expected_partition or {}).items()
            if key != "materialization"
        }
        expected_name = (
            ".checkpoints/"
            + hashlib.sha256(partition_id.encode("utf-8")).hexdigest()
            + ".json"
        )
        if not (
            expected_partition is not None
            and relative == expected_name
            and checkpoint.get("schema_version") == PARTITION_CHECKPOINT_SCHEMA
            and checkpoint.get("descriptor_sha256") == descriptor_sha256
            and checkpoint.get("checkpoint_sha256")
            == _canonical_sha256(checkpoint_payload)
            and saved_base == expected_base
        ):
            raise ValueError("partition checkpoint is stale or inexact")

    summary_path = root / "build-checkpoint.json"
    restart_summary, summary_fact, summary_identity = _load_json_object(
        summary_path,
        max_bytes=MAXIMUM_CHECKPOINT_BYTES,
    )
    package_artifacts["build-checkpoint.json"] = (
        summary_fact,
        summary_identity,
        MAXIMUM_CHECKPOINT_BYTES,
    )
    partition_checkpoint_root = _partition_checkpoint_root(partitions)
    expected_restart_summary = {
        "schema_version": "outcome_pair_discovery_build_checkpoint_v1",
        "status": "complete",
        "descriptor_sha256": descriptor_sha256,
        "partition_checkpoint_root_sha256": partition_checkpoint_root,
        "partitions": EXPECTED_PAIR_PARTITIONS,
        "rows": EXPECTED_SOURCE_COUNTS["pairs"],
        "source_artifacts_unchanged": True,
    }
    if restart_summary != expected_restart_summary:
        raise ValueError("build checkpoint summary is stale or inexact")

    restart_contract = manifest.get("restart_contract")
    if not isinstance(restart_contract, dict):
        raise TypeError("manifest restart contract must be an object")
    recovered = _exact_int(
        restart_contract.get("partitions_recovered_from_checkpoints"),
        label="recovered partition count",
    )
    descriptor_temps = _exact_int(
        restart_contract.get("interrupted_descriptor_temps_recovered"),
        label="descriptor temp recovery count",
    )
    identity_recovered = _exact_int(
        restart_contract.get("identity_companion_files_recovered"),
        label="identity recovery count",
    )
    if not (
        set(restart_contract)
        == {
            "schema_version",
            "descriptor_sha256",
            "partition_checkpoint_schema_version",
            "partition_checkpoint_root_sha256",
            "checkpoint_granularity",
            "resumed_build",
            "partitions_recovered_from_checkpoints",
            "incomplete_partition_files_removed_on_resume",
            "config_or_source_drift_fails_closed",
            "work_preserved_on_failure",
            "interrupted_descriptor_temps_recovered",
            "invalid_identity_audit_copy_recovered",
            "identity_companion_files_recovered",
        }
        and restart_contract.get("schema_version") == BUILD_DESCRIPTOR_SCHEMA
        and restart_contract.get("descriptor_sha256") == descriptor_sha256
        and restart_contract.get("partition_checkpoint_schema_version")
        == PARTITION_CHECKPOINT_SCHEMA
        and restart_contract.get("partition_checkpoint_root_sha256")
        == partition_checkpoint_root
        and restart_contract.get("checkpoint_granularity")
        == "completed_semantic_partition"
        and type(restart_contract.get("resumed_build")) is bool
        and 0 <= recovered <= EXPECTED_PAIR_PARTITIONS
        and restart_contract.get("incomplete_partition_files_removed_on_resume") is True
        and restart_contract.get("config_or_source_drift_fails_closed") is True
        and restart_contract.get("work_preserved_on_failure") is True
        and 0 <= descriptor_temps <= EXPECTED_PAIR_FILES
        and type(restart_contract.get("invalid_identity_audit_copy_recovered")) is bool
        and 0 <= identity_recovered <= len(expected_identity_paths)
    ):
        raise ValueError("manifest restart contract is unbounded or inexact")

    incremental = manifest.get("incremental_contract")
    if not isinstance(incremental, dict):
        raise TypeError("manifest incremental contract must be an object")
    reused = _exact_int(
        incremental.get("partitions_reused"),
        label="reused partitions",
    )
    rebuilt = _exact_int(
        incremental.get("partitions_rebuilt"),
        label="rebuilt partitions",
    )
    checkpoint_resumed = _exact_int(
        incremental.get("partitions_checkpoint_resumed"),
        label="checkpoint-resumed partitions",
    )
    hardlinked = _exact_int(
        incremental.get("files_hardlinked"),
        label="hardlinked files",
    )
    copied = _exact_int(incremental.get("files_copied"), label="copied files")
    incremental_previous = incremental.get("previous_manifest_sha256")
    if incremental_previous is not None and not _is_sha256(incremental_previous):
        raise ValueError("incremental previous manifest checksum is invalid")
    if not (
        set(incremental)
        == {
            "input_fingerprint",
            "reuse_key",
            "previous_manifest_sha256",
            "partitions_reused",
            "partitions_rebuilt",
            "partitions_checkpoint_resumed",
            "files_hardlinked",
            "files_copied",
        }
        and incremental.get("input_fingerprint") == "sha256_canonical_internal_rows"
        and incremental.get("reuse_key")
        == [
            "partition_id",
            "input_sha256",
            "schema_sha256",
            "transformer_version",
            "partition_contract",
        ]
        and incremental_previous == previous_sha
        and reused + rebuilt == EXPECTED_PAIR_PARTITIONS
        and 0 <= checkpoint_resumed <= EXPECTED_PAIR_PARTITIONS
        and checkpoint_resumed == recovered
        and hardlinked == 0
        and 0 <= copied <= reused
        and (incremental_previous is not None or reused == 0)
    ):
        raise ValueError("incremental contract is unbounded or inconsistent")

    datasets = manifest.get("datasets")
    if not isinstance(datasets, dict) or set(datasets) != {
        "pairs",
        "identity_member_votes",
        "identity_action_participant_projections",
    }:
        raise ValueError("manifest dataset inventory differs from v2")
    dataset_interface = _validate_pair_dataset_interface(
        root=root,
        manifest_dataset=datasets["pairs"],
        partitions=partitions,
        expected_rows=rows_total,
    )
    if datasets["identity_member_votes"] != {
        "path": f"{IDENTITY_COMPANION_DIRECTORY}/member_vote_identities",
        "format": "parquet",
        "rows": identity_companion_proof["counts"]["member_vote_rows"],
    } or datasets["identity_action_participant_projections"] != {
        "path": (f"{IDENTITY_COMPANION_DIRECTORY}/action_participant_projections"),
        "format": "parquet",
        "rows": identity_companion_proof["counts"]["actions"],
    }:
        raise ValueError("manifest identity dataset descriptors are inexact")

    expected_totals = {
        "rows": rows_total,
        "source_url_rows": source_url_rows,
        "indicator_source_url_rows": indicator_source_url_rows,
        "official_identity_reference_rows": identity_reference_rows,
        "private_token_findings": private_findings,
        "publication_eligible_rows": publication_eligible_rows,
        "ranking_eligible_rows": ranking_eligible_rows,
        "actions": len(action_ids),
        "series": len(series_ids),
        "distinct_official_names_at_source": EXPECTED_SOURCE_COUNTS[
            "official_names_source_resolved"
        ],
        "member_votes_at_source": EXPECTED_SOURCE_COUNTS[
            "member_votes_source_resolved"
        ],
        "partitions": EXPECTED_PAIR_PARTITIONS,
        "pair_files": EXPECTED_PAIR_FILES,
        "identity_companion_files": len(identity_parquet_paths),
        "files": EXPECTED_PAIR_FILES + len(identity_parquet_paths),
        "pair_parquet_bytes": pair_bytes_total,
        "identity_companion_parquet_bytes": identity_parquet_bytes,
        "parquet_bytes": pair_bytes_total + identity_parquet_bytes,
        "identity_companion_member_vote_rows": identity_companion_proof["counts"][
            "member_vote_rows"
        ],
        "identity_companion_distinct_official_names": identity_companion_proof[
            "counts"
        ]["distinct_official_names"],
        "identity_companion_actions": identity_companion_proof["counts"]["actions"],
    }
    physical_inventory = [
        {
            "path": str(partition["files"][0]["path"]),
            "bytes": int(partition["files"][0]["bytes"]),
            "sha256": str(partition["files"][0]["sha256"]),
        }
        for partition in partitions
    ]
    physical_inventory.extend(
        {
            "path": f"{IDENTITY_COMPANION_DIRECTORY}/{item['path']}",
            "bytes": int(item["bytes"]),
            "sha256": str(item["sha256"]),
        }
        for item in identity_inventory
        if str(item["path"]).endswith(".parquet")
    )
    physical_inventory.sort(key=lambda item: item["path"])
    if len(physical_inventory) != EXPECTED_PAIR_FILES + len(
        identity_parquet_paths
    ) or len({item["path"] for item in physical_inventory}) != len(physical_inventory):
        raise ValueError("physical Parquet inventory is incomplete or duplicated")
    expected_physical_inventory_root = _canonical_sha256(physical_inventory)
    expected_portable_root = _canonical_sha256(
        {
            "contract": "outcome_pair_discovery_portable_package_v2",
            "identity_companion_semantic_root_sha256": identity_companion_proof[
                "package_semantic_root_sha256"
            ],
            "pair_semantic_root_sha256": aggregate_digest.hexdigest(),
            "physical_inventory_root_sha256": expected_physical_inventory_root,
        }
    )
    expected_limitations = [
        "Rows enumerate real action-indicator discovery pairs; they are not outcome, association, effect, merit, blame, or corruption claims.",
        "Public participant names and exact member-vote rows are bundled once in a normalized identity companion; pair rows resolve by action_id without duplicating names millions of times.",
        "Local Parquet packaging and unchanged-partition replay do not prove durable remote origin, isolated remote restore, human review, or publication eligibility.",
    ]
    source_metadata_valid = manifest.get("source") == _expected_source_metadata(
        source_db_path=source_db_path,
        source_manifest_path=source_manifest_path,
        source_validation_path=source_validation_path,
        identity_source_db_path=identity_source_db_path,
        identity_config_path=identity_config_path,
        source_proof=source_proof,
        identity_resolver_proof=identity_resolver_proof,
        identity_companion_proof=identity_companion_proof,
    )

    if set(package_artifacts) != expected_package_files:
        raise RuntimeError("not every exact package artifact received an initial hash")
    package_stable = True
    for relative, (fact, identity, cap) in package_artifacts.items():
        package_stable = (
            _rehash_exact(
                _package_child(root, relative),
                initial_fact=fact,
                initial_identity=identity,
                max_bytes=cap,
            )
            and package_stable
        )
    sources_stable = True
    for path, (fact, identity, cap, database) in source_artifacts.items():
        sources_stable = (
            _rehash_exact(
                path,
                initial_fact=fact,
                initial_identity=identity,
                max_bytes=cap,
                database=database,
            )
            and sources_stable
        )
    final_files, final_directories, final_unsafe = _complete_file_inventory(
        root,
        max_files=MAXIMUM_PACKAGE_FILES,
        max_directories=MAXIMUM_PACKAGE_DIRECTORIES,
        max_depth=MAXIMUM_PACKAGE_DEPTH,
        max_path_bytes=MAXIMUM_PACKAGE_PATH_BYTES,
    )
    try:
        exact_inventory_files, exact_inventory_directories = exact_regular_inventory(
            root,
            max_files=MAXIMUM_PACKAGE_FILES,
            max_directories=MAXIMUM_PACKAGE_DIRECTORIES,
            max_depth=MAXIMUM_PACKAGE_DEPTH,
            max_path_bytes=MAXIMUM_PACKAGE_PATH_BYTES,
        )
        exact_inventory_directories.discard(".")
    except RuntimeError:
        exact_inventory_files, exact_inventory_directories = set(), set()
        final_unsafe = True
    root_stable = FileIdentity.from_stat(root.lstat()) == root_identity
    final_inventory_exact = (
        not final_unsafe
        and final_files == expected_package_files == exact_inventory_files
        and final_directories == expected_directories == exact_inventory_directories
        and root_stable
    )
    peak_rss = peak_rss_mb()
    checks = {
        "manifest_schema": manifest.get("schema_version") == MANIFEST_SCHEMA_VERSION,
        "manifest_self_root": manifest.get("manifest_root_sha256")
        == expected_manifest_root,
        "manifest_contract_date": contract_date == EXPECTED_SOURCE_CONTRACT_DATE,
        "lane": manifest.get("lane") == LANE,
        "transformer_version": manifest.get("transformer_version")
        == TRANSFORMER_VERSION,
        "schema_contract": manifest.get("schema") == list(OUTCOME_PAIR_CONTRACT.schema),
        "schema_sha256": manifest.get("schema_sha256")
        == OUTCOME_PAIR_CONTRACT.schema_sha256,
        "physical_layout_contract": manifest.get("partition_contract")
        == _expected_physical_contract(),
        "canonical_pyarrow_runtime": pa.__version__ == CANONICAL_PYARROW_VERSION,
        "exact_pair_shape": (
            rows_total == EXPECTED_SOURCE_COUNTS["pairs"]
            and len(partitions) == EXPECTED_PAIR_PARTITIONS
            and files_total == EXPECTED_PAIR_FILES
            and min(declared_partition_rows) == EXPECTED_MIN_PARTITION_ROWS
            and max(declared_partition_rows) == EXPECTED_MAX_PARTITION_ROWS
        ),
        "hard_byte_contract": (
            pair_bytes_total <= MAXIMUM_PAIR_PARQUET_BYTES
            and identity_parquet_bytes <= MAXIMUM_IDENTITY_PARQUET_BYTES
            and pair_bytes_total + identity_parquet_bytes
            <= MAXIMUM_PORTABLE_PARQUET_BYTES
        ),
        "ordinary_hive_dataset": dataset_interface["rows"] == rows_total,
        "source_query_plan_index": any(
            "idx_outcome_pair_plan_pairs_partition" in detail
            for detail in source_query_plan
        ),
        "source_query_plan_no_temp_btree": not any(
            "TEMP B-TREE" in detail.upper() for detail in source_query_plan
        ),
        "exact_source_parity": exact_source_parity,
        "source_exhausted_exactly": source_exhausted_exactly,
        "source_metadata": source_metadata_valid,
        "policy_contract": manifest.get("policy") == _expected_policy(),
        "identity_lineage_contract": manifest.get("identity_lineage")
        == _expected_identity_lineage(
            identity_companion_proof=identity_companion_proof,
            identity_resolver_proof=identity_resolver_proof,
        ),
        "identity_companion_exact_source_parity": all(
            identity_companion_proof["counts"].get(key) == expected
            for key, expected in {
                "member_vote_rows": EXPECTED_SOURCE_COUNTS[
                    "member_votes_source_resolved"
                ],
                "distinct_official_names": EXPECTED_SOURCE_COUNTS[
                    "official_names_source_resolved"
                ],
                "actions": EXPECTED_SOURCE_COUNTS["actions"],
                "publication_eligible_rows": 0,
                "ranking_eligible_rows": 0,
            }.items()
        ),
        "materialization_checks_exact": manifest.get("checks")
        == EXPECTED_MATERIALIZATION_CHECKS,
        "local_package_gate_true": manifest.get("local_package_gate_passed") is True,
        "independent_validation_pending": manifest.get("independent_validation_passed")
        is False,
        "promotion_checks_exact": manifest.get("promotion_checks")
        == EXPECTED_PROMOTION_CHECKS,
        "promotion_gate_false": manifest.get("promotion_gate_passed") is False,
        "internal_not_publication_eligible": manifest.get("publication_status")
        == "internal_l0_pre_l1_not_publication_eligible",
        "manifest_totals_exact": manifest.get("totals") == expected_totals,
        "semantic_root": manifest.get("semantic_root_sha256")
        == aggregate_digest.hexdigest(),
        "physical_inventory_root": manifest.get("physical_inventory_root_sha256")
        == expected_physical_inventory_root,
        "portable_package_root": manifest.get("portable_package_root_sha256")
        == expected_portable_root,
        "restart_descriptor": True,
        "restart_partition_checkpoints": True,
        "restart_summary": True,
        "restart_contract": True,
        "incremental_contract": True,
        "limitations_exact": manifest.get("limitations") == expected_limitations,
        "no_private_tokens": private_findings == 0,
        "publication_eligible_rows_zero": publication_eligible_rows == 0,
        "ranking_eligible_rows_zero": ranking_eligible_rows == 0,
        "exact_complete_file_inventory": final_inventory_exact,
        "all_package_artifacts_stable_and_rehashed": package_stable,
        "all_source_artifacts_stable_and_rehashed": sources_stable,
        "bounded_peak_rss": peak_rss <= float(max_peak_rss_mb),
        "hard_resource_contract": (
            batch_rows <= MAXIMUM_BATCH_ROWS
            and max_peak_rss_mb <= MAXIMUM_PEAK_RSS_MB
            and CANONICAL_ROW_GROUP_ROWS == 25_000
            and CANONICAL_MAX_FILE_ROWS == 100_000
            and CANONICAL_COMPRESSION == "zstd"
            and CANONICAL_COMPRESSION_LEVEL == 3
            and maximum_row_group_uncompressed_bytes
            <= MAXIMUM_PAIR_ROW_GROUP_UNCOMPRESSED_BYTES
            and maximum_column_uncompressed_bytes
            <= MAXIMUM_PAIR_COLUMN_UNCOMPRESSED_BYTES
            and maximum_batch_bytes <= MAXIMUM_PAIR_BATCH_BYTES
            and maximum_string_bytes <= MAXIMUM_PAIR_STRING_BYTES
            and len(final_files) <= MAXIMUM_PACKAGE_FILES
            and len(final_directories) <= MAXIMUM_PACKAGE_DIRECTORIES
        ),
    }
    status = "ok" if all(checks.values()) else "failed"
    elapsed = time.monotonic() - started
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "status": status,
        "manifest_file": manifest_path.name,
        "manifest_sha256": manifest_fact["sha256"],
        "root_name": root.name,
        "checks": checks,
        "counts": {
            "pairs": rows_total,
            "partitions": len(partitions),
            "pair_files": files_total,
            "identity_companion_files": len(identity_parquet_paths),
            "files": files_total + len(identity_parquet_paths),
            "pair_parquet_bytes": pair_bytes_total,
            "identity_companion_parquet_bytes": identity_parquet_bytes,
            "parquet_bytes": pair_bytes_total + identity_parquet_bytes,
            "identity_companion_member_vote_rows": identity_companion_proof["counts"][
                "member_vote_rows"
            ],
            "identity_companion_distinct_official_names": (
                identity_companion_proof["counts"]["distinct_official_names"]
            ),
            "identity_companion_actions": identity_companion_proof["counts"]["actions"],
            "actions": len(action_ids),
            "series": len(series_ids),
            "source_url_rows": source_url_rows,
            "indicator_source_url_rows": indicator_source_url_rows,
            "official_identity_reference_rows": identity_reference_rows,
            "private_token_findings": private_findings,
            "publication_eligible_rows": publication_eligible_rows,
            "ranking_eligible_rows": ranking_eligible_rows,
        },
        "dataset_pair_counts": dict(sorted(dataset_counts.items())),
        "source_query_plan": list(source_query_plan),
        "roots": {
            "manifest_root_sha256": expected_manifest_root,
            "package_semantic_root_sha256": aggregate_digest.hexdigest(),
            "physical_inventory_root_sha256": expected_physical_inventory_root,
            "portable_package_root_sha256": expected_portable_root,
            "identity_companion_semantic_root_sha256": identity_companion_proof[
                "package_semantic_root_sha256"
            ],
            "identity_companion_member_rows_root_sha256": identity_companion_proof[
                "roots"
            ]["member_rows_root_sha256"],
            "identity_companion_official_names_root_sha256": (
                identity_companion_proof["roots"]["official_names_root_sha256"]
            ),
            "source_database_sha256_before": source_artifacts[
                source_db_path.resolve(strict=True)
            ][0]["sha256"],
            "source_database_sha256_after": source_proof["database_sha256"],
        },
        "policy": {
            "official_real_records_only": True,
            "synthetic_or_mock_records_counted": False,
            "official_public_domain_personal_information_retained": True,
            "machine_decisions_invented": False,
            "evidence_level": "L0",
            "publication_eligible_rows": 0,
        },
        "performance": {
            "seconds": round(elapsed, 6),
            "rows_per_second": round(rows_total / max(elapsed, 0.000001), 3),
            "peak_rss_mb": peak_rss,
            "max_peak_rss_mb": float(max_peak_rss_mb),
            "batch_rows": batch_rows,
            "maximum_row_group_uncompressed_bytes": (
                maximum_row_group_uncompressed_bytes
            ),
            "maximum_column_uncompressed_bytes": maximum_column_uncompressed_bytes,
            "maximum_batch_bytes": maximum_batch_bytes,
            "maximum_string_bytes": maximum_string_bytes,
        },
        "local_package_gate_passed": all(checks.values()),
        "promotion_gate_passed": False,
        "publication_status": "internal_l0_pre_l1_not_publication_eligible",
        "partitions": partition_reports,
    }


__all__ = ["VALIDATION_SCHEMA_VERSION", "validate_outcome_pair_partitions"]
