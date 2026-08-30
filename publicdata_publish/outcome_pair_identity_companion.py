"""Build exact real Senate participant identities for the pinned C2B corpus.

This internal L0 companion retains every official public member-vote identity.
It never publishes, ranks, attributes merit or blame, or makes causal claims.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import shutil
import sqlite3
import struct
from collections.abc import Iterator, Sequence
from contextlib import ExitStack, nullcontext
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .outcome_pair_identity_safety import (
    BoundRegularFile,
    FileIdentity,
    assert_regular_file_stable,
    bound_regular_file,
    fsync_directory,
    fsync_regular_file,
    identity_companion_leases,
    preflight_output_root,
    require_bounded_finite_float,
    require_exact_int,
    stable_regular_file_fact,
)
from .semantic_contracts import SemanticLaneContract, peak_rss_mb, sha256_file

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "etl/data/manual/outcome_links/planner_scope_c2b_v1.json"
DEFAULT_SOURCE_DB = REPO_ROOT / "etl/data/staging/politicos-es.db"
DEFAULT_PAIR_PLAN_DB = (
    REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1.db"
)

MANIFEST_SCHEMA_VERSION = "outcome_pair_identity_companion_manifest_v1"
TRANSFORMER_VERSION = "outcome_pair_identity_companion_internal_v1"
MEMBER_ROW_CONTRACT_VERSION = "outcome_pair_identity_companion_member_row_v1"
ACTION_ROW_CONTRACT_VERSION = "outcome_pair_identity_companion_action_row_v1"
PACKAGE_ROOT_CONTRACT_VERSION = "outcome_pair_identity_companion_package_root_v1"

EXPECTED_CONFIG_FILE_SHA256 = (
    "e29b579c07bb20c57d35acd61dfce1f92a55aa461a0350500fea86e5de58511d"
)
EXPECTED_CONFIG_CANONICAL_SHA256 = (
    "7079f1d2faaeb7a3cd8176cf556c92b945246be85814d9a819cb8055927c195b"
)
EXPECTED_SOURCE_DATABASE_SHA256 = (
    "46e72488f24bbecc240ac94c524fe503b8599d742c983595919678a842c5f0e3"
)
EXPECTED_SOURCE_DATABASE_BYTES = 1_575_038_976
EXPECTED_PAIR_PLAN_DATABASE_SHA256 = (
    "04c8265154bf6659971b732db135f07fe6db0d45a0482d775bb30c15bde57680"
)
EXPECTED_PAIR_PLAN_DATABASE_BYTES = 3_587_743_744
EXPECTED_PAIR_PLAN_PIPELINE_KEY = (
    "vclc:outcome-pair-plan-c2b-pipeline:294c93befa7e73b46c84355d"
)
EXPECTED_MEMBER_COMPONENT_ROOT_SHA256 = (
    "95aac5313afd057f042d7c1d39a7cfc8b20db8522eff591fff52f84774cf1631"
)
EXPECTED_MEMBER_ROWS_ROOT_SHA256 = (
    "36777c1cc04f2021fdf0e5bbb196d971f2cc8a5a091678d2cce6fefc65a95c6a"
)
EXPECTED_ACTION_ROWS_ROOT_SHA256 = (
    "d8942201554983fc495df34334fcf555d5c2358ed3b8329b211d4555ba39bd9f"
)
EXPECTED_OFFICIAL_NAMES_ROOT_SHA256 = (
    "00a32036f831169dbf975958097558462961414f8b71b630388bd1296219f439"
)
EXPECTED_PACKAGE_SEMANTIC_ROOT_SHA256 = (
    "e6891375adfabf8a6a89f0c3691eff7f895856817cdb036d6def98b9d37c2a4e"
)
EXPECTED_MEMBER_ROWS = 119_116
EXPECTED_OFFICIAL_NAMES = 490
EXPECTED_ACTIONS = 458
EXPECTED_ACTION_YEARS = (2020, 2021, 2022, 2023, 2024)

CANONICAL_COMPRESSION = "zstd"
CANONICAL_COMPRESSION_LEVEL = 1
CANONICAL_ROW_GROUP_ROWS = 5_000
CANONICAL_MAX_FILE_ROWS = 25_000
CANONICAL_SOURCE_PAGE_SIZE = 25_000
CANONICAL_PYARROW_VERSION = "20.0.0"
CANONICAL_PARQUET_CREATED_BY = "parquet-cpp-arrow version 20.0.0"
CANONICAL_PARQUET_FORMAT_VERSION = "2.6"
CANONICAL_DATA_PAGE_VERSION = "1.0"
CANONICAL_WRITE_BATCH_SIZE = 1_024
CANONICAL_DICTIONARY_PAGE_SIZE_LIMIT = 1_048_576
MAXIMUM_PEAK_RSS_MB = 512.0
MAX_PARQUET_FILE_BYTES = 128 * 1024 * 1024
MAX_PACKAGE_PARQUET_BYTES = 1024 * 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
SCRATCH_CACHE_KIB = 32 * 1024

MEMBER_PROJECTION_FIELDS = (
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
)
MEMBER_PROJECTION_FIELD_MAP = {
    "action_id": "action_id",
    "member_vote_id": "member_vote_id",
    "seat": "seat",
    "member_name": "member_name",
    "member_name_normalized": "member_name_normalized",
    "person_id": "person_id",
    "group_code": "group_code",
    "vote_choice": "vote_choice",
    "source_id": "source_id",
    "source_url": "member_source_url",
    "source_snapshot_date": "source_snapshot_date",
}

POLICY = {
    "real_data_only": True,
    "official_public_identities_retained": True,
    "identity_dimension": "exact_official_member_vote_rows",
    "evidence_level": "L0",
    "companion_state": "internal_identity_companion",
    "association_assessment": "not_assessed",
    "causal_assessment": "not_assessed",
    "effect_estimate_state": "not_computed",
    "political_merit_or_blame": "not_assessed",
    "corruption_assessment": "not_assessed",
    "ranking_eligible": False,
    "publication_eligible": False,
    "internal_companion_only": True,
}

MEMBER_CONTRACT = SemanticLaneContract(
    lane="outcome_pair_identity_companion_member_votes",
    transformer_version=TRANSFORMER_VERSION,
    id_column="member_vote_id",
    year_column="action_year",
    schema=(
        {"name": "member_vote_id", "type": "int64", "nullable": False},
        {"name": "action_id", "type": "string", "nullable": False},
        {"name": "action_date", "type": "string", "nullable": False},
        {"name": "action_year", "type": "int64", "nullable": False},
        {"name": "action_label", "type": "string", "nullable": False},
        {"name": "official_action_url", "type": "string", "nullable": False},
        {"name": "action_source_page_url", "type": "string", "nullable": False},
        {"name": "action_source_record_pk", "type": "int64", "nullable": False},
        {"name": "action_source_record_id", "type": "string", "nullable": False},
        {
            "name": "action_source_record_content_sha256",
            "type": "string",
            "nullable": False,
        },
        {"name": "seat", "type": "string", "nullable": False},
        {"name": "member_name", "type": "string", "nullable": False},
        {"name": "member_name_normalized", "type": "string", "nullable": False},
        {"name": "person_id", "type": "string", "nullable": False},
        {"name": "group_code", "type": "string", "nullable": False},
        {"name": "vote_choice", "type": "string", "nullable": False},
        {"name": "source_id", "type": "string", "nullable": False},
        {"name": "member_source_url", "type": "string", "nullable": False},
        {"name": "source_snapshot_date", "type": "string", "nullable": False},
        {"name": "evidence_level", "type": "string", "nullable": False},
        {"name": "companion_state", "type": "string", "nullable": False},
        {"name": "ranking_eligible", "type": "int64", "nullable": False},
        {"name": "publication_eligible", "type": "int64", "nullable": False},
        {"name": "row_semantic_sha256", "type": "string", "nullable": False},
    ),
)

ACTION_CONTRACT = SemanticLaneContract(
    lane="outcome_pair_identity_companion_action_projections",
    transformer_version=TRANSFORMER_VERSION,
    id_column="action_id",
    year_column="action_year",
    schema=(
        {"name": "action_id", "type": "string", "nullable": False},
        {"name": "action_date", "type": "string", "nullable": False},
        {"name": "action_year", "type": "int64", "nullable": False},
        {"name": "action_label", "type": "string", "nullable": False},
        {"name": "source_id", "type": "string", "nullable": False},
        {"name": "official_action_url", "type": "string", "nullable": False},
        {"name": "action_source_page_url", "type": "string", "nullable": False},
        {"name": "action_source_record_pk", "type": "int64", "nullable": False},
        {"name": "action_source_record_id", "type": "string", "nullable": False},
        {
            "name": "action_source_record_content_sha256",
            "type": "string",
            "nullable": False,
        },
        {"name": "source_snapshot_date", "type": "string", "nullable": False},
        {"name": "member_vote_count", "type": "int64", "nullable": False},
        {"name": "official_name_count", "type": "int64", "nullable": False},
        {
            "name": "participant_projection_sha256",
            "type": "string",
            "nullable": False,
        },
        {"name": "evidence_level", "type": "string", "nullable": False},
        {"name": "companion_state", "type": "string", "nullable": False},
        {"name": "ranking_eligible", "type": "int64", "nullable": False},
        {"name": "publication_eligible", "type": "int64", "nullable": False},
        {"name": "row_semantic_sha256", "type": "string", "nullable": False},
    ),
)

SOURCE_ACTION_SCAN_SQL = """
SELECT v.vote_event_id AS action_id,v.vote_date AS action_date,
       v.title AS action_label,v.source_id,v.source_record_pk,
       sr.source_record_id,sr.source_snapshot_date,
       substr(v.vote_event_id,5) AS official_action_url,
       v.source_url AS source_page_url,
       sr.content_sha256 AS source_record_content_sha256
