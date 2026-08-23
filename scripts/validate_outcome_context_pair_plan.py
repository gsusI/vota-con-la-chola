#!/usr/bin/env python3
"""Independently validate the canonical real C2A sparse pair plan."""

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
DEFAULT_PLAN_DB = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-v1.db"
DEFAULT_MATERIALIZATION_REPORT = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-v1-report.json"
DEFAULT_REPORT = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-v1-validation.json"
SCHEMA_BEGIN = "-- BEGIN OUTCOME PAIR PLANNER C2A SCHEMA"
SCHEMA_END = "-- END OUTCOME PAIR PLANNER C2A SCHEMA"
REPORT_SCHEMA = "outcome_context_pair_plan_validation_v1"

EXPECTED_CONFIG_SHA256 = "e707524e5bf7596388842dd88250074c865806f4f79cf72e7d78b2516f9d0d87"
EXPECTED_INPUT_ROOT_SHA256 = "6f00974d8bd9ab6aaf715dd57bcf4a1dc3e33d64e8a882d261c774477ea956ca"
EXPECTED_SCHEMA_ROOT_SHA256 = "a26c722dc3066e91c871a692782572114eaf289630abba0f21e0c02f257fa8b0"
EXPECTED_SEMANTIC_ROOT_SHA256 = "0fc7c257f891108dbeca034d8337bd0d342e019dfd2b0b5d6d09f76f74de54de"
EXPECTED_PIPELINE_KEY = "vclc:outcome-pair-plan-pipeline:fa09600aaac1cd953030a959"
EXPECTED_COMPONENT_ROOTS = {
    "actions": "82270662693210d25190f5fe82e7388c21beba29c1ec52d27aef3da2975d5881",
    "members": "95aac5313afd057f042d7c1d39a7cfc8b20db8522eff591fff52f84774cf1631",
    "points": "17de884213b0a7fb865e7020850ff724d328691dd413855cac8fc0d13f31f18f",
    "series": "231263de868f9eb05ead076c9253ec0311e93ec551277b2bed308faa10f79b4b",
}
EMPTY_CHAIN = hashlib.sha256(b"").hexdigest()

ACTION_SQL = "SELECT v.vote_event_id AS action_id,v.vote_date AS action_date,v.title AS action_label,v.source_id,v.source_record_pk,sr.source_record_id,sr.source_snapshot_date,substr(v.vote_event_id,5) AS official_action_url,v.source_url AS source_page_url,sr.content_sha256 AS source_record_content_sha256 FROM parl_vote_events v JOIN source_records sr ON sr.source_record_pk=v.source_record_pk WHERE v.source_id=? AND sr.source_snapshot_date=? AND v.vote_date IS NOT NULL AND trim(v.vote_date)<>'' AND (v.vote_date>? OR (v.vote_date=? AND v.vote_event_id>?)) ORDER BY v.vote_date,v.vote_event_id LIMIT ?"
MEMBER_SQL = "SELECT m.vote_event_id AS action_id,m.member_vote_id,m.seat,m.member_name,m.member_name_normalized,CAST(m.person_id AS TEXT) AS person_id,m.group_code,m.vote_choice,m.source_id,m.source_url,m.source_snapshot_date FROM parl_vote_member_votes m JOIN parl_vote_events v ON v.vote_event_id=m.vote_event_id JOIN source_records sr ON sr.source_record_pk=v.source_record_pk WHERE v.source_id=? AND sr.source_snapshot_date=? AND v.vote_date IS NOT NULL AND trim(v.vote_date)<>'' AND (m.vote_event_id>? OR (m.vote_event_id=? AND m.member_vote_id>?)) ORDER BY m.vote_event_id,m.member_vote_id LIMIT ?"
SERIES_SQL = "SELECT s.indicator_series_id,s.canonical_key,s.label AS series_label,json_extract(s.dimensions_json,'$.dataset_code') AS dataset_code,json_extract(s.dimensions_json,'$.series_dimensions.geo') AS geography_code,s.frequency AS frequency_code,s.unit AS unit_code,s.dimensions_json,s.source_id,s.source_record_pk,sr.source_record_id,sr.source_snapshot_date,s.source_url AS official_source_url,sr.content_sha256 AS source_record_content_sha256,json_extract(s.raw_payload,'$.origin_capture_sha256') AS origin_capture_sha256 FROM indicator_series s JOIN source_records sr ON sr.source_record_pk=s.source_record_pk WHERE s.source_id=? AND sr.source_snapshot_date=? AND s.frequency=? AND json_extract(s.dimensions_json,'$.series_dimensions.geo')=? AND s.indicator_series_id>? ORDER BY s.indicator_series_id LIMIT ?"
POINT_SQL = "SELECT p.indicator_series_id,p.date,p.indicator_point_id,CAST(p.value AS TEXT) AS value_decimal,p.value_text FROM indicator_points p JOIN indicator_series s ON s.indicator_series_id=p.indicator_series_id JOIN source_records sr ON sr.source_record_pk=s.source_record_pk WHERE s.source_id=? AND sr.source_snapshot_date=? AND s.frequency=? AND json_extract(s.dimensions_json,'$.series_dimensions.geo')=? AND (p.indicator_series_id>? OR (p.indicator_series_id=? AND (p.date>? OR (p.date=? AND p.indicator_point_id>?)))) ORDER BY p.indicator_series_id,p.date,p.indicator_point_id LIMIT ?"

