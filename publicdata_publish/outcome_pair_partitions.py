"""Internal, bounded Parquet packaging for real C2B outcome discovery pairs.

This lane is deliberately pre-L1. It makes the complete real discovery universe
portable and replayable without turning any pair into a claim or public result.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import secrets
import sqlite3
import stat
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .outcome_pair_identity_safety import FileIdentity, bound_regular_file
from .semantic_contracts import (
    MANIFEST_SCHEMA_VERSION,
    SemanticLaneContract,
    peak_rss_mb,
    private_token_findings,
    public_http_url,
    safe_child,
    safe_component,
    sha256_file,
)
from .semantic_parquet_io import (
    PartitionWriter,
    reusable_partition,
    reuse_partition_files,
)

LANE = "outcome_pair_discovery"
TRANSFORMER_VERSION = "outcome_pair_discovery_internal_v2"
SOURCE_MANIFEST_SCHEMA = "outcome_context_pair_plan_c2b_manifest_v1"
SOURCE_VALIDATION_SCHEMA = "outcome_context_pair_plan_c2b_validation_v1"
EXPECTED_SOURCE_DATABASE_SHA256 = (
    "04c8265154bf6659971b732db135f07fe6db0d45a0482d775bb30c15bde57680"
)
EXPECTED_SOURCE_MANIFEST_SHA256 = (
    "e89430cd5f537d93d6c73458b1fe3954eb541f0abce8f1adb9a5670b31b71007"
)
EXPECTED_SOURCE_VALIDATION_SHA256 = (
    "c590a4fc01c918a01a9fbe3c83f652086773855df970c44ee397de7f9af77fee"
)
EXPECTED_SOURCE_MANIFEST_ROOT_SHA256 = (
    "9ba36e3994ef2ab1ba90dacf2441fc20fdcda6f14d1942f7fe4fc58be40a24b6"
)
EXPECTED_SOURCE_SEMANTIC_ROOT_SHA256 = (
    "e9fecdb89e518c7d8f6ecc947c6930c84afa96dad031c4bbc332842cc685d7ae"
)
EXPECTED_SOURCE_PIPELINE_KEY = (
    "vclc:outcome-pair-plan-c2b-pipeline:294c93befa7e73b46c84355d"
)
EXPECTED_SOURCE_CONTRACT_DATE = "2026-08-23"
EXPECTED_SOURCE_COUNTS = {
    "actions": 458,
    "base_partitions": 1205,
    "bucket_partitions": 197196,
    "geographies": 89,
    "member_votes_source_resolved": 119116,
    "observations": 79722,
    "official_names_source_resolved": 490,
    "pairs": 2865602,
    "series": 6400,
}
EXPECTED_MEMBER_COMPONENT_ROOT_SHA256 = (
    "95aac5313afd057f042d7c1d39a7cfc8b20db8522eff591fff52f84774cf1631"
)
BUILD_DESCRIPTOR_SCHEMA = "outcome_pair_discovery_build_descriptor_v1"
PARTITION_CHECKPOINT_SCHEMA = "outcome_pair_discovery_partition_checkpoint_v1"
IDENTITY_RESOLVER_AUDIT_SCHEMA = "outcome_pair_identity_resolver_audit_v1"
EXPECTED_IDENTITY_RESOLVER_AUDIT_SHA256 = (
    "2090ffa4aabdf6aaee422656faa50284f0ec6fd83a048907a9f12ecdd2bb478f"
)
MINIMUM_REAL_PAIR_ROWS = 1_000_000
CANONICAL_PYARROW_VERSION = "20.0.0"
CANONICAL_ROW_GROUP_ROWS = 25_000
CANONICAL_MAX_FILE_ROWS = 100_000
CANONICAL_COMPRESSION = "zstd"
CANONICAL_COMPRESSION_LEVEL = 3
MAXIMUM_ROW_GROUP_ROWS = CANONICAL_ROW_GROUP_ROWS
MAXIMUM_FILE_ROWS = CANONICAL_MAX_FILE_ROWS
MAXIMUM_PEAK_RSS_MB = 1024.0
MAXIMUM_BATCH_ROWS = 25_000
EXPECTED_PAIR_PARTITIONS = 1_205
EXPECTED_PAIR_FILES = 1_205
EXPECTED_MIN_PARTITION_ROWS = 27
EXPECTED_MAX_PARTITION_ROWS = 18_348
MAXIMUM_PAIR_FILE_BYTES = 64 * 1024**2
MAXIMUM_PAIR_PARQUET_BYTES = 1024**3
MAXIMUM_IDENTITY_PARQUET_BYTES = 64 * 1024**2
MAXIMUM_PORTABLE_PARQUET_BYTES = (
    MAXIMUM_PAIR_PARQUET_BYTES + MAXIMUM_IDENTITY_PARQUET_BYTES
)
MAXIMUM_JSON_BYTES = 32 * 1024**2
MAXIMUM_CHECKPOINT_BYTES = 1024**2
MAXIMUM_PACKAGE_FILES = 4_096
MAXIMUM_PACKAGE_DIRECTORIES = 2_048
MAXIMUM_PACKAGE_DEPTH = 12
MAXIMUM_PACKAGE_PATH_BYTES = 512
MAXIMUM_PAIR_ROW_GROUP_UNCOMPRESSED_BYTES = 16 * 1024**2
MAXIMUM_PAIR_COLUMN_UNCOMPRESSED_BYTES = 4 * 1024**2
MAXIMUM_PAIR_BATCH_BYTES = 32 * 1024**2
MAXIMUM_PAIR_STRING_BYTES = 4 * 1024
ACTION_YEAR_PARTITION_FIELD = "action_year_partition"
IDENTITY_COMPANION_DIRECTORY = "identity-companion"
IDENTITY_COMPANION_VALIDATION_PATH = "control/identity-companion-validation.json"
BUILD_LEASE_SCHEMA = "outcome_pair_discovery_build_lease_v1"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTCOME_PAIR_LOCK_ROOT = PROJECT_ROOT / "etl/data/derived/.outcome-pair-writer-locks"
MEMBER_PROJECTION_FIELDS = [
    "action_id",
    "member_vote_id",
    "seat",
    "member_name",
    "member_name_normalized",
    "person_id",
    "group_code",
    "vote_choice",
    "source_id",
    "source_url",
    "source_snapshot_date",
]

OUTCOME_PAIR_CONTRACT = SemanticLaneContract(
    lane=LANE,
    transformer_version=TRANSFORMER_VERSION,
    id_column="pair_plan_id",
    year_column="action_year",
    schema=(
        {"name": "pair_plan_id", "type": "string", "nullable": False},
        {"name": "pipeline_key", "type": "string", "nullable": False},
        {"name": "base_partition_key", "type": "string", "nullable": False},
        {"name": "partition_key", "type": "string", "nullable": False},
        {"name": "pair_bucket", "type": "string", "nullable": False},
        {"name": "action_plan_pk", "type": "int64", "nullable": False},
        {"name": "series_plan_pk", "type": "int64", "nullable": False},
        {"name": "action_year", "type": "int64", "nullable": False},
        {"name": "action_id", "type": "string", "nullable": False},
        {"name": "action_date", "type": "string", "nullable": False},
        {"name": "action_label", "type": "string", "nullable": False},
        {"name": "source_id", "type": "string", "nullable": False},
        {"name": "source_url", "type": "string", "nullable": False},
        {"name": "action_source_record_pk", "type": "int64", "nullable": False},
        {"name": "action_source_record_id", "type": "string", "nullable": False},
        {"name": "action_source_snapshot_date", "type": "string", "nullable": False},
        {"name": "action_source_page_url", "type": "string", "nullable": False},
        {
            "name": "action_source_record_content_sha256",
            "type": "string",
            "nullable": False,
        },
        {"name": "member_vote_count", "type": "int64", "nullable": False},
        {"name": "official_name_count", "type": "int64", "nullable": False},
        {"name": "participant_projection_sha256", "type": "string", "nullable": False},
        {"name": "indicator_series_id", "type": "int64", "nullable": False},
        {"name": "indicator_canonical_key", "type": "string", "nullable": False},
        {"name": "indicator_series_label", "type": "string", "nullable": False},
        {"name": "dataset_code", "type": "string", "nullable": False},
        {"name": "country_code", "type": "string", "nullable": False},
        {"name": "geography_code", "type": "string", "nullable": False},
        {"name": "frequency_code", "type": "string", "nullable": False},
        {"name": "unit_code", "type": "string", "nullable": False},
        {"name": "indicator_dimensions_json", "type": "string", "nullable": False},
        {"name": "indicator_source_id", "type": "string", "nullable": False},
        {"name": "indicator_source_record_pk", "type": "int64", "nullable": False},
        {"name": "indicator_source_record_id", "type": "string", "nullable": False},
        {"name": "indicator_source_snapshot_date", "type": "string", "nullable": False},
        {"name": "indicator_source_url", "type": "string", "nullable": False},
        {
            "name": "indicator_source_record_content_sha256",
            "type": "string",
            "nullable": False,
        },
        {
            "name": "indicator_origin_capture_sha256",
            "type": "string",
            "nullable": False,
        },
        {"name": "indicator_observation_count", "type": "int64", "nullable": False},
        {
            "name": "indicator_observation_years_json",
            "type": "string",
            "nullable": False,
        },
        {
            "name": "indicator_observation_projection_sha256",
            "type": "string",
            "nullable": False,
        },
        {"name": "first_observation_date", "type": "string", "nullable": False},
        {"name": "last_observation_date", "type": "string", "nullable": False},
        {"name": "strict_pre_latest_date", "type": "string", "nullable": False},
        {"name": "strict_post_earliest_date", "type": "string", "nullable": False},
        {"name": "evidence_level", "type": "string", "nullable": False},
        {"name": "link_state", "type": "string", "nullable": False},
        {"name": "association_assessment", "type": "string", "nullable": False},
        {"name": "causal_assessment", "type": "string", "nullable": False},
        {"name": "effect_estimate_state", "type": "string", "nullable": False},
        {"name": "political_merit_or_blame", "type": "string", "nullable": False},
        {"name": "corruption_assessment", "type": "string", "nullable": False},
        {"name": "ranking_eligible", "type": "int64", "nullable": False},
        {"name": "publication_eligible", "type": "int64", "nullable": False},
        {"name": "row_semantic_sha256", "type": "string", "nullable": False},
        {"name": "public_identity_model", "type": "string", "nullable": False},
    ),
)

PAIR_SQL = """
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