FROM parl_vote_events v
JOIN source_records sr ON sr.source_record_pk=v.source_record_pk
WHERE v.source_id=? AND sr.source_snapshot_date=?
  AND v.vote_date IS NOT NULL AND trim(v.vote_date)<>''
"""

SOURCE_MEMBER_SCAN_SQL = """
SELECT m.vote_event_id AS action_id,m.member_vote_id,m.seat,m.member_name,
       m.member_name_normalized,CAST(m.person_id AS TEXT) AS person_id,
       m.group_code,m.vote_choice,m.source_id,m.source_url,
       m.source_snapshot_date,CAST(substr(v.vote_date,1,4) AS INTEGER) AS action_year
FROM parl_vote_member_votes m
JOIN parl_vote_events v ON v.vote_event_id=m.vote_event_id
JOIN source_records sr ON sr.source_record_pk=v.source_record_pk
WHERE v.source_id=? AND sr.source_snapshot_date=?
  AND v.vote_date IS NOT NULL AND trim(v.vote_date)<>''
"""

MEMBER_STAGE_ORDER_SQL = """
SELECT action_id,member_vote_id,seat,member_name,member_name_normalized,
       person_id,group_code,vote_choice,source_id,source_url,source_snapshot_date
FROM source_members INDEXED BY source_members_action_idx
ORDER BY action_id,member_vote_id
"""

MEMBER_OUTPUT_ORDER_SQL = """
SELECT m.action_id,m.member_vote_id,m.seat,m.member_name,m.member_name_normalized,
       m.person_id,m.group_code,m.vote_choice,m.source_id,m.source_url,
       m.source_snapshot_date,a.action_date,a.action_label,
       a.source_record_pk,a.source_record_id,a.official_action_url,
       a.source_page_url,a.source_record_content_sha256
FROM source_members AS m INDEXED BY source_members_action_idx
JOIN source_actions AS a ON a.action_id=m.action_id
ORDER BY m.action_id,m.member_vote_id
"""

MEMBER_OUTPUT_YEAR_SQL = """
SELECT m.action_id,m.member_vote_id,m.seat,m.member_name,m.member_name_normalized,
       m.person_id,m.group_code,m.vote_choice,m.source_id,m.source_url,
       m.source_snapshot_date,a.action_date,a.action_label,
       a.source_record_pk,a.source_record_id,a.official_action_url,
       a.source_page_url,a.source_record_content_sha256
