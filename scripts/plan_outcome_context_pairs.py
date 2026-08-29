#!/usr/bin/env python3
"""Plan real, internal L0 action/indicator discovery pairs with keyset resume.

This is a sparse discovery planner, not an outcome-link producer. It makes no
association, causal, effect, ranking, publication, merit, blame, or corruption
claim. Official public identities remain in their canonical source rows and are
closed by a streaming participant projection for every selected action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import sqlite3
import struct
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterator, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "etl/data/manual/outcome_links/planner_scope_v1.json"
DEFAULT_SCHEMA = REPO_ROOT / "etl/load/sqlite_schema.sql"
DEFAULT_OUT_DB = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-v1.db"
DEFAULT_REPORT = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-v1-report.json"
SCHEMA_BEGIN = "-- BEGIN OUTCOME PAIR PLANNER C2A SCHEMA"
SCHEMA_END = "-- END OUTCOME PAIR PLANNER C2A SCHEMA"
PLAN_CONTRACT = "outcome_context_sparse_pair_planner_c2a_v1"
REPORT_SCHEMA = "outcome_context_pair_plan_report_v1"
EMPTY_CHAIN = hashlib.sha256(b"").hexdigest()
STAGES = ("actions", "series", "pairs")
ACTION_ROW_COLUMNS = (
    "action_plan_pk", "pipeline_key", "action_id", "action_date", "action_year",
    "action_label", "source_id", "source_record_pk", "source_record_id",
    "source_snapshot_date", "official_action_url", "source_page_url",
    "source_record_content_sha256", "member_vote_count", "official_name_count",
    "participant_projection_sha256",
)
SERIES_ROW_COLUMNS = (
    "series_plan_pk", "pipeline_key", "indicator_series_id", "canonical_key",
    "series_label", "dataset_code", "country_code", "geography_code",
    "frequency_code", "unit_code", "dimensions_json", "source_id",
    "source_record_pk", "source_record_id", "source_snapshot_date",
    "official_source_url", "source_record_content_sha256", "origin_capture_sha256",
    "observation_count", "observation_years_json", "observation_projection_sha256",
    "first_observation_date", "last_observation_date",
)
PAIR_ROW_COLUMNS = (
    "pair_plan_id", "pipeline_key", "base_partition_key", "pair_bucket",
    "partition_key", "action_plan_pk", "series_plan_pk", "action_year",
    "dataset_code", "strict_pre_latest_date", "strict_post_earliest_date",
    "evidence_level", "link_state", "association_assessment", "causal_assessment",
    "effect_estimate_state", "political_merit_or_blame", "corruption_assessment",
    "ranking_eligible", "publication_eligible",
)


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=reject_duplicate_keys)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stream_hash_add(hasher: Any, value: Any) -> None:
    encoded = canonical_bytes(value)
    hasher.update(struct.pack(">Q", len(encoded)))
    hasher.update(encoded)


def stream_root(contract: str, count: int, hasher: Any) -> str:
    return sha256_bytes(
        canonical_bytes(
            {
                "contract_version": contract,
                "row_count": count,
                "stream_sha256": hasher.hexdigest(),
            }
        )
    )


def chain_add(previous: str, row_sha256: str) -> str:
    return hashlib.sha256(bytes.fromhex(previous) + bytes.fromhex(row_sha256)).hexdigest()


def persisted_row_sha256(contract_version: str, row: dict[str, Any]) -> str:
    """Bind every persisted, non-hash column into one deterministic row digest."""
    if "row_semantic_sha256" in row:
        raise RuntimeError("row semantic input must exclude its own digest")
    return sha256_bytes(
        canonical_bytes(
            {"contract_version": contract_version, "persisted_row": row}
        )
    )


def max_rss_bytes() -> int:
    # Linux ru_maxrss can retain the parent's pre-exec high-water mark. VmHWM
    # measures this process image, so composed validation keeps a truthful cap.
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
                parts = line.split()
                if len(parts) == 3 and parts[0] == "VmHWM:" and parts[2] == "kB":
                    return int(parts[1]) * 1024
        except (OSError, ValueError):
            pass
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def resolve_config_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def file_sha256_stable(path: Path) -> tuple[dict[str, Any], tuple[int, ...]]:
    if not path.is_file():
        raise RuntimeError(f"real source database missing: {repo_path(path)}")
    reject_nonempty_wal(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(handle.fileno())
    path_after = path.stat()
    identities = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    if identities != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ) or identities != (
        path_after.st_dev,
        path_after.st_ino,
        path_after.st_size,
        path_after.st_mtime_ns,
        path_after.st_ctime_ns,
    ):
        raise RuntimeError(f"source changed while hashing: {repo_path(path)}")
    return (
        {
            "path": repo_path(path),
            "bytes": before.st_size,
            "sha256": digest.hexdigest(),
            "wal_bytes": 0,
        },
        identities,
    )


def reject_nonempty_wal(path: Path) -> None:
    wal = Path(f"{path}-wal")
    wal_bytes = wal.stat().st_size if wal.exists() else 0
    if wal_bytes:
        raise RuntimeError(
            f"source database has a non-empty WAL: {repo_path(path)} ({wal_bytes} bytes)"
        )


def assert_source_stable(path: Path, identity: tuple[int, ...]) -> None:
    reject_nonempty_wal(path)
    current = path.stat()
    now = (
        current.st_dev,
        current.st_ino,
        current.st_size,
        current.st_mtime_ns,
        current.st_ctime_ns,
    )
    if now != identity:
        raise RuntimeError(f"source changed during read transaction: {repo_path(path)}")


def open_source(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro&immutable=1",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.execute("BEGIN")
    return connection


def extract_schema_block(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    start = text.find(SCHEMA_BEGIN)
    end = text.find(SCHEMA_END)
    if start < 0 or end < 0 or end <= start:
        raise RuntimeError("C2A schema marker missing or malformed")
    block = text[start : end + len(SCHEMA_END)] + "\n"
    return block, sha256_bytes(block.encode("utf-8"))


def validate_config(config: dict[str, Any]) -> None:
    expected_root_keys = {
        "format_version",
        "scope_revision",
        "planner_contract_version",
        "checkpoint_contract_version",
        "checkpoint_batch_size",
        "contract_date",
        "canonicalization",
        "policy",
        "sources",
        "query_contract",
        "expected",
    }
    if set(config) != expected_root_keys:
        raise RuntimeError("planner config root keys do not match v1 contract")
    if config["format_version"] != "outcome_context_pair_planner_scope_v1":
        raise RuntimeError("unsupported planner config format")
    if config["planner_contract_version"] != PLAN_CONTRACT:
        raise RuntimeError("unsupported planner contract")
    if not isinstance(config["scope_revision"], int) or config["scope_revision"] < 1:
        raise RuntimeError("scope_revision must be a positive integer")
    if (
        not isinstance(config["checkpoint_batch_size"], int)
        or config["checkpoint_batch_size"] < 1
    ):
        raise RuntimeError("checkpoint_batch_size must be a positive integer")
    policy = config["policy"]
    required_policy = {
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
    if policy != required_policy:
        raise RuntimeError("planner policy is not the mandatory internal L0 zero-claim policy")
    query = config["query_contract"]
    for name in ("actions", "members", "series", "points"):
        sql = query[f"{name}_keyset_sql_utf8"]
        if " OFFSET " in f" {sql.upper()} ":
            raise RuntimeError(f"{name} query uses OFFSET")
        actual = sha256_bytes(sql.encode("utf-8"))
        if actual != query[f"{name}_keyset_sql_sha256"]:
            raise RuntimeError(f"{name} query hash mismatch")


def check_source_fact(actual: dict[str, Any], expected: dict[str, Any], label: str) -> None:
    for key in ("path", "bytes", "sha256"):
        if actual[key] != expected[key]:
            raise RuntimeError(
                f"{label} source {key} mismatch: expected {expected[key]!r}, "
                f"got {actual[key]!r}"
            )


def init_input_cache(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE action_inputs (
          action_id TEXT PRIMARY KEY,
          action_date TEXT NOT NULL,
          action_label TEXT NOT NULL,
          source_id TEXT NOT NULL,
          source_record_pk INTEGER NOT NULL,
          source_record_id TEXT NOT NULL,
          source_snapshot_date TEXT NOT NULL,
          official_action_url TEXT NOT NULL,
          source_page_url TEXT NOT NULL,
          source_record_content_sha256 TEXT NOT NULL
        );
        CREATE INDEX idx_action_inputs_order ON action_inputs(action_date, action_id);
        CREATE TABLE member_aggregates (
          action_id TEXT PRIMARY KEY,
          member_vote_count INTEGER NOT NULL,
          official_name_count INTEGER NOT NULL,
          participant_projection_sha256 TEXT NOT NULL
        );
        CREATE TABLE official_names (official_name TEXT PRIMARY KEY);
        CREATE TABLE series_inputs (
          indicator_series_id INTEGER PRIMARY KEY,
          canonical_key TEXT NOT NULL,
          series_label TEXT NOT NULL,
          dataset_code TEXT NOT NULL,
          geography_code TEXT NOT NULL,
          frequency_code TEXT NOT NULL,
          unit_code TEXT NOT NULL,
          dimensions_json TEXT NOT NULL,
          source_id TEXT NOT NULL,
          source_record_pk INTEGER NOT NULL,
          source_record_id TEXT NOT NULL,
          source_snapshot_date TEXT NOT NULL,
          official_source_url TEXT NOT NULL,
          source_record_content_sha256 TEXT NOT NULL,
          origin_capture_sha256 TEXT NOT NULL
        );
        CREATE TABLE point_aggregates (
          indicator_series_id INTEGER PRIMARY KEY,
          observation_count INTEGER NOT NULL,
          observation_dates_json TEXT NOT NULL,
          observation_projection_sha256 TEXT NOT NULL
        );
        """
    )
    return connection