def _load_json_object(
    path: Path, *, max_bytes: int = MAXIMUM_JSON_BYTES
) -> dict[str, Any]:
    path = Path(path)
    with bound_regular_file(path) as bound:
        if bound.identity.size < 2 or bound.identity.size > max_bytes:
            raise ValueError(f"JSON artifact is outside its byte contract: {path.name}")
        raw = bound.read_bytes(max_bytes=max_bytes)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"JSON artifact is invalid UTF-8 JSON: {path.name}") from exc
    if not isinstance(payload, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return payload


def _canonical_json_text(value: Any) -> str:
    payload = json.loads(str(value))
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def validate_export_path_separation(
    *,
    db_path: Path,
    source_manifest_path: Path,
    source_validation_path: Path,
    identity_resolver_audit_path: Path,
    identity_source_db_path: Path,
    identity_config_path: Path,
    identity_companion_root: Path,
    identity_companion_manifest_path: Path,
    identity_companion_validation_path: Path,
    output_root: Path,
    previous_manifest_path: Path | None,
    previous_root: Path | None,
) -> None:
    inputs = {
        Path(db_path).resolve(),
        Path(source_manifest_path).resolve(),
        Path(source_validation_path).resolve(),
        Path(identity_resolver_audit_path).resolve(),
        Path(identity_source_db_path).resolve(),
        Path(identity_config_path).resolve(),
        Path(identity_companion_manifest_path).resolve(),
        Path(identity_companion_validation_path).resolve(),
        *(
            [Path(previous_manifest_path).resolve()]
            if previous_manifest_path is not None
            else []
        ),
    }
    output = Path(output_root).resolve()
    work = output.parent / f".{output.name}.work"
    build_lock = outcome_pair_lease_path(output, namespace="build")
    command_lock = outcome_pair_lease_path(output, namespace="command")
    mutation_targets = (output, work, build_lock, command_lock)
    for index, candidate in enumerate(mutation_targets):
        for other in mutation_targets[index + 1 :]:
            if _path_within(candidate, other) or _path_within(other, candidate):
                raise ValueError("package, work, and lock targets must be disjoint")
        if candidate in inputs or any(_path_within(path, candidate) for path in inputs):
            raise ValueError("package output aliases or contains immutable input")
    companion_root = Path(identity_companion_root).resolve()
    for candidate in (output, work, build_lock, command_lock):
        if _path_within(candidate, companion_root) or _path_within(
            companion_root, candidate
        ):
            raise ValueError("package output must be disjoint from identity companion")
    if previous_root is not None:
        previous = Path(previous_root).resolve()
        for candidate in (output, work, build_lock, command_lock):
            if _path_within(candidate, previous) or _path_within(previous, candidate):
                raise ValueError("package output must be disjoint from previous root")


def _exact_public_url(value: Any, *, host: str, label: str) -> str:
    raw = str(value or "").strip()
    safe = public_http_url(raw)
    if safe is None or safe != raw:
        raise ValueError(f"{label} is not an exact public HTTP URL")
    parsed = urlsplit(safe)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != host:
        raise ValueError(f"{label} is outside the pinned official host")
    return safe


def _expected_base_partition(row: sqlite3.Row) -> str:
    return (
        "action_source=senado_votaciones/"
        f"year={int(row['action_year'])}/"
        "indicator_source=eurostat_sdmx/"
        f"dataset={row['dataset_code']}/"
        f"country={row['country_code']}/"
        f"geography={row['geography_code']}"
    )


def public_pair_row(row: sqlite3.Row) -> dict[str, Any]:
    base_partition = _expected_base_partition(row)
    if str(row["base_partition_key"]) != base_partition:
        raise ValueError(f"pair has invalid base partition: {row['pair_plan_id']}")
    pair_bucket = str(row["pair_bucket"])
    if str(row["partition_key"]) != f"{base_partition}/bucket={pair_bucket}":
        raise ValueError(f"pair has invalid bucket partition: {row['pair_plan_id']}")
    if str(row["action_source_id"]) != "senado_votaciones":
        raise ValueError("C2B action source drifted")
    if str(row["indicator_source_id"]) != "eurostat_sdmx":
        raise ValueError("C2B indicator source drifted")
    action_url = _exact_public_url(
        row["official_action_url"], host="www.senado.es", label="action source URL"
    )
    action_page_url = _exact_public_url(
        row["action_source_page_url"],
        host="www.senado.es",
        label="action page URL",
    )
    indicator_url = _exact_public_url(
        row["indicator_source_url"],
        host="ec.europa.eu",
        label="indicator source URL",
    )
    policy = {
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
    for key, expected in policy.items():
        actual = int(row[key]) if isinstance(expected, int) else str(row[key])
        if actual != expected:
            raise ValueError(f"C2B no-claim policy drifted: {key}")
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
        **policy,
        "row_semantic_sha256": str(row["row_semantic_sha256"]),
        "public_identity_model": "normalized_reference_to_member_vote_corpus",
    }


def _only_pipeline_key(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        "SELECT DISTINCT pipeline_key FROM outcome_pair_plan_pairs "
        "ORDER BY pipeline_key LIMIT 2"
    ).fetchall()
    if len(rows) != 1 or not str(rows[0][0]):
        raise ValueError("C2B source must contain exactly one non-empty pipeline")
    return str(rows[0][0])


@contextmanager
def _bound_sqlite_connection(
    db_path: Path,
    *,
    expected_identity: FileIdentity | None = None,
) -> Iterator[sqlite3.Connection]:
    """Open SQLite through a held descriptor so pathname swaps cannot redirect it."""

    with bound_regular_file(Path(db_path), database=True) as bound:
        if expected_identity is not None and bound.identity != expected_identity:
            raise RuntimeError("SQLite source inode differs from pinned source proof")
        uri = f"file:/dev/fd/{bound.handle.fileno()}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA query_only=ON")
            conn.execute("PRAGMA trusted_schema=OFF")
            yield conn
        finally:
            conn.close()


def iter_public_pair_rows(
    db_path: Path,
    *,
    pipeline_key: str | None = None,
    expected_database_identity: FileIdentity | None = None,
) -> Iterator[dict[str, Any]]:
    with _bound_sqlite_connection(
        db_path,
        expected_identity=expected_database_identity,
    ) as conn:
        exact_pipeline_key = pipeline_key or _only_pipeline_key(conn)
        for row in conn.execute(PAIR_SQL, (exact_pipeline_key,)):
            yield public_pair_row(row)


def partition_key(row: dict[str, Any]) -> tuple[int, str, str]:
    return (
        int(row["action_year"]),
        str(row["dataset_code"]),
        str(row["geography_code"]),
    )


def partition_id(key: tuple[int, str, str]) -> str:
    return f"{key[0]}|{key[1]}|{key[2]}"


def partition_dir(contract_date: str, key: tuple[int, str, str]) -> Path:
    return Path(
        f"lane={LANE}",
        f"contract_date={safe_component(contract_date)}",
        "action_source=senado_votaciones",
        f"{ACTION_YEAR_PARTITION_FIELD}={key[0]}",
        "indicator_source=eurostat_sdmx",
        f"dataset={safe_component(key[1])}",
        f"geography={safe_component(key[2])}",
    )