FROM source_members AS m INDEXED BY source_members_year_idx
JOIN source_actions AS a ON a.action_id=m.action_id
WHERE m.action_year=?
ORDER BY m.action_id,m.member_vote_id
"""

EXECUTED_ACTION_SCAN_SQL_SHA256 = (
    "6ff7760d3d3868f955c829ed6a4f70a39277fb8818e582040d2ad55d77fa2f7b"
)
EXECUTED_MEMBER_SCAN_SQL_SHA256 = (
    "bea18818da27939d1d37bc7bdd4590640fb94dff331b64cd4cc743f1f2b7e81b"
)


def assert_executed_scan_sql_contract() -> None:
    actual = {
        "actions": hashlib.sha256(SOURCE_ACTION_SCAN_SQL.encode("utf-8")).hexdigest(),
        "members": hashlib.sha256(SOURCE_MEMBER_SCAN_SQL.encode("utf-8")).hexdigest(),
    }
    expected = {
        "actions": EXECUTED_ACTION_SCAN_SQL_SHA256,
        "members": EXECUTED_MEMBER_SCAN_SQL_SHA256,
    }
    if actual != expected:
        raise RuntimeError("executed identity scan SQL drifted from its pinned proof")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json_bytes(payload: bytes) -> dict[str, Any]:
    def reject_nonfinite(value: str) -> None:
        raise ValueError(f"non-finite JSON number is forbidden: {value}")

    value = json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_nonfinite,
    )
    if not isinstance(value, dict):
        raise TypeError("JSON root must be an object")
    return value


def load_json(path: Path) -> dict[str, Any]:
    with bound_regular_file(path) as bound:
        return load_json_bytes(bound.read_bytes(max_bytes=MAX_JSON_BYTES))


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def require_canonical_pyarrow() -> None:
    try:
        import pyarrow  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pyarrow is required; install the project parquet extra"
        ) from exc
    if pyarrow.__version__ != CANONICAL_PYARROW_VERSION:
        raise RuntimeError(
            f"identity companion requires exact PyArrow {CANONICAL_PYARROW_VERSION}"
        )


def stream_hash_add(hasher: Any, value: Any) -> None:
    encoded = canonical_bytes(value)
    hasher.update(struct.pack(">Q", len(encoded)))
    hasher.update(encoded)


def stream_root(contract_version: str, row_count: int, hasher: Any) -> str:
    return canonical_sha256(
        {
            "contract_version": contract_version,
            "row_count": row_count,
            "stream_sha256": hasher.hexdigest(),
        }
    )


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def assert_pinned_real_input_paths(
    source_db_path: Path, config_path: Path, pair_plan_db_path: Path
) -> None:
    expected = (DEFAULT_SOURCE_DB, DEFAULT_CONFIG, DEFAULT_PAIR_PLAN_DB)
    actual = (source_db_path, config_path, pair_plan_db_path)
    try:
        matches = all(
            Path(value).resolve(strict=True) == pinned.resolve(strict=True)
            for value, pinned in zip(actual, expected, strict=True)
        )
    except FileNotFoundError as exc:
        raise RuntimeError("one pinned real identity input is missing") from exc
    if not matches:
        raise RuntimeError(
            "identity companion accepts only pinned canonical real input paths"
        )


def stable_file_fact(path: Path) -> tuple[dict[str, Any], FileIdentity]:
    fact, identity = stable_regular_file_fact(path, database=Path(path).suffix == ".db")
    return {
        "path": repo_path(Path(fact["resolved"])),
        "bytes": int(fact["bytes"]),
        "sha256": str(fact["sha256"]),
        "wal_bytes": 0 if Path(path).suffix == ".db" else None,
    }, identity


def assert_file_stable(path: Path, identity: FileIdentity) -> None:
    assert_regular_file_stable(path, identity, database=Path(path).suffix == ".db")


def open_readonly_database(
    source: Path | BoundRegularFile,
) -> sqlite3.Connection:
    if isinstance(source, BoundRegularFile):
        if FileIdentity.from_stat(os.fstat(source.handle.fileno())) != source.identity:
            raise RuntimeError("bound SQLite descriptor changed before open")
        database_path = f"/dev/fd/{source.handle.fileno()}"
    else:
        database_path = Path(source).resolve(strict=True).as_posix()
    connection = sqlite3.connect(f"file:{database_path}?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.execute("PRAGMA temp_store=FILE")
    connection.execute("PRAGMA cache_size=-8192")
    connection.execute("PRAGMA mmap_size=0")
    connection.execute("BEGIN")
    return connection


def validate_config(config: dict[str, Any]) -> None:
    assert_executed_scan_sql_contract()
    if canonical_sha256(config) != EXPECTED_CONFIG_CANONICAL_SHA256:
        raise RuntimeError("C2B config canonical hash mismatch")
    expected_policy = {
        "real_data_only": True,
        "official_public_identities_retained": True,
        "evidence_level": "L0",
        "link_state": "internal_discovery_pair",
        "association_assessment": "not_assessed",
        "causal_assessment": "not_assessed",
        "effect_estimate_state": "not_computed",
        "political_merit_or_blame": "not_assessed",
        "corruption_assessment": "not_assessed",
        "ranking_eligible": False,
        "publication_eligible": False,
    }
    if config.get("policy") != expected_policy:
        raise RuntimeError("C2B zero-claim policy drifted")
    source = config.get("sources", {}).get("actions", {})
    if source != {
        "path": "etl/data/staging/politicos-es.db",
        "bytes": EXPECTED_SOURCE_DATABASE_BYTES,
        "sha256": EXPECTED_SOURCE_DATABASE_SHA256,
        "source_id": "senado_votaciones",
        "source_snapshot_date": "2026-02-12",
        "official_url_prefix": "https://www.senado.es/",
    }:
        raise RuntimeError("C2B Senate source contract drifted")
    expected = config.get("expected", {})
    if (
        type(expected.get("member_votes")) is not int
        or expected["member_votes"] != EXPECTED_MEMBER_ROWS
        or type(expected.get("distinct_official_names")) is not int
        or expected["distinct_official_names"] != EXPECTED_OFFICIAL_NAMES
        or type(expected.get("dated_actions")) is not int
        or expected["dated_actions"] != EXPECTED_ACTIONS
        or type(config.get("scope_revision")) is not int
    ):
        raise RuntimeError("C2B identity counts or revision drifted")
    query_contract = config.get("query_contract", {})
    for name in ("actions", "members"):
        sql = query_contract.get(f"{name}_keyset_sql_utf8")
        digest = query_contract.get(f"{name}_keyset_sql_sha256")
        if type(sql) is not str or not sql or " OFFSET " in f" {sql.upper()} ":
            raise RuntimeError(f"C2B {name} query is missing or uses OFFSET")
        if (
            type(digest) is not str
            or hashlib.sha256(sql.encode()).hexdigest() != digest
        ):
            raise RuntimeError(f"C2B {name} query hash mismatch")


def _exact_senate_url(value: Any, label: str) -> str:
    raw = str(value or "")
    if not raw or raw.strip() != raw:
        raise RuntimeError(f"{label} is empty or non-canonical")
    parsed = urlsplit(raw)
    if (
        parsed.scheme != "https"
        or (parsed.hostname or "").lower() != "www.senado.es"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise RuntimeError(f"{label} is outside the pinned official Senate host")
    return raw


def _is_sha256(value: Any) -> bool:
    raw = str(value or "")
    return len(raw) == 64 and all(char in "0123456789abcdef" for char in raw)


def _row_semantic_sha256(contract_version: str, row: dict[str, Any]) -> str:
    if "row_semantic_sha256" in row:
        raise RuntimeError("row digest input contains its own digest")
    return canonical_sha256(
        {"contract_version": contract_version, "persisted_row": row}
    )


def _assert_no_temp_sort(
    connection: sqlite3.Connection, sql: str, parameters: Sequence[Any] = ()
) -> None:
    details = [
        str(row[3]).upper()
        for row in connection.execute(f"EXPLAIN QUERY PLAN {sql}", parameters)
    ]
    if any("USE TEMP B-TREE" in detail for detail in details):
        raise RuntimeError("identity stream query would perform a repeated temp sort")


def _scratch_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    os.chmod(path, 0o600)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA temp_store=FILE")
    connection.execute(f"PRAGMA cache_size=-{SCRATCH_CACHE_KIB}")
    connection.execute("PRAGMA mmap_size=0")
    connection.executescript(
        """
        CREATE TABLE source_actions(
          action_id TEXT PRIMARY KEY, action_date TEXT NOT NULL,
          action_label TEXT NOT NULL, source_id TEXT NOT NULL,
          source_record_pk INTEGER NOT NULL, source_record_id TEXT NOT NULL,
          source_snapshot_date TEXT NOT NULL, official_action_url TEXT NOT NULL,
          source_page_url TEXT NOT NULL,
          source_record_content_sha256 TEXT NOT NULL
        ) WITHOUT ROWID;
        CREATE TABLE source_members(
          member_vote_id INTEGER PRIMARY KEY, action_id TEXT NOT NULL,
          action_year INTEGER NOT NULL, seat TEXT NOT NULL,
          member_name TEXT NOT NULL, member_name_normalized TEXT NOT NULL,
          person_id TEXT NOT NULL, group_code TEXT NOT NULL,
          vote_choice TEXT NOT NULL, source_id TEXT NOT NULL,
          source_url TEXT NOT NULL, source_snapshot_date TEXT NOT NULL,
          FOREIGN KEY(action_id) REFERENCES source_actions(action_id)
        );
        CREATE UNIQUE INDEX source_members_action_idx
          ON source_members(action_id,member_vote_id);
        CREATE UNIQUE INDEX source_members_year_idx
          ON source_members(action_year,action_id,member_vote_id);
        CREATE TABLE action_names(
          action_id TEXT NOT NULL, member_name TEXT NOT NULL,
          PRIMARY KEY(action_id,member_name),
          FOREIGN KEY(action_id) REFERENCES source_actions(action_id)
        ) WITHOUT ROWID;
        CREATE TABLE official_names(member_name TEXT PRIMARY KEY) WITHOUT ROWID;
        CREATE TABLE plan_actions(
          action_id TEXT PRIMARY KEY, action_date TEXT NOT NULL,
          action_year INTEGER NOT NULL, action_label TEXT NOT NULL,
          source_id TEXT NOT NULL, source_record_pk INTEGER NOT NULL,
          source_record_id TEXT NOT NULL, source_snapshot_date TEXT NOT NULL,
          official_action_url TEXT NOT NULL, source_page_url TEXT NOT NULL,
          source_record_content_sha256 TEXT NOT NULL,
          member_vote_count INTEGER NOT NULL, official_name_count INTEGER NOT NULL,
          participant_projection_sha256 TEXT NOT NULL
        ) WITHOUT ROWID;
        CREATE TABLE action_aggregates(
          action_id TEXT PRIMARY KEY, member_vote_count INTEGER NOT NULL,
          official_name_count INTEGER NOT NULL,
          participant_projection_sha256 TEXT NOT NULL,
          FOREIGN KEY(action_id) REFERENCES source_actions(action_id)
        ) WITHOUT ROWID;
        """
    )
    return connection


def _fetchmany(cursor: sqlite3.Cursor, size: int) -> Iterator[list[sqlite3.Row]]:
    while True:
        rows = cursor.fetchmany(size)
        if not rows:
            return
        yield rows


def _validate_source_action(row: dict[str, Any]) -> None:
    action_date = str(row["action_date"])
    if len(action_date) != 10 or action_date[4] != "-" or action_date[7] != "-":
        raise RuntimeError("C2B action date is non-canonical")
    official_url = _exact_senate_url(row["official_action_url"], "action URL")
    _exact_senate_url(row["source_page_url"], "action page URL")
    if str(row["action_id"]) != f"url:{official_url}":
        raise RuntimeError("C2B action identity does not match official URL")
    if str(row["source_record_id"]) != str(row["action_id"]):
        raise RuntimeError("C2B action source-record identity drifted")
    if not _is_sha256(row["source_record_content_sha256"]):
        raise RuntimeError("C2B action source record lacks SHA-256")


def _validate_source_member(row: dict[str, Any]) -> None:
    if tuple(row) != (*MEMBER_PROJECTION_FIELDS, "action_year"):
        raise RuntimeError("C2B member source projection fields drifted")
    for field in (
        "seat",
        "member_name",
        "member_name_normalized",
        "person_id",
        "group_code",
        "vote_choice",
    ):
        if not str(row[field] or "").strip():
            raise RuntimeError("official member-vote identity field is empty")
    if int(row["member_vote_id"]) < 1 or not str(row["person_id"]).isdigit():
        raise RuntimeError("official member-vote identity has an invalid ID")
    if str(row["source_id"]) != "senado_votaciones":
        raise RuntimeError("member-vote source identity drifted")
    if str(row["source_snapshot_date"]) != "2026-02-12":
        raise RuntimeError("member-vote snapshot identity drifted")
    _exact_senate_url(row["source_url"], "member source URL")


def _stage_real_inputs(
    *,
    source_connection: sqlite3.Connection,
    plan_connection: sqlite3.Connection,
    scratch: sqlite3.Connection,
    config: dict[str, Any],
    batch_rows: int,
) -> None:
    assert_executed_scan_sql_contract()
    source = config["sources"]["actions"]
    parameters = (source["source_id"], source["source_snapshot_date"])
    _assert_no_temp_sort(source_connection, SOURCE_ACTION_SCAN_SQL, parameters)
    action_cursor = source_connection.execute(SOURCE_ACTION_SCAN_SQL, parameters)
    for rows in _fetchmany(action_cursor, batch_rows):
        values = []
        for source_row in rows:
            row = dict(source_row)
            _validate_source_action(row)
            values.append(tuple(row.values()))
        scratch.executemany(
            "INSERT INTO source_actions VALUES(?,?,?,?,?,?,?,?,?,?)", values
        )
    action_cursor.close()
    if (
        scratch.execute("SELECT COUNT(*) FROM source_actions").fetchone()[0]
        != EXPECTED_ACTIONS
    ):
        raise RuntimeError("C2B action count does not match pinned real scope")

    _assert_no_temp_sort(source_connection, SOURCE_MEMBER_SCAN_SQL, parameters)
    member_cursor = source_connection.execute(SOURCE_MEMBER_SCAN_SQL, parameters)
    for rows in _fetchmany(member_cursor, batch_rows):
        member_values = []
        action_name_values = []
        official_name_values = []
        for source_row in rows:
            row = dict(source_row)
            _validate_source_member(row)
            member_values.append(
                (
                    int(row["member_vote_id"]),
                    str(row["action_id"]),
                    int(row["action_year"]),
                    str(row["seat"]),
                    str(row["member_name"]),
                    str(row["member_name_normalized"]),
                    str(row["person_id"]),
                    str(row["group_code"]),
                    str(row["vote_choice"]),
                    str(row["source_id"]),
                    str(row["source_url"]),
                    str(row["source_snapshot_date"]),
                )
            )
            action_name_values.append((str(row["action_id"]), str(row["member_name"])))
            official_name_values.append((str(row["member_name"]),))
        scratch.executemany(
            "INSERT INTO source_members VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", member_values
        )
        scratch.executemany(
            "INSERT OR IGNORE INTO action_names VALUES(?,?)", action_name_values
        )
        scratch.executemany(
            "INSERT OR IGNORE INTO official_names VALUES(?)", official_name_values
        )
    member_cursor.close()

    pipeline_rows = plan_connection.execute(
        "SELECT pipeline_key FROM outcome_pair_plan_actions LIMIT 2"
    ).fetchmany(2)
    if not pipeline_rows or any(
        row[0] != EXPECTED_PAIR_PLAN_PIPELINE_KEY for row in pipeline_rows
    ):
        raise RuntimeError("C2B pair-plan pipeline identity drifted")
    plan_cursor = plan_connection.execute(
        """
        SELECT action_id,action_date,action_year,action_label,source_id,
               source_record_pk,source_record_id,source_snapshot_date,
               official_action_url,source_page_url,source_record_content_sha256,
               member_vote_count,official_name_count,participant_projection_sha256
        FROM outcome_pair_plan_actions WHERE pipeline_key=?
        """,
        (EXPECTED_PAIR_PLAN_PIPELINE_KEY,),
    )
    for rows in _fetchmany(plan_cursor, batch_rows):
        scratch.executemany(
            "INSERT INTO plan_actions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [tuple(row) for row in rows],
        )
    plan_cursor.close()
    scratch.commit()
    counts = scratch.execute(
        "SELECT (SELECT COUNT(*) FROM source_members),"
        "(SELECT COUNT(*) FROM official_names),(SELECT COUNT(*) FROM plan_actions)"
    ).fetchone()
    if tuple(counts) != (
        EXPECTED_MEMBER_ROWS,
        EXPECTED_OFFICIAL_NAMES,
        EXPECTED_ACTIONS,
    ):
        raise RuntimeError("pinned real identity staging counts drifted")
    years = tuple(
        int(row[0])
        for row in scratch.execute(
            "SELECT DISTINCT action_year FROM source_members ORDER BY action_year"
        )
    )
    if years != EXPECTED_ACTION_YEARS:
        raise RuntimeError("pinned real action-year scope drifted")
    for sql, params in (
        (MEMBER_STAGE_ORDER_SQL, ()),
        (MEMBER_OUTPUT_ORDER_SQL, ()),
        (MEMBER_OUTPUT_YEAR_SQL, (EXPECTED_ACTION_YEARS[0],)),
        ("SELECT member_name FROM official_names ORDER BY member_name", ()),
        ("SELECT * FROM source_actions ORDER BY action_id", ()),
        ("SELECT * FROM plan_actions ORDER BY action_id", ()),
    ):
        _assert_no_temp_sort(scratch, sql, params)


def _source_member_from_stage(row: sqlite3.Row) -> dict[str, Any]:
    return {name: row[name] for name in MEMBER_PROJECTION_FIELDS}


def _action_from_member_join(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "action_id": row["action_id"],
        "action_date": row["action_date"],
        "action_label": row["action_label"],
        "source_record_pk": row["source_record_pk"],
        "source_record_id": row["source_record_id"],
        "source_snapshot_date": row["source_snapshot_date"],
        "official_action_url": row["official_action_url"],
        "source_page_url": row["source_page_url"],
        "source_record_content_sha256": row["source_record_content_sha256"],
    }


def _member_output_row(
    member: dict[str, Any], action: dict[str, Any]
) -> dict[str, Any]:
    official_url = _exact_senate_url(action["official_action_url"], "action URL")
    persisted = {
        "member_vote_id": int(member["member_vote_id"]),
        "action_id": str(member["action_id"]),
        "action_date": str(action["action_date"]),
        "action_year": int(str(action["action_date"])[:4]),
        "action_label": str(action["action_label"]),
        "official_action_url": official_url,
        "action_source_page_url": _exact_senate_url(
            action["source_page_url"], "action page URL"
        ),
        "action_source_record_pk": int(action["source_record_pk"]),
        "action_source_record_id": str(action["source_record_id"]),
        "action_source_record_content_sha256": str(
            action["source_record_content_sha256"]
        ),
        "seat": str(member["seat"]),
        "member_name": str(member["member_name"]),
        "member_name_normalized": str(member["member_name_normalized"]),
        "person_id": str(member["person_id"]),
        "group_code": str(member["group_code"]),
        "vote_choice": str(member["vote_choice"]),
        "source_id": str(member["source_id"]),
        "member_source_url": _exact_senate_url(
            member["source_url"], "member source URL"
        ),
        "source_snapshot_date": str(member["source_snapshot_date"]),
        "evidence_level": "L0",
        "companion_state": "internal_identity_companion",
        "ranking_eligible": 0,
        "publication_eligible": 0,
    }
    if persisted["action_id"] != f"url:{official_url}":
        raise RuntimeError("member action identity does not match official URL")
    persisted["row_semantic_sha256"] = _row_semantic_sha256(
        MEMBER_ROW_CONTRACT_VERSION, persisted
    )
    return persisted


def _action_output_row(
    action: dict[str, Any], aggregate: dict[str, Any]
) -> dict[str, Any]:
    persisted = {
        "action_id": str(action["action_id"]),
        "action_date": str(action["action_date"]),
        "action_year": int(str(action["action_date"])[:4]),
        "action_label": str(action["action_label"]),
        "source_id": str(action["source_id"]),
        "official_action_url": _exact_senate_url(
            action["official_action_url"], "action URL"
        ),
        "action_source_page_url": _exact_senate_url(
            action["source_page_url"], "action page URL"
        ),
        "action_source_record_pk": int(action["source_record_pk"]),
        "action_source_record_id": str(action["source_record_id"]),
        "action_source_record_content_sha256": str(
            action["source_record_content_sha256"]
        ),
        "source_snapshot_date": str(action["source_snapshot_date"]),
        "member_vote_count": int(aggregate["member_vote_count"]),
        "official_name_count": int(aggregate["official_name_count"]),
        "participant_projection_sha256": str(
            aggregate["participant_projection_sha256"]
        ),
        "evidence_level": "L0",
        "companion_state": "internal_identity_companion",
        "ranking_eligible": 0,
        "publication_eligible": 0,
    }
    persisted["row_semantic_sha256"] = _row_semantic_sha256(
        ACTION_ROW_CONTRACT_VERSION, persisted
    )
    return persisted


def _assert_action_plan_parity(
    *,
    source_action: dict[str, Any],
    aggregate: dict[str, Any],
    plan_action: dict[str, Any],
) -> None:
    expected = {
        "action_id": str(source_action["action_id"]),
        "action_date": str(source_action["action_date"]),
        "action_year": int(str(source_action["action_date"])[:4]),
        "action_label": str(source_action["action_label"]),
        "source_id": str(source_action["source_id"]),
        "source_record_pk": int(source_action["source_record_pk"]),
        "source_record_id": str(source_action["source_record_id"]),
        "source_snapshot_date": str(source_action["source_snapshot_date"]),
        "official_action_url": str(source_action["official_action_url"]),
        "source_page_url": str(source_action["source_page_url"]),
        "source_record_content_sha256": str(
            source_action["source_record_content_sha256"]
        ),
        "member_vote_count": int(aggregate["member_vote_count"]),
        "official_name_count": int(aggregate["official_name_count"]),
        "participant_projection_sha256": str(
            aggregate["participant_projection_sha256"]
        ),
    }
    if {key: plan_action[key] for key in expected} != expected:
        raise RuntimeError("per-action C2B participant projection parity failed")


def _materialize_action_aggregates(scratch: sqlite3.Connection) -> str:
    component_hasher = hashlib.sha256()
    name_counts = iter(
        scratch.execute(
            "SELECT action_id,COUNT(*) AS names FROM action_names GROUP BY action_id ORDER BY action_id"
        )
    )
    next_name = next(name_counts, None)
    current_action: str | None = None
    current_hasher = hashlib.sha256()
    current_count = 0
    total = 0
    pending: list[tuple[Any, ...]] = []

    def finish() -> None:
        nonlocal next_name, current_action, current_hasher, current_count, pending
        if current_action is None:
            return
        if next_name is None or str(next_name["action_id"]) != current_action:
            raise RuntimeError("per-action official-name stream lost alignment")
        name_count = int(next_name["names"])
        if name_count != current_count:
            raise RuntimeError("official name repeats within a Senate action")
        pending.append(
            (
                current_action,
                current_count,
                name_count,
                stream_root(
                    "outcome_pair_plan_action_participant_projection_v1",
                    current_count,
                    current_hasher,
                ),
            )
        )
        if len(pending) >= 1_000:
            scratch.executemany(
                "INSERT INTO action_aggregates VALUES(?,?,?,?)", pending
            )
            pending = []
        next_name = next(name_counts, None)

    for row in scratch.execute(MEMBER_STAGE_ORDER_SQL):
        member = _source_member_from_stage(row)
        action_id = str(member["action_id"])
        if current_action != action_id:
            finish()
            current_action = action_id
            current_hasher = hashlib.sha256()
            current_count = 0
        stream_hash_add(current_hasher, member)
        stream_hash_add(component_hasher, member)
        current_count += 1
        total += 1
    finish()
    if pending:
        scratch.executemany("INSERT INTO action_aggregates VALUES(?,?,?,?)", pending)
    scratch.commit()
    if next_name is not None or total != EXPECTED_MEMBER_ROWS:
        raise RuntimeError("member aggregate stream cardinality drifted")

    missing = object()
    streams = (
        scratch.execute("SELECT * FROM source_actions ORDER BY action_id"),
        scratch.execute("SELECT * FROM action_aggregates ORDER BY action_id"),
        scratch.execute("SELECT * FROM plan_actions ORDER BY action_id"),
    )
    checked = 0
    for source_row, aggregate_row, plan_row in itertools.zip_longest(
        *streams, fillvalue=missing
    ):
        if source_row is missing or aggregate_row is missing or plan_row is missing:
            raise RuntimeError("source, aggregate, and plan action streams differ")
        if not (
            source_row["action_id"]
            == aggregate_row["action_id"]
            == plan_row["action_id"]
        ):
            raise RuntimeError("action parity streams lost alignment")
        _assert_action_plan_parity(
            source_action=dict(source_row),
            aggregate=dict(aggregate_row),
            plan_action=dict(plan_row),
        )
        checked += 1
    if checked != EXPECTED_ACTIONS:
        raise RuntimeError("not every C2B action has participant parity")
    root = stream_root("outcome_pair_plan_input_members_v1", total, component_hasher)
    if root != EXPECTED_MEMBER_COMPONENT_ROOT_SHA256:
        raise RuntimeError("C2B member component root mismatch")
    return root


class _ContentAddressedParquetWriter:
    def __init__(
        self, *, root: Path, relative_dir: Path, contract: SemanticLaneContract
    ) -> None:
        self.root = root
        self.relative_dir = relative_dir
        self.contract = contract
        self.schema = contract.arrow_schema()
        self.columns = {name: [] for name in contract.columns}
        self.buffered_rows = 0
        self.total_rows = 0
        self.partition_digest = hashlib.sha256()
        self.files: list[dict[str, Any]] = []
        self.writer = None
        self.pending_path: Path | None = None
        self.file_rows = 0
        self.file_digest = hashlib.sha256()
        self.file_min_id: str | int | None = None
        self.file_max_id: str | int | None = None

    def _open(self) -> None:
        import pyarrow.parquet as pq  # type: ignore

        if self.writer is not None:
            return
        directory = self.root / self.relative_dir
        directory.mkdir(parents=True, exist_ok=True)
        self.pending_path = directory / f".part-{len(self.files):05d}.pending.parquet"
        self.writer = pq.ParquetWriter(
            self.pending_path,
            self.schema,
            compression=CANONICAL_COMPRESSION,
            compression_level=CANONICAL_COMPRESSION_LEVEL,
            use_dictionary=True,
            write_statistics=True,
            version=CANONICAL_PARQUET_FORMAT_VERSION,
            use_byte_stream_split=False,
            data_page_version=CANONICAL_DATA_PAGE_VERSION,
            use_compliant_nested_type=True,
            write_batch_size=CANONICAL_WRITE_BATCH_SIZE,
            dictionary_pagesize_limit=CANONICAL_DICTIONARY_PAGE_SIZE_LIMIT,
            store_schema=True,
            write_page_index=False,
            write_page_checksum=False,
            store_decimal_as_integer=False,
        )

    def append(self, row: dict[str, Any]) -> None:
        if set(row) != set(self.contract.columns):
            raise RuntimeError("Parquet row fields do not match identity contract")
        encoded = self.contract.canonical_row_bytes(row)
        self.partition_digest.update(encoded)
        self.file_digest.update(encoded)
        identity = row[self.contract.id_column]
        self.file_min_id = (
            identity if self.file_min_id is None else min(self.file_min_id, identity)
        )
        self.file_max_id = (
            identity if self.file_max_id is None else max(self.file_max_id, identity)
        )
        for name in self.contract.columns:
            self.columns[name].append(row[name])
        self.buffered_rows += 1
        if self.buffered_rows == CANONICAL_ROW_GROUP_ROWS:
            self._flush()
        if self.file_rows + self.buffered_rows == CANONICAL_MAX_FILE_ROWS:
            self._flush()
            self._close()

    def _flush(self) -> None:
        if not self.buffered_rows:
            return
        import pyarrow as pa  # type: ignore

        self._open()
        self.writer.write_table(
            pa.Table.from_pydict(self.columns, schema=self.schema),
            row_group_size=CANONICAL_ROW_GROUP_ROWS,
        )
        self.file_rows += self.buffered_rows
        self.total_rows += self.buffered_rows
        self.columns = {name: [] for name in self.contract.columns}
        self.buffered_rows = 0

    def _close(self) -> None:
        if self.writer is None:
            return
        self.writer.close()
        semantic_sha256 = self.file_digest.hexdigest()
        assert self.pending_path is not None
        final_path = self.pending_path.parent / f"part-{semantic_sha256}.parquet"
        if final_path.exists() or final_path.is_symlink():
            raise RuntimeError("duplicate content-addressed Parquet file")
        os.replace(self.pending_path, final_path)
        fsync_regular_file(final_path)
        fsync_directory(final_path.parent)
        size = int(final_path.stat().st_size)
        if size < 1 or size > MAX_PARQUET_FILE_BYTES:
            raise RuntimeError("Parquet file byte size violates hard bound")
        self.files.append(
            {
                "path": final_path.relative_to(self.root).as_posix(),
                "rows": self.file_rows,
                "bytes": size,
                "sha256": sha256_file(final_path),
                "semantic_sha256": semantic_sha256,
                "min_id": self.file_min_id,
                "max_id": self.file_max_id,
            }
        )
        self.writer = None
        self.pending_path = None
        self.file_rows = 0
        self.file_digest = hashlib.sha256()
        self.file_min_id = None
        self.file_max_id = None

    def close(self) -> dict[str, Any]:
        self._flush()
        self._close()
        if self.total_rows < 1 or not self.files:
            raise RuntimeError("empty Parquet table or partition is forbidden")
        return {
            "rows": self.total_rows,
            "input_sha256": self.partition_digest.hexdigest(),
            "files": self.files,
        }


def _manifest_root(manifest: dict[str, Any]) -> str:
    return canonical_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_root_sha256"}
    )


def _safe_clear_work_root(work_root: Path) -> None:
    if work_root.is_symlink():
        raise RuntimeError("deterministic work root is a symlink")
    if work_root.exists():
        if not work_root.is_dir():
            raise RuntimeError("deterministic work root is not a directory")
        shutil.rmtree(work_root)
        fsync_directory(work_root.parent)


def export_outcome_pair_identity_companion(
    *,
    source_db_path: Path,
    config_path: Path,
    pair_plan_db_path: Path,
    output_root: Path,
    compression: str = CANONICAL_COMPRESSION,
    row_group_rows: int = CANONICAL_ROW_GROUP_ROWS,
    max_file_rows: int = CANONICAL_MAX_FILE_ROWS,
    source_page_size: int = CANONICAL_SOURCE_PAGE_SIZE,
    max_peak_rss_mb: float = MAXIMUM_PEAK_RSS_MB,
    _leases_held: bool = False,
) -> dict[str, Any]:
    """Build one fresh, deterministic, bounded package from pinned real files."""
    require_canonical_pyarrow()
    if compression != CANONICAL_COMPRESSION:
        raise ValueError("compression must equal the pinned physical contract")
    require_exact_int("row_group_rows", row_group_rows, CANONICAL_ROW_GROUP_ROWS)
    require_exact_int("max_file_rows", max_file_rows, CANONICAL_MAX_FILE_ROWS)
    require_exact_int("source_page_size", source_page_size, CANONICAL_SOURCE_PAGE_SIZE)
    rss_limit = require_bounded_finite_float(
        "max_peak_rss_mb",
        max_peak_rss_mb,
        minimum_exclusive=0.0,
        maximum=MAXIMUM_PEAK_RSS_MB,
    )
    source_db_path = Path(source_db_path)
    config_path = Path(config_path)
    pair_plan_db_path = Path(pair_plan_db_path)
    assert_pinned_real_input_paths(source_db_path, config_path, pair_plan_db_path)
    output_root = preflight_output_root(Path(output_root))
    lease_context = (
        nullcontext()
        if _leases_held
        else identity_companion_leases(
            [source_db_path, config_path, pair_plan_db_path, output_root],
            namespace="build",
        )
    )
    with lease_context, ExitStack() as evidence:
        if output_root.exists() or output_root.is_symlink():
            raise FileExistsError("identity companion output root already exists")
        config_bound = evidence.enter_context(bound_regular_file(config_path))
        source_bound = evidence.enter_context(
            bound_regular_file(source_db_path, database=True)
        )
        plan_bound = evidence.enter_context(
            bound_regular_file(pair_plan_db_path, database=True)
        )
        config_fact = {
            "path": repo_path(config_bound.path),
            "bytes": config_bound.identity.size,
            "sha256": config_bound.sha256(),
        }
        plan_fact = {
            "path": repo_path(plan_bound.path),
            "bytes": plan_bound.identity.size,
            "sha256": plan_bound.sha256(),
        }
        if config_fact["sha256"] != EXPECTED_CONFIG_FILE_SHA256:
            raise RuntimeError("C2B config file hash mismatch")
        if (plan_fact["sha256"], plan_fact["bytes"]) != (
            EXPECTED_PAIR_PLAN_DATABASE_SHA256,
            EXPECTED_PAIR_PLAN_DATABASE_BYTES,
        ):
            raise RuntimeError("C2B pair-plan reference bytes mismatch")
        config = load_json_bytes(config_bound.read_bytes(max_bytes=MAX_JSON_BYTES))
        validate_config(config)

        work_root = output_root.parent / f".{output_root.name}.work"
        _safe_clear_work_root(work_root)
        work_root.mkdir(mode=0o700)
        package_root = work_root / "package"
        package_root.mkdir(mode=0o700)
        scratch_path = work_root / "identity-stage.sqlite3"
        source_connection: sqlite3.Connection | None = None
        plan_connection: sqlite3.Connection | None = None
        scratch: sqlite3.Connection | None = None
        try:
            source_connection = open_readonly_database(source_bound)
            plan_connection = open_readonly_database(plan_bound)
            scratch = _scratch_connection(scratch_path)
            _stage_real_inputs(
                source_connection=source_connection,
                plan_connection=plan_connection,
                scratch=scratch,
                config=config,
                batch_rows=source_page_size,
            )
            member_component_root = _materialize_action_aggregates(scratch)

            member_package_hasher = hashlib.sha256()
            member_rows = 0
            for joined in scratch.execute(MEMBER_OUTPUT_ORDER_SQL):
                output_row = _member_output_row(
                    _source_member_from_stage(joined), _action_from_member_join(joined)
                )
                stream_hash_add(member_package_hasher, output_row)
                member_rows += 1
            if member_rows != EXPECTED_MEMBER_ROWS:
                raise RuntimeError("real member-vote output count mismatch")

            member_partitions: list[dict[str, Any]] = []
            for year in EXPECTED_ACTION_YEARS:
                writer = _ContentAddressedParquetWriter(
                    root=package_root,
                    relative_dir=Path(
                        "member_vote_identities", "by_action_year", str(year)
                    ),
                    contract=MEMBER_CONTRACT,
                )
                for joined in scratch.execute(MEMBER_OUTPUT_YEAR_SQL, (year,)):
                    writer.append(
                        _member_output_row(
                            _source_member_from_stage(joined),
                            _action_from_member_join(joined),
                        )
                    )
                result = writer.close()
                member_partitions.append(
                    {
                        "partition_id": f"action_year={year}",
                        "relative_dir": f"member_vote_identities/by_action_year/{year}",
                        "values": {"action_year": year},
                        **result,
                    }
                )

            action_writer = _ContentAddressedParquetWriter(
                root=package_root,
                relative_dir=Path("action_participant_projections"),
                contract=ACTION_CONTRACT,
            )
            action_package_hasher = hashlib.sha256()
            action_count = 0
            for action, aggregate in zip(
                scratch.execute("SELECT * FROM source_actions ORDER BY action_id"),
                scratch.execute("SELECT * FROM action_aggregates ORDER BY action_id"),
                strict=True,
            ):
                if action["action_id"] != aggregate["action_id"]:
                    raise RuntimeError("action output streams lost alignment")
                output_row = _action_output_row(dict(action), dict(aggregate))
                stream_hash_add(action_package_hasher, output_row)
                action_writer.append(output_row)
                action_count += 1
            action_result = action_writer.close()
            if action_count != EXPECTED_ACTIONS:
                raise RuntimeError("real action output count mismatch")

            official_names_hasher = hashlib.sha256()
            official_name_count = 0
            for row in scratch.execute(
                "SELECT member_name FROM official_names ORDER BY member_name"
            ):
                stream_hash_add(
                    official_names_hasher, {"official_name": str(row["member_name"])}
                )
                official_name_count += 1
            if official_name_count != EXPECTED_OFFICIAL_NAMES:
                raise RuntimeError("exact official-name cardinality mismatch")
            roots = {
                "member_component_root_sha256": member_component_root,
                "member_rows_root_sha256": stream_root(
                    "outcome_pair_identity_companion_member_rows_v1",
                    member_rows,
                    member_package_hasher,
                ),
                "action_rows_root_sha256": stream_root(
                    "outcome_pair_identity_companion_action_rows_v1",
                    action_count,
                    action_package_hasher,
                ),
                "official_names_root_sha256": stream_root(
                    "outcome_pair_identity_companion_official_names_v1",
                    official_name_count,
                    official_names_hasher,
                ),
            }
            if roots != {
                "member_component_root_sha256": EXPECTED_MEMBER_COMPONENT_ROOT_SHA256,
                "member_rows_root_sha256": EXPECTED_MEMBER_ROWS_ROOT_SHA256,
                "action_rows_root_sha256": EXPECTED_ACTION_ROWS_ROOT_SHA256,
                "official_names_root_sha256": EXPECTED_OFFICIAL_NAMES_ROOT_SHA256,
            }:
                raise RuntimeError("pinned identity semantic roots drifted")
            counts = {
                "member_vote_rows": member_rows,
                "distinct_official_names": official_name_count,
                "actions": action_count,
                "member_partitions": len(member_partitions),
                "member_files": sum(
                    len(partition["files"]) for partition in member_partitions
                ),
                "action_files": len(action_result["files"]),
                "publication_eligible_rows": 0,
                "ranking_eligible_rows": 0,
            }
            package_semantic_root = canonical_sha256(
                {
                    "contract_version": PACKAGE_ROOT_CONTRACT_VERSION,
                    "counts": counts,
                    "policy": POLICY,
                    "roots": roots,
                    "schemas": {
                        "member_votes": MEMBER_CONTRACT.schema_sha256,
                        "action_projections": ACTION_CONTRACT.schema_sha256,
                    },
                }
            )
            if package_semantic_root != EXPECTED_PACKAGE_SEMANTIC_ROOT_SHA256:
                raise RuntimeError("pinned identity package semantic root drifted")
            parquet_bytes = sum(
                int(file_meta["bytes"])
                for partition in member_partitions
                for file_meta in partition["files"]
            ) + sum(int(file_meta["bytes"]) for file_meta in action_result["files"])
            if parquet_bytes < 1 or parquet_bytes > MAX_PACKAGE_PARQUET_BYTES:
                raise RuntimeError("package Parquet bytes violate hard bound")
            manifest: dict[str, Any] = {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "transformer_version": TRANSFORMER_VERSION,
                "contract_date": str(config["contract_date"]),
                "created_at": f"{config['contract_date']}T00:00:00Z",
                "scope_revision": int(config["scope_revision"]),
                "source": {
                    "config_path": str(config_fact["path"]),
                    "config_file_bytes": int(config_fact["bytes"]),
                    "config_file_sha256": str(config_fact["sha256"]),
                    "config_canonical_sha256": EXPECTED_CONFIG_CANONICAL_SHA256,
                    # Bind the artifact to its original source fact. A later
                    # mutable database is accepted only if every scoped row
                    # reproduces the exact semantic roots below.
                    "database_path": str(config["sources"]["actions"]["path"]),
                    "database_bytes": int(config["sources"]["actions"]["bytes"]),
                    "database_sha256": str(
                        config["sources"]["actions"]["sha256"]
                    ),
                    "source_id": "senado_votaciones",
                    "source_snapshot_date": "2026-02-12",
                    "executed_actions_scan_sql_sha256": (
                        EXECUTED_ACTION_SCAN_SQL_SHA256
                    ),
                    "executed_members_scan_sql_sha256": (
                        EXECUTED_MEMBER_SCAN_SQL_SHA256
                    ),
                    "configured_actions_keyset_sql_sha256": str(
                        config["query_contract"]["actions_keyset_sql_sha256"]
                    ),
                    "configured_members_keyset_sql_sha256": str(
                        config["query_contract"]["members_keyset_sql_sha256"]
                    ),
                },
                "reference_pair_plan": {
                    "database_path": str(plan_fact["path"]),
                    "database_bytes": int(plan_fact["bytes"]),
                    "database_sha256": str(plan_fact["sha256"]),
                    "pipeline_key": EXPECTED_PAIR_PLAN_PIPELINE_KEY,
                    "role": "read_only_per_action_projection_parity_reference",
                },
                "policy": dict(POLICY),
                "layout": {
                    "compression": CANONICAL_COMPRESSION,
                    "compression_level": CANONICAL_COMPRESSION_LEVEL,
                    "row_group_rows": CANONICAL_ROW_GROUP_ROWS,
                    "max_file_rows": CANONICAL_MAX_FILE_ROWS,
                    "partition_key": "action_year",
                    "partition_directory_contract": "member_vote_identities/by_action_year/{year}",
                    "file_name_contract": "part-{semantic_sha256}.parquet",
                    "content_address": "SHA-256 of ordered canonical persisted rows",
                    "pyarrow_version": CANONICAL_PYARROW_VERSION,
                    "parquet_created_by": CANONICAL_PARQUET_CREATED_BY,
                    "parquet_format_version": CANONICAL_PARQUET_FORMAT_VERSION,
                    "data_page_version": CANONICAL_DATA_PAGE_VERSION,
                    "write_batch_size": CANONICAL_WRITE_BATCH_SIZE,
                    "dictionary_page_size_limit_bytes": (
                        CANONICAL_DICTIONARY_PAGE_SIZE_LIMIT
                    ),
                    "dictionary_encoding": True,
                    "statistics": True,
                    "byte_stream_split": False,
                    "compliant_nested_types": True,
                    "store_arrow_schema": True,
                    "page_index": False,
                    "page_checksum": False,
                    "decimal_as_integer": False,
                },
                "tables": {
                    "member_vote_identities": {
                        "schema": list(MEMBER_CONTRACT.schema),
                        "schema_sha256": MEMBER_CONTRACT.schema_sha256,
                        "participant_projection_fields": list(MEMBER_PROJECTION_FIELDS),
                        "participant_projection_field_map": dict(
                            MEMBER_PROJECTION_FIELD_MAP
                        ),
                        "rows": member_rows,
                        "partitions": member_partitions,
                    },
                    "action_participant_projections": {
                        "schema": list(ACTION_CONTRACT.schema),
                        "schema_sha256": ACTION_CONTRACT.schema_sha256,
                        "rows": action_count,
                        "relative_dir": "action_participant_projections",
                        "input_sha256": action_result["input_sha256"],
                        "files": action_result["files"],
                    },
                },
                "counts": counts,
                "roots": roots,
                "parquet_bytes": parquet_bytes,
                "package_semantic_root_sha256": package_semantic_root,
                "checks": {
                    "real_source_hash_pinned": True,
                    "config_hash_pinned": True,
                    "executed_scan_sql_hashes_pinned": True,
                    "descriptor_bound_sqlite_reads": True,
                    "source_read_only_and_stable": True,
                    "pair_plan_reference_read_only_and_stable": True,
                    "all_member_vote_rows_retained": True,
                    "all_exact_official_names_retained": True,
                    "all_official_ids_retained": True,
                    "all_official_urls_retained": True,
                    "per_action_participant_projection_parity": True,
                    "participant_projection_field_map_explicit": True,
                    "bounded_files": True,
                    "content_addressed_files": True,
                    "canonical_pyarrow_physical_writer": True,
                    "dataset_api_compatible_layout": True,
                    "publication_disabled": True,
                    "ranking_disabled": True,
                },
                "publication_gate_passed": False,
                "ranking_gate_passed": False,
            }
            manifest["manifest_root_sha256"] = _manifest_root(manifest)
            manifest_path = package_root / "manifest.json"
            encoded_manifest = (
                json.dumps(
                    manifest,
                    ensure_ascii=True,
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n"
            ).encode()
            if len(encoded_manifest) > MAX_JSON_BYTES:
                raise RuntimeError("identity manifest exceeds hard byte bound")
            descriptor = os.open(
                manifest_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
            )
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded_manifest)
                handle.flush()
                os.fsync(handle.fileno())
            fsync_directory(package_root)

            source_connection.rollback()
            plan_connection.rollback()
            source_connection.close()
            plan_connection.close()
            scratch.close()
            source_connection = plan_connection = scratch = None
            scratch_path.unlink()
            fsync_directory(work_root)
            peak = peak_rss_mb()
            if peak > rss_limit:
                raise RuntimeError(
                    f"identity companion exceeded RSS limit: {peak} > {rss_limit} MiB"
                )
            os.replace(package_root, output_root)
            fsync_directory(output_root.parent)
            work_root.rmdir()
            fsync_directory(output_root.parent)
            return manifest
        except BaseException:
            for connection in (scratch, source_connection, plan_connection):
                if connection is not None:
                    connection.close()
            if work_root.exists() and not work_root.is_symlink():
                shutil.rmtree(work_root)
                fsync_directory(work_root.parent)
            raise


__all__ = [
    "ACTION_CONTRACT",
    "ACTION_ROW_CONTRACT_VERSION",
    "CANONICAL_COMPRESSION",
    "CANONICAL_COMPRESSION_LEVEL",
    "CANONICAL_DATA_PAGE_VERSION",
    "CANONICAL_DICTIONARY_PAGE_SIZE_LIMIT",
    "CANONICAL_MAX_FILE_ROWS",
    "CANONICAL_ROW_GROUP_ROWS",
    "CANONICAL_PARQUET_CREATED_BY",
    "CANONICAL_PARQUET_FORMAT_VERSION",
    "CANONICAL_PYARROW_VERSION",
    "CANONICAL_SOURCE_PAGE_SIZE",
    "CANONICAL_WRITE_BATCH_SIZE",
    "DEFAULT_CONFIG",
    "DEFAULT_PAIR_PLAN_DB",
    "DEFAULT_SOURCE_DB",
    "EXPECTED_ACTIONS",
    "EXPECTED_ACTION_YEARS",
    "EXPECTED_CONFIG_CANONICAL_SHA256",
    "EXPECTED_CONFIG_FILE_SHA256",
    "EXPECTED_MEMBER_COMPONENT_ROOT_SHA256",
    "EXPECTED_MEMBER_ROWS_ROOT_SHA256",
    "EXPECTED_ACTION_ROWS_ROOT_SHA256",
    "EXPECTED_OFFICIAL_NAMES_ROOT_SHA256",
    "EXPECTED_PACKAGE_SEMANTIC_ROOT_SHA256",
    "EXPECTED_MEMBER_ROWS",
    "EXPECTED_OFFICIAL_NAMES",
    "EXPECTED_PAIR_PLAN_DATABASE_BYTES",
    "EXPECTED_PAIR_PLAN_DATABASE_SHA256",
    "EXPECTED_PAIR_PLAN_PIPELINE_KEY",
    "EXPECTED_SOURCE_DATABASE_BYTES",
    "EXPECTED_SOURCE_DATABASE_SHA256",
    "EXECUTED_ACTION_SCAN_SQL_SHA256",
    "EXECUTED_MEMBER_SCAN_SQL_SHA256",
    "MANIFEST_SCHEMA_VERSION",
    "MAXIMUM_PEAK_RSS_MB",
    "MAX_JSON_BYTES",
    "MAX_PACKAGE_PARQUET_BYTES",
    "MAX_PARQUET_FILE_BYTES",
    "MEMBER_CONTRACT",
    "MEMBER_OUTPUT_ORDER_SQL",
    "MEMBER_PROJECTION_FIELDS",
    "MEMBER_PROJECTION_FIELD_MAP",
    "MEMBER_ROW_CONTRACT_VERSION",
    "PACKAGE_ROOT_CONTRACT_VERSION",
    "POLICY",
    "SOURCE_ACTION_SCAN_SQL",
    "SOURCE_MEMBER_SCAN_SQL",
    "TRANSFORMER_VERSION",
    "_action_from_member_join",
    "_action_output_row",
    "_assert_no_temp_sort",
    "_exact_senate_url",
    "_member_output_row",
    "_row_semantic_sha256",
    "_scratch_connection",
    "_source_member_from_stage",
    "_stage_real_inputs",
    "assert_file_stable",
    "assert_pinned_real_input_paths",
    "canonical_bytes",
    "canonical_sha256",
    "export_outcome_pair_identity_companion",
    "load_json",
    "load_json_bytes",
    "open_readonly_database",
    "repo_path",
    "stable_file_fact",
    "require_canonical_pyarrow",
    "stream_hash_add",
    "stream_root",
    "validate_config",
]