def query_pages(
    connection: sqlite3.Connection,
    sql: str,
    parameters_for_key: Any,
) -> Iterator[sqlite3.Row]:
    while True:
        parameters = parameters_for_key()
        seen = 0
        cursor = connection.execute(sql, parameters)
        for row in cursor:
            seen += 1
            yield row
        cursor.close()
        if seen == 0:
            return


def hydrate_real_inputs(
    *,
    config: dict[str, Any],
    actions: sqlite3.Connection,
    indicators: sqlite3.Connection,
    cache: sqlite3.Connection,
    source_batch_size: int,
) -> dict[str, Any]:
    query = config["query_contract"]
    action_source = config["sources"]["actions"]
    indicator_source = config["sources"]["indicators"]
    expected = config["expected"]

    component_hashers = {
        "actions": hashlib.sha256(),
        "members": hashlib.sha256(),
        "series": hashlib.sha256(),
        "points": hashlib.sha256(),
    }
    counts = {key: 0 for key in component_hashers}

    action_key = ["", ""]

    def action_parameters() -> Sequence[Any]:
        return (
            action_source["source_id"],
            action_source["source_snapshot_date"],
            action_key[0],
            action_key[0],
            action_key[1],
            source_batch_size,
        )

    for row in query_pages(actions, query["actions_keyset_sql_utf8"], action_parameters):
        item = dict(row)
        if not item["official_action_url"].startswith(action_source["official_url_prefix"]):
            raise RuntimeError(f"non-official Senate action URL: {item['official_action_url']}")
        if not item["source_page_url"].startswith(action_source["official_url_prefix"]):
            raise RuntimeError(f"non-official Senate source URL: {item['source_page_url']}")
        if len(item["source_record_content_sha256"]) != 64:
            raise RuntimeError("Senate source record lacks content hash")
        stream_hash_add(component_hashers["actions"], item)
        counts["actions"] += 1
        cache.execute(
            "INSERT INTO action_inputs VALUES (?,?,?,?,?,?,?,?,?,?)",
            tuple(item[key] for key in item),
        )
        action_key[:] = [item["action_date"], item["action_id"]]

    member_key: list[Any] = ["", "", -1]
    current_action: str | None = None
    current_hasher = hashlib.sha256()
    current_count = 0
    current_official_names: set[str] = set()

    def finish_member_action() -> None:
        nonlocal current_action, current_hasher, current_count, current_official_names
        if current_action is None:
            return
        projection = stream_root(
            "outcome_pair_plan_action_participant_projection_v1",
            current_count,
            current_hasher,
        )
        cache.execute(
            "INSERT INTO member_aggregates VALUES (?,?,?,?)",
            (current_action, current_count, len(current_official_names), projection),
        )

    def member_parameters() -> Sequence[Any]:
        return (
            action_source["source_id"],
            action_source["source_snapshot_date"],
            member_key[0],
            member_key[0],
            member_key[2],
            source_batch_size,
        )

    for row in query_pages(actions, query["members_keyset_sql_utf8"], member_parameters):
        item = dict(row)
        if item["source_id"] != action_source["source_id"]:
            raise RuntimeError("member-vote source does not resolve to Senate source")
        if not item["member_name"] or not item["source_url"].startswith(
            action_source["official_url_prefix"]
        ):
            raise RuntimeError("member-vote row lacks official identity or URL")
        if current_action != item["action_id"]:
            finish_member_action()
            current_action = item["action_id"]
            current_hasher = hashlib.sha256()
            current_count = 0
            current_official_names = set()
        stream_hash_add(current_hasher, item)
        stream_hash_add(component_hashers["members"], item)
        current_count += 1
        current_official_names.add(item["member_name"])
        counts["members"] += 1
        cache.execute(
            "INSERT OR IGNORE INTO official_names(official_name) VALUES (?)",
            (item["member_name"],),
        )
        member_key[:] = [item["action_id"], item["action_id"], item["member_vote_id"]]
    finish_member_action()

    series_key = [-1]

    def series_parameters() -> Sequence[Any]:
        return (
            indicator_source["source_id"],
            indicator_source["source_snapshot_date"],
            indicator_source["frequency_code"],
            indicator_source["geography_code"],
            series_key[0],
            source_batch_size,
        )

    for row in query_pages(indicators, query["series_keyset_sql_utf8"], series_parameters):
        item = dict(row)
        dimensions = load_json_value(item["dimensions_json"], "series dimensions")
        item["dimensions_json"] = canonical_json(dimensions)
        if not item["official_source_url"].startswith(
            indicator_source["official_url_prefix"]
        ):
            raise RuntimeError(f"non-official Eurostat URL: {item['official_source_url']}")
        for hash_key in ("source_record_content_sha256", "origin_capture_sha256"):
            if len(item[hash_key]) != 64:
                raise RuntimeError(f"Eurostat series lacks {hash_key}")
        stream_hash_add(component_hashers["series"], item)
        counts["series"] += 1
        cache.execute(
            "INSERT INTO series_inputs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            tuple(item[key] for key in item),
        )
        series_key[0] = item["indicator_series_id"]

    point_key: list[Any] = [-1, -1, "", "", -1]
    current_series: int | None = None
    current_point_hasher = hashlib.sha256()
    current_dates: list[str] = []

    def finish_series_points() -> None:
        nonlocal current_series, current_point_hasher, current_dates
        if current_series is None:
            return
        cache.execute(
            "INSERT INTO point_aggregates VALUES (?,?,?,?)",
            (
                current_series,
                len(current_dates),
                canonical_json(current_dates),
                stream_root(
                    "outcome_pair_plan_series_observation_projection_v1",
                    len(current_dates),
                    current_point_hasher,
                ),
            ),
        )

    def point_parameters() -> Sequence[Any]:
        return (
            indicator_source["source_id"],
            indicator_source["source_snapshot_date"],
            indicator_source["frequency_code"],
            indicator_source["geography_code"],
            point_key[0],
            point_key[1],
            point_key[2],
            point_key[3],
            point_key[4],
            source_batch_size,
        )

    for row in query_pages(indicators, query["points_keyset_sql_utf8"], point_parameters):
        item = dict(row)
        if len(item["date"]) != 10 or item["date"][4:] != "-01-01":
            raise RuntimeError(f"non-annual Eurostat point date: {item['date']}")
        if current_series != item["indicator_series_id"]:
            finish_series_points()
            current_series = item["indicator_series_id"]
            current_point_hasher = hashlib.sha256()
            current_dates = []
        if current_dates and item["date"] <= current_dates[-1]:
            raise RuntimeError("Eurostat series point order is not strictly increasing")
        current_dates.append(item["date"])
        stream_hash_add(current_point_hasher, item)
        stream_hash_add(component_hashers["points"], item)
        counts["points"] += 1
        point_key[:] = [
            item["indicator_series_id"],
            item["indicator_series_id"],
            item["date"],
            item["date"],
            item["indicator_point_id"],
        ]
    finish_series_points()
    cache.commit()

    scalar = lambda sql: cache.execute(sql).fetchone()[0]
    names = scalar("SELECT COUNT(*) FROM official_names")
    action_member_closure = scalar(
        """
        SELECT COUNT(*)
        FROM action_inputs a
        JOIN member_aggregates m USING(action_id)
        WHERE m.member_vote_count = m.official_name_count
        """
    )
    series_point_closure = scalar(
        """
        SELECT COUNT(*)
        FROM series_inputs s
        JOIN point_aggregates p USING(indicator_series_id)
        WHERE p.observation_count > 1
        """
    )
    all_series = indicators.execute("SELECT COUNT(*) FROM indicator_series").fetchone()[0]
    expected_pairs = expected["dated_actions"] * expected["eligible_es_annual_series"]
    exact = {
        "actions": expected["dated_actions"],
        "members": expected["member_votes"],
        "series": expected["eligible_es_annual_series"],
        "points": expected["eligible_series_observations"],
    }
    if counts != exact:
        raise RuntimeError(f"real source selection count mismatch: {counts!r} != {exact!r}")
    if names != expected["distinct_official_names"]:
        raise RuntimeError(f"official name count mismatch: {names}")
    if action_member_closure != counts["actions"]:
        raise RuntimeError("not every action resolves to unique official member-vote identities")
    if series_point_closure != counts["series"]:
        raise RuntimeError("not every selected series resolves to annual observations")
    if all_series != expected["all_indicator_series"]:
        raise RuntimeError(f"global indicator-series count mismatch: {all_series}")
    if counts["actions"] * all_series != expected["global_unfiltered_product"]:
        raise RuntimeError("global product count mismatch")
    if expected_pairs >= expected["global_unfiltered_product"]:
        raise RuntimeError("sparse scope does not reduce global product")

    roots = {
        key: stream_root(f"outcome_pair_plan_input_{key}_v1", counts[key], hasher)
        for key, hasher in component_hashers.items()
    }
    input_root = sha256_bytes(
        canonical_bytes(
            {
                "contract_version": "outcome_pair_plan_input_root_v1",
                "component_roots": roots,
                "counts": {
                    **counts,
                    "distinct_official_names": names,
                    "all_indicator_series": all_series,
                },
                "source_snapshots": {
                    "actions": action_source["source_snapshot_date"],
                    "indicators": indicator_source["source_snapshot_date"],
                },
            }
        )
    )
    return {
        "counts": {
            **counts,
            "distinct_official_names": names,
            "all_indicator_series": all_series,
        },
        "component_roots": roots,
        "input_root_sha256": input_root,
    }