TABLE_COLUMNS = {
    "pipeline_keyset_checkpoints": (
        "pipeline_key", "stage", "partition_key", "checkpoint_contract_version",
        "config_sha256", "input_root_sha256", "schema_root_sha256",
        "last_key_json", "rows_written", "batches_committed",
        "semantic_chain_sha256", "completed", "updated_at",
    ),
    "outcome_pair_plan_actions": (
        "action_plan_pk", "pipeline_key", "action_id", "action_date", "action_year",
        "action_label", "source_id", "source_record_pk", "source_record_id",
        "source_snapshot_date", "official_action_url", "source_page_url",
        "source_record_content_sha256", "member_vote_count", "official_name_count",
        "participant_projection_sha256", "row_semantic_sha256",
    ),
    "outcome_pair_plan_series": (
        "series_plan_pk", "pipeline_key", "indicator_series_id", "canonical_key",
        "series_label", "dataset_code", "country_code", "geography_code", "frequency_code",
        "unit_code", "dimensions_json", "source_id", "source_record_pk",
        "source_record_id", "source_snapshot_date", "official_source_url",
        "source_record_content_sha256", "origin_capture_sha256", "observation_count",
        "observation_years_json", "observation_projection_sha256",
        "first_observation_date", "last_observation_date", "row_semantic_sha256",
    ),
    "outcome_pair_plan_pairs": (
        "pair_plan_id", "pipeline_key", "base_partition_key", "pair_bucket",
        "partition_key", "action_plan_pk",
        "series_plan_pk", "action_year", "dataset_code", "strict_pre_latest_date",
        "strict_post_earliest_date", "evidence_level", "link_state",
        "association_assessment", "causal_assessment", "effect_estimate_state",
        "political_merit_or_blame", "corruption_assessment", "ranking_eligible",
        "publication_eligible", "row_semantic_sha256",
    ),
}
EXPECTED_INDEXES = {
    "idx_pipeline_keyset_checkpoints_state",
    "idx_outcome_pair_plan_actions_keyset",
    "idx_outcome_pair_plan_series_keyset",
    "idx_outcome_pair_plan_pairs_partition",
    "idx_outcome_pair_plan_pairs_action",
    "idx_outcome_pair_plan_pairs_series",
}
EXPECTED_TRIGGERS = {
    f"trg_{table}_no_{operation}"
    for table in (
        "outcome_pair_plan_actions",
        "outcome_pair_plan_series",
        "outcome_pair_plan_pairs",
    )
    for operation in ("update", "delete")
}
EXPECTED_TRIGGERS.add("trg_pipeline_keyset_checkpoints_roots_immutable")
EXPECTED_TRIGGERS.add("trg_pipeline_keyset_checkpoints_completed_immutable")


class Audit:
    def __init__(self) -> None:
        self.checks: dict[str, bool] = {}
        self.failed: list[str] = []

    def check(self, name: str, condition: bool) -> None:
        condition = bool(condition)
        self.checks[name] = condition
        if not condition:
            self.failed.append(name)

    def equal(self, name: str, actual: Any, expected: Any) -> None:
        self.check(name, actual == expected)
        if actual != expected:
            raise RuntimeError(f"{name}: expected {expected!r}, got {actual!r}")


def require_equal(label: str, actual: Any, expected: Any) -> None:
    """Fail fast without retaining one audit-dictionary entry per source row."""
    if actual != expected:
        raise RuntimeError(f"{label}: expected {expected!r}, got {actual!r}")


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


def parse_json(value: str) -> Any:
    return json.loads(value, object_pairs_hook=reject_duplicate_keys)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
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
    if "row_semantic_sha256" in row:
        raise RuntimeError("row semantic input must exclude its own digest")
    return sha256_bytes(
        canonical_bytes(
            {"contract_version": contract_version, "persisted_row": row}
        )
    )