def validate_pair_dataset_interface(
    *, root: Path, partitions: list[dict[str, Any]], expected_rows: int
) -> dict[str, Any]:
    """Open the declared pair table through the ordinary Hive dataset API."""

    import pyarrow.dataset as ds  # type: ignore

    relative_root = f"lane={LANE}"
    dataset = ds.dataset(
        Path(root) / relative_root,
        format="parquet",
        partitioning="hive",
    )
    fields = set(dataset.schema.names)
    required = {
        *OUTCOME_PAIR_CONTRACT.columns,
        "contract_date",
        "action_source",
        ACTION_YEAR_PARTITION_FIELD,
        "indicator_source",
        "dataset",
        "geography",
    }
    if not required.issubset(fields):
        raise ValueError("pair Hive dataset omits declared data or partition fields")
    counted = int(dataset.count_rows())
    if counted != int(expected_rows):
        raise ValueError("pair Hive dataset row count differs from materialization")
    probes: list[dict[str, Any]] = []
    probe_indexes = sorted({0, len(partitions) // 2, len(partitions) - 1})
    for index in probe_indexes:
        partition = partitions[index]
        values = dict(partition["values"])
        expression = (
            (ds.field(ACTION_YEAR_PARTITION_FIELD) == int(values["action_year"]))
            & (ds.field("dataset") == str(values["dataset_code"]))
            & (ds.field("geography") == str(values["geography_code"]))
        )
        probe_rows = int(dataset.count_rows(filter=expression))
        if probe_rows != int(partition["rows"]):
            raise ValueError("pair Hive dataset partition filter is not exact")
        probes.append(
            {
                "partition_id": str(partition["partition_id"]),
                "rows": probe_rows,
            }
        )
    return {
        "path": relative_root,
        "format": "parquet",
        "partitioning": "hive",
        "rows": counted,
        "action_year_partition_field": ACTION_YEAR_PARTITION_FIELD,
        "probes": probes,
    }


def _new_partition(contract_date: str, key: tuple[int, str, str]) -> dict[str, Any]:
    return {
        "partition_id": partition_id(key),
        "values": {
            "contract_date": contract_date,
            "source_id": "senado_votaciones",
            "action_year": key[0],
            "indicator_source_id": "eurostat_sdmx",
            "dataset_code": key[1],
            "geography_code": key[2],
        },
        "relative_dir": partition_dir(contract_date, key).as_posix(),
        "rows": 0,
        "min_id": None,
        "max_id": None,
        "source_url_rows": 0,
        "indicator_source_url_rows": 0,
        "official_identity_reference_rows": 0,
        "private_token_findings": 0,
        "publication_eligible_rows": 0,
        "ranking_eligible_rows": 0,
        "_digest": hashlib.sha256(),
    }


def scan_partitions(
    db_path: Path,
    *,
    contract_date: str,
    pipeline_key: str,
    expected_database_identity: FileIdentity,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    totals = {
        "rows": 0,
        "source_url_rows": 0,
        "indicator_source_url_rows": 0,
        "official_identity_reference_rows": 0,
        "private_token_findings": 0,
        "publication_eligible_rows": 0,
        "ranking_eligible_rows": 0,
    }
    partitions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_key: tuple[int, str, str] | None = None
    for row in iter_public_pair_rows(
        db_path,
        pipeline_key=pipeline_key,
        expected_database_identity=expected_database_identity,
    ):
        key = partition_key(row)
        if current_key != key:
            if current is not None:
                current["input_sha256"] = current.pop("_digest").hexdigest()
                partitions.append(current)
            current_key = key
            current = _new_partition(contract_date, key)
        assert current is not None
        row_id = str(row["pair_plan_id"])
        current["rows"] += 1
        current["min_id"] = (
            row_id if current["min_id"] is None else min(str(current["min_id"]), row_id)
        )
        current["max_id"] = (
            row_id if current["max_id"] is None else max(str(current["max_id"]), row_id)
        )
        for metric, field in (
            ("source_url_rows", "source_url"),
            ("indicator_source_url_rows", "indicator_source_url"),
        ):
            if row[field]:
                current[metric] += 1
                totals[metric] += 1
        if int(row["official_name_count"]) > 0 and int(row["member_vote_count"]) > 0:
            current["official_identity_reference_rows"] += 1
            totals["official_identity_reference_rows"] += 1
        findings = private_token_findings(row)
        current["private_token_findings"] += findings
        totals["private_token_findings"] += findings
        current["publication_eligible_rows"] += int(row["publication_eligible"])
        totals["publication_eligible_rows"] += int(row["publication_eligible"])
        current["ranking_eligible_rows"] += int(row["ranking_eligible"])
        totals["ranking_eligible_rows"] += int(row["ranking_eligible"])
        current["_digest"].update(OUTCOME_PAIR_CONTRACT.canonical_row_bytes(row))
        totals["rows"] += 1
    if current is not None:
        current["input_sha256"] = current.pop("_digest").hexdigest()
        partitions.append(current)
    return partitions, totals


def load_source_proof(
    *, db_path: Path, source_manifest_path: Path, source_validation_path: Path
) -> dict[str, Any]:
    expected_names = (
        "outcome-context-pair-plan-c2b-v1.db",
        "outcome-context-pair-plan-c2b-v1-manifest.json",
        "outcome-context-pair-plan-c2b-v1-validation.json",
    )
    if (
        db_path.name,
        source_manifest_path.name,
        source_validation_path.name,
    ) != expected_names:
        raise ValueError("C2B source artifacts require their canonical basenames")
    manifest_file_sha256 = sha256_file(source_manifest_path)
    validation_file_sha256 = sha256_file(source_validation_path)
    if manifest_file_sha256 != EXPECTED_SOURCE_MANIFEST_SHA256:
        raise ValueError("C2B source manifest checksum differs from pinned evidence")
    if validation_file_sha256 != EXPECTED_SOURCE_VALIDATION_SHA256:
        raise ValueError("C2B source validation checksum differs from pinned evidence")
    with bound_regular_file(db_path, database=True) as bound_database:
        actual_db_sha = bound_database.sha256()
        database_bytes = int(bound_database.identity.size)
        database_identity = bound_database.identity
    if actual_db_sha != EXPECTED_SOURCE_DATABASE_SHA256:
        raise ValueError("C2B source database checksum differs from pinned evidence")
    manifest = _load_json_object(source_manifest_path)
    validation = _load_json_object(source_validation_path)
    if manifest.get("schema_version") != SOURCE_MANIFEST_SCHEMA:
        raise ValueError("unsupported C2B source manifest")
    if (
        validation.get("schema_version") != SOURCE_VALIDATION_SCHEMA
        or validation.get("status") != "passed"
    ):
        raise ValueError("C2B source validation has not passed")
    roots = dict(validation.get("roots") or {})
    counts = dict(validation.get("counts") or {})
    proof = dict(validation.get("proof") or {})
    source_roots = dict(manifest.get("roots") or {})
    source_shards = list(manifest.get("shards") or [])
    manifest_payload = {
        key: value for key, value in manifest.items() if key != "manifest_root_sha256"
    }
    if manifest.get("manifest_root_sha256") != _canonical_sha256(manifest_payload):
        raise ValueError("C2B source manifest self-hash mismatch")
    pinned_contract = {
        "database_sha256": actual_db_sha,
        "manifest_sha256": manifest_file_sha256,
        "validation_sha256": validation_file_sha256,
        "manifest_root_sha256": str(manifest.get("manifest_root_sha256") or ""),
        "semantic_root_sha256": str(roots.get("semantic_root_sha256") or ""),
        "pipeline_key": str(manifest.get("pipeline_key") or ""),
        "contract_date": str(manifest.get("contract_date") or ""),
        "counts": counts,
        "passed_checks": int(validation.get("passed_checks") or 0),
        "failed_checks": list(validation.get("failed_checks") or []),
    }
    expected_contract = {
        "database_sha256": EXPECTED_SOURCE_DATABASE_SHA256,
        "manifest_sha256": EXPECTED_SOURCE_MANIFEST_SHA256,
        "validation_sha256": EXPECTED_SOURCE_VALIDATION_SHA256,
        "manifest_root_sha256": EXPECTED_SOURCE_MANIFEST_ROOT_SHA256,
        "semantic_root_sha256": EXPECTED_SOURCE_SEMANTIC_ROOT_SHA256,
        "pipeline_key": EXPECTED_SOURCE_PIPELINE_KEY,
        "contract_date": EXPECTED_SOURCE_CONTRACT_DATE,
        "counts": EXPECTED_SOURCE_COUNTS,
        "passed_checks": 107,
        "failed_checks": [],
    }
    if pinned_contract != expected_contract:
        raise ValueError("C2B source evidence differs from the pinned real contract")
    if len(source_shards) != 1:
        raise ValueError("C2B source must declare exactly one SQLite shard")
    if (
        roots.get("database_sha256") != actual_db_sha
        or source_shards[0].get("sha256") != actual_db_sha
    ):
        raise ValueError("C2B source database checksum mismatch")
    if roots.get("semantic_root_sha256") != source_roots.get("semantic_root_sha256"):
        raise ValueError("C2B source semantic root mismatch")
    if roots.get("manifest_root_sha256") != manifest.get("manifest_root_sha256"):
        raise ValueError("C2B source manifest root mismatch")
    if int(counts.get("pairs") or 0) != int(source_shards[0].get("pair_rows") or -1):
        raise ValueError("C2B source pair count mismatch")
    required_zero = (
        "association_claims",
        "causal_claims",
        "effect_estimates",
        "ranking_eligible_rows",
        "publication_eligible_rows",
    )
    if any(int(proof.get(key) or 0) != 0 for key in required_zero):
        raise ValueError("C2B source no-claim proof failed")
    if proof.get("official_public_identities_retained_at_source") is not True:
        raise ValueError("C2B source identity-retention proof failed")
    wal_path = Path(f"{db_path}-wal")
    if wal_path.exists() and wal_path.stat().st_size:
        raise ValueError("C2B source has a non-empty WAL")
    return {
        "database_sha256": actual_db_sha,
        "database_bytes": database_bytes,
        # Internal-only capability.  It is deliberately omitted from every
        # serialized descriptor and manifest, then required by every reopen.
        "database_identity": database_identity,
        "manifest_sha256": manifest_file_sha256,
        "validation_sha256": validation_file_sha256,
        "manifest_root_sha256": str(manifest.get("manifest_root_sha256") or ""),
        "semantic_root_sha256": str(roots.get("semantic_root_sha256") or ""),
        "pipeline_key": str(manifest.get("pipeline_key") or ""),
        "contract_date": str(manifest.get("contract_date") or ""),
        "input_component_roots": dict(source_roots.get("input_component_roots") or {}),
        "counts": counts,
    }


def load_identity_resolver_audit(path: Path) -> dict[str, Any]:
    path = Path(path)
    audit_sha256 = sha256_file(path)
    if audit_sha256 != EXPECTED_IDENTITY_RESOLVER_AUDIT_SHA256:
        raise ValueError("identity resolver audit checksum differs from real C2B proof")
    payload = _load_json_object(path)
    counts = dict(payload.get("counts") or {})
    roots = dict(payload.get("roots") or {})
    policy = dict(payload.get("policy") or {})
    checks = dict(payload.get("checks") or {})
    expected_counts = {
        "actions": 458,
        "count_mismatches": 64,
        "missing_actions": 0,
        "private_token_findings": 0,
        "resolver_distinct_official_names": 492,
        "resolver_member_votes": 108554,
        "source_member_votes": 119116,
        "source_official_name_rows": 119116,
    }
    expected_policy = {
        "action_locator_resolved": True,
        "exact_source_participant_projection_resolved": False,
        "official_public_names_retained": True,
        "official_real_records_only": True,
        "synthetic_or_mock_records_counted": False,
    }
    if not (
        payload.get("schema_version") == IDENTITY_RESOLVER_AUDIT_SCHEMA
        and payload.get("status") == "passed"
        and checks
        and all(checks.values())
        and counts == expected_counts
        and policy == expected_policy
        and roots.get("source_database_sha256") == EXPECTED_SOURCE_DATABASE_SHA256
        and roots.get("source_member_component_root_sha256")
        == EXPECTED_MEMBER_COMPONENT_ROOT_SHA256
        and private_token_findings(payload) == 0
    ):
        raise ValueError("identity resolver audit differs from real C2B proof")
    return {
        "sha256": audit_sha256,
        "counts": counts,
        "roots": roots,
        "policy": policy,
    }


def _identity_companion_inventory(
    *, root: Path, manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    expected: dict[str, dict[str, Any]] = {}
    tables = dict(manifest.get("tables") or {})
    member_table = dict(tables.get("member_vote_identities") or {})
    action_table = dict(tables.get("action_participant_projections") or {})
    file_items = [
        *(
            file_meta
            for partition in list(member_table.get("partitions") or [])
            for file_meta in list(dict(partition).get("files") or [])
        ),
        *list(action_table.get("files") or []),
    ]
    for raw_meta in file_items:
        meta = dict(raw_meta)
        relative = str(meta.get("path") or "")
        path = safe_child(root, relative)
        if (
            not relative
            or relative in expected
            or path is None
            or path.is_symlink()
            or not path.is_file()
        ):
            raise ValueError("identity companion declares an unsafe file inventory")
        actual = {
            "path": relative,
            "bytes": int(path.stat().st_size),
            "sha256": sha256_file(path),
        }
        if actual["bytes"] != int(meta.get("bytes") or -1) or actual["sha256"] != str(
            meta.get("sha256") or ""
        ):
            raise ValueError("identity companion file checksum differs from manifest")
        expected[relative] = actual
    root_manifest = root / "manifest.json"
    expected["manifest.json"] = {
        "path": "manifest.json",
        "bytes": int(root_manifest.stat().st_size),
        "sha256": sha256_file(root_manifest),
    }
    actual_paths, actual_directories, unsafe = _work_inventory_paths(
        root,
        max_files=MAXIMUM_PACKAGE_FILES,
        max_directories=MAXIMUM_PACKAGE_DIRECTORIES,
        max_depth=MAXIMUM_PACKAGE_DEPTH,
        max_path_bytes=MAXIMUM_PACKAGE_PATH_BYTES,
    )
    if (
        unsafe
        or actual_paths != set(expected)
        or actual_directories != _expected_parent_directories(set(expected))
    ):
        raise ValueError("identity companion has an inexact or unsafe inventory")
    return [expected[path] for path in sorted(expected)]


def load_identity_companion_proof(
    *,
    root: Path,
    manifest_path: Path,
    validation_path: Path,
    source_db_path: Path,
    config_path: Path,
    pair_plan_db_path: Path,
    max_peak_rss_mb: float,
) -> dict[str, Any]:
    """Independently validate the exact portable public-identity dimension."""

    from .outcome_pair_identity_companion import (
        EXPECTED_ACTIONS,
        EXPECTED_MEMBER_ROWS,
        EXPECTED_OFFICIAL_NAMES,
    )
    from .outcome_pair_identity_companion import (
        EXPECTED_MEMBER_COMPONENT_ROOT_SHA256 as COMPANION_MEMBER_ROOT,
    )
    from .outcome_pair_identity_companion import (
        MANIFEST_SCHEMA_VERSION as IDENTITY_MANIFEST_SCHEMA,
    )
    from .outcome_pair_identity_companion_validation import (
        VALIDATION_SCHEMA_VERSION as IDENTITY_VALIDATION_SCHEMA,
    )
    from .outcome_pair_identity_companion_validation import (
        validate_outcome_pair_identity_companion,
    )

    root = Path(root)
    manifest_path = Path(manifest_path)
    validation_path = Path(validation_path)
    source_db_path = Path(source_db_path)
    config_path = Path(config_path)
    pair_plan_db_path = Path(pair_plan_db_path)
    for required in (
        manifest_path,
        validation_path,
        source_db_path,
        config_path,
        pair_plan_db_path,
    ):
        if not required.is_file() or required.is_symlink():
            raise FileNotFoundError(required)
    validation_before_sha256 = sha256_file(validation_path)
    fresh = validate_outcome_pair_identity_companion(
        root=root,
        manifest_path=manifest_path,
        source_db_path=source_db_path,
        config_path=config_path,
        pair_plan_db_path=pair_plan_db_path,
        max_peak_rss_mb=min(float(max_peak_rss_mb), 512.0),
    )
    supplied = _load_json_object(validation_path)
    stable_fields = (
        "schema_version",
        "status",
        "manifest_sha256",
        "manifest_root_sha256",
        "package_semantic_root_sha256",
        "policy",
        "counts",
        "roots",
        "parquet_bytes",
        "checks",
        "publication_gate_passed",
        "ranking_gate_passed",
        "promotion_gate_passed",
    )
    if (
        fresh.get("schema_version") != IDENTITY_VALIDATION_SCHEMA
        or fresh.get("status") != "ok"
        or supplied.get("schema_version") != IDENTITY_VALIDATION_SCHEMA
        or supplied.get("status") != "ok"
        or any(supplied.get(key) != fresh.get(key) for key in stable_fields)
        or validation_before_sha256 != sha256_file(validation_path)
    ):
        raise ValueError("identity companion validation evidence is stale or invalid")
    manifest = _load_json_object(manifest_path)
    counts = dict(manifest.get("counts") or {})
    roots = dict(manifest.get("roots") or {})
    policy = dict(manifest.get("policy") or {})
    if not (
        manifest.get("schema_version") == IDENTITY_MANIFEST_SCHEMA
        and counts.get("member_vote_rows") == EXPECTED_MEMBER_ROWS
        and counts.get("distinct_official_names") == EXPECTED_OFFICIAL_NAMES
        and counts.get("actions") == EXPECTED_ACTIONS
        and counts.get("publication_eligible_rows") == 0
        and counts.get("ranking_eligible_rows") == 0
        and roots.get("member_component_root_sha256") == COMPANION_MEMBER_ROOT
        and policy.get("real_data_only") is True
        and policy.get("official_public_identities_retained") is True
        and manifest.get("publication_gate_passed") is False
        and manifest.get("ranking_gate_passed") is False
        and private_token_findings(manifest) == 0
        and private_token_findings(supplied) == 0
    ):
        raise ValueError("identity companion does not satisfy exact public-name policy")
    inventory = _identity_companion_inventory(root=root, manifest=manifest)
    return {
        "manifest_sha256": sha256_file(manifest_path),
        "manifest_root_sha256": str(manifest["manifest_root_sha256"]),
        "validation_sha256": validation_before_sha256,
        "package_semantic_root_sha256": str(manifest["package_semantic_root_sha256"]),
        "contract_date": str(manifest["contract_date"]),
        "counts": counts,
        "roots": roots,
        "policy": policy,
        "parquet_bytes": int(manifest.get("parquet_bytes") or 0),
        "inventory": inventory,
        "inventory_root_sha256": _canonical_sha256(inventory),
        "source_database_sha256": sha256_file(source_db_path),
        "config_sha256": sha256_file(config_path),
    }


@contextmanager
def outcome_pair_build_lease(
    output_root: Path, *, namespace: str = "build"
) -> Iterator[Path]:
    """Hold one kernel-backed writer lease for an output-root namespace.

    The lock file is intentionally persistent. A crashed process loses its
    kernel lock automatically; the next owner can then overwrite stale owner
    metadata without deleting and recreating the inode.
    """

    output_root = Path(output_root)
    if namespace not in {"build", "command"}:
        raise ValueError("unsupported outcome-pair lease namespace")
    lock_path = outcome_pair_lease_path(output_root, namespace=namespace)
    lock_root_fd = _open_secure_lock_root()
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(lock_path.name, flags, 0o600, dir_fd=lock_root_fd)
    except BaseException:
        os.close(lock_root_fd)
        raise
    lock_stat = os.fstat(fd)
    if not (
        stat.S_ISREG(lock_stat.st_mode)
        and lock_stat.st_uid == os.geteuid()
        and lock_stat.st_nlink == 1
        and stat.S_IMODE(lock_stat.st_mode) == 0o600
    ):
        os.close(fd)
        os.close(lock_root_fd)
        raise RuntimeError("outcome-pair lease inode is unsafe")
    os.fsync(lock_root_fd)
    acquired = False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                f"another outcome-pair {namespace} writer holds the build lease"
            ) from exc
        acquired = True
        owner = {
            "schema_version": BUILD_LEASE_SCHEMA,
            "state": "held",
            "namespace": namespace,
            "target_identity_sha256": lock_path.stem,
            "pid": os.getpid(),
            "acquired_at": _now_iso(),
            "stale_lock_recovery": (
                "kernel_releases_flock_on_process_exit_then_next_owner_overwrites_metadata"
            ),
        }
        encoded = (
            json.dumps(
                owner,
                allow_nan=False,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, encoded)
        os.fsync(fd)
        yield lock_path
        owner["state"] = "released"
        owner["released_at"] = _now_iso()
        encoded = (
            json.dumps(
                owner,
                allow_nan=False,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, encoded)
        os.fsync(fd)
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        os.close(lock_root_fd)


def _open_secure_lock_root() -> int:
    """Create and open the ignored lock root without following any symlink."""

    project_root = PROJECT_ROOT.resolve()
    try:
        relative = OUTCOME_PAIR_LOCK_ROOT.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise RuntimeError("outcome-pair lock root escaped project") from exc
    directory_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        directory_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        directory_flags |= os.O_NOFOLLOW
    current_fd = os.open(project_root, directory_flags)
    try:
        for component in relative.parts:
            try:
                os.mkdir(component, 0o700, dir_fd=current_fd)
            except FileExistsError:
                pass
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            next_stat = os.fstat(next_fd)
            if not stat.S_ISDIR(next_stat.st_mode):
                os.close(next_fd)
                raise RuntimeError("outcome-pair lock-root path is unsafe")
            os.close(current_fd)
            current_fd = next_fd
        root_stat = os.fstat(current_fd)
        if root_stat.st_uid != os.geteuid():
            raise RuntimeError("outcome-pair lock root has an unsafe owner")
        if stat.S_IMODE(root_stat.st_mode) != 0o700:
            os.fchmod(current_fd, 0o700)
        os.fsync(current_fd)
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def outcome_pair_lease_path(target: Path, *, namespace: str) -> Path:
    """Return a cross-runtime lock path without persisting workstation paths."""

    if namespace not in {"build", "command"}:
        raise ValueError("unsupported outcome-pair lease namespace")
    target = Path(target).resolve()
    try:
        stable_target = "repo:" + target.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        stable_target = "external:" + target.as_posix()
    identity = hashlib.sha256(f"{namespace}\0{stable_target}".encode()).hexdigest()
    return OUTCOME_PAIR_LOCK_ROOT / f"{identity}.lock"


def _previous_partitions(
    manifest_path: Path | None,
    *,
    expected_partition_contract: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], str | None]:
    if manifest_path is None:
        return {}, None
    payload = _load_json_object(manifest_path)
    valid = (
        payload.get("schema_version") == MANIFEST_SCHEMA_VERSION
        and payload.get("lane") == LANE
        and payload.get("transformer_version") == TRANSFORMER_VERSION
        and payload.get("schema_sha256") == OUTCOME_PAIR_CONTRACT.schema_sha256
        and payload.get("partition_contract") == expected_partition_contract
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


def _aggregate_partition_root(partitions: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for partition in partitions:
        digest.update(str(partition["partition_id"]).encode("utf-8") + b"\0")
        digest.update(str(partition["input_sha256"]).encode("ascii") + b"\n")
    return digest.hexdigest()


def _physical_parquet_inventory(
    *,
    partitions: list[dict[str, Any]],
    identity_companion_inventory: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return the complete sorted portable Parquet path/size/hash inventory."""

    inventory = [
        {
            "path": str(file_meta["path"]),
            "bytes": int(file_meta["bytes"]),
            "sha256": str(file_meta["sha256"]),
        }
        for partition in partitions
        for file_meta in list(partition.get("files") or [])
    ]
    inventory.extend(
        {
            "path": f"{IDENTITY_COMPANION_DIRECTORY}/{item['path']}",
            "bytes": int(item["bytes"]),
            "sha256": str(item["sha256"]),
        }
        for item in identity_companion_inventory
        if str(item.get("path") or "").endswith(".parquet")
    )
    inventory.sort(key=lambda item: item["path"])
    paths = [item["path"] for item in inventory]
    if len(paths) != len(set(paths)):
        raise ValueError("portable Parquet inventory contains duplicate paths")
    return inventory


def _physical_inventory_root(inventory: list[dict[str, Any]]) -> str:
    expected_keys = {"path", "bytes", "sha256"}
    if any(set(item) != expected_keys for item in inventory):
        raise ValueError("portable Parquet inventory has noncanonical entries")
    ordered = sorted(inventory, key=lambda item: str(item["path"]))
    if ordered != inventory:
        raise ValueError("portable Parquet inventory is not path sorted")
    return _canonical_sha256(inventory)


def _open_control_parent(path: Path) -> tuple[Path, int]:
    """Pin one real parent directory for race-safe control mutation."""

    path = Path(path)
    if path.name in {"", ".", ".."}:
        raise ValueError("control target name is unsafe")
    absolute = Path(os.path.abspath(path))
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(absolute.anchor, flags)
    try:
        for component in absolute.parent.parts[1:]:
            try:
                os.mkdir(component, 0o755, dir_fd=descriptor)
            except FileExistsError:
                pass
            following = os.open(component, flags, dir_fd=descriptor)
            following_stat = os.fstat(following)
            if not stat.S_ISDIR(following_stat.st_mode):
                os.close(following)
                raise RuntimeError("control output ancestor is not a real directory")
            os.close(descriptor)
            descriptor = following
        return absolute, descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _control_target_identity(parent_fd: int, name: str) -> FileIdentity | None:
    try:
        target_stat = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(target_stat.st_mode) or target_stat.st_nlink != 1:
        raise RuntimeError("control target is not a regular single-link file")
    return FileIdentity.from_stat(target_stat)


def secure_atomic_write_bytes(path: Path, payload: bytes) -> Path:
    """Atomically replace one control through a pinned parent descriptor."""

    stable_path, parent_fd = _open_control_parent(path)
    initial_identity = _control_target_identity(parent_fd, stable_path.name)
    temporary_name = f".{stable_path.name}.{secrets.token_hex(16)}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    temporary_fd: int | None = None
    try:
        temporary_fd = os.open(
            temporary_name,
            flags,
            0o600,
            dir_fd=parent_fd,
        )
        temporary_stat = os.fstat(temporary_fd)
        if not (stat.S_ISREG(temporary_stat.st_mode) and temporary_stat.st_nlink == 1):
            raise RuntimeError("temporary control inode is unsafe")
        view = memoryview(payload)
        offset = 0
        while offset < len(view):
            written = os.write(temporary_fd, view[offset:])
            if written < 1:
                raise RuntimeError("temporary control write made no progress")
            offset += written
        os.fsync(temporary_fd)
        os.close(temporary_fd)
        temporary_fd = None
        if _control_target_identity(parent_fd, stable_path.name) != initial_identity:
            raise RuntimeError("control target changed before atomic replacement")
        os.rename(
            temporary_name,
            stable_path.name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        final_identity = _control_target_identity(parent_fd, stable_path.name)
        if final_identity is None or final_identity.size != len(payload):
            raise RuntimeError("published control inode is invalid")
        os.fsync(parent_fd)
        return stable_path
    except BaseException:
        if temporary_fd is not None:
            os.close(temporary_fd)
        try:
            os.unlink(temporary_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        raise
    finally:
        os.close(parent_fd)


def secure_atomic_write_json(path: Path, payload: dict[str, Any]) -> Path:
    encoded = (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    return secure_atomic_write_bytes(path, encoded)


def secure_unlink_control(path: Path) -> bool:
    """Detach one regular/symlink control entry through its pinned parent."""

    stable_path, parent_fd = _open_control_parent(path)
    quarantine_name = f".{stable_path.name}.{secrets.token_hex(16)}.unlink"
    try:
        try:
            initial_stat = os.stat(
                stable_path.name,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return False
        if not (
            stat.S_ISREG(initial_stat.st_mode) or stat.S_ISLNK(initial_stat.st_mode)
        ):
            raise RuntimeError("control target is not a detachable file entry")
        os.rename(
            stable_path.name,
            quarantine_name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        quarantined_stat = os.stat(
            quarantine_name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        same_inode_after_rename = (
            int(quarantined_stat.st_dev),
            int(quarantined_stat.st_ino),
            stat.S_IFMT(quarantined_stat.st_mode),
            int(quarantined_stat.st_size),
            int(quarantined_stat.st_mtime_ns),
        ) == (
            int(initial_stat.st_dev),
            int(initial_stat.st_ino),
            stat.S_IFMT(initial_stat.st_mode),
            int(initial_stat.st_size),
            int(initial_stat.st_mtime_ns),
        )
        if not same_inode_after_rename:
            try:
                try:
                    os.stat(
                        stable_path.name,
                        dir_fd=parent_fd,
                        follow_symlinks=False,
                    )
                    target_absent = False
                except FileNotFoundError:
                    target_absent = True
                if target_absent:
                    os.rename(
                        quarantine_name,
                        stable_path.name,
                        src_dir_fd=parent_fd,
                        dst_dir_fd=parent_fd,
                    )
            finally:
                raise RuntimeError("control target changed before unlink")
        os.unlink(quarantine_name, dir_fd=parent_fd)
        os.fsync(parent_fd)
        return True
    finally:
        os.close(parent_fd)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    secure_atomic_write_json(path, payload)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _stable_directory_identity(path: Path) -> tuple[int, int]:
    """Return a fail-closed identity for a real, non-symlink directory."""

    path_stat = path.lstat()
    if path.is_symlink() or not stat.S_ISDIR(path_stat.st_mode):
        raise ValueError(f"directory target is unsafe: {path.name}")
    return int(path_stat.st_dev), int(path_stat.st_ino)


def _assert_directory_identity(path: Path, expected: tuple[int, int]) -> None:
    if _stable_directory_identity(path) != expected:
        raise RuntimeError(f"directory target changed during build: {path.name}")


def _atomic_copy_verified(
    source: Path, destination: Path, expected_sha256: str
) -> None:
    stable_destination, parent_fd = _open_control_parent(destination)
    initial_identity = _control_target_identity(parent_fd, stable_destination.name)
    temporary_name = f".{stable_destination.name}.{secrets.token_hex(16)}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    temporary_fd: int | None = None
    try:
        temporary_fd = os.open(
            temporary_name,
            flags,
            0o600,
            dir_fd=parent_fd,
        )
        digest = hashlib.sha256()
        with bound_regular_file(source) as bound:
            bound.handle.seek(0)
            while chunk := bound.handle.read(1024 * 1024):
                digest.update(chunk)
                view = memoryview(chunk)
                offset = 0
                while offset < len(view):
                    offset += os.write(temporary_fd, view[offset:])
        os.fsync(temporary_fd)
        os.close(temporary_fd)
        temporary_fd = None
        if digest.hexdigest() != expected_sha256:
            raise RuntimeError("atomic control-file copy checksum mismatch")
        if (
            _control_target_identity(parent_fd, stable_destination.name)
            != initial_identity
        ):
            raise RuntimeError("copy target changed before atomic replacement")
        os.rename(
            temporary_name,
            stable_destination.name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        if _control_target_identity(parent_fd, stable_destination.name) is None:
            raise RuntimeError("published copy inode is invalid")
        os.fsync(parent_fd)
    except BaseException:
        if temporary_fd is not None:
            os.close(temporary_fd)
        try:
            os.unlink(temporary_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass
        raise
    finally:
        os.close(parent_fd)


def _copy_identity_companion(
    *,
    source_root: Path,
    source_validation_path: Path,
    staging_root: Path,
    proof: dict[str, Any],
) -> int:
    recovered_files = 0
    target_root = staging_root / IDENTITY_COMPANION_DIRECTORY
    for file_meta in list(proof["inventory"]):
        relative = str(file_meta["path"])
        source = safe_child(source_root, relative)
        destination = safe_child(target_root, relative)
        if source is None or destination is None:
            raise ValueError("identity companion copy path is unsafe")
        if (destination.exists() or destination.is_symlink()) and (
            destination.is_symlink()
            or not destination.is_file()
            or int(destination.stat().st_size) != int(file_meta["bytes"])
            or sha256_file(destination) != str(file_meta["sha256"])
        ):
            if destination.is_dir() and not destination.is_symlink():
                raise ValueError("identity companion file target became a directory")
            destination.unlink()
            recovered_files += 1
        if not destination.exists():
            _atomic_copy_verified(
                source,
                destination,
                str(file_meta["sha256"]),
            )
    validation_destination = staging_root / IDENTITY_COMPANION_VALIDATION_PATH
    if (validation_destination.exists() or validation_destination.is_symlink()) and (
        validation_destination.is_symlink()
        or not validation_destination.is_file()
        or sha256_file(validation_destination) != str(proof["validation_sha256"])
    ):
        if validation_destination.is_dir() and not validation_destination.is_symlink():
            raise ValueError("identity validation target became a directory")
        validation_destination.unlink()
        recovered_files += 1
    if not validation_destination.exists():
        _atomic_copy_verified(
            source_validation_path,
            validation_destination,
            str(proof["validation_sha256"]),
        )
    copied_manifest = target_root / "manifest.json"
    if sha256_file(copied_manifest) != str(proof["manifest_sha256"]):
        raise RuntimeError("bundled identity companion manifest differs")
    return recovered_files


def _discard_interrupted_descriptor_temps(staging_root: Path) -> int:
    removed = 0
    for path in staging_root.glob(".build-descriptor.json.*.tmp"):
        if path.parent != staging_root or path.is_symlink() or not path.is_file():
            raise ValueError("unsafe interrupted descriptor temporary file")
        path.unlink()
        removed += 1
    if removed:
        _fsync_directory(staging_root)
    return removed


def _checkpoint_path(staging_root: Path, partition_identifier: str) -> Path:
    name = hashlib.sha256(partition_identifier.encode("utf-8")).hexdigest()
    return staging_root / ".checkpoints" / f"{name}.json"


def _partition_checkpoint_root(partitions: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for partition in partitions:
        digest.update(str(partition["partition_id"]).encode("utf-8") + b"\0")
        digest.update(str(partition["input_sha256"]).encode("ascii") + b"\0")
        for file_meta in list(partition.get("files") or []):
            digest.update(str(file_meta["path"]).encode("utf-8") + b"\0")
            digest.update(str(file_meta["sha256"]).encode("ascii") + b"\n")
    return digest.hexdigest()


def _write_partition_checkpoint(
    *,
    staging_root: Path,
    descriptor_sha256: str,
    partition: dict[str, Any],
) -> None:
    payload = {
        "schema_version": PARTITION_CHECKPOINT_SCHEMA,
        "descriptor_sha256": descriptor_sha256,
        "partition": partition,
    }
    payload["checkpoint_sha256"] = _canonical_sha256(payload)
    _atomic_write_json(
        _checkpoint_path(staging_root, str(partition["partition_id"])), payload
    )


def _fsync_partition_files(*, staging_root: Path, partition: dict[str, Any]) -> None:
    parent_directories: set[Path] = set()
    for file_meta in list(partition.get("files") or []):
        path = safe_child(staging_root, str(file_meta.get("path") or ""))
        if path is None or path.is_symlink() or not path.is_file():
            raise ValueError("partition file is unsafe or missing before checkpoint")
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        parent_directories.add(path.parent)
    for directory in sorted(parent_directories, key=lambda path: path.as_posix()):
        _fsync_directory(directory)


def _enforce_pair_parquet_metadata_bounds(
    metadata: Any,
    *,
    max_row_group_uncompressed_bytes: int = (MAXIMUM_PAIR_ROW_GROUP_UNCOMPRESSED_BYTES),
    max_column_uncompressed_bytes: int = MAXIMUM_PAIR_COLUMN_UNCOMPRESSED_BYTES,
) -> None:
    """Reject compressed payloads whose declared decode size can exhaust memory."""

    for value, hard_maximum, label in (
        (
            max_row_group_uncompressed_bytes,
            MAXIMUM_PAIR_ROW_GROUP_UNCOMPRESSED_BYTES,
            "row-group uncompressed bytes",
        ),
        (
            max_column_uncompressed_bytes,
            MAXIMUM_PAIR_COLUMN_UNCOMPRESSED_BYTES,
            "column uncompressed bytes",
        ),
    ):
        if type(value) is not int or value < 1 or value > hard_maximum:
            raise ValueError(f"pair Parquet {label} bound is invalid")
    for row_group_index in range(int(metadata.num_row_groups)):
        row_group = metadata.row_group(row_group_index)
        uncompressed = 0
        for column_index in range(int(row_group.num_columns)):
            column_bytes = int(row_group.column(column_index).total_uncompressed_size)
            if column_bytes < 1 or column_bytes > max_column_uncompressed_bytes:
                raise ValueError("pair Parquet column exceeds uncompressed byte bound")
            uncompressed += column_bytes
            if uncompressed > max_row_group_uncompressed_bytes:
                raise ValueError(
                    "pair Parquet row group exceeds uncompressed byte bound"
                )


def _enforce_pair_batch_bounds(
    batch: Any,
    *,
    max_batch_bytes: int = MAXIMUM_PAIR_BATCH_BYTES,
) -> None:
    if (
        type(max_batch_bytes) is not int
        or max_batch_bytes < 1
        or max_batch_bytes > MAXIMUM_PAIR_BATCH_BYTES
    ):
        raise ValueError("pair record-batch byte bound is invalid")
    if int(batch.nbytes) < 1 or int(batch.nbytes) > max_batch_bytes:
        raise ValueError("pair record batch exceeds decoded byte bound")


def _enforce_pair_string_bounds(columns: dict[str, list[Any]]) -> None:
    string_fields = {
        field["name"]
        for field in OUTCOME_PAIR_CONTRACT.schema
        if field["type"] == "string"
    }
    for name in string_fields:
        for value in columns[name]:
            if (
                type(value) is not str
                or len(value.encode("utf-8")) > MAXIMUM_PAIR_STRING_BYTES
            ):
                raise ValueError("pair string exceeds decoded byte bound")


def _validate_checkpoint_partition(
    *,
    staging_root: Path,
    current: dict[str, Any],
    checkpoint: dict[str, Any],
) -> dict[str, Any]:
    try:
        import pyarrow.parquet as pq  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pyarrow is required; install the project parquet extra"
        ) from exc
    saved = dict(checkpoint.get("partition") or {})
    saved_base = {
        key: value
        for key, value in saved.items()
        if key not in {"files", "materialization"}
    }
    if saved_base != current:
        raise ValueError(f"partition checkpoint drifted: {current['partition_id']}")
    digest = hashlib.sha256()
    rows = 0
    expected_schema = OUTCOME_PAIR_CONTRACT.arrow_schema()
    files = list(saved.get("files") or [])
    if len(files) != 1:
        raise ValueError("partition checkpoint must contain one canonical Parquet file")
    for file_meta in files:
        file_path = safe_child(staging_root, str(file_meta.get("path") or ""))
        if file_path is None or file_path.is_symlink() or not file_path.is_file():
            raise ValueError("partition checkpoint file is unsafe or missing")
        file_stat = file_path.lstat()
        if (
            not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_nlink != 1
            or int(file_stat.st_size) > MAXIMUM_PAIR_FILE_BYTES
        ):
            raise ValueError("partition checkpoint file violates physical bounds")
        if int(file_path.stat().st_size) != int(
            file_meta.get("bytes") or -1
        ) or sha256_file(file_path) != str(file_meta.get("sha256") or ""):
            raise ValueError("partition checkpoint file hash mismatch")
        parquet_file = pq.ParquetFile(file_path)
        _enforce_pair_parquet_metadata_bounds(parquet_file.metadata)
        if not parquet_file.schema_arrow.equals(expected_schema, check_metadata=True):
            raise ValueError("partition checkpoint Parquet schema mismatch")
        if (
            parquet_file.metadata.num_row_groups != 1
            or int(parquet_file.metadata.num_rows) != int(current["rows"])
            or int(current["rows"]) < 1
            or int(current["rows"]) > CANONICAL_ROW_GROUP_ROWS
        ):
            raise ValueError("partition checkpoint Parquet layout is noncanonical")
        file_rows = 0
        for batch in parquet_file.iter_batches(batch_size=5_000):
            _enforce_pair_batch_bounds(batch)
            columns = {
                name: batch.column(index).to_pylist()
                for index, name in enumerate(OUTCOME_PAIR_CONTRACT.columns)
            }
            _enforce_pair_string_bounds(columns)
            for row_index in range(batch.num_rows):
                row = {
                    name: columns[name][row_index]
                    for name in OUTCOME_PAIR_CONTRACT.columns
                }
                digest.update(OUTCOME_PAIR_CONTRACT.canonical_row_bytes(row))
                file_rows += 1
                rows += 1
        if file_rows != int(file_meta.get("rows") or -1):
            raise ValueError("partition checkpoint Parquet row count mismatch")
    if rows != int(current["rows"]) or digest.hexdigest() != current["input_sha256"]:
        raise ValueError("partition checkpoint content differs from current source")
    saved["materialization"] = "checkpoint_resumed"
    return saved


def _load_build_checkpoints(
    *,
    staging_root: Path,
    descriptor_sha256: str | None,
    partition_by_id: dict[str, dict[str, Any]],
    non_partition_paths: set[str],
) -> dict[str, dict[str, Any]]:
    completed: dict[str, dict[str, Any]] = {}
    checkpoint_dir = staging_root / ".checkpoints"
    for checkpoint_path in sorted(checkpoint_dir.glob("*.json")):
        if descriptor_sha256 is None:
            raise ValueError("partition checkpoint exists before build descriptor")
        checkpoint = _load_json_object(
            checkpoint_path, max_bytes=MAXIMUM_CHECKPOINT_BYTES
        )
        checkpoint_payload = {
            key: value
            for key, value in checkpoint.items()
            if key != "checkpoint_sha256"
        }
        if (
            checkpoint.get("schema_version") != PARTITION_CHECKPOINT_SCHEMA
            or checkpoint.get("descriptor_sha256") != descriptor_sha256
            or checkpoint.get("checkpoint_sha256")
            != _canonical_sha256(checkpoint_payload)
        ):
            raise ValueError(f"invalid build checkpoint: {checkpoint_path.name}")
        saved = dict(checkpoint.get("partition") or {})
        partition_identifier = str(saved.get("partition_id") or "")
        current = partition_by_id.get(partition_identifier)
        if current is None or partition_identifier in completed:
            raise ValueError("build checkpoint has unknown or duplicate partition")
        completed[partition_identifier] = _validate_checkpoint_partition(
            staging_root=staging_root,
            current=current,
            checkpoint=checkpoint,
        )
    expected_paths = {
        str(file_meta["path"])
        for partition in completed.values()
        for file_meta in list(partition.get("files") or [])
    }
    for parquet_path in staging_root.rglob("*.parquet"):
        relative = parquet_path.relative_to(staging_root).as_posix()
        if relative in non_partition_paths:
            continue
        if relative not in expected_paths:
            relative_parent = parquet_path.parent.relative_to(staging_root).as_posix()
            known_partition_dirs = {
                str(partition["relative_dir"]) for partition in partition_by_id.values()
            }
            if (
                relative_parent in known_partition_dirs
                and parquet_path.name.startswith("part-")
                and parquet_path.name.endswith(".parquet")
            ):
                parquet_path.unlink()
            else:
                raise ValueError("unexpected Parquet file in build work directory")
    return completed


def _expected_parent_directories(paths: set[str]) -> set[str]:
    directories: set[str] = set()
    for relative in paths:
        parent = Path(relative).parent
        while parent != Path("."):
            directories.add(parent.as_posix())
            parent = parent.parent
    return directories


def _work_inventory_paths(
    root: Path,
    *,
    max_files: int = MAXIMUM_PACKAGE_FILES,
    max_directories: int = MAXIMUM_PACKAGE_DIRECTORIES,
    max_depth: int = MAXIMUM_PACKAGE_DEPTH,
    max_path_bytes: int = MAXIMUM_PACKAGE_PATH_BYTES,
) -> tuple[set[str], set[str], bool]:
    """Stream a fail-closed inventory without attacker-sized collections."""

    for name, value, maximum in (
        ("files", max_files, MAXIMUM_PACKAGE_FILES),
        ("directories", max_directories, MAXIMUM_PACKAGE_DIRECTORIES),
        ("depth", max_depth, MAXIMUM_PACKAGE_DEPTH),
        ("path bytes", max_path_bytes, MAXIMUM_PACKAGE_PATH_BYTES),
    ):
        if type(value) is not int or value < 1 or value > maximum:
            raise ValueError(f"package inventory {name} bound is invalid")
    files: set[str] = set()
    directories: set[str] = set()
    unsafe = False
    file_inodes: set[tuple[int, int]] = set()
    directory_inodes: set[tuple[int, int]] = set()
    try:
        root_stat = Path(root).lstat()
        if Path(root).is_symlink() or not stat.S_ISDIR(root_stat.st_mode):
            return files, directories, True
        directory_inodes.add((int(root_stat.st_dev), int(root_stat.st_ino)))
        pending: list[tuple[Path, int]] = [(Path(root), 0)]
        while pending:
            current, depth = pending.pop()
            with os.scandir(current) as entries:
                for entry in entries:
                    path = current / entry.name
                    path_stat = entry.stat(follow_symlinks=False)
                    relative = path.relative_to(root).as_posix()
                    relative_bytes = len(relative.encode("utf-8"))
                    child_depth = depth + 1
                    if child_depth > max_depth or relative_bytes > max_path_bytes:
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


def _remove_empty_work_directories(root: Path) -> None:
    directories = sorted(
        (path for path in root.rglob("*") if path.is_dir() and not path.is_symlink()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            pass


def _clean_or_reject_work_inventory(
    *,
    staging_root: Path,
    completed: dict[str, dict[str, Any]],
    identity_companion_paths: set[str],
) -> None:
    allowed = {
        ".build-descriptor.json",
        "control/identity-resolver-audit.json",
        IDENTITY_COMPANION_VALIDATION_PATH,
        *identity_companion_paths,
        *(
            _checkpoint_path(staging_root, partition_identifier)
            .relative_to(staging_root)
            .as_posix()
            for partition_identifier in completed
        ),
        *(
            str(file_meta["path"])
            for partition in completed.values()
            for file_meta in list(partition.get("files") or [])
        ),
    }
    actual, _, unsafe = _work_inventory_paths(
        staging_root,
        max_files=MAXIMUM_PACKAGE_FILES,
        max_directories=MAXIMUM_PACKAGE_DIRECTORIES,
        max_depth=MAXIMUM_PACKAGE_DEPTH,
        max_path_bytes=MAXIMUM_PACKAGE_PATH_BYTES,
    )
    if unsafe:
        raise ValueError("build work directory contains a symlink or special file")
    for relative in sorted(actual - allowed):
        path = staging_root / relative
        if relative in {"manifest.json", "build-checkpoint.json"} or (
            path.name.startswith(".") and path.name.endswith(".tmp")
        ):
            path.unlink()
            continue
        raise ValueError(f"unexpected build work file: {relative}")
    _remove_empty_work_directories(staging_root)
    actual, actual_directories, unsafe = _work_inventory_paths(
        staging_root,
        max_files=MAXIMUM_PACKAGE_FILES,
        max_directories=MAXIMUM_PACKAGE_DIRECTORIES,
        max_depth=MAXIMUM_PACKAGE_DEPTH,
        max_path_bytes=MAXIMUM_PACKAGE_PATH_BYTES,
    )
    if unsafe or actual != allowed:
        raise ValueError("build work inventory changed during cleanup")
    if actual_directories != _expected_parent_directories(allowed):
        raise ValueError("build work directory inventory is not exact")


def _assert_final_inventory(
    *,
    staging_root: Path,
    partitions: list[dict[str, Any]],
    identity_companion_paths: set[str],
) -> None:
    allowed = {
        ".build-descriptor.json",
        "build-checkpoint.json",
        "control/identity-resolver-audit.json",
        IDENTITY_COMPANION_VALIDATION_PATH,
        *identity_companion_paths,
        "manifest.json",
        *(
            _checkpoint_path(staging_root, str(partition["partition_id"]))
            .relative_to(staging_root)
            .as_posix()
            for partition in partitions
        ),
        *(
            str(file_meta["path"])
            for partition in partitions
            for file_meta in list(partition.get("files") or [])
        ),
    }
    actual, actual_directories, unsafe = _work_inventory_paths(
        staging_root,
        max_files=MAXIMUM_PACKAGE_FILES,
        max_directories=MAXIMUM_PACKAGE_DIRECTORIES,
        max_depth=MAXIMUM_PACKAGE_DEPTH,
        max_path_bytes=MAXIMUM_PACKAGE_PATH_BYTES,
    )
    if (
        unsafe
        or actual != allowed
        or actual_directories != _expected_parent_directories(allowed)
    ):
        raise ValueError("final package inventory contains missing or undeclared files")


def _export_outcome_pair_partitions_unlocked(
    *,
    db_path: Path,
    source_manifest_path: Path,
    source_validation_path: Path,
    identity_resolver_audit_path: Path,
    identity_source_db_path: Path,
    identity_config_path: Path,
    identity_companion_root: Path,
    identity_companion_manifest_path: Path,
    identity_companion_validation_path: Path,
    output_root: Path,
    compression: str = "zstd",
    row_group_rows: int = 25_000,
    max_file_rows: int = 100_000,
    previous_manifest_path: Path | None = None,
    previous_root: Path | None = None,
    min_rows: int = 1_000_000,
    max_peak_rss_mb: float = 1024.0,
    interrupt_after_new_partitions: int | None = None,
) -> dict[str, Any]:
    db_path = Path(db_path)
    source_manifest_path = Path(source_manifest_path)
    source_validation_path = Path(source_validation_path)
    identity_resolver_audit_path = Path(identity_resolver_audit_path)
    identity_source_db_path = Path(identity_source_db_path)
    identity_config_path = Path(identity_config_path)
    identity_companion_root = Path(identity_companion_root)
    identity_companion_manifest_path = Path(identity_companion_manifest_path)
    identity_companion_validation_path = Path(identity_companion_validation_path)
    output_root = Path(output_root)
    previous_manifest_path = (
        Path(previous_manifest_path) if previous_manifest_path is not None else None
    )
    previous_root = Path(previous_root) if previous_root is not None else None
    validate_export_path_separation(
        db_path=db_path,
        source_manifest_path=source_manifest_path,
        source_validation_path=source_validation_path,
        identity_resolver_audit_path=identity_resolver_audit_path,
        identity_source_db_path=identity_source_db_path,
        identity_config_path=identity_config_path,
        identity_companion_root=identity_companion_root,
        identity_companion_manifest_path=identity_companion_manifest_path,
        identity_companion_validation_path=identity_companion_validation_path,
        output_root=output_root,
        previous_manifest_path=previous_manifest_path,
        previous_root=previous_root,
    )
    for required in (
        db_path,
        source_manifest_path,
        source_validation_path,
        identity_resolver_audit_path,
        identity_source_db_path,
        identity_config_path,
        identity_companion_manifest_path,
        identity_companion_validation_path,
    ):
        if not required.is_file():
            raise FileNotFoundError(required)
    if not identity_companion_root.is_dir() or identity_companion_root.is_symlink():
        raise FileNotFoundError(identity_companion_root)
    if output_root.exists() or output_root.is_symlink():
        raise FileExistsError(output_root)
    if (
        row_group_rows != CANONICAL_ROW_GROUP_ROWS
        or max_file_rows != CANONICAL_MAX_FILE_ROWS
        or compression != CANONICAL_COMPRESSION
    ):
        raise ValueError("Parquet settings differ from the canonical scale contract")
    if min_rows < MINIMUM_REAL_PAIR_ROWS:
        raise ValueError(
            f"minimum real-row gate cannot be below {MINIMUM_REAL_PAIR_ROWS}"
        )
    if (
        not math.isfinite(max_peak_rss_mb)
        or max_peak_rss_mb <= 0
        or max_peak_rss_mb > MAXIMUM_PEAK_RSS_MB
    ):
        raise ValueError("maximum peak RSS exceeds the hard scale resource contract")
    if (
        interrupt_after_new_partitions is not None
        and interrupt_after_new_partitions < 1
    ):
        raise ValueError("interrupt partition count must be positive")
    if (previous_manifest_path is None) != (previous_root is None):
        raise ValueError("previous manifest and root must be provided together")
    import pyarrow as pa  # type: ignore

    if pa.__version__ != CANONICAL_PYARROW_VERSION:
        raise RuntimeError(
            "canonical C2B export requires PyArrow "
            f"{CANONICAL_PYARROW_VERSION}, found {pa.__version__}"
        )
    output_root.parent.mkdir(parents=True, exist_ok=True)
    output_parent_identity = _stable_directory_identity(output_root.parent)
    staging_root = output_root.parent / f".{output_root.name}.work"
    if staging_root.is_symlink():
        raise ValueError("build work root must not be a symlink")
    if staging_root.exists():
        if not staging_root.is_dir():
            raise ValueError("build work root must be a real directory")
        _, _, unsafe_work_inventory = _work_inventory_paths(
            staging_root,
            max_files=MAXIMUM_PACKAGE_FILES,
            max_directories=MAXIMUM_PACKAGE_DIRECTORIES,
            max_depth=MAXIMUM_PACKAGE_DEPTH,
            max_path_bytes=MAXIMUM_PACKAGE_PATH_BYTES,
        )
        if unsafe_work_inventory:
            raise ValueError("build work directory contains a symlink or special file")

    started = time.monotonic()
    source_proof = load_source_proof(
        db_path=db_path,
        source_manifest_path=source_manifest_path,
        source_validation_path=source_validation_path,
    )
    identity_resolver_proof = load_identity_resolver_audit(identity_resolver_audit_path)
    identity_companion_proof = load_identity_companion_proof(
        root=identity_companion_root,
        manifest_path=identity_companion_manifest_path,
        validation_path=identity_companion_validation_path,
        source_db_path=identity_source_db_path,
        config_path=identity_config_path,
        pair_plan_db_path=db_path,
        max_peak_rss_mb=max_peak_rss_mb,
    )
    if identity_companion_proof["contract_date"] != source_proof["contract_date"]:
        raise ValueError("identity companion contract date differs from C2B source")
    previous_validated_manifest_sha256: str | None = None
    if previous_manifest_path is not None and previous_root is not None:
        from .outcome_pair_partition_validation import (
            validate_outcome_pair_partitions,
        )

        previous_validation = validate_outcome_pair_partitions(
            root=previous_root,
            manifest_path=previous_manifest_path,
            source_db_path=db_path,
            source_manifest_path=source_manifest_path,
            source_validation_path=source_validation_path,
            identity_source_db_path=identity_source_db_path,
            identity_config_path=identity_config_path,
            min_rows=min_rows,
            max_peak_rss_mb=max_peak_rss_mb,
            require_source_parity=True,
        )
        if previous_validation["status"] != "ok":
            failed = [
                key
                for key, passed in previous_validation["checks"].items()
                if not passed
            ]
            raise ValueError(
                "previous C2B package failed independent validation: "
                + ", ".join(failed)
            )
        previous_validated_manifest_sha256 = str(previous_validation["manifest_sha256"])
    contract_date = str(source_proof["contract_date"])
    scan_started = time.monotonic()
    partitions, scan_totals = scan_partitions(
        db_path,
        contract_date=contract_date,
        pipeline_key=str(source_proof["pipeline_key"]),
        expected_database_identity=source_proof["database_identity"],
    )
    scan_seconds = time.monotonic() - scan_started
    partition_row_counts = [int(item["rows"]) for item in partitions]
    if not (
        len(partitions) == EXPECTED_PAIR_PARTITIONS
        and partition_row_counts
        and min(partition_row_counts) == EXPECTED_MIN_PARTITION_ROWS
        and max(partition_row_counts) == EXPECTED_MAX_PARTITION_ROWS
        and sum(partition_row_counts) == EXPECTED_SOURCE_COUNTS["pairs"]
    ):
        raise ValueError("C2B partition shape differs from the pinned real contract")
    if int(identity_companion_proof["parquet_bytes"]) > MAXIMUM_IDENTITY_PARQUET_BYTES:
        raise ValueError("identity companion exceeds the hard byte contract")
    writer_contract = {
        "library": "pyarrow",
        "library_version": CANONICAL_PYARROW_VERSION,
        "parquet_format_version": "2.6",
        "data_page_version": "1.0",
        "compression_level": CANONICAL_COMPRESSION_LEVEL,
        "use_dictionary": True,
        "write_statistics": True,
        "physical_replay": "byte_exact_only_when_checksum_reused",
        "semantic_replay": "canonical_row_root_exact",
    }
    desired_partition_contract = {
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
        "row_group_rows": int(row_group_rows),
        "max_file_rows": int(max_file_rows),
        "compression": compression,
        "writer": writer_contract,
    }
    previous_by_id, previous_sha = _previous_partitions(
        previous_manifest_path,
        expected_partition_contract=desired_partition_contract,
    )
    if previous_sha != previous_validated_manifest_sha256:
        raise ValueError("previous manifest changed after independent validation")
    reusable: dict[str, dict[str, Any]] = {}
    for partition in partitions:
        eligible = reusable_partition(
            partition=partition,
            previous=previous_by_id.get(str(partition["partition_id"])),
            previous_root=previous_root,
        )
        if eligible is not None:
            reusable[str(partition["partition_id"])] = eligible

    partition_by_id = {str(item["partition_id"]): item for item in partitions}
    identity_companion_package_paths = {
        f"{IDENTITY_COMPANION_DIRECTORY}/{file_meta['path']}"
        for file_meta in list(identity_companion_proof["inventory"])
    }
    identity_companion_parquet_paths = {
        path for path in identity_companion_package_paths if path.endswith(".parquet")
    }
    build_descriptor = {
        "schema_version": BUILD_DESCRIPTOR_SCHEMA,
        "lane": LANE,
        "transformer_version": TRANSFORMER_VERSION,
        "schema_sha256": OUTCOME_PAIR_CONTRACT.schema_sha256,
        "source_database_sha256": source_proof["database_sha256"],
        "source_manifest_sha256": source_proof["manifest_sha256"],
        "source_validation_sha256": source_proof["validation_sha256"],
        "identity_resolver_audit_sha256": identity_resolver_proof["sha256"],
        "identity_companion_manifest_sha256": identity_companion_proof[
            "manifest_sha256"
        ],
        "identity_companion_validation_sha256": identity_companion_proof[
            "validation_sha256"
        ],
        "identity_companion_semantic_root_sha256": identity_companion_proof[
            "package_semantic_root_sha256"
        ],
        "identity_companion_inventory_root_sha256": identity_companion_proof[
            "inventory_root_sha256"
        ],
        "identity_source_database_sha256": identity_companion_proof[
            "source_database_sha256"
        ],
        "identity_config_sha256": identity_companion_proof["config_sha256"],
        "source_semantic_root_sha256": source_proof["semantic_root_sha256"],
        "partition_input_root_sha256": _aggregate_partition_root(partitions),
        "partition_contract": desired_partition_contract,
        "partitions": len(partitions),
        "rows": int(scan_totals["rows"]),
        "minimum_rows_gate": int(min_rows),
        "maximum_peak_rss_mb": float(max_peak_rss_mb),
        "hard_caps": {
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
        },
        "implementation": {
            "transformer_sha256": sha256_file(Path(__file__)),
            "partition_writer_sha256": sha256_file(
                Path(__file__).with_name("semantic_parquet_io.py")
            ),
        },
        "previous_manifest_sha256": previous_sha,
    }
    descriptor_sha256 = _canonical_sha256(build_descriptor)
    descriptor_path = staging_root / ".build-descriptor.json"
    bundled_identity_audit = staging_root / "control" / "identity-resolver-audit.json"
    resumed_build = False
    descriptor_temps_recovered = 0
    identity_audit_copy_recovered = False
    completed: dict[str, dict[str, Any]] = {}
    if staging_root.is_symlink():
        raise ValueError("build work root must not be a symlink")
    if staging_root.exists():
        if not staging_root.is_dir():
            raise ValueError("build work root must be a real directory")
        _, _, unsafe_work_inventory = _work_inventory_paths(
            staging_root,
            max_files=MAXIMUM_PACKAGE_FILES,
            max_directories=MAXIMUM_PACKAGE_DIRECTORIES,
            max_depth=MAXIMUM_PACKAGE_DEPTH,
            max_path_bytes=MAXIMUM_PACKAGE_PATH_BYTES,
        )
        if unsafe_work_inventory:
            raise ValueError("build work directory contains a symlink or special file")
        descriptor_temps_recovered = _discard_interrupted_descriptor_temps(staging_root)
        if not descriptor_path.is_file():
            if any(staging_root.iterdir()):
                raise ValueError("build work directory lacks an immutable descriptor")
            _atomic_write_json(
                descriptor_path,
                {**build_descriptor, "descriptor_sha256": descriptor_sha256},
            )
        existing_descriptor = _load_json_object(descriptor_path)
        expected_descriptor = {
            **build_descriptor,
            "descriptor_sha256": descriptor_sha256,
        }
        if existing_descriptor != expected_descriptor:
            raise ValueError("build descriptor drifted; existing work was preserved")
        resumed_build = True
        completed = _load_build_checkpoints(
            staging_root=staging_root,
            descriptor_sha256=descriptor_sha256,
            partition_by_id=partition_by_id,
            non_partition_paths=identity_companion_parquet_paths,
        )
        for current_id, saved in completed.items():
            partition_by_id[current_id].update(saved)
    else:
        staging_root.mkdir(parents=True)
        _atomic_write_json(
            descriptor_path,
            {**build_descriptor, "descriptor_sha256": descriptor_sha256},
        )
    bundled_identity_audit.parent.mkdir(parents=True, exist_ok=True)
    if (
        bundled_identity_audit.exists()
        and sha256_file(bundled_identity_audit) != identity_resolver_proof["sha256"]
    ):
        bundled_identity_audit.unlink()
        identity_audit_copy_recovered = True
    if not bundled_identity_audit.exists():
        _atomic_copy_verified(
            identity_resolver_audit_path,
            bundled_identity_audit,
            identity_resolver_proof["sha256"],
        )
    identity_companion_files_recovered = _copy_identity_companion(
        source_root=identity_companion_root,
        source_validation_path=identity_companion_validation_path,
        staging_root=staging_root,
        proof=identity_companion_proof,
    )
    _clean_or_reject_work_inventory(
        staging_root=staging_root,
        completed=completed,
        identity_companion_paths=identity_companion_package_paths,
    )
    hardlinks = 0
    copies = 0
    newly_checkpointed = 0

    def checkpoint_new_partition(partition: dict[str, Any]) -> None:
        nonlocal newly_checkpointed
        _fsync_partition_files(
            staging_root=staging_root,
            partition=partition,
        )
        _write_partition_checkpoint(
            staging_root=staging_root,
            descriptor_sha256=descriptor_sha256,
            partition=partition,
        )
        newly_checkpointed += 1
        if (
            interrupt_after_new_partitions is not None
            and newly_checkpointed >= interrupt_after_new_partitions
        ):
            raise RuntimeError(
                "intentional checkpoint interruption after durable partition boundary"
            )

    try:
        for current_id, previous in reusable.items():
            if current_id in completed:
                continue
            partition = partition_by_id[current_id]
            files, modes = reuse_partition_files(
                previous=previous,
                previous_root=Path(previous_root),
                staging_root=staging_root,
                partition=partition,
                allow_hardlink=False,
            )
            partition["files"] = files
            partition["materialization"] = "reused"
            checkpoint_new_partition(partition)
            hardlinks += modes["hardlink"]
            copies += modes["copy"]

        export_started = time.monotonic()
        active_id: str | None = None
        active_writer: PartitionWriter | None = None
        available_partition_ids = set(reusable) | set(completed)
        if len(available_partition_ids) < len(partitions):
            for row in iter_public_pair_rows(
                db_path,
                pipeline_key=str(source_proof["pipeline_key"]),
                expected_database_identity=source_proof["database_identity"],
            ):
                current_id = partition_id(partition_key(row))
                if current_id != active_id:
                    if active_writer is not None:
                        partition_by_id[str(active_id)]["files"] = active_writer.close()
                        partition_by_id[str(active_id)]["materialization"] = "rebuilt"
                        checkpoint_new_partition(partition_by_id[str(active_id)])
                    active_id = current_id
                    active_writer = (
                        None
                        if current_id in available_partition_ids
                        else PartitionWriter(
                            root=staging_root,
                            partition=partition_by_id[current_id],
                            contract=OUTCOME_PAIR_CONTRACT,
                            compression=compression,
                            row_group_rows=row_group_rows,
                            max_file_rows=max_file_rows,
                            compression_level=CANONICAL_COMPRESSION_LEVEL,
                        )
                    )
                if active_writer is not None:
                    active_writer.append(row)
            if active_writer is not None:
                partition_by_id[str(active_id)]["files"] = active_writer.close()
                partition_by_id[str(active_id)]["materialization"] = "rebuilt"
                checkpoint_new_partition(partition_by_id[str(active_id)])
        export_seconds = time.monotonic() - export_started

        try:
            with bound_regular_file(db_path, database=True) as final_database:
                source_database_unchanged = (
                    final_database.identity == source_proof["database_identity"]
                    and final_database.sha256() == source_proof["database_sha256"]
                )
        except (OSError, RuntimeError):
            source_database_unchanged = False
        source_artifacts_unchanged = (
            source_database_unchanged
            and sha256_file(source_manifest_path) == source_proof["manifest_sha256"]
            and sha256_file(source_validation_path) == source_proof["validation_sha256"]
            and sha256_file(identity_resolver_audit_path)
            == identity_resolver_proof["sha256"]
            and sha256_file(identity_companion_manifest_path)
            == identity_companion_proof["manifest_sha256"]
            and sha256_file(identity_companion_validation_path)
            == identity_companion_proof["validation_sha256"]
            and sha256_file(identity_source_db_path)
            == identity_companion_proof["source_database_sha256"]
            and sha256_file(identity_config_path)
            == identity_companion_proof["config_sha256"]
            and _canonical_sha256(
                _identity_companion_inventory(
                    root=identity_companion_root,
                    manifest=_load_json_object(identity_companion_manifest_path),
                )
            )
            == identity_companion_proof["inventory_root_sha256"]
            and (
                previous_manifest_path is None
                or sha256_file(previous_manifest_path)
                == previous_validated_manifest_sha256
            )
            and not (
                Path(f"{db_path}-wal").exists()
                and Path(f"{db_path}-wal").stat().st_size
            )
        )

        rows = int(scan_totals["rows"])
        files = sum(len(list(item.get("files") or [])) for item in partitions)
        parquet_bytes = sum(
            int(file_meta["bytes"])
            for item in partitions
            for file_meta in list(item.get("files") or [])
        )
        largest_pair_file_bytes = max(
            int(file_meta["bytes"])
            for item in partitions
            for file_meta in list(item.get("files") or [])
        )
        pair_layout_exact = (
            len(partitions) == EXPECTED_PAIR_PARTITIONS
            and files == EXPECTED_PAIR_FILES
            and all(
                len(list(item.get("files") or [])) == 1
                and int(next(iter(item["files"]))["rows"]) == int(item["rows"])
                and 0 < int(item["rows"]) <= CANONICAL_ROW_GROUP_ROWS
                for item in partitions
            )
        )
        portable_parquet_bytes = parquet_bytes + int(
            identity_companion_proof["parquet_bytes"]
        )
        hard_byte_contract = (
            largest_pair_file_bytes <= MAXIMUM_PAIR_FILE_BYTES
            and parquet_bytes <= MAXIMUM_PAIR_PARQUET_BYTES
            and int(identity_companion_proof["parquet_bytes"])
            <= MAXIMUM_IDENTITY_PARQUET_BYTES
            and portable_parquet_bytes <= MAXIMUM_PORTABLE_PARQUET_BYTES
        )
        dataset_interface = validate_pair_dataset_interface(
            root=staging_root,
            partitions=partitions,
            expected_rows=rows,
        )
        source_counts = dict(source_proof["counts"])
        pair_semantic_root = _aggregate_partition_root(partitions)
        physical_inventory = _physical_parquet_inventory(
            partitions=partitions,
            identity_companion_inventory=identity_companion_proof["inventory"],
        )
        physical_inventory_root = _physical_inventory_root(physical_inventory)
        portable_package_root = _canonical_sha256(
            {
                "contract": "outcome_pair_discovery_portable_package_v2",
                "identity_companion_semantic_root_sha256": (
                    identity_companion_proof["package_semantic_root_sha256"]
                ),
                "pair_semantic_root_sha256": pair_semantic_root,
                "physical_inventory_root_sha256": physical_inventory_root,
            }
        )
        peak_rss = peak_rss_mb()
        checks = {
            "source_validation_passed": True,
            "source_artifacts_unchanged": source_artifacts_unchanged,
            "exact_source_pair_count": rows == int(source_counts.get("pairs") or -1),
            "minimum_real_rows": rows >= int(min_rows),
            "source_url_complete": scan_totals["source_url_rows"] == rows,
            "indicator_source_url_complete": scan_totals["indicator_source_url_rows"]
            == rows,
            "official_identity_reference_complete": scan_totals[
                "official_identity_reference_rows"
            ]
            == rows,
            "official_public_names_retained_at_source": int(
                source_counts.get("official_names_source_resolved") or 0
            )
            > 0,
            "member_votes_retained_at_source": int(
                source_counts.get("member_votes_source_resolved") or 0
            )
            > 0,
            "identity_companion_validation_passed": True,
            "exact_member_votes_bundled": identity_companion_proof["counts"][
                "member_vote_rows"
            ]
            == int(source_counts.get("member_votes_source_resolved") or -1),
            "exact_official_names_bundled": identity_companion_proof["counts"][
                "distinct_official_names"
            ]
            == int(source_counts.get("official_names_source_resolved") or -1),
            "exact_action_projections_bundled": identity_companion_proof["counts"][
                "actions"
            ]
            == int(source_counts.get("actions") or -1),
            "identity_companion_inventory_exact": bool(
                identity_companion_proof["inventory"]
            ),
            "no_private_tokens": scan_totals["private_token_findings"] == 0,
            "association_claims_zero": True,
            "causal_claims_zero": True,
            "effect_estimates_zero": True,
            "ranking_eligible_rows_zero": scan_totals["ranking_eligible_rows"] == 0,
            "publication_eligible_rows_zero": scan_totals["publication_eligible_rows"]
            == 0,
            "bounded_file_rows": all(
                int(meta["rows"]) <= int(max_file_rows)
                for item in partitions
                for meta in list(item.get("files") or [])
            ),
            "bounded_peak_rss": peak_rss <= float(max_peak_rss_mb),
            "hard_resource_contract": (
                row_group_rows == CANONICAL_ROW_GROUP_ROWS
                and max_file_rows == CANONICAL_MAX_FILE_ROWS
                and compression == CANONICAL_COMPRESSION
                and pa.__version__ == CANONICAL_PYARROW_VERSION
                and max_peak_rss_mb <= MAXIMUM_PEAK_RSS_MB
            ),
            "exact_canonical_pair_layout": pair_layout_exact,
            "hard_byte_contract": hard_byte_contract,
            "downstream_hive_dataset_compatible": dataset_interface["rows"] == rows,
        }
        package_gate = all(checks.values())
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "contract_date": contract_date,
            "lane": LANE,
            "transformer_version": TRANSFORMER_VERSION,
            "schema": OUTCOME_PAIR_CONTRACT.schema,
            "schema_sha256": OUTCOME_PAIR_CONTRACT.schema_sha256,
            "partition_contract": desired_partition_contract,
            "datasets": {
                "pairs": dataset_interface,
                "identity_member_votes": {
                    "path": (f"{IDENTITY_COMPANION_DIRECTORY}/member_vote_identities"),
                    "format": "parquet",
                    "rows": identity_companion_proof["counts"]["member_vote_rows"],
                },
                "identity_action_participant_projections": {
                    "path": (
                        f"{IDENTITY_COMPANION_DIRECTORY}/action_participant_projections"
                    ),
                    "format": "parquet",
                    "rows": identity_companion_proof["counts"]["actions"],
                },
            },
            "incremental_contract": {
                "input_fingerprint": "sha256_canonical_internal_rows",
                "reuse_key": [
                    "partition_id",
                    "input_sha256",
                    "schema_sha256",
                    "transformer_version",
                    "partition_contract",
                ],
                "previous_manifest_sha256": previous_sha,
                "partitions_reused": len(reusable),
                "partitions_rebuilt": len(partitions) - len(reusable),
                "partitions_checkpoint_resumed": len(completed),
                "files_hardlinked": hardlinks,
                "files_copied": copies,
            },
            "restart_contract": {
                "schema_version": BUILD_DESCRIPTOR_SCHEMA,
                "descriptor_sha256": descriptor_sha256,
                "partition_checkpoint_schema_version": PARTITION_CHECKPOINT_SCHEMA,
                "partition_checkpoint_root_sha256": _partition_checkpoint_root(
                    partitions
                ),
                "checkpoint_granularity": "completed_semantic_partition",
                "resumed_build": resumed_build,
                "partitions_recovered_from_checkpoints": len(completed),
                "incomplete_partition_files_removed_on_resume": True,
                "config_or_source_drift_fails_closed": True,
                "work_preserved_on_failure": True,
                "interrupted_descriptor_temps_recovered": (descriptor_temps_recovered),
                "invalid_identity_audit_copy_recovered": (
                    identity_audit_copy_recovered
                ),
                "identity_companion_files_recovered": (
                    identity_companion_files_recovered
                ),
            },
            "source": {
                "database_file": db_path.name,
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
                "identity_companion_manifest_root_sha256": (
                    identity_companion_proof["manifest_root_sha256"]
                ),
                "identity_companion_validation_file": (
                    IDENTITY_COMPANION_VALIDATION_PATH
                ),
                "identity_companion_validation_sha256": identity_companion_proof[
                    "validation_sha256"
                ],
                "identity_companion_semantic_root_sha256": (
                    identity_companion_proof["package_semantic_root_sha256"]
                ),
                "identity_companion_inventory_root_sha256": (
                    identity_companion_proof["inventory_root_sha256"]
                ),
                "identity_source_database_file": identity_source_db_path.name,
                "identity_source_database_sha256": identity_companion_proof[
                    "source_database_sha256"
                ],
                "identity_config_file": identity_config_path.name,
                "identity_config_sha256": identity_companion_proof["config_sha256"],
            },
            "identity_lineage": {
                "storage_model": (
                    "bundled_normalized_exact_member_vote_identity_companion"
                ),
                "authoritative_source_table": "parl_vote_member_votes",
                "source_component_root_sha256": source_proof["input_component_roots"][
                    "members"
                ],
                "source_member_vote_rows": int(
                    source_counts.get("member_votes_source_resolved") or 0
                ),
                "source_distinct_official_names": int(
                    source_counts.get("official_names_source_resolved") or 0
                ),
                "join_contract": {
                    "pair_fields": ["source_id", "action_id"],
                    "identity_companion_fields": ["source_id", "action_id"],
                    "cardinality": "one_action_to_many_member_votes",
                    "source_table_alias": "parl_vote_member_votes.vote_event_id -> action_id",
                },
                "projection_contract": {
                    "version": "outcome_pair_plan_action_participant_projection_v1",
                    "ordering": ["action_id", "member_vote_id"],
                    "fields": MEMBER_PROJECTION_FIELDS,
                    "row_encoding": "canonical_json_utf8_length_prefixed_u64_be",
                    "root_encoding": "canonical_json_of_contract_row_count_and_stream_sha256",
                    "row_reference_field": "participant_projection_sha256",
                },
                "public_name_policy": "retain_exact_official_member_name",
                "portable_exact_source_identity_dimension": True,
                "exact_source_participant_projection_bundled": True,
                "identity_companion_path": IDENTITY_COMPANION_DIRECTORY,
                "identity_companion_manifest_root_sha256": (
                    identity_companion_proof["manifest_root_sha256"]
                ),
                "identity_companion_semantic_root_sha256": (
                    identity_companion_proof["package_semantic_root_sha256"]
                ),
                "identity_companion_member_rows_root_sha256": (
                    identity_companion_proof["roots"]["member_rows_root_sha256"]
                ),
                "identity_companion_official_names_root_sha256": (
                    identity_companion_proof["roots"]["official_names_root_sha256"]
                ),
                "identity_companion_action_rows_root_sha256": (
                    identity_companion_proof["roots"]["action_rows_root_sha256"]
                ),
                "identity_companion_member_vote_rows": (
                    identity_companion_proof["counts"]["member_vote_rows"]
                ),
                "identity_companion_distinct_official_names": (
                    identity_companion_proof["counts"]["distinct_official_names"]
                ),
                "identity_companion_actions": identity_companion_proof["counts"][
                    "actions"
                ],
                "durable_remote_identity_origin": False,
                "durable_action_locator_available": True,
                "resolver_audit_path": "control/identity-resolver-audit.json",
                "resolver_audit_sha256": identity_resolver_proof["sha256"],
                "resolver_action_resolution_root_sha256": (
                    identity_resolver_proof["roots"]["action_resolution_root_sha256"]
                ),
                "resolver_count_mismatch_root_sha256": (
                    identity_resolver_proof["roots"]["count_mismatch_root_sha256"]
                ),
                "resolver_member_vote_rows": identity_resolver_proof["counts"][
                    "resolver_member_votes"
                ],
                "resolver_distinct_official_names": identity_resolver_proof["counts"][
                    "resolver_distinct_official_names"
                ],
                "durable_action_locator_registry": "docs/etl/real-corpus-registry.json#member_votes",
                "durable_action_locator_manifest": "etl/data/published/member-vote-shard-manifest-latest.json",
                "secondary_action_locator_limitation": (
                    "All action IDs resolve, but 64 action member counts differ from "
                    "the pinned C2B source; use the bundled exact identity companion "
                    "for participant resolution."
                ),
            },
            "policy": {
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
            },
            "totals": {
                **scan_totals,
                "actions": int(source_counts.get("actions") or 0),
                "series": int(source_counts.get("series") or 0),
                "distinct_official_names_at_source": int(
                    source_counts.get("official_names_source_resolved") or 0
                ),
                "member_votes_at_source": int(
                    source_counts.get("member_votes_source_resolved") or 0
                ),
                "partitions": len(partitions),
                "pair_files": files,
                "identity_companion_files": int(
                    identity_companion_proof["counts"]["member_files"]
                )
                + int(identity_companion_proof["counts"]["action_files"]),
                "files": files
                + int(identity_companion_proof["counts"]["member_files"])
                + int(identity_companion_proof["counts"]["action_files"]),
                "pair_parquet_bytes": parquet_bytes,
                "identity_companion_parquet_bytes": identity_companion_proof[
                    "parquet_bytes"
                ],
                "parquet_bytes": portable_parquet_bytes,
                "identity_companion_member_vote_rows": identity_companion_proof[
                    "counts"
                ]["member_vote_rows"],
                "identity_companion_distinct_official_names": (
                    identity_companion_proof["counts"]["distinct_official_names"]
                ),
                "identity_companion_actions": identity_companion_proof["counts"][
                    "actions"
                ],
            },
            "semantic_root_sha256": pair_semantic_root,
            "physical_inventory_root_sha256": physical_inventory_root,
            "portable_package_root_sha256": portable_package_root,
            "checks": checks,
            "local_package_gate_passed": package_gate,
            "independent_validation_passed": False,
            "promotion_checks": {
                "local_package_gate": package_gate,
                "full_l1_candidate_materialization": False,
                "real_human_review": False,
                "durable_remote_origin": False,
                "isolated_remote_restore": False,
                "publication_authorized": False,
            },
            "promotion_gate_passed": False,
            "publication_status": "internal_l0_pre_l1_not_publication_eligible",
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
                "Rows enumerate real action-indicator discovery pairs; they are not outcome, association, effect, merit, blame, or corruption claims.",
                "Public participant names and exact member-vote rows are bundled once in a normalized identity companion; pair rows resolve by action_id without duplicating names millions of times.",
                "Local Parquet packaging and unchanged-partition replay do not prove durable remote origin, isolated remote restore, human review, or publication eligibility.",
            ],
        }
        manifest["manifest_root_sha256"] = _canonical_sha256(manifest)
        if not package_gate:
            failed = [key for key, passed in checks.items() if not passed]
            raise RuntimeError("outcome-pair package gate failed: " + ", ".join(failed))
        _atomic_write_json(staging_root / "manifest.json", manifest)
        _atomic_write_json(
            staging_root / "build-checkpoint.json",
            {
                "schema_version": "outcome_pair_discovery_build_checkpoint_v1",
                "status": "complete",
                "descriptor_sha256": descriptor_sha256,
                "partition_checkpoint_root_sha256": manifest["restart_contract"][
                    "partition_checkpoint_root_sha256"
                ],
                "partitions": len(partitions),
                "rows": rows,
                "source_artifacts_unchanged": source_artifacts_unchanged,
            },
        )
        _assert_final_inventory(
            staging_root=staging_root,
            partitions=partitions,
            identity_companion_paths=identity_companion_package_paths,
        )
        _assert_directory_identity(output_root.parent, output_parent_identity)
        if output_root.exists() or output_root.is_symlink():
            raise FileExistsError(output_root)
        parent_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        if hasattr(os, "O_NOFOLLOW"):
            parent_flags |= os.O_NOFOLLOW
        parent_fd = os.open(output_root.parent, parent_flags)
        try:
            parent_stat = os.fstat(parent_fd)
            if (int(parent_stat.st_dev), int(parent_stat.st_ino)) != (
                output_parent_identity
            ):
                raise RuntimeError("output parent changed before package promotion")
            os.rename(
                staging_root.name,
                output_root.name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        _fsync_directory(output_root.parent)
    except BaseException:
        _fsync_directory(staging_root.parent)
        raise
    return manifest


def export_outcome_pair_partitions(
    *,
    db_path: Path,
    source_manifest_path: Path,
    source_validation_path: Path,
    identity_resolver_audit_path: Path,
    identity_source_db_path: Path,
    identity_config_path: Path,
    identity_companion_root: Path,
    identity_companion_manifest_path: Path,
    identity_companion_validation_path: Path,
    output_root: Path,
    compression: str = "zstd",
    row_group_rows: int = 25_000,
    max_file_rows: int = 100_000,
    previous_manifest_path: Path | None = None,
    previous_root: Path | None = None,
    min_rows: int = 1_000_000,
    max_peak_rss_mb: float = 1024.0,
    interrupt_after_new_partitions: int | None = None,
) -> dict[str, Any]:
    """Export while excluding concurrent writers for this exact output root."""

    validate_export_path_separation(
        db_path=Path(db_path),
        source_manifest_path=Path(source_manifest_path),
        source_validation_path=Path(source_validation_path),
        identity_resolver_audit_path=Path(identity_resolver_audit_path),
        identity_source_db_path=Path(identity_source_db_path),
        identity_config_path=Path(identity_config_path),
        identity_companion_root=Path(identity_companion_root),
        identity_companion_manifest_path=Path(identity_companion_manifest_path),
        identity_companion_validation_path=Path(identity_companion_validation_path),
        output_root=Path(output_root),
        previous_manifest_path=(
            Path(previous_manifest_path) if previous_manifest_path is not None else None
        ),
        previous_root=Path(previous_root) if previous_root is not None else None,
    )
    with outcome_pair_build_lease(Path(output_root), namespace="build"):
        return _export_outcome_pair_partitions_unlocked(
            db_path=db_path,
            source_manifest_path=source_manifest_path,
            source_validation_path=source_validation_path,
            identity_resolver_audit_path=identity_resolver_audit_path,
            identity_source_db_path=identity_source_db_path,
            identity_config_path=identity_config_path,
            identity_companion_root=identity_companion_root,
            identity_companion_manifest_path=identity_companion_manifest_path,
            identity_companion_validation_path=(identity_companion_validation_path),
            output_root=output_root,
            compression=compression,
            row_group_rows=row_group_rows,
            max_file_rows=max_file_rows,
            previous_manifest_path=previous_manifest_path,
            previous_root=previous_root,
            min_rows=min_rows,
            max_peak_rss_mb=max_peak_rss_mb,
            interrupt_after_new_partitions=interrupt_after_new_partitions,
        )


__all__ = [
    "CANONICAL_COMPRESSION_LEVEL",
    "LANE",
    "MAXIMUM_PACKAGE_DEPTH",
    "MAXIMUM_PACKAGE_DIRECTORIES",
    "MAXIMUM_PACKAGE_FILES",
    "MAXIMUM_PACKAGE_PATH_BYTES",
    "MAXIMUM_PAIR_BATCH_BYTES",
    "MAXIMUM_PAIR_COLUMN_UNCOMPRESSED_BYTES",
    "MAXIMUM_PAIR_ROW_GROUP_UNCOMPRESSED_BYTES",
    "MAXIMUM_PAIR_STRING_BYTES",
    "OUTCOME_PAIR_CONTRACT",
    "PAIR_SQL",
    "TRANSFORMER_VERSION",
    "export_outcome_pair_partitions",
    "iter_public_pair_rows",
    "load_identity_companion_proof",
    "load_source_proof",
    "outcome_pair_build_lease",
    "outcome_pair_lease_path",
    "partition_id",
    "partition_key",
    "public_pair_row",
    "scan_partitions",
    "secure_atomic_write_bytes",
    "secure_atomic_write_json",
    "secure_unlink_control",
]