def load_json_value(value: str, label: str) -> Any:
    try:
        parsed = json.loads(value, object_pairs_hook=reject_duplicate_keys)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid {label}: {exc}") from exc
    return parsed


def open_target(path: Path, schema_block: str, roots: dict[str, str]) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    existed = path.exists() and path.stat().st_size > 0
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    if existed:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "pipeline_keyset_checkpoints" not in tables:
            connection.close()
            raise RuntimeError("refusing non-empty target without C2A checkpoints")
        for row in connection.execute(
            "SELECT DISTINCT config_sha256,input_root_sha256,schema_root_sha256 "
            "FROM pipeline_keyset_checkpoints"
        ):
            actual = {
                "config_sha256": row[0],
                "input_root_sha256": row[1],
                "schema_root_sha256": row[2],
            }
            if actual != roots:
                connection.close()
                raise RuntimeError(
                    "resume drift: target checkpoints are pinned to different "
                    "config/input/schema roots"
                )
    connection.executescript(schema_block)
    return connection


def ensure_checkpoint(
    connection: sqlite3.Connection,
    *,
    pipeline_key: str,
    stage: str,
    config: dict[str, Any],
    roots: dict[str, str],
) -> sqlite3.Row:
    connection.execute(
        """
        INSERT OR IGNORE INTO pipeline_keyset_checkpoints(
          pipeline_key,stage,partition_key,checkpoint_contract_version,
          config_sha256,input_root_sha256,schema_root_sha256,last_key_json,
          rows_written,batches_committed,semantic_chain_sha256,completed,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,0,0,?,0,?)
        """,
        (
            pipeline_key,
            stage,
            "",
            config["checkpoint_contract_version"],
            roots["config_sha256"],
            roots["input_root_sha256"],
            roots["schema_root_sha256"],
            "[]",
            EMPTY_CHAIN,
            f"{config['contract_date']}T00:00:00Z",
        ),
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM pipeline_keyset_checkpoints "
        "WHERE pipeline_key=? AND stage=? AND partition_key=''",
        (pipeline_key, stage),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"checkpoint missing after initialization: {stage}")
    pinned = {
        "config_sha256": row["config_sha256"],
        "input_root_sha256": row["input_root_sha256"],
        "schema_root_sha256": row["schema_root_sha256"],
    }
    if pinned != roots:
        raise RuntimeError(f"resume drift in {stage} checkpoint")
    return row