def schema_object_definitions(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    names = set(TABLE_COLUMNS) | EXPECTED_INDEXES | EXPECTED_TRIGGERS
    placeholders = ",".join("?" for _ in names)
    result: list[dict[str, Any]] = []
    for row in connection.execute(
        f"SELECT type,name,tbl_name,sql FROM sqlite_master "
        f"WHERE name IN ({placeholders}) ORDER BY type,name",
        tuple(sorted(names)),
    ):
        result.append(
            {
                "type": row[0],
                "name": row[1],
                "table": row[2],
                "sql": " ".join((row[3] or "").split()),
            }
        )
    return result


def max_rss_bytes() -> int:
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_nonempty_wal(path: Path) -> None:
    wal = Path(f"{path}-wal")
    if wal.exists() and wal.stat().st_size:
        raise RuntimeError(f"non-empty source WAL: {repo_path(path)}")


def open_source(path: Path) -> tuple[sqlite3.Connection, tuple[int, ...]]:
    reject_nonempty_wal(path)
    stat = path.stat()
    identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro&immutable=1", uri=True
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.execute("BEGIN")
    return connection, identity


def close_source(connection: sqlite3.Connection, path: Path, identity: tuple[int, ...]) -> None:
    if connection.total_changes:
        raise RuntimeError("source connection wrote data")
    connection.commit()
    connection.close()
    reject_nonempty_wal(path)
    stat = path.stat()
    after = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    if after != identity:
        raise RuntimeError(f"source changed during validation: {repo_path(path)}")


def query_pages(
    connection: sqlite3.Connection, sql: str, parameters_for_key: Any
) -> Iterator[sqlite3.Row]:
    while True:
        cursor = connection.execute(sql, parameters_for_key())
        seen = 0
        for row in cursor:
            seen += 1
            yield row
        cursor.close()
        if seen == 0:
            return


def build_source_cache(
    *,
    config: dict[str, Any],
    actions: sqlite3.Connection,
    indicators: sqlite3.Connection,
    cache_path: Path,
    page_size: int,
) -> tuple[sqlite3.Connection, dict[str, Any]]:
    cache = sqlite3.connect(cache_path)
    cache.row_factory = sqlite3.Row
    cache.executescript(
        """
        PRAGMA journal_mode=OFF;
        CREATE TABLE actions(
          action_id TEXT PRIMARY KEY,action_date TEXT,action_label TEXT,source_id TEXT,
          source_record_pk INTEGER,source_record_id TEXT,source_snapshot_date TEXT,
          official_action_url TEXT,source_page_url TEXT,
          source_record_content_sha256 TEXT,member_vote_count INTEGER,
          official_name_count INTEGER,participant_projection_sha256 TEXT
        );
        CREATE INDEX idx_actions_order ON actions(action_date,action_id);
        CREATE TABLE series(
          indicator_series_id INTEGER PRIMARY KEY,canonical_key TEXT,series_label TEXT,
          dataset_code TEXT,geography_code TEXT,frequency_code TEXT,unit_code TEXT,
          dimensions_json TEXT,source_id TEXT,source_record_pk INTEGER,
          source_record_id TEXT,source_snapshot_date TEXT,official_source_url TEXT,
          source_record_content_sha256 TEXT,origin_capture_sha256 TEXT,
          observation_count INTEGER,observation_dates_json TEXT,
          observation_projection_sha256 TEXT
        );
        CREATE TABLE names(name TEXT PRIMARY KEY);
        CREATE TABLE member_aggs(
          action_id TEXT PRIMARY KEY,row_count INTEGER,distinct_name_count INTEGER,
          projection_sha256 TEXT
        );
        CREATE TABLE point_aggs(
          indicator_series_id INTEGER PRIMARY KEY,row_count INTEGER,
          dates_json TEXT,projection_sha256 TEXT
        );
        """
    )
    action_src = config["sources"]["actions"]
    indicator_src = config["sources"]["indicators"]
    hashers = {name: hashlib.sha256() for name in ("actions", "members", "series", "points")}
    counts = {name: 0 for name in hashers}

    action_key = ["", ""]
    for row in query_pages(
        actions,
        ACTION_SQL,
        lambda: (
            action_src["source_id"], action_src["source_snapshot_date"],
            action_key[0], action_key[0], action_key[1], page_size,
        ),
    ):
        item = dict(row)
        stream_hash_add(hashers["actions"], item)
        counts["actions"] += 1
        cache.execute(
            "INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            tuple(item.values()) + (None, None, None),
        )
        action_key[:] = [item["action_date"], item["action_id"]]

    member_key: list[Any] = ["", -1]
    current_action: str | None = None
    current_count = 0
    current_names: set[str] = set()
    current_hasher = hashlib.sha256()

    def finish_members() -> None:
        if current_action is None:
            return
        cache.execute(
            "INSERT INTO member_aggs VALUES (?,?,?,?)",
            (
                current_action,
                current_count,
                len(current_names),
                stream_root(
                    "outcome_pair_plan_action_participant_projection_v1",
                    current_count,
                    current_hasher,
                ),
            ),
        )

    for row in query_pages(
        actions,
        MEMBER_SQL,
        lambda: (
            action_src["source_id"], action_src["source_snapshot_date"],
            member_key[0], member_key[0], member_key[1], page_size,
        ),
    ):
        item = dict(row)
        if current_action != item["action_id"]:
            finish_members()
            current_action = item["action_id"]
            current_count = 0
            current_names = set()
            current_hasher = hashlib.sha256()
        stream_hash_add(current_hasher, item)
        stream_hash_add(hashers["members"], item)
        counts["members"] += 1
        current_count += 1
        current_names.add(item["member_name"])
        cache.execute("INSERT OR IGNORE INTO names VALUES (?)", (item["member_name"],))
        member_key[:] = [item["action_id"], item["member_vote_id"]]
    finish_members()
    cache.execute(
        """
        UPDATE actions
        SET member_vote_count=(SELECT row_count FROM member_aggs m WHERE m.action_id=actions.action_id),
            official_name_count=(SELECT distinct_name_count FROM member_aggs m WHERE m.action_id=actions.action_id),
            participant_projection_sha256=(SELECT projection_sha256 FROM member_aggs m WHERE m.action_id=actions.action_id)
        """
    )

    series_key = [-1]
    for row in query_pages(
        indicators,
        SERIES_SQL,
        lambda: (
            indicator_src["source_id"], indicator_src["source_snapshot_date"],
            indicator_src["frequency_code"], indicator_src["geography_code"],
            series_key[0], page_size,
        ),
    ):
        item = dict(row)
        item["dimensions_json"] = canonical_json(parse_json(item["dimensions_json"]))
        stream_hash_add(hashers["series"], item)
        counts["series"] += 1
        cache.execute(
            "INSERT INTO series VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            tuple(item.values()) + (None, None, None),
        )
        series_key[0] = item["indicator_series_id"]

    point_key: list[Any] = [-1, "", -1]
    current_series: int | None = None
    current_dates: list[str] = []
    current_point_hasher = hashlib.sha256()

    def finish_points() -> None:
        if current_series is None:
            return
        cache.execute(
            "INSERT INTO point_aggs VALUES (?,?,?,?)",
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

    for row in query_pages(
        indicators,
        POINT_SQL,
        lambda: (
            indicator_src["source_id"], indicator_src["source_snapshot_date"],
            indicator_src["frequency_code"], indicator_src["geography_code"],
            point_key[0], point_key[0], point_key[1], point_key[1], point_key[2],
            page_size,
        ),
    ):
        item = dict(row)
        if current_series != item["indicator_series_id"]:
            finish_points()
            current_series = item["indicator_series_id"]
            current_dates = []
            current_point_hasher = hashlib.sha256()
        current_dates.append(item["date"])
        stream_hash_add(current_point_hasher, item)
        stream_hash_add(hashers["points"], item)
        counts["points"] += 1
        point_key[:] = [item["indicator_series_id"], item["date"], item["indicator_point_id"]]
    finish_points()
    cache.execute(
        """
        UPDATE series
        SET observation_count=(SELECT row_count FROM point_aggs p WHERE p.indicator_series_id=series.indicator_series_id),
            observation_dates_json=(SELECT dates_json FROM point_aggs p WHERE p.indicator_series_id=series.indicator_series_id),
            observation_projection_sha256=(SELECT projection_sha256 FROM point_aggs p WHERE p.indicator_series_id=series.indicator_series_id)
        """
    )
    cache.commit()
    distinct_names = cache.execute("SELECT COUNT(*) FROM names").fetchone()[0]
    actions_with_duplicate_names = cache.execute(
        "SELECT COUNT(*) FROM member_aggs WHERE row_count<>distinct_name_count"
    ).fetchone()[0]
    if actions_with_duplicate_names:
        raise RuntimeError(
            "real Senate source has repeated official names within an action: "
            f"{actions_with_duplicate_names} actions"
        )
    all_series = indicators.execute("SELECT COUNT(*) FROM indicator_series").fetchone()[0]
    component_roots = {
        key: stream_root(f"outcome_pair_plan_input_{key}_v1", counts[key], value)
        for key, value in hashers.items()
    }
    input_root = sha256_bytes(
        canonical_bytes(
            {
                "contract_version": "outcome_pair_plan_input_root_v1",
                "component_roots": component_roots,
                "counts": {
                    **counts,
                    "distinct_official_names": distinct_names,
                    "all_indicator_series": all_series,
                },
                "source_snapshots": {
                    "actions": action_src["source_snapshot_date"],
                    "indicators": indicator_src["source_snapshot_date"],
                },
            }
        )
    )
    return cache, {
        "counts": {
            **counts,
            "distinct_official_names": distinct_names,
            "all_indicator_series": all_series,
        },
        "component_roots": component_roots,
        "input_root_sha256": input_root,
    }


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
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
    parser.add_argument("--plan-db", type=Path, default=DEFAULT_PLAN_DB)
    parser.add_argument(
        "--materialization-report", type=Path, default=DEFAULT_MATERIALIZATION_REPORT
    )
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--page-size", type=int, default=10_000)
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.monotonic()
    audit = Audit()
    config = load_json(args.config)
    materialization = load_json(args.materialization_report)
    config_sha = sha256_bytes(canonical_bytes(config))
    audit.equal("canonical_config_sha256", config_sha, EXPECTED_CONFIG_SHA256)
    query = config["query_contract"]
    exact_queries = {
        "actions": ACTION_SQL,
        "members": MEMBER_SQL,
        "series": SERIES_SQL,
        "points": POINT_SQL,
    }
    for name, sql in exact_queries.items():
        audit.equal(f"{name}_query_exact", query[f"{name}_keyset_sql_utf8"], sql)
        audit.equal(
            f"{name}_query_sha256",
            query[f"{name}_keyset_sql_sha256"],
            sha256_bytes(sql.encode()),
        )
        audit.check(f"{name}_query_no_offset", " OFFSET " not in f" {sql.upper()} ")

    schema_text = args.schema.read_text(encoding="utf-8")
    start = schema_text.index(SCHEMA_BEGIN)
    end = schema_text.index(SCHEMA_END)
    schema_block = schema_text[start : end + len(SCHEMA_END)] + "\n"
    schema_root = sha256_bytes(schema_block.encode())
    audit.equal("schema_root_sha256", schema_root, EXPECTED_SCHEMA_ROOT_SHA256)
    reference_schema = sqlite3.connect(":memory:")
    try:
        reference_schema.executescript(schema_block)
        expected_schema_definitions = schema_object_definitions(reference_schema)
    finally:
        reference_schema.close()

    actions_path = args.actions_db or resolve_config_path(config["sources"]["actions"]["path"])
    indicators_path = args.indicators_db or resolve_config_path(
        config["sources"]["indicators"]["path"]
    )
    for label, path in (("actions", actions_path), ("indicators", indicators_path)):
        expected = config["sources"][label]
        audit.equal(f"{label}_source_path", repo_path(path), expected["path"])
        audit.equal(f"{label}_source_bytes", path.stat().st_size, expected["bytes"])
        audit.equal(f"{label}_source_sha256", sha256_file(path), expected["sha256"])

    actions, action_identity = open_source(actions_path)
    indicators, indicator_identity = open_source(indicators_path)
    with tempfile.TemporaryDirectory(prefix="vclc-outcome-pair-validation-") as temp_dir:
        try:
            source_cache, source = build_source_cache(
                config=config,
                actions=actions,
                indicators=indicators,
                cache_path=Path(temp_dir) / "source-cache.db",
                page_size=args.page_size,
            )
            close_source(actions, actions_path, action_identity)
            close_source(indicators, indicators_path, indicator_identity)
        except Exception:
            actions.close()
            indicators.close()
            raise
        audit.equal("input_component_roots", source["component_roots"], EXPECTED_COMPONENT_ROOTS)
        audit.equal("input_root_sha256", source["input_root_sha256"], EXPECTED_INPUT_ROOT_SHA256)
        audit.equal(
            "source_counts",
            source["counts"],
            {
                "actions": 458,
                "members": 119116,
                "series": 75,
                "points": 937,
                "distinct_official_names": 490,
                "all_indicator_series": 155435,
            },
        )

        plan = sqlite3.connect(f"file:{args.plan_db.resolve().as_posix()}?mode=rw", uri=True)
        plan.row_factory = sqlite3.Row
        plan.execute("PRAGMA foreign_keys=ON")
        try:
            tables = {
                row[0]
                for row in plan.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            audit.equal("exact_c2a_tables", tables, set(TABLE_COLUMNS))
            for table, columns in TABLE_COLUMNS.items():
                actual = tuple(row[1] for row in plan.execute(f"PRAGMA table_info({table})"))
                audit.equal(f"{table}_columns", actual, columns)
            indexes = {
                row[0]
                for row in plan.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
                )
            }
            audit.equal("planner_indexes", indexes, EXPECTED_INDEXES)
            triggers = {
                row[0]
                for row in plan.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
            }
            audit.equal("append_only_triggers", triggers, EXPECTED_TRIGGERS)
            audit.equal(
                "canonical_schema_object_definitions",
                schema_object_definitions(plan),
                expected_schema_definitions,
            )

            checkpoints = {
                row["stage"]: dict(row)
                for row in plan.execute(
                    "SELECT * FROM pipeline_keyset_checkpoints ORDER BY stage"
                )
            }
            audit.equal("checkpoint_stages", set(checkpoints), {"actions", "series", "pairs"})
            last_action = source_cache.execute(
                "SELECT action_date,action_id FROM actions "
                "ORDER BY action_date DESC,action_id DESC LIMIT 1"
            ).fetchone()
            last_series_id = source_cache.execute(
                "SELECT MAX(indicator_series_id) FROM series"
            ).fetchone()[0]
            expected_checkpoint_progress = {
                "actions": {
                    "last_key": [last_action["action_date"], last_action["action_id"]],
                    "rows_written": 458,
                    "work_rows": 458,
                },
                "series": {
                    "last_key": [last_series_id],
                    "rows_written": 75,
                    "work_rows": 75,
                },
                "pairs": {
                    "last_key": [458, 75],
                    "rows_written": 33726,
                    "work_rows": 458 * 75,
                },
            }
            checkpoint_batch_size = config["checkpoint_batch_size"]
            audit.equal(
                "materialization_checkpoint_batch_size",
                materialization["performance"]["batch_size"],
                checkpoint_batch_size,
            )
            for stage, row in checkpoints.items():
                audit.equal(f"{stage}_checkpoint_pipeline", row["pipeline_key"], EXPECTED_PIPELINE_KEY)
                audit.equal(f"{stage}_checkpoint_partition", row["partition_key"], "")
                audit.equal(
                    f"{stage}_checkpoint_contract",
                    row["checkpoint_contract_version"],
                    config["checkpoint_contract_version"],
                )
                audit.equal(f"{stage}_checkpoint_config", row["config_sha256"], EXPECTED_CONFIG_SHA256)
                audit.equal(f"{stage}_checkpoint_input", row["input_root_sha256"], EXPECTED_INPUT_ROOT_SHA256)
                audit.equal(f"{stage}_checkpoint_schema", row["schema_root_sha256"], EXPECTED_SCHEMA_ROOT_SHA256)
                audit.equal(
                    f"{stage}_checkpoint_last_key",
                    parse_json(row["last_key_json"]),
                    expected_checkpoint_progress[stage]["last_key"],
                )
                audit.equal(
                    f"{stage}_checkpoint_rows_written",
                    row["rows_written"],
                    expected_checkpoint_progress[stage]["rows_written"],
                )
                audit.equal(
                    f"{stage}_checkpoint_batches_exact",
                    row["batches_committed"],
                    (
                        expected_checkpoint_progress[stage]["work_rows"]
                        + checkpoint_batch_size
                        - 1
                    )
                    // checkpoint_batch_size,
                )
                audit.equal(f"{stage}_checkpoint_complete", row["completed"], 1)
                audit.equal(
                    f"{stage}_checkpoint_updated_at",
                    row["updated_at"],
                    f"{config['contract_date']}T00:00:00Z",
                )
            checkpoint_projection = [
                {
                    "stage": stage,
                    "last_key": parse_json(checkpoints[stage]["last_key_json"]),
                    "rows_written": checkpoints[stage]["rows_written"],
                    "batches_committed": checkpoints[stage]["batches_committed"],
                    "semantic_chain_sha256": checkpoints[stage]["semantic_chain_sha256"],
                    "completed": bool(checkpoints[stage]["completed"]),
                }
                for stage in sorted(checkpoints)
            ]
            audit.equal(
                "materialization_checkpoint_parity",
                materialization["checkpoints"],
                checkpoint_projection,
            )
            audit.check(
                "materialization_execution_known",
                materialization["execution"] in {"fresh", "resumed", "replayed_noop"},
            )
            plan.execute("SAVEPOINT checkpoint_roots")
            try:
                try:
                    plan.execute(
                        "UPDATE pipeline_keyset_checkpoints SET config_sha256=? "
                        "WHERE stage='actions'",
                        ("0" * 64,),
                    )
                except sqlite3.IntegrityError:
                    audit.check("checkpoint_identity_roots_immutable", True)
                else:
                    audit.check("checkpoint_identity_roots_immutable", False)
                plan.execute("ROLLBACK TO checkpoint_roots")
            finally:
                plan.execute("RELEASE checkpoint_roots")

            action_chain = EMPTY_CHAIN
            target_actions = plan.execute(
                "SELECT * FROM outcome_pair_plan_actions ORDER BY action_plan_pk"
            )
            source_actions = source_cache.execute(
                "SELECT * FROM actions ORDER BY action_date,action_id"
            )
            action_count = 0
            for action_count, (expected_row, actual_row) in enumerate(
                zip(source_actions, target_actions, strict=True), start=1
            ):
                expected_dict = dict(expected_row)
                expected_persisted = {
                    "action_plan_pk": action_count,
                    "pipeline_key": EXPECTED_PIPELINE_KEY,
                    **{key: expected_dict[key] for key in TABLE_COLUMNS["outcome_pair_plan_actions"] if key in expected_dict},
                    "action_year": int(expected_dict["action_date"][:4]),
                }
                row_sha = persisted_row_sha256(
                    "outcome_pair_plan_action_row_v2", expected_persisted
                )
                action_chain = chain_add(action_chain, row_sha)
                expected_target = {
                    **expected_persisted,
                    "row_semantic_sha256": row_sha,
                }
                require_equal(f"action row {action_count}", dict(actual_row), expected_target)
            audit.equal("action_count", action_count, 458)
            audit.check("all_action_rows_source_exact", True)
            audit.equal("action_chain", action_chain, checkpoints["actions"]["semantic_chain_sha256"])

            series_chain = EMPTY_CHAIN
            target_series = plan.execute(
                "SELECT * FROM outcome_pair_plan_series ORDER BY series_plan_pk"
            )
            source_series = source_cache.execute(
                "SELECT * FROM series ORDER BY indicator_series_id"
            )
            series_count = 0
            for series_count, (expected_row, actual_row) in enumerate(
                zip(source_series, target_series, strict=True), start=1
            ):
                expected_dict = dict(expected_row)
                dates = parse_json(expected_dict.pop("observation_dates_json"))
                years = [int(value[:4]) for value in dates]
                expected_persisted = {
                    "series_plan_pk": series_count,
                    "pipeline_key": EXPECTED_PIPELINE_KEY,
                    **{key: expected_dict[key] for key in TABLE_COLUMNS["outcome_pair_plan_series"] if key in expected_dict},
                    "country_code": expected_dict["geography_code"][:2],
                    "observation_years_json": canonical_json(years),
                    "first_observation_date": dates[0],
                    "last_observation_date": dates[-1],
                }
                row_sha = persisted_row_sha256(
                    "outcome_pair_plan_series_row_v2", expected_persisted
                )
                series_chain = chain_add(series_chain, row_sha)
                expected_target = {
                    **expected_persisted,
                    "row_semantic_sha256": row_sha,
                }
                require_equal(f"series row {series_count}", dict(actual_row), expected_target)
            audit.equal("series_count", series_count, 75)
            audit.check("all_series_rows_source_exact", True)
            audit.equal("series_chain", series_chain, checkpoints["series"]["semantic_chain_sha256"])

            pair_chain = EMPTY_CHAIN
            pair_count = 0
            base_partitions: dict[str, int] = {}
            bucket_partitions: dict[str, int] = {}
            target_pairs = iter(
                plan.execute(
                    "SELECT * FROM outcome_pair_plan_pairs ORDER BY action_plan_pk,series_plan_pk"
                )
            )
            product = source_cache.execute(
                """
                WITH ordered_actions AS (
                  SELECT ROW_NUMBER() OVER (
                           ORDER BY action_date,action_id
                         ) AS action_plan_pk,
                         action_id,action_date,source_id AS action_source_id
                  FROM actions
                ), ordered_series AS (
                  SELECT ROW_NUMBER() OVER (
                           ORDER BY indicator_series_id
                         ) AS series_plan_pk,
                         indicator_series_id,canonical_key,dataset_code,
                         source_id AS indicator_source_id,geography_code,
                         observation_dates_json
                  FROM series
                )
                SELECT a.action_plan_pk,a.action_id,a.action_date,a.action_source_id,
                       s.series_plan_pk,s.indicator_series_id,s.canonical_key,
                       s.dataset_code,s.indicator_source_id,s.geography_code,
                       s.observation_dates_json
                FROM ordered_actions a CROSS JOIN ordered_series s
                ORDER BY a.action_plan_pk,s.series_plan_pk
                """
            )
            for product_row in product:
                action_year = int(product_row["action_date"][:4])
                years = [int(value[:4]) for value in parse_json(product_row["observation_dates_json"])]
                pre = [year for year in years if year < action_year]
                post = [year for year in years if year > action_year]
                if not pre or not post:
                    continue
                pair_count += 1
                actual = next(target_pairs, None)
                if actual is None:
                    raise RuntimeError("pair plan ended before independent source product")
                identity = {
                    "identity_contract_version": "outcome_pair_plan_identity_v1",
                    "action_id": product_row["action_id"],
                    "indicator_series_canonical_key": product_row["canonical_key"],
                    "eligibility": "strict_pre_and_strict_post_annual_observations",
                }
                identity_sha = sha256_bytes(canonical_bytes(identity))
                pair_bucket = identity_sha[:2]
                base_partition = (
                    f"action_source={product_row['action_source_id']}/year={action_year}/"
                    f"indicator_source={product_row['indicator_source_id']}/"
                    f"dataset={product_row['dataset_code']}/"
                    f"country={product_row['geography_code'][:2]}"
                )
                partition = f"{base_partition}/bucket={pair_bucket}"
                base_partitions[base_partition] = base_partitions.get(base_partition, 0) + 1
                bucket_partitions[partition] = bucket_partitions.get(partition, 0) + 1
                expected_persisted = {
                    "pair_plan_id": f"vclc:outcome-pair-plan:{identity_sha[:24]}",
                    "pipeline_key": EXPECTED_PIPELINE_KEY,
                    "base_partition_key": base_partition,
                    "pair_bucket": pair_bucket,
                    "partition_key": partition,
                    "action_plan_pk": product_row["action_plan_pk"],
                    "series_plan_pk": product_row["series_plan_pk"],
                    "action_year": action_year,
                    "dataset_code": product_row["dataset_code"],
                    "strict_pre_latest_date": f"{max(pre):04d}-01-01",
                    "strict_post_earliest_date": f"{min(post):04d}-01-01",
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
                row_sha = persisted_row_sha256(
                    "outcome_pair_plan_pair_row_v2", expected_persisted
                )
                pair_chain = chain_add(pair_chain, row_sha)
                expected_target = {
                    **expected_persisted,
                    "row_semantic_sha256": row_sha,
                }
                require_equal(
                    f"pair row {pair_count}", dict(actual), expected_target
                )
            audit.equal("no_extra_pairs", next(target_pairs, None), None)
            audit.equal("pair_count", pair_count, 33726)
            audit.check("all_pair_rows_source_exact", True)
            audit.equal("pair_base_partitions", base_partitions, config["expected"]["partition_rows"])
            audit.equal("bucket_partition_count", len(bucket_partitions), 2598)
            audit.equal("bucket_partition_row_sum", sum(bucket_partitions.values()), 33726)
            audit.equal("bucket_partition_max_rows", max(bucket_partitions.values()), 93)
            audit.equal("pair_chain", pair_chain, checkpoints["pairs"]["semantic_chain_sha256"])
            audit.equal(
                "foreign_key_check",
                sum(1 for _ in plan.execute("PRAGMA foreign_key_check")),
                0,
            )

            counts = {"actions": action_count, "series": series_count, "pairs": pair_count}
            chains = {
                "actions": action_chain,
                "series": series_chain,
                "pairs": pair_chain,
            }
            semantic_root = sha256_bytes(
                canonical_bytes(
                    {
                        "contract_version": "outcome_pair_plan_semantic_root_v1",
                        "config_sha256": config_sha,
                        "input_root_sha256": source["input_root_sha256"],
                        "schema_root_sha256": schema_root,
                        "counts": counts,
                        "base_partition_rows": base_partitions,
                        "bucket_partition_rows": bucket_partitions,
                        "stage_semantic_chains": chains,
                        "policy": config["policy"],
                    }
                )
            )
            audit.equal("semantic_root_sha256", semantic_root, EXPECTED_SEMANTIC_ROOT_SHA256)

            unsafe = plan.execute(
                """
                SELECT COUNT(*) FROM outcome_pair_plan_pairs
                WHERE evidence_level<>'L0'
                   OR link_state<>'internal_discovery_pair'
                   OR association_assessment<>'not_assessed'
                   OR causal_assessment<>'not_assessed'
                   OR effect_estimate_state<>'not_computed'
                   OR political_merit_or_blame<>'not_assessed'
                   OR corruption_assessment<>'not_assessed'
                   OR ranking_eligible<>0 OR publication_eligible<>0
                """
            ).fetchone()[0]
            audit.equal("unsafe_claim_rows", unsafe, 0)
            for table, key in (
                ("outcome_pair_plan_actions", "action_plan_pk"),
                ("outcome_pair_plan_series", "series_plan_pk"),
                ("outcome_pair_plan_pairs", "pair_plan_id"),
            ):
                for operation in ("update", "delete"):
                    plan.execute("SAVEPOINT immutability")
                    try:
                        try:
                            if operation == "update":
                                plan.execute(
                                    f"UPDATE {table} SET {key}={key} "
                                    f"WHERE {key}=(SELECT {key} FROM {table} "
                                    f"ORDER BY {key} LIMIT 1)"
                                )
                            else:
                                plan.execute(
                                    f"DELETE FROM {table} "
                                    f"WHERE {key}=(SELECT {key} FROM {table} "
                                    f"ORDER BY {key} LIMIT 1)"
                                )
                        except sqlite3.IntegrityError:
                            audit.check(f"{table}_{operation}_blocked", True)
                        else:
                            audit.check(f"{table}_{operation}_blocked", False)
                        plan.execute("ROLLBACK TO immutability")
                    finally:
                        plan.execute("RELEASE immutability")
            plan.execute("SAVEPOINT completed_checkpoint_immutability")
            try:
                try:
                    plan.execute(
                        "UPDATE pipeline_keyset_checkpoints "
                        "SET rows_written=rows_written WHERE stage='actions'"
                    )
                except sqlite3.IntegrityError:
                    audit.check("completed_checkpoint_progress_immutable", True)
                else:
                    audit.check("completed_checkpoint_progress_immutable", False)
                plan.execute("ROLLBACK TO completed_checkpoint_immutability")
            finally:
                plan.execute("RELEASE completed_checkpoint_immutability")
            pair_plan = " ".join(
                row[3]
                for row in plan.execute(
                    "EXPLAIN QUERY PLAN SELECT pair_plan_id FROM outcome_pair_plan_pairs "
                    "WHERE pipeline_key=? AND base_partition_key=? AND pair_bucket=? "
                    "ORDER BY action_plan_pk,series_plan_pk",
                    (
                        EXPECTED_PIPELINE_KEY,
                        "action_source=senado_votaciones/year=2024/indicator_source=eurostat_sdmx/dataset=ilc_peps11n/country=ES",
                        "00",
                    ),
                )
            )
            audit.check("partition_index_used", "idx_outcome_pair_plan_pairs_partition" in pair_plan)

            audit.equal("materialization_status", materialization["status"], "passed")
            audit.equal("materialization_pipeline", materialization["pipeline_key"], EXPECTED_PIPELINE_KEY)
            audit.equal(
                "materialization_roots",
                {
                    key: materialization["roots"][key]
                    for key in (
                        "config_sha256",
                        "input_root_sha256",
                        "schema_root_sha256",
                        "semantic_root_sha256",
                    )
                },
                {
                    "config_sha256": EXPECTED_CONFIG_SHA256,
                    "input_root_sha256": EXPECTED_INPUT_ROOT_SHA256,
                    "schema_root_sha256": EXPECTED_SCHEMA_ROOT_SHA256,
                    "semantic_root_sha256": EXPECTED_SEMANTIC_ROOT_SHA256,
                },
            )
            audit.equal("materialization_plan_actions", materialization["plan_counts"]["actions"], 458)
            audit.equal("materialization_plan_series", materialization["plan_counts"]["series"], 75)
            audit.equal("materialization_plan_pairs", materialization["plan_counts"]["pairs"], 33726)
            audit.equal("materialization_base_partitions", materialization["plan_counts"]["base_partitions"], 18)
            audit.equal("materialization_bucket_partitions", materialization["plan_counts"]["bucket_partitions"], 2598)
            audit.equal("materialization_max_bucket_rows", materialization["plan_counts"]["max_bucket_partition_rows"], 93)
            audit.equal(
                "materialization_bucket_distribution",
                materialization["bucket_partition_distribution"],
                {
                    "partition_count": 2598,
                    "row_count": 33726,
                    "minimum_rows": min(bucket_partitions.values()),
                    "maximum_rows": max(bucket_partitions.values()),
                    "distribution_sha256": sha256_bytes(canonical_bytes(bucket_partitions)),
                },
            )
            audit.equal(
                "materialization_database_bytes",
                materialization["performance"]["output_database_bytes"],
                args.plan_db.stat().st_size,
            )
            audit.equal("materialization_retries", materialization["performance"]["retries"], 0)
            audit.equal("materialization_dead_letters", materialization["performance"]["dead_letters"], 0)
            audit.check("materialization_max_rss_bytes", materialization["performance"]["max_rss_bytes"] > 0)
            elapsed = materialization["performance"]["elapsed_seconds"]
            eligible_this_run = materialization["performance"]["eligible_pairs_processed_this_run"]
            scanned_this_run = materialization["performance"]["scanned_pairs_processed_this_run"]
            if eligible_this_run:
                audit.check(
                    "materialization_eligible_throughput_formula",
                    abs(
                        materialization["performance"]["eligible_pairs_per_second"]
                        - round(eligible_this_run / elapsed, 3)
                    ) <= 0.002,
                )
                audit.check(
                    "materialization_cost_proxy_formula",
                    abs(
                        materialization["performance"]["compute_cost_proxy_seconds_per_1000_eligible_pairs"]
                        - round(elapsed / (eligible_this_run / 1000), 6)
                    ) <= 0.000002,
                )
            else:
                audit.equal(
                    "materialization_noop_eligible_throughput",
                    materialization["performance"]["eligible_pairs_per_second"],
                    None,
                )
            if scanned_this_run:
                audit.check(
                    "materialization_scanned_throughput_formula",
                    abs(
                        materialization["performance"]["scanned_pairs_per_second"]
                        - round(scanned_this_run / elapsed, 3)
                    ) <= 0.002,
                )
            else:
                audit.equal(
                    "materialization_noop_scanned_throughput",
                    materialization["performance"]["scanned_pairs_per_second"],
                    None,
                )
        finally:
            plan.close()
            source_cache.close()

    if audit.failed:
        raise RuntimeError(f"validation checks failed: {audit.failed}")
    validation_elapsed = time.monotonic() - started
    report = {
        "schema_version": REPORT_SCHEMA,
        "status": "passed",
        "passed_checks": len(audit.checks),
        "failed_checks": audit.failed,
        "pipeline_key": EXPECTED_PIPELINE_KEY,
        "counts": {
            "actions": 458,
            "series": 75,
            "pairs": 33726,
            "base_partitions": 18,
            "member_votes_source_resolved": 119116,
            "official_names_source_resolved": 490,
            "eligible_series_observations": 937,
            "global_unfiltered_product": 71189230,
        },
        "roots": {
            "config_sha256": EXPECTED_CONFIG_SHA256,
            "input_root_sha256": EXPECTED_INPUT_ROOT_SHA256,
            "schema_root_sha256": EXPECTED_SCHEMA_ROOT_SHA256,
            "semantic_root_sha256": EXPECTED_SEMANTIC_ROOT_SHA256,
            "input_component_roots": EXPECTED_COMPONENT_ROOTS,
        },
        "proof": {
            "independent_source_reconstruction": True,
            "streaming_keyset_queries": True,
            "offset_queries": 0,
            "source_transactions_read_only": True,
            "non_empty_wal_rejected": True,
            "config_input_schema_roots_pinned": True,
            "checkpoint_stages_complete": 3,
            "append_only_plan_tables": 3,
            "official_public_identities_retained_at_source": True,
            "association_claims": 0,
            "causal_claims": 0,
            "effect_estimates": 0,
            "ranking_eligible_rows": 0,
            "publication_eligible_rows": 0,
        },
        "artifacts": {
            "plan_db": repo_path(args.plan_db),
            "config": repo_path(args.config),
            "schema": repo_path(args.schema),
            "materialization_report": repo_path(args.materialization_report),
            "report": repo_path(args.report_out),
        },
        "performance": {
            "elapsed_seconds": round(validation_elapsed, 6),
            "max_rss_bytes": max_rss_bytes(),
            "pairs_reconstructed": 33726,
            "pairs_per_second": round(33726 / validation_elapsed, 3),
            "compute_cost_proxy_seconds_per_1000_pairs": round(
                validation_elapsed / (33726 / 1000), 6
            ),
            "plan_database_bytes": args.plan_db.stat().st_size,
            "retries": 0,
            "dead_letters": 0,
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