class RunLimiter:
    def __init__(self, max_batches: int | None, fault_batch: int | None) -> None:
        self.max_batches = max_batches
        self.fault_batch = fault_batch
        self.attempted = 0
        self.committed = 0
        self.eligible_pairs_processed = 0
        self.scanned_pairs_processed = 0

    def begin_batch(self) -> None:
        self.attempted += 1

    def fault_now(self) -> bool:
        return self.fault_batch is not None and self.attempted == self.fault_batch

    def committed_batch(self) -> bool:
        self.committed += 1
        return self.max_batches is not None and self.committed >= self.max_batches


def commit_checkpoint_batch(
    connection: sqlite3.Connection,
    *,
    limiter: RunLimiter,
    pipeline_key: str,
    stage: str,
    inserts_sql: str,
    inserts: list[Sequence[Any]],
    last_key: list[Any],
    rows_written: int,
    batches_committed: int,
    semantic_chain: str,
    completed: bool,
    updated_at: str,
    scanned_pairs: int = 0,
    eligible_pairs: int = 0,
) -> bool:
    limiter.begin_batch()
    try:
        connection.execute("BEGIN IMMEDIATE")
        if inserts:
            connection.executemany(inserts_sql, inserts)
        if limiter.fault_now():
            raise RuntimeError(
                f"injected fault before atomic checkpoint commit at batch {limiter.attempted}"
            )
        connection.execute(
            """
            UPDATE pipeline_keyset_checkpoints
            SET last_key_json=?,rows_written=?,batches_committed=?,
                semantic_chain_sha256=?,completed=?,updated_at=?
            WHERE pipeline_key=? AND stage=? AND partition_key=''
            """,
            (
                canonical_json(last_key),
                rows_written,
                batches_committed,
                semantic_chain,
                int(completed),
                updated_at,
                pipeline_key,
                stage,
            ),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    limiter.scanned_pairs_processed += scanned_pairs
    limiter.eligible_pairs_processed += eligible_pairs
    return limiter.committed_batch()


def materialize_actions(
    *,
    target: sqlite3.Connection,
    cache: sqlite3.Connection,
    pipeline_key: str,
    config: dict[str, Any],
    roots: dict[str, str],
    batch_size: int,
    limiter: RunLimiter,
) -> bool:
    checkpoint = ensure_checkpoint(
        target,
        pipeline_key=pipeline_key,
        stage="actions",
        config=config,
        roots=roots,
    )
    if checkpoint["completed"]:
        return False
    last = load_json_value(checkpoint["last_key_json"], "action checkpoint key")
    last_date, last_id = (last if last else ["", ""])
    ordinal = checkpoint["rows_written"]
    chain = checkpoint["semantic_chain_sha256"]
    batches = checkpoint["batches_committed"]
    while True:
        cursor = cache.execute(
            """
            SELECT a.*,m.member_vote_count,m.official_name_count,
                   m.participant_projection_sha256
            FROM action_inputs a JOIN member_aggregates m USING(action_id)
            WHERE a.action_date>? OR (a.action_date=? AND a.action_id>?)
            ORDER BY a.action_date,a.action_id LIMIT ?
            """,
            (last_date, last_date, last_id, batch_size),
        )
        inserts: list[Sequence[Any]] = []
        for row in cursor:
            ordinal += 1
            persisted = {
                "action_plan_pk": ordinal,
                "pipeline_key": pipeline_key,
                "action_id": row["action_id"],
                "action_date": row["action_date"],
                "action_year": int(row["action_date"][:4]),
                "action_label": row["action_label"],
                "source_id": row["source_id"],
                "source_record_pk": row["source_record_pk"],
                "source_record_id": row["source_record_id"],
                "source_snapshot_date": row["source_snapshot_date"],
                "official_action_url": row["official_action_url"],
                "source_page_url": row["source_page_url"],
                "source_record_content_sha256": row["source_record_content_sha256"],
                "member_vote_count": row["member_vote_count"],
                "official_name_count": row["official_name_count"],
                "participant_projection_sha256": row["participant_projection_sha256"],
            }
            row_sha = persisted_row_sha256("outcome_pair_plan_action_row_v2", persisted)
            chain = chain_add(chain, row_sha)
            inserts.append(tuple(persisted[key] for key in ACTION_ROW_COLUMNS) + (row_sha,))
            last_date, last_id = row["action_date"], row["action_id"]
        cursor.close()
        if not inserts:
            target.execute("BEGIN IMMEDIATE")
            target.execute(
                "UPDATE pipeline_keyset_checkpoints SET completed=1,updated_at=? "
                "WHERE pipeline_key=? AND stage='actions' AND partition_key=''",
                (f"{config['contract_date']}T00:00:00Z", pipeline_key),
            )
            target.commit()
            return False
        batches += 1
        should_stop = commit_checkpoint_batch(
            target,
            limiter=limiter,
            pipeline_key=pipeline_key,
            stage="actions",
            inserts_sql=(
                "INSERT INTO outcome_pair_plan_actions VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            ),
            inserts=inserts,
            last_key=[last_date, last_id],
            rows_written=ordinal,
            batches_committed=batches,
            semantic_chain=chain,
            completed=ordinal == config["expected"]["dated_actions"],
            updated_at=f"{config['contract_date']}T00:00:00Z",
        )
        if should_stop:
            return True
        if ordinal == config["expected"]["dated_actions"]:
            return False


def materialize_series(
    *,
    target: sqlite3.Connection,
    cache: sqlite3.Connection,
    pipeline_key: str,
    config: dict[str, Any],
    roots: dict[str, str],
    batch_size: int,
    limiter: RunLimiter,
) -> bool:
    checkpoint = ensure_checkpoint(
        target,
        pipeline_key=pipeline_key,
        stage="series",
        config=config,
        roots=roots,
    )
    if checkpoint["completed"]:
        return False
    last = load_json_value(checkpoint["last_key_json"], "series checkpoint key")
    last_id = last[0] if last else -1
    ordinal = checkpoint["rows_written"]
    chain = checkpoint["semantic_chain_sha256"]
    batches = checkpoint["batches_committed"]
    while True:
        cursor = cache.execute(
            """
            SELECT s.*,p.observation_count,p.observation_dates_json,
                   p.observation_projection_sha256
            FROM series_inputs s JOIN point_aggregates p USING(indicator_series_id)
            WHERE s.indicator_series_id>?
            ORDER BY s.indicator_series_id LIMIT ?
            """,
            (last_id, batch_size),
        )
        inserts: list[Sequence[Any]] = []
        for row in cursor:
            ordinal += 1
            dates = load_json_value(row["observation_dates_json"], "observation dates")
            years = [int(value[:4]) for value in dates]
            if len(years) != len(set(years)):
                raise RuntimeError("annual series has duplicate observation year")
            years_json = canonical_json(years)
            persisted = {
                "series_plan_pk": ordinal,
                "pipeline_key": pipeline_key,
                "indicator_series_id": row["indicator_series_id"],
                "canonical_key": row["canonical_key"],
                "series_label": row["series_label"],
                "dataset_code": row["dataset_code"],
                "country_code": row["geography_code"][:2],
                "geography_code": row["geography_code"],
                "frequency_code": row["frequency_code"],
                "unit_code": row["unit_code"],
                "dimensions_json": row["dimensions_json"],
                "source_id": row["source_id"],
                "source_record_pk": row["source_record_pk"],
                "source_record_id": row["source_record_id"],
                "source_snapshot_date": row["source_snapshot_date"],
                "official_source_url": row["official_source_url"],
                "source_record_content_sha256": row["source_record_content_sha256"],
                "origin_capture_sha256": row["origin_capture_sha256"],
                "observation_count": row["observation_count"],
                "observation_years_json": years_json,
                "observation_projection_sha256": row["observation_projection_sha256"],
                "first_observation_date": dates[0],
                "last_observation_date": dates[-1],
            }
            row_sha = persisted_row_sha256("outcome_pair_plan_series_row_v2", persisted)
            chain = chain_add(chain, row_sha)
            inserts.append(tuple(persisted[key] for key in SERIES_ROW_COLUMNS) + (row_sha,))
            last_id = row["indicator_series_id"]
        cursor.close()
        if not inserts:
            target.execute("BEGIN IMMEDIATE")
            target.execute(
                "UPDATE pipeline_keyset_checkpoints SET completed=1,updated_at=? "
                "WHERE pipeline_key=? AND stage='series' AND partition_key=''",
                (f"{config['contract_date']}T00:00:00Z", pipeline_key),
            )
            target.commit()
            return False
        batches += 1
        should_stop = commit_checkpoint_batch(
            target,
            limiter=limiter,
            pipeline_key=pipeline_key,
            stage="series",
            inserts_sql=(
                "INSERT INTO outcome_pair_plan_series VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            ),
            inserts=inserts,
            last_key=[last_id],
            rows_written=ordinal,
            batches_committed=batches,
            semantic_chain=chain,
            completed=ordinal == config["expected"]["eligible_es_annual_series"],
            updated_at=f"{config['contract_date']}T00:00:00Z",
        )
        if should_stop:
            return True
        if ordinal == config["expected"]["eligible_es_annual_series"]:
            return False


def materialize_pairs(
    *,
    target: sqlite3.Connection,
    pipeline_key: str,
    config: dict[str, Any],
    roots: dict[str, str],
    batch_size: int,
    limiter: RunLimiter,
) -> bool:
    checkpoint = ensure_checkpoint(
        target,
        pipeline_key=pipeline_key,
        stage="pairs",
        config=config,
        roots=roots,
    )
    if checkpoint["completed"]:
        return False
    last = load_json_value(checkpoint["last_key_json"], "pair checkpoint key")
    last_action, last_series = (last if last else [0, 0])
    written = checkpoint["rows_written"]
    chain = checkpoint["semantic_chain_sha256"]
    batches = checkpoint["batches_committed"]
    total_products = (
        config["expected"]["dated_actions"]
        * config["expected"]["eligible_es_annual_series"]
    )
    scanned = last_action * config["expected"]["eligible_es_annual_series"]
    if last_action:
        scanned = (
            (last_action - 1) * config["expected"]["eligible_es_annual_series"]
            + last_series
        )
    while True:
        cursor = target.execute(
            """
            SELECT a.action_plan_pk,a.action_id,a.action_year,
                   a.source_id AS action_source_id,
                   s.series_plan_pk,s.canonical_key,s.dataset_code,
                   s.source_id AS indicator_source_id,s.country_code,
                   s.observation_years_json
            FROM outcome_pair_plan_actions a
            CROSS JOIN outcome_pair_plan_series s
            WHERE a.pipeline_key=? AND s.pipeline_key=?
              AND (a.action_plan_pk>? OR
                   (a.action_plan_pk=? AND s.series_plan_pk>?))
            ORDER BY a.action_plan_pk,s.series_plan_pk
            LIMIT ?
            """,
            (pipeline_key, pipeline_key, last_action, last_action, last_series, batch_size),
        )
        inserts: list[Sequence[Any]] = []
        page_rows = 0
        for row in cursor:
            page_rows += 1
            years = load_json_value(row["observation_years_json"], "series years")
            action_year = row["action_year"]
            pre = [year for year in years if year < action_year]
            post = [year for year in years if year > action_year]
            last_action, last_series = row["action_plan_pk"], row["series_plan_pk"]
            scanned += 1
            if not pre or not post:
                continue
            pre_date = f"{max(pre):04d}-01-01"
            post_date = f"{min(post):04d}-01-01"
            identity = {
                "identity_contract_version": "outcome_pair_plan_identity_v1",
                "action_id": row["action_id"],
                "indicator_series_canonical_key": row["canonical_key"],
                "eligibility": "strict_pre_and_strict_post_annual_observations",
            }
            identity_sha = sha256_bytes(canonical_bytes(identity))
            pair_id = f"vclc:outcome-pair-plan:{identity_sha[:24]}"
            pair_bucket = identity_sha[:2]
            base_partition = (
                f"action_source={row['action_source_id']}/year={action_year}/"
                f"indicator_source={row['indicator_source_id']}/"
                f"dataset={row['dataset_code']}/country={row['country_code']}"
            )
            partition = f"{base_partition}/bucket={pair_bucket}"
            persisted = {
                "pair_plan_id": pair_id,
                "pipeline_key": pipeline_key,
                "base_partition_key": base_partition,
                "pair_bucket": pair_bucket,
                "partition_key": partition,
                "action_plan_pk": row["action_plan_pk"],
                "series_plan_pk": row["series_plan_pk"],
                "action_year": action_year,
                "dataset_code": row["dataset_code"],
                "strict_pre_latest_date": pre_date,
                "strict_post_earliest_date": post_date,
                "evidence_level": config["policy"]["evidence_level"],
                "link_state": config["policy"]["link_state"],
                "association_assessment": config["policy"]["association_assessment"],
                "causal_assessment": config["policy"]["causal_assessment"],
                "effect_estimate_state": config["policy"]["effect_estimate_state"],
                "political_merit_or_blame": config["policy"]["political_merit_or_blame"],
                "corruption_assessment": config["policy"]["corruption_assessment"],
                "ranking_eligible": int(config["policy"]["ranking_eligible"]),
                "publication_eligible": int(config["policy"]["publication_eligible"]),
            }
            row_sha = persisted_row_sha256("outcome_pair_plan_pair_row_v2", persisted)
            chain = chain_add(chain, row_sha)
            written += 1
            inserts.append(tuple(persisted[key] for key in PAIR_ROW_COLUMNS) + (row_sha,))
        cursor.close()
        if page_rows == 0:
            if scanned != total_products:
                raise RuntimeError(f"pair product scan incomplete: {scanned} != {total_products}")
            target.execute("BEGIN IMMEDIATE")
            target.execute(
                "UPDATE pipeline_keyset_checkpoints SET completed=1,updated_at=? "
                "WHERE pipeline_key=? AND stage='pairs' AND partition_key=''",
                (f"{config['contract_date']}T00:00:00Z", pipeline_key),
            )
            target.commit()
            return False
        batches += 1
        completed = scanned == total_products
        should_stop = commit_checkpoint_batch(
            target,
            limiter=limiter,
            pipeline_key=pipeline_key,
            stage="pairs",
            inserts_sql=(
                "INSERT INTO outcome_pair_plan_pairs VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            ),
            inserts=inserts,
            last_key=[last_action, last_series],
            rows_written=written,
            batches_committed=batches,
            semantic_chain=chain,
            completed=completed,
            updated_at=f"{config['contract_date']}T00:00:00Z",
            scanned_pairs=page_rows,
            eligible_pairs=len(inserts),
        )
        if completed:
            return False
        if should_stop:
            return True


def output_summary(
    connection: sqlite3.Connection,
    *,
    pipeline_key: str,
    roots: dict[str, str],
    config: dict[str, Any],
) -> dict[str, Any]:
    counts = {
        "actions": connection.execute(
            "SELECT COUNT(*) FROM outcome_pair_plan_actions WHERE pipeline_key=?",
            (pipeline_key,),
        ).fetchone()[0],
        "series": connection.execute(
            "SELECT COUNT(*) FROM outcome_pair_plan_series WHERE pipeline_key=?",
            (pipeline_key,),
        ).fetchone()[0],
        "pairs": connection.execute(
            "SELECT COUNT(*) FROM outcome_pair_plan_pairs WHERE pipeline_key=?",
            (pipeline_key,),
        ).fetchone()[0],
    }
    base_partition_rows = {
        row[0]: row[1]
        for row in connection.execute(
            "SELECT base_partition_key,COUNT(*) FROM outcome_pair_plan_pairs "
            "WHERE pipeline_key=? GROUP BY base_partition_key ORDER BY base_partition_key",
            (pipeline_key,),
        )
    }
    bucket_partition_rows = {
        row[0]: row[1]
        for row in connection.execute(
            "SELECT partition_key,COUNT(*) FROM outcome_pair_plan_pairs "
            "WHERE pipeline_key=? GROUP BY partition_key ORDER BY partition_key",
            (pipeline_key,),
        )
    }
    checkpoints = []
    for row in connection.execute(
        "SELECT stage,last_key_json,rows_written,batches_committed,"
        "semantic_chain_sha256,completed FROM pipeline_keyset_checkpoints "
        "WHERE pipeline_key=? ORDER BY stage",
        (pipeline_key,),
    ):
        checkpoints.append(
            {
                "stage": row["stage"],
                "last_key": load_json_value(row["last_key_json"], "checkpoint key"),
                "rows_written": row["rows_written"],
                "batches_committed": row["batches_committed"],
                "semantic_chain_sha256": row["semantic_chain_sha256"],
                "completed": bool(row["completed"]),
            }
        )
    chains = {row["stage"]: row["semantic_chain_sha256"] for row in checkpoints}
    semantic_root = sha256_bytes(
        canonical_bytes(
            {
                "contract_version": "outcome_pair_plan_semantic_root_v1",
                **roots,
                "counts": counts,
                "base_partition_rows": base_partition_rows,
                "bucket_partition_rows": bucket_partition_rows,
                "stage_semantic_chains": chains,
                "policy": config["policy"],
            }
        )
    )
    return {
        "counts": counts,
        "base_partition_rows": base_partition_rows,
        "bucket_partition_rows": bucket_partition_rows,
        "checkpoints": checkpoints,
        "semantic_root_sha256": semantic_root,
    }


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--actions-db", type=Path)
    parser.add_argument("--indicators-db", type=Path)
    parser.add_argument("--out-db", type=Path, default=DEFAULT_OUT_DB)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--batch-size", type=int, default=1_000)
    parser.add_argument("--source-batch-size", type=int, default=10_000)
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--fault-before-checkpoint-batch", type=int)
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.monotonic()
    if args.batch_size < 1 or args.source_batch_size < 1:
        raise RuntimeError("batch sizes must be positive")
    if args.max_batches is not None and args.max_batches < 1:
        raise RuntimeError("max-batches must be positive")
    if args.fault_before_checkpoint_batch is not None and args.fault_before_checkpoint_batch < 1:
        raise RuntimeError("fault batch must be positive")

    config = load_json(args.config)
    validate_config(config)
    if args.batch_size != config["checkpoint_batch_size"]:
        raise RuntimeError(
            "batch-size must equal config checkpoint_batch_size so resume progress "
            "is independently verifiable"
        )
    config_sha = sha256_bytes(canonical_bytes(config))
    schema_block, schema_root = extract_schema_block(args.schema)
    actions_path = args.actions_db or resolve_config_path(config["sources"]["actions"]["path"])
    indicators_path = args.indicators_db or resolve_config_path(
        config["sources"]["indicators"]["path"]
    )

    action_fact, action_identity = file_sha256_stable(actions_path)
    indicator_fact, indicator_identity = file_sha256_stable(indicators_path)
    expected_action_fact = config["sources"]["actions"]
    expected_indicator_fact = config["sources"]["indicators"]
    check_source_fact(action_fact, expected_action_fact, "actions")
    check_source_fact(indicator_fact, expected_indicator_fact, "indicators")

    with tempfile.TemporaryDirectory(prefix="vclc-outcome-pair-input-") as temp_dir:
        cache = init_input_cache(Path(temp_dir) / "input-cache.db")
        actions = open_source(actions_path)
        indicators = open_source(indicators_path)
        try:
            inputs = hydrate_real_inputs(
                config=config,
                actions=actions,
                indicators=indicators,
                cache=cache,
                source_batch_size=args.source_batch_size,
            )
            if actions.total_changes or indicators.total_changes:
                raise RuntimeError("read-only source connection reports writes")
            actions.commit()
            indicators.commit()
        finally:
            actions.close()
            indicators.close()
        assert_source_stable(actions_path, action_identity)
        assert_source_stable(indicators_path, indicator_identity)

        roots = {
            "config_sha256": config_sha,
            "input_root_sha256": inputs["input_root_sha256"],
            "schema_root_sha256": schema_root,
        }
        pipeline_digest = sha256_bytes(
            canonical_bytes(
                {
                    "contract_version": "outcome_pair_plan_pipeline_identity_v1",
                    **roots,
                }
            )
        )
        pipeline_key = f"vclc:outcome-pair-plan-pipeline:{pipeline_digest[:24]}"
        target_existed = args.out_db.exists() and args.out_db.stat().st_size > 0
        target = open_target(args.out_db, schema_block, roots)
        limiter = RunLimiter(args.max_batches, args.fault_before_checkpoint_batch)
        try:
            existing_stage_states = {
                row["stage"]: bool(row["completed"])
                for row in target.execute(
                    "SELECT stage,completed FROM pipeline_keyset_checkpoints "
                    "WHERE pipeline_key=? AND partition_key=''",
                    (pipeline_key,),
                )
            }
            pre_complete = all(existing_stage_states.get(stage, False) for stage in STAGES)
            interrupted = materialize_actions(
                target=target,
                cache=cache,
                pipeline_key=pipeline_key,
                config=config,
                roots=roots,
                batch_size=args.batch_size,
                limiter=limiter,
            )
            if not interrupted:
                interrupted = materialize_series(
                    target=target,
                    cache=cache,
                    pipeline_key=pipeline_key,
                    config=config,
                    roots=roots,
                    batch_size=args.batch_size,
                    limiter=limiter,
                )
            if not interrupted:
                interrupted = materialize_pairs(
                    target=target,
                    pipeline_key=pipeline_key,
                    config=config,
                    roots=roots,
                    batch_size=args.batch_size,
                    limiter=limiter,
                )
            summary = output_summary(
                target,
                pipeline_key=pipeline_key,
                roots=roots,
                config=config,
            )
            foreign_key_errors = sum(1 for _ in target.execute("PRAGMA foreign_key_check"))
        finally:
            target.close()
            cache.close()

    completed = len(summary["checkpoints"]) == 3 and all(
        row["completed"] for row in summary["checkpoints"]
    )
    if completed:
        expected = config["expected"]
        if summary["counts"] != {
            "actions": expected["dated_actions"],
            "series": expected["eligible_es_annual_series"],
            "pairs": expected["eligible_pairs"],
        }:
            raise RuntimeError(f"completed plan count mismatch: {summary['counts']!r}")
        if summary["base_partition_rows"] != expected["partition_rows"]:
            raise RuntimeError("completed plan partition closure mismatch")
    status = "interrupted" if interrupted else "passed"
    execution = "resumed_or_new"
    if completed and pre_complete and limiter.committed == 0:
        execution = "replayed_noop"
    elif target_existed:
        execution = "resumed"
    else:
        execution = "fresh"
    elapsed = time.monotonic() - started
    selected_product = (
        config["expected"]["dated_actions"]
        * config["expected"]["eligible_es_annual_series"]
    )
    bucket_sizes = list(summary["bucket_partition_rows"].values())
    report = {
        "schema_version": REPORT_SCHEMA,
        "status": status,
        "execution": execution,
        "pipeline_key": pipeline_key,
        "contract_date": config["contract_date"],
        "policy": config["policy"],
        "roots": {
            **roots,
            "semantic_root_sha256": summary["semantic_root_sha256"],
            "input_component_roots": inputs["component_roots"],
        },
        "source_facts": {
            "actions": action_fact,
            "indicators": indicator_fact,
            "read_only_transactions": True,
            "non_empty_wal_rejected": True,
            "pre_post_stat_identity_match": True,
        },
        "source_counts": inputs["counts"],
        "plan_counts": {
            **summary["counts"],
            "base_partitions": len(summary["base_partition_rows"]),
            "bucket_partitions": len(summary["bucket_partition_rows"]),
            "max_bucket_partition_rows": max(bucket_sizes, default=0),
            "global_unfiltered_product": config["expected"]["global_unfiltered_product"],
            "selected_product": selected_product,
        },
        "base_partition_rows": summary["base_partition_rows"],
        "bucket_partition_distribution": {
            "partition_count": len(summary["bucket_partition_rows"]),
            "row_count": sum(summary["bucket_partition_rows"].values()),
            "minimum_rows": min(bucket_sizes, default=0),
            "maximum_rows": max(bucket_sizes, default=0),
            "distribution_sha256": sha256_bytes(
                canonical_bytes(summary["bucket_partition_rows"])
            ),
        },
        "checkpoints": summary["checkpoints"],
        "integrity": {
            "foreign_key_errors": foreign_key_errors,
            "config_input_schema_roots_pin_resume": True,
            "batch_rows_and_checkpoint_atomic": True,
            "streaming_keyset_no_offset": True,
            "official_names_source_resolvable": inputs["counts"]["distinct_official_names"],
            "member_votes_source_resolvable": inputs["counts"]["members"],
        },
        "performance": {
            "batch_size": args.batch_size,
            "source_batch_size": args.source_batch_size,
            "batches_attempted_this_run": limiter.attempted,
            "batches_committed_this_run": limiter.committed,
            "elapsed_seconds": round(elapsed, 6),
            "max_rss_bytes": max_rss_bytes(),
            "eligible_pairs_processed_this_run": limiter.eligible_pairs_processed,
            "scanned_pairs_processed_this_run": limiter.scanned_pairs_processed,
            "eligible_pairs_per_second": round(
                limiter.eligible_pairs_processed / elapsed, 3
            ) if limiter.eligible_pairs_processed else None,
            "scanned_pairs_per_second": round(
                limiter.scanned_pairs_processed / elapsed, 3
            ) if limiter.scanned_pairs_processed else None,
            "compute_cost_proxy_seconds_per_1000_eligible_pairs": round(
                elapsed / (limiter.eligible_pairs_processed / 1000), 6
            ) if limiter.eligible_pairs_processed else None,
            "output_database_bytes": args.out_db.stat().st_size,
            "retries": 0,
            "dead_letters": 0,
        },
        "artifact": {
            "database": repo_path(args.out_db),
            "report": repo_path(args.report_out),
        },
    }
    atomic_write_json(args.report_out, report)
    return report


def main() -> int:
    args = parse_args()
    try:
        report = run(args)
    except Exception as exc:
        try:
            atomic_write_json(
                args.report_out,
                {
                    "schema_version": REPORT_SCHEMA,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "success_report_invalidated": True,
                },
            )
        except Exception as report_exc:
            print(
                f"ERROR: could not invalidate stale report: {report_exc}",
                file=sys.stderr,
            )
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
