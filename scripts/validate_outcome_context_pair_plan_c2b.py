#!/usr/bin/env python3
"""Independently reconstruct and validate the real C2B ES* pair plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import resource
import sqlite3
import struct
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterator, Sequence
from urllib.parse import quote


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "etl/data/manual/outcome_links/planner_scope_c2b_v1.json"
DEFAULT_SCHEMA = REPO_ROOT / "etl/load/sqlite_schema.sql"
DEFAULT_PLAN_DB = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1.db"
DEFAULT_MATERIALIZATION_REPORT = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1-report.json"
DEFAULT_MANIFEST = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1-manifest.json"
DEFAULT_REPORT = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1-validation.json"
SCHEMA_BEGIN = "-- BEGIN OUTCOME PAIR PLANNER C2A SCHEMA"
SCHEMA_END = "-- END OUTCOME PAIR PLANNER C2A SCHEMA"
REPORT_SCHEMA = "outcome_context_pair_plan_c2b_validation_v1"
MANIFEST_SCHEMA = "outcome_context_pair_plan_c2b_manifest_v1"

EXPECTED_CONFIG_SHA256 = "7079f1d2faaeb7a3cd8176cf556c92b945246be85814d9a819cb8055927c195b"
EXPECTED_INPUT_ROOT_SHA256 = "7a4862f7e7c90792d6b7c46559d0ce2de97e5844b0ad87f064ec6e5f7d88d7a3"
EXPECTED_SCHEMA_ROOT_SHA256 = "a26c722dc3066e91c871a692782572114eaf289630abba0f21e0c02f257fa8b0"
EXPECTED_SEMANTIC_ROOT_SHA256 = "e9fecdb89e518c7d8f6ecc947c6930c84afa96dad031c4bbc332842cc685d7ae"
EXPECTED_PIPELINE_KEY = "vclc:outcome-pair-plan-c2b-pipeline:294c93befa7e73b46c84355d"
EXPECTED_DATABASE_BYTES = 3587743744
EXPECTED_DATABASE_SHA256 = "04c8265154bf6659971b732db135f07fe6db0d45a0482d775bb30c15bde57680"
EXPECTED_MANIFEST_ROOT_SHA256 = "9ba36e3994ef2ab1ba90dacf2441fc20fdcda6f14d1942f7fe4fc58be40a24b6"
EXPECTED_MANIFEST_FILE_SHA256 = "e89430cd5f537d93d6c73458b1fe3954eb541f0abce8f1adb9a5670b31b71007"
EXPECTED_COMPONENT_ROOTS = {
    "actions": "82270662693210d25190f5fe82e7388c21beba29c1ec52d27aef3da2975d5881",
    "members": "95aac5313afd057f042d7c1d39a7cfc8b20db8522eff591fff52f84774cf1631",
    "points": "86699a6b34e3b31425c10c11250cc2a5dba6e79db148a7eafae11a88314fa296",
    "series": "9fa9a9f0f4f99f39f0f7a2668cfd81e117f6352017d38d32a03c974948edda66",
}
EMPTY_CHAIN = hashlib.sha256(b"").hexdigest()

ACTION_SQL = "SELECT v.vote_event_id AS action_id,v.vote_date AS action_date,v.title AS action_label,v.source_id,v.source_record_pk,sr.source_record_id,sr.source_snapshot_date,substr(v.vote_event_id,5) AS official_action_url,v.source_url AS source_page_url,sr.content_sha256 AS source_record_content_sha256 FROM parl_vote_events v JOIN source_records sr ON sr.source_record_pk=v.source_record_pk WHERE v.source_id=? AND sr.source_snapshot_date=? AND v.vote_date IS NOT NULL AND trim(v.vote_date)<>'' AND (v.vote_date>? OR (v.vote_date=? AND v.vote_event_id>?)) ORDER BY v.vote_date,v.vote_event_id LIMIT ?"
MEMBER_SQL = "SELECT m.vote_event_id AS action_id,m.member_vote_id,m.seat,m.member_name,m.member_name_normalized,CAST(m.person_id AS TEXT) AS person_id,m.group_code,m.vote_choice,m.source_id,m.source_url,m.source_snapshot_date FROM parl_vote_member_votes m JOIN parl_vote_events v ON v.vote_event_id=m.vote_event_id JOIN source_records sr ON sr.source_record_pk=v.source_record_pk WHERE v.source_id=? AND sr.source_snapshot_date=? AND v.vote_date IS NOT NULL AND trim(v.vote_date)<>'' AND (m.vote_event_id>? OR (m.vote_event_id=? AND m.member_vote_id>?)) ORDER BY m.vote_event_id,m.member_vote_id LIMIT ?"
SERIES_SQL = "SELECT s.indicator_series_id,s.canonical_key,s.label AS series_label,json_extract(s.dimensions_json,'$.dataset_code') AS dataset_code,json_extract(s.dimensions_json,'$.series_dimensions.geo') AS geography_code,s.frequency AS frequency_code,s.unit AS unit_code,s.dimensions_json,s.source_id,s.source_record_pk,sr.source_record_id,sr.source_snapshot_date,s.source_url AS official_source_url,sr.content_sha256 AS source_record_content_sha256,json_extract(s.raw_payload,'$.origin_capture_sha256') AS origin_capture_sha256 FROM indicator_series s JOIN source_records sr ON sr.source_record_pk=s.source_record_pk WHERE s.source_id=? AND sr.source_snapshot_date=? AND s.frequency=? AND json_extract(s.dimensions_json,'$.series_dimensions.geo') GLOB ? AND s.indicator_series_id>? ORDER BY s.indicator_series_id LIMIT ?"
POINT_SQL = "SELECT p.indicator_series_id,p.date,p.indicator_point_id,CAST(p.value AS TEXT) AS value_decimal,p.value_text FROM indicator_points p JOIN indicator_series s ON s.indicator_series_id=p.indicator_series_id JOIN source_records sr ON sr.source_record_pk=s.source_record_pk WHERE s.source_id=? AND sr.source_snapshot_date=? AND s.frequency=? AND json_extract(s.dimensions_json,'$.series_dimensions.geo') GLOB ? AND (p.indicator_series_id>? OR (p.indicator_series_id=? AND (p.date>? OR (p.date=? AND p.indicator_point_id>?)))) ORDER BY p.indicator_series_id,p.date,p.indicator_point_id LIMIT ?"

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
        "series_label", "dataset_code", "country_code", "geography_code",
        "frequency_code", "unit_code", "dimensions_json", "source_id",
        "source_record_pk", "source_record_id", "source_snapshot_date",
        "official_source_url", "source_record_content_sha256", "origin_capture_sha256",
        "observation_count", "observation_years_json",
        "observation_projection_sha256", "first_observation_date",
        "last_observation_date", "row_semantic_sha256",
    ),
    "outcome_pair_plan_pairs": (
        "pair_plan_id", "pipeline_key", "base_partition_key", "pair_bucket",
        "partition_key", "action_plan_pk", "series_plan_pk", "action_year",
        "dataset_code", "strict_pre_latest_date", "strict_post_earliest_date",
        "evidence_level", "link_state", "association_assessment",
        "causal_assessment", "effect_estimate_state", "political_merit_or_blame",
        "corruption_assessment", "ranking_eligible", "publication_eligible",
        "row_semantic_sha256",
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
} | {
    "trg_pipeline_keyset_checkpoints_roots_immutable",
    "trg_pipeline_keyset_checkpoints_completed_immutable",
}


class Audit:
    def __init__(self) -> None:
        self.checks: dict[str, bool] = {}

    def equal(self, name: str, actual: Any, expected: Any) -> None:
        self.checks[name] = actual == expected
        if actual != expected:
            raise RuntimeError(f"{name}: expected {expected!r}, got {actual!r}")

    def check(self, name: str, condition: bool) -> None:
        self.checks[name] = bool(condition)
        if not condition:
            raise RuntimeError(f"{name}: check failed")


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    return sha256_bytes(
        canonical_bytes(
            {"contract_version": contract_version, "persisted_row": row}
        )
    )


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


def require_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise RuntimeError(f"{label}: expected {expected!r}, got {actual!r}")


def partition_component(value: Any) -> str:
    return quote(str(value), safe="-._~")


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


def init_source_cache(path: Path) -> sqlite3.Connection:
    cache = sqlite3.connect(path)
    cache.row_factory = sqlite3.Row
    cache.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE actions(
          action_plan_pk INTEGER PRIMARY KEY,action_id TEXT UNIQUE,action_date TEXT,
          action_year INTEGER,action_label TEXT,source_id TEXT,source_record_pk INTEGER,
          source_record_id TEXT,source_snapshot_date TEXT,official_action_url TEXT,
          source_page_url TEXT,source_record_content_sha256 TEXT,
          member_vote_count INTEGER,official_name_count INTEGER,
          participant_projection_sha256 TEXT
        );
        CREATE TABLE series(
          series_plan_pk INTEGER PRIMARY KEY,indicator_series_id INTEGER UNIQUE,
          canonical_key TEXT,series_label TEXT,dataset_code TEXT,country_code TEXT,
          geography_code TEXT,frequency_code TEXT,unit_code TEXT,dimensions_json TEXT,
          source_id TEXT,source_record_pk INTEGER,source_record_id TEXT,
          source_snapshot_date TEXT,official_source_url TEXT,
          source_record_content_sha256 TEXT,origin_capture_sha256 TEXT,
          observation_count INTEGER,observation_years_json TEXT,
          observation_projection_sha256 TEXT,first_observation_date TEXT,
          last_observation_date TEXT
        );
        CREATE TABLE eligibility(
          series_plan_pk INTEGER,action_year INTEGER,strict_pre_latest_date TEXT,
          strict_post_earliest_date TEXT,
          PRIMARY KEY(series_plan_pk,action_year)
        );
        CREATE TABLE names(name TEXT PRIMARY KEY);
        """
    )
    return cache


def build_source_cache(
    *,
    config: dict[str, Any],
    actions: sqlite3.Connection,
    indicators: sqlite3.Connection,
    cache_path: Path,
    page_size: int,
) -> tuple[sqlite3.Connection, dict[str, Any]]:
    cache = init_source_cache(cache_path)
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
        if not item["official_action_url"].startswith(action_src["official_url_prefix"]):
            raise RuntimeError("non-official action URL")
        stream_hash_add(hashers["actions"], item)
        counts["actions"] += 1
        cache.execute(
            "INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                counts["actions"], item["action_id"], item["action_date"],
                int(item["action_date"][:4]), item["action_label"], item["source_id"],
                item["source_record_pk"], item["source_record_id"],
                item["source_snapshot_date"], item["official_action_url"],
                item["source_page_url"], item["source_record_content_sha256"],
                None, None, None,
            ),
        )
        action_key[:] = [item["action_date"], item["action_id"]
        ]

    member_key: list[Any] = ["", -1]
    current_action: str | None = None
    current_count = 0
    current_names: set[str] = set()
    current_hasher = hashlib.sha256()

    def finish_members() -> None:
        if current_action is None:
            return
        if current_count != len(current_names):
            raise RuntimeError("official name is repeated within a real Senate action")
        cache.execute(
            "UPDATE actions SET member_vote_count=?,official_name_count=?,"
            "participant_projection_sha256=? WHERE action_id=?",
            (
                current_count,
                len(current_names),
                stream_root(
                    "outcome_pair_plan_action_participant_projection_v1",
                    current_count,
                    current_hasher,
                ),
                current_action,
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
        if not item["member_name"] or not item["source_url"].startswith(
            action_src["official_url_prefix"]
        ):
            raise RuntimeError("member vote lacks official public identity or URL")
        if current_action != item["action_id"]:
            finish_members()
            current_action = item["action_id"]
            current_count = 0
            current_names = set()
            current_hasher = hashlib.sha256()
        stream_hash_add(current_hasher, item)
        stream_hash_add(hashers["members"], item)
        current_count += 1
        counts["members"] += 1
        current_names.add(item["member_name"])
        cache.execute("INSERT OR IGNORE INTO names VALUES (?)", (item["member_name"],))
        member_key[:] = [item["action_id"], item["member_vote_id"]]
    finish_members()

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
        if not item["official_source_url"].startswith(indicator_src["official_url_prefix"]):
            raise RuntimeError("non-official indicator URL")
        stream_hash_add(hashers["series"], item)
        counts["series"] += 1
        cache.execute(
            "INSERT INTO series VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                counts["series"], item["indicator_series_id"], item["canonical_key"],
                item["series_label"], item["dataset_code"], item["geography_code"][:2],
                item["geography_code"], item["frequency_code"], item["unit_code"],
                item["dimensions_json"], item["source_id"], item["source_record_pk"],
                item["source_record_id"], item["source_snapshot_date"],
                item["official_source_url"], item["source_record_content_sha256"],
                item["origin_capture_sha256"], None, None, None, None, None,
            ),
        )
        series_key[0] = item["indicator_series_id"]

    action_years = tuple(
        row[0] for row in cache.execute("SELECT DISTINCT action_year FROM actions ORDER BY action_year")
    )
    point_key: list[Any] = [-1, "", -1]
    current_series_id: int | None = None
    current_series_pk = 0
    current_dates: list[str] = []
    current_point_hasher = hashlib.sha256()

    def finish_points() -> None:
        if current_series_id is None:
            return
        years = [int(value[:4]) for value in current_dates]
        if len(years) != len(set(years)):
            raise RuntimeError("annual series has duplicate observation year")
        cache.execute(
            "UPDATE series SET observation_count=?,observation_years_json=?,"
            "observation_projection_sha256=?,first_observation_date=?,"
            "last_observation_date=? WHERE series_plan_pk=?",
            (
                len(current_dates), canonical_json(years),
                stream_root(
                    "outcome_pair_plan_series_observation_projection_v1",
                    len(current_dates), current_point_hasher,
                ),
                current_dates[0], current_dates[-1], current_series_pk,
            ),
        )
        for action_year in action_years:
            pre = [year for year in years if year < action_year]
            post = [year for year in years if year > action_year]
            if pre and post:
                cache.execute(
                    "INSERT INTO eligibility VALUES (?,?,?,?)",
                    (
                        current_series_pk, action_year,
                        f"{max(pre):04d}-01-01", f"{min(post):04d}-01-01",
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
        if len(item["date"]) != 10 or item["date"][4:] != "-01-01":
            raise RuntimeError("non-annual C2B point date")
        if current_series_id != item["indicator_series_id"]:
            finish_points()
            current_series_id = item["indicator_series_id"]
            current_series_pk += 1
            current_dates = []
            current_point_hasher = hashlib.sha256()
        if current_dates and item["date"] <= current_dates[-1]:
            raise RuntimeError("C2B points are not strictly ordered")
        current_dates.append(item["date"])
        stream_hash_add(current_point_hasher, item)
        stream_hash_add(hashers["points"], item)
        counts["points"] += 1
        point_key[:] = [item["indicator_series_id"], item["date"], item["indicator_point_id"]]
    finish_points()
    if current_series_pk != counts["series"]:
        raise RuntimeError("not every selected C2B series resolved to observations")
    cache.commit()

    distinct_names = cache.execute("SELECT COUNT(*) FROM names").fetchone()[0]
    geographies = cache.execute(
        "SELECT COUNT(DISTINCT geography_code) FROM series"
    ).fetchone()[0]
    datasets = cache.execute("SELECT COUNT(DISTINCT dataset_code) FROM series").fetchone()[0]
    all_series = indicators.execute("SELECT COUNT(*) FROM indicator_series").fetchone()[0]
    expected = config["expected"]
    expected_counts = {
        "actions": expected["dated_actions"],
        "members": expected["member_votes"],
        "series": expected["eligible_es_annual_series"],
        "points": expected["eligible_series_observations"],
    }
    if counts != expected_counts:
        raise RuntimeError(f"C2B source counts drifted: {counts!r}")
    if distinct_names != expected["distinct_official_names"]:
        raise RuntimeError("C2B official-name count drifted")
    if geographies != expected["geographies"] or datasets != expected["datasets"]:
        raise RuntimeError("C2B geography or dataset count drifted")
    if all_series != expected["all_indicator_series"]:
        raise RuntimeError("global indicator count drifted")
    eligible_pairs = cache.execute(
        "SELECT SUM(a.row_count) FROM eligibility e JOIN "
        "(SELECT action_year,COUNT(*) row_count FROM actions GROUP BY action_year) a "
        "USING(action_year)"
    ).fetchone()[0]
    if eligible_pairs != expected["eligible_pairs"]:
        raise RuntimeError(f"independent eligible-pair count drifted: {eligible_pairs}")
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
            "geographies": geographies,
            "datasets": datasets,
            "eligible_pairs": eligible_pairs,
        },
        "component_roots": component_roots,
        "input_root_sha256": input_root,
    }


def schema_object_definitions(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    names = set(TABLE_COLUMNS) | EXPECTED_INDEXES | EXPECTED_TRIGGERS
    placeholders = ",".join("?" for _ in names)
    result = []
    for row in connection.execute(
        f"SELECT type,name,tbl_name,sql FROM sqlite_master "
        f"WHERE name IN ({placeholders}) ORDER BY type,name",
        tuple(sorted(names)),
    ):
        result.append(
            {
                "type": row[0], "name": row[1], "table": row[2],
                "sql": " ".join((row[3] or "").split()),
            }
        )
    return result


def distribution_summary(
    connection: sqlite3.Connection, *, column: str, contract_version: str
) -> dict[str, Any]:
    hasher = hashlib.sha256()
    partition_count = 0
    row_count = 0
    minimum_rows: int | None = None
    maximum_rows = 0
    if column == "partition_key":
        cursor = connection.execute(
            "SELECT base_partition_key,pair_bucket,COUNT(*) "
            "FROM outcome_pair_plan_pairs "
            "GROUP BY base_partition_key,pair_bucket "
            "ORDER BY base_partition_key,pair_bucket"
        )
        rows_iter = (
            (f"{base_partition_key}/bucket={pair_bucket}", rows)
            for base_partition_key, pair_bucket, rows in cursor
        )
    else:
        cursor = connection.execute(
            f"SELECT {column},COUNT(*) FROM outcome_pair_plan_pairs "
            f"GROUP BY {column} ORDER BY {column}"
        )
        rows_iter = cursor
    for partition_key, rows in rows_iter:
        rows = int(rows)
        stream_hash_add(hasher, {"partition_key": partition_key, "row_count": rows})
        partition_count += 1
        row_count += rows
        minimum_rows = rows if minimum_rows is None else min(minimum_rows, rows)
        maximum_rows = max(maximum_rows, rows)
    cursor.close()
    return {
        "partition_count": partition_count,
        "row_count": row_count,
        "minimum_rows": minimum_rows or 0,
        "maximum_rows": maximum_rows,
        "distribution_root_sha256": stream_root(
            contract_version, partition_count, hasher
        ),
    }


def expected_completed_run_pair_deltas(
    source_cache: sqlite3.Connection, *, series_count: int, batch_size: int
) -> dict[int, tuple[int, int]]:
    """Map successful completed-run batch counts to exact scanned/eligible deltas."""
    actions = [
        (int(row[0]), int(row[1]))
        for row in source_cache.execute(
            "SELECT action_plan_pk,action_year FROM actions ORDER BY action_plan_pk"
        )
    ]
    total_products = len(actions) * series_count
    pair_batches: list[tuple[int, int]] = []
    for page_start in range(0, total_products, batch_size):
        page_end = min(page_start + batch_size, total_products)
        eligible = 0
        position = page_start
        while position < page_end:
            action_index = position // series_count
            series_first = position % series_count + 1
            action_end = min(page_end, (action_index + 1) * series_count)
            series_last = (action_end - 1) % series_count + 1
            action_year = actions[action_index][1]
            eligible += int(
                source_cache.execute(
                    "SELECT COUNT(*) FROM eligibility "
                    "WHERE action_year=? AND series_plan_pk BETWEEN ? AND ?",
                    (action_year, series_first, series_last),
                ).fetchone()[0]
            )
            position = action_end
        pair_batches.append((page_end - page_start, eligible))

    deltas: dict[int, tuple[int, int]] = {}
    all_scanned = sum(scanned for scanned, _ in pair_batches)
    all_eligible = sum(eligible for _, eligible in pair_batches)
    # Existing DB can resume before actions, before series, or before pair batches.
    deltas[len(pair_batches) + 2] = (all_scanned, all_eligible)
    deltas[len(pair_batches) + 1] = (all_scanned, all_eligible)
    deltas[len(pair_batches)] = (all_scanned, all_eligible)
    scanned_suffix = 0
    eligible_suffix = 0
    for committed, (scanned, eligible) in enumerate(reversed(pair_batches), start=1):
        scanned_suffix += scanned
        eligible_suffix += eligible
        deltas[committed] = (scanned_suffix, eligible_suffix)
    return deltas


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
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--page-size", type=int, default=25_000)
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.monotonic()
    audit = Audit()
    config = load_json(args.config)
    materialization = load_json(args.materialization_report)
    manifest = load_json(args.manifest)
    config_sha = sha256_bytes(canonical_bytes(config))
    audit.equal("config_sha256", config_sha, EXPECTED_CONFIG_SHA256)
    audit.check(
        "materialization_execution_allowed",
        materialization.get("execution") in {"fresh", "resumed", "replayed_noop"},
    )
    audit.equal(
        "manifest_file_sha256",
        sha256_file(args.manifest),
        EXPECTED_MANIFEST_FILE_SHA256,
    )
    manifest_payload = {
        key: value for key, value in manifest.items() if key != "manifest_root_sha256"
    }
    audit.equal("manifest_schema", manifest["schema_version"], MANIFEST_SCHEMA)
    audit.equal(
        "manifest_root",
        manifest["manifest_root_sha256"],
        sha256_bytes(canonical_bytes(manifest_payload)),
    )
    audit.equal(
        "manifest_root_pinned",
        manifest["manifest_root_sha256"],
        EXPECTED_MANIFEST_ROOT_SHA256,
    )
    audit.equal("manifest_shard_count", len(manifest["shards"]), 1)
    shard = manifest["shards"][0]
    audit.equal("manifest_shard_id", shard["shard_id"], "sqlite-00000")
    audit.equal("plan_database_bytes", args.plan_db.stat().st_size, EXPECTED_DATABASE_BYTES)
    audit.equal("manifest_database_bytes", shard["bytes"], EXPECTED_DATABASE_BYTES)
    actual_database_sha256 = sha256_file(args.plan_db)
    audit.equal("plan_database_sha256", actual_database_sha256, EXPECTED_DATABASE_SHA256)
    audit.equal("manifest_database_sha256", shard["sha256"], EXPECTED_DATABASE_SHA256)

    exact_queries = {
        "actions": ACTION_SQL, "members": MEMBER_SQL,
        "series": SERIES_SQL, "points": POINT_SQL,
    }
    for name, sql in exact_queries.items():
        audit.equal(
            f"{name}_query_exact",
            config["query_contract"][f"{name}_keyset_sql_utf8"], sql,
        )
        audit.equal(
            f"{name}_query_hash",
            config["query_contract"][f"{name}_keyset_sql_sha256"],
            sha256_bytes(sql.encode()),
        )
        audit.check(f"{name}_query_no_offset", " OFFSET " not in f" {sql.upper()} ")

    schema_text = args.schema.read_text(encoding="utf-8")
    start = schema_text.index(SCHEMA_BEGIN)
    end = schema_text.index(SCHEMA_END)
    schema_block = schema_text[start : end + len(SCHEMA_END)] + "\n"
    schema_root = sha256_bytes(schema_block.encode())
    audit.equal("schema_root", schema_root, EXPECTED_SCHEMA_ROOT_SHA256)
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
        audit.equal(f"{label}_path", repo_path(path), expected["path"])
        audit.equal(f"{label}_bytes", path.stat().st_size, expected["bytes"])
        audit.equal(f"{label}_sha256", sha256_file(path), expected["sha256"])

    actions, action_identity = open_source(actions_path)
    indicators, indicator_identity = open_source(indicators_path)
    with tempfile.TemporaryDirectory(prefix="vclc-c2b-validation-") as temp_dir:
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
        audit.equal("component_roots", source["component_roots"], EXPECTED_COMPONENT_ROOTS)
        audit.equal("input_root", source["input_root_sha256"], EXPECTED_INPUT_ROOT_SHA256)
        audit.equal(
            "source_counts",
            source["counts"],
            {
                "actions": 458, "members": 119116, "series": 6400,
                "points": 79722, "distinct_official_names": 490,
                "all_indicator_series": 155435, "geographies": 89,
                "datasets": 4, "eligible_pairs": 2865602,
            },
        )

        plan = sqlite3.connect(
            f"file:{args.plan_db.resolve().as_posix()}?mode=ro&immutable=1", uri=True
        )
        plan.row_factory = sqlite3.Row
        plan.execute("PRAGMA query_only=ON")
        plan.execute("PRAGMA temp_store=FILE")
        try:
            tables = {
                row[0]
                for row in plan.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            }
            audit.equal("exact_tables", tables, set(TABLE_COLUMNS))
            for table, columns in TABLE_COLUMNS.items():
                audit.equal(
                    f"{table}_columns",
                    tuple(row[1] for row in plan.execute(f"PRAGMA table_info({table})")),
                    columns,
                )
            audit.equal(
                "schema_object_definitions",
                schema_object_definitions(plan), expected_schema_definitions,
            )

            checkpoints = {
                row["stage"]: dict(row)
                for row in plan.execute(
                    "SELECT * FROM pipeline_keyset_checkpoints ORDER BY stage"
                )
            }
            audit.equal("checkpoint_stages", set(checkpoints), {"actions", "series", "pairs"})
            last_action = source_cache.execute(
                "SELECT action_date,action_id FROM actions ORDER BY action_plan_pk DESC LIMIT 1"
            ).fetchone()
            last_series_id = source_cache.execute(
                "SELECT indicator_series_id FROM series ORDER BY series_plan_pk DESC LIMIT 1"
            ).fetchone()[0]
            expected_progress = {
                "actions": ([last_action["action_date"], last_action["action_id"]], 458, 1),
                "series": ([last_series_id], 6400, 1),
                "pairs": ([458, 6400], 2865602, 118),
            }
            for stage, row in checkpoints.items():
                last_key, rows_written, batches = expected_progress[stage]
                audit.equal(f"{stage}_pipeline", row["pipeline_key"], EXPECTED_PIPELINE_KEY)
                audit.equal(f"{stage}_partition", row["partition_key"], "")
                audit.equal(
                    f"{stage}_checkpoint_contract", row["checkpoint_contract_version"],
                    config["checkpoint_contract_version"],
                )
                audit.equal(f"{stage}_config", row["config_sha256"], EXPECTED_CONFIG_SHA256)
                audit.equal(f"{stage}_input", row["input_root_sha256"], EXPECTED_INPUT_ROOT_SHA256)
                audit.equal(f"{stage}_schema", row["schema_root_sha256"], EXPECTED_SCHEMA_ROOT_SHA256)
                audit.equal(f"{stage}_last_key", parse_json(row["last_key_json"]), last_key)
                audit.equal(f"{stage}_rows", row["rows_written"], rows_written)
                audit.equal(f"{stage}_batches", row["batches_committed"], batches)
                audit.equal(f"{stage}_completed", row["completed"], 1)
                audit.equal(
                    f"{stage}_updated_at", row["updated_at"],
                    f"{config['contract_date']}T00:00:00Z",
                )

            action_chain = EMPTY_CHAIN
            action_count = 0
            target_actions = plan.execute(
                "SELECT * FROM outcome_pair_plan_actions ORDER BY action_plan_pk"
            )
            source_actions = source_cache.execute(
                "SELECT * FROM actions ORDER BY action_plan_pk"
            )
            for action_count, (source_row, target_row) in enumerate(
                zip(source_actions, target_actions, strict=True), start=1
            ):
                expected_persisted = {
                    "action_plan_pk": source_row["action_plan_pk"],
                    "pipeline_key": EXPECTED_PIPELINE_KEY,
                    **{
                        key: source_row[key]
                        for key in TABLE_COLUMNS["outcome_pair_plan_actions"]
                        if key in source_row.keys()
                    },
                }
                row_sha = persisted_row_sha256(
                    "outcome_pair_plan_action_row_v2", expected_persisted
                )
                action_chain = chain_add(action_chain, row_sha)
                require_equal(
                    f"action row {action_count}", dict(target_row),
                    {**expected_persisted, "row_semantic_sha256": row_sha},
                )
            audit.equal("action_count", action_count, 458)
            audit.equal("action_chain", action_chain, checkpoints["actions"]["semantic_chain_sha256"])

            series_chain = EMPTY_CHAIN
            series_count = 0
            target_series = plan.execute(
                "SELECT * FROM outcome_pair_plan_series ORDER BY series_plan_pk"
            )
            source_series = source_cache.execute(
                "SELECT * FROM series ORDER BY series_plan_pk"
            )
            for series_count, (source_row, target_row) in enumerate(
                zip(source_series, target_series, strict=True), start=1
            ):
                expected_persisted = {
                    "series_plan_pk": source_row["series_plan_pk"],
                    "pipeline_key": EXPECTED_PIPELINE_KEY,
                    **{
                        key: source_row[key]
                        for key in TABLE_COLUMNS["outcome_pair_plan_series"]
                        if key in source_row.keys()
                    },
                }
                row_sha = persisted_row_sha256(
                    "outcome_pair_plan_series_row_v2", expected_persisted
                )
                series_chain = chain_add(series_chain, row_sha)
                require_equal(
                    f"series row {series_count}", dict(target_row),
                    {**expected_persisted, "row_semantic_sha256": row_sha},
                )
            audit.equal("series_count", series_count, 6400)
            audit.equal("series_chain", series_chain, checkpoints["series"]["semantic_chain_sha256"])

            pair_chain = EMPTY_CHAIN
            pair_count = 0
            target_pairs = iter(
                plan.execute(
                    "SELECT * FROM outcome_pair_plan_pairs "
                    "ORDER BY action_plan_pk,series_plan_pk"
                )
            )
            product = source_cache.execute(
                """
                SELECT a.action_plan_pk,a.action_id,a.action_year,
                       a.source_id AS action_source_id,
                       s.series_plan_pk,s.canonical_key,s.dataset_code,
                       s.source_id AS indicator_source_id,s.country_code,
                       s.geography_code,e.strict_pre_latest_date,
                       e.strict_post_earliest_date
                FROM actions a
                JOIN eligibility e ON e.action_year=a.action_year
                JOIN series s ON s.series_plan_pk=e.series_plan_pk
                ORDER BY a.action_plan_pk,s.series_plan_pk
                """
            )
            for product_row in product:
                pair_count += 1
                actual = next(target_pairs, None)
                if actual is None:
                    raise RuntimeError("pair plan ended before independent C2B product")
                identity = {
                    "identity_contract_version": "outcome_pair_plan_identity_v1",
                    "action_id": product_row["action_id"],
                    "indicator_series_canonical_key": product_row["canonical_key"],
                    "eligibility": "strict_pre_and_strict_post_annual_observations",
                }
                identity_sha = sha256_bytes(canonical_bytes(identity))
                pair_bucket = identity_sha[:2]
                base_partition = (
                    f"action_source={partition_component(product_row['action_source_id'])}/"
                    f"year={product_row['action_year']}/"
                    f"indicator_source={partition_component(product_row['indicator_source_id'])}/"
                    f"dataset={partition_component(product_row['dataset_code'])}/"
                    f"country={partition_component(product_row['country_code'])}/"
                    f"geography={partition_component(product_row['geography_code'])}"
                )
                expected_persisted = {
                    "pair_plan_id": f"vclc:outcome-pair-plan:{identity_sha[:24]}",
                    "pipeline_key": EXPECTED_PIPELINE_KEY,
                    "base_partition_key": base_partition,
                    "pair_bucket": pair_bucket,
                    "partition_key": f"{base_partition}/bucket={pair_bucket}",
                    "action_plan_pk": product_row["action_plan_pk"],
                    "series_plan_pk": product_row["series_plan_pk"],
                    "action_year": product_row["action_year"],
                    "dataset_code": product_row["dataset_code"],
                    "strict_pre_latest_date": product_row["strict_pre_latest_date"],
                    "strict_post_earliest_date": product_row["strict_post_earliest_date"],
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
                row_sha = persisted_row_sha256(
                    "outcome_pair_plan_pair_row_v2", expected_persisted
                )
                pair_chain = chain_add(pair_chain, row_sha)
                require_equal(
                    f"pair row {pair_count}", dict(actual),
                    {**expected_persisted, "row_semantic_sha256": row_sha},
                )
            audit.equal("no_extra_pairs", next(target_pairs, None), None)
            audit.equal("pair_count", pair_count, 2865602)
            audit.equal("pair_chain", pair_chain, checkpoints["pairs"]["semantic_chain_sha256"])
            audit.equal(
                "foreign_key_check",
                sum(1 for _ in plan.execute("PRAGMA foreign_key_check")), 0,
            )

            base_distribution = distribution_summary(
                plan,
                column="base_partition_key",
                contract_version="outcome_pair_plan_base_partition_distribution_c2b_v1",
            )
            bucket_distribution = distribution_summary(
                plan,
                column="partition_key",
                contract_version="outcome_pair_plan_bucket_partition_distribution_c2b_v1",
            )
            audit.equal(
                "base_partition_distribution",
                base_distribution, config["expected"]["base_partition_distribution"],
            )
            audit.equal(
                "bucket_partition_distribution",
                bucket_distribution, config["expected"]["bucket_partition_distribution"],
            )
            counts = {"actions": action_count, "series": series_count, "pairs": pair_count}
            chains = {
                "actions": action_chain, "series": series_chain, "pairs": pair_chain,
            }
            semantic_root = sha256_bytes(
                canonical_bytes(
                    {
                        "contract_version": "outcome_pair_plan_semantic_root_c2b_v1",
                        "config_sha256": config_sha,
                        "input_root_sha256": source["input_root_sha256"],
                        "schema_root_sha256": schema_root,
                        "counts": counts,
                        "base_partition_distribution": base_distribution,
                        "bucket_partition_distribution": bucket_distribution,
                        "stage_semantic_chains": chains,
                        "policy": config["policy"],
                    }
                )
            )
            audit.equal("semantic_root", semantic_root, EXPECTED_SEMANTIC_ROOT_SHA256)
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
            expected_roots = {
                "config_sha256": EXPECTED_CONFIG_SHA256,
                "input_root_sha256": EXPECTED_INPUT_ROOT_SHA256,
                "schema_root_sha256": EXPECTED_SCHEMA_ROOT_SHA256,
                "semantic_root_sha256": EXPECTED_SEMANTIC_ROOT_SHA256,
                "input_component_roots": EXPECTED_COMPONENT_ROOTS,
            }
            expected_manifest_payload = {
                "schema_version": MANIFEST_SCHEMA,
                "contract_date": "2026-08-23",
                "pipeline_key": EXPECTED_PIPELINE_KEY,
                "roots": expected_roots,
                "counts": {
                    "actions": 458,
                    "series": 6400,
                    "pairs": 2865602,
                    "member_votes": 119116,
                    "official_names": 490,
                    "observations": 79722,
                    "geographies": 89,
                },
                "base_partition_distribution": base_distribution,
                "bucket_partition_distribution": bucket_distribution,
                "policy": config["policy"],
                "shards": [
                    {
                        "shard_id": "sqlite-00000",
                        "logical_name": "outcome-context-pair-plan-c2b-v1.db",
                        "bytes": EXPECTED_DATABASE_BYTES,
                        "sha256": EXPECTED_DATABASE_SHA256,
                        "pair_rows": 2865602,
                    }
                ],
                "local_origin_state": (
                    "immutable_content_manifest_only_not_durable_public_origin"
                ),
            }
            expected_manifest = {
                **expected_manifest_payload,
                "manifest_root_sha256": EXPECTED_MANIFEST_ROOT_SHA256,
            }
            audit.equal("complete_manifest_exact", manifest, expected_manifest)
            audit.equal(
                "manifest_reconstructed_root",
                sha256_bytes(canonical_bytes(expected_manifest_payload)),
                EXPECTED_MANIFEST_ROOT_SHA256,
            )

            expected_source_facts = {
                "actions": {
                    "path": repo_path(actions_path),
                    "bytes": config["sources"]["actions"]["bytes"],
                    "sha256": config["sources"]["actions"]["sha256"],
                    "wal_bytes": 0,
                },
                "indicators": {
                    "path": repo_path(indicators_path),
                    "bytes": config["sources"]["indicators"]["bytes"],
                    "sha256": config["sources"]["indicators"]["sha256"],
                    "wal_bytes": 0,
                },
                "read_only_transactions": True,
                "non_empty_wal_rejected": True,
            }
            execution = materialization["execution"]
            performance = materialization.get("performance")
            audit.check("materialization_performance_object", isinstance(performance, dict))
            audit.equal(
                "materialization_performance_keys",
                set(performance),
                {
                    "batch_size",
                    "source_batch_size",
                    "batches_attempted_this_run",
                    "batches_committed_this_run",
                    "elapsed_seconds",
                    "max_rss_bytes",
                    "eligible_pairs_processed_this_run",
                    "scanned_pairs_processed_this_run",
                    "eligible_pairs_per_second",
                    "scanned_pairs_per_second",
                    "compute_cost_proxy_seconds_per_1000_eligible_pairs",
                    "output_database_bytes",
                    "retries",
                    "dead_letters",
                },
            )
            audit.equal("materialization_batch_size", performance["batch_size"], 25000)
            audit.equal(
                "materialization_source_batch_size",
                performance["source_batch_size"],
                25000,
            )
            audit.equal(
                "materialization_output_database_bytes",
                performance["output_database_bytes"],
                EXPECTED_DATABASE_BYTES,
            )
            audit.equal("materialization_retries", performance["retries"], 0)
            audit.equal("materialization_dead_letters", performance["dead_letters"], 0)
            audit.check(
                "materialization_elapsed_finite_positive",
                type(performance["elapsed_seconds"]) in {int, float}
                and math.isfinite(performance["elapsed_seconds"])
                and performance["elapsed_seconds"] > 0,
            )
            audit.check(
                "materialization_rss_bounded",
                type(performance["max_rss_bytes"]) is int
                and 0 < performance["max_rss_bytes"] <= 512 * 1024 * 1024,
            )
            audit.check(
                "materialization_batch_counters_integer",
                type(performance["batches_attempted_this_run"]) is int
                and type(performance["batches_committed_this_run"]) is int,
            )
            audit.equal(
                "materialization_attempted_committed_parity",
                performance["batches_attempted_this_run"],
                performance["batches_committed_this_run"],
            )

            if execution == "replayed_noop":
                expected_batches = 0
                expected_scanned = 0
                expected_eligible = 0
                expected_eligible_rate = None
                expected_scanned_rate = None
                expected_cost_proxy = None
            else:
                completed_run_deltas = expected_completed_run_pair_deltas(
                    source_cache, series_count=6400, batch_size=25000
                )
                expected_batches = performance["batches_committed_this_run"]
                if execution == "fresh":
                    audit.equal(
                        "fresh_materialization_batches_exact",
                        expected_batches,
                        max(completed_run_deltas),
                    )
                else:
                    audit.check(
                        "resumed_materialization_batches_valid",
                        expected_batches in completed_run_deltas,
                    )
                expected_scanned, expected_eligible = completed_run_deltas[
                    expected_batches
                ]
                expected_eligible_rate = round(
                    expected_eligible / performance["elapsed_seconds"], 3
                )
                expected_scanned_rate = round(
                    expected_scanned / performance["elapsed_seconds"], 3
                )
                expected_cost_proxy = round(
                    performance["elapsed_seconds"] / (expected_eligible / 1000), 6
                )

            audit.equal(
                "materialization_batches_attempted_exact",
                performance["batches_attempted_this_run"],
                expected_batches,
            )
            audit.equal(
                "materialization_eligible_delta_exact",
                performance["eligible_pairs_processed_this_run"],
                expected_eligible,
            )
            audit.equal(
                "materialization_scanned_delta_exact",
                performance["scanned_pairs_processed_this_run"],
                expected_scanned,
            )
            audit.equal(
                "eligible_throughput_formula",
                performance["eligible_pairs_per_second"],
                expected_eligible_rate,
            )
            audit.equal(
                "scanned_throughput_formula",
                performance["scanned_pairs_per_second"],
                expected_scanned_rate,
            )
            audit.equal(
                "cost_proxy_formula",
                performance[
                    "compute_cost_proxy_seconds_per_1000_eligible_pairs"
                ],
                expected_cost_proxy,
            )
            expected_performance = {
                "batch_size": 25000,
                "source_batch_size": 25000,
                "batches_attempted_this_run": expected_batches,
                "batches_committed_this_run": expected_batches,
                "elapsed_seconds": performance["elapsed_seconds"],
                "max_rss_bytes": performance["max_rss_bytes"],
                "eligible_pairs_processed_this_run": expected_eligible,
                "scanned_pairs_processed_this_run": expected_scanned,
                "eligible_pairs_per_second": expected_eligible_rate,
                "scanned_pairs_per_second": expected_scanned_rate,
                "compute_cost_proxy_seconds_per_1000_eligible_pairs": (
                    expected_cost_proxy
                ),
                "output_database_bytes": EXPECTED_DATABASE_BYTES,
                "retries": 0,
                "dead_letters": 0,
            }
            expected_materialization = {
                "schema_version": "outcome_context_pair_plan_c2b_report_v1",
                "status": "passed",
                "execution": execution,
                "pipeline_key": EXPECTED_PIPELINE_KEY,
                "contract_date": "2026-08-23",
                "policy": config["policy"],
                "roots": {
                    **expected_roots,
                    "manifest_root_sha256": EXPECTED_MANIFEST_ROOT_SHA256,
                },
                "source_facts": expected_source_facts,
                "source_counts": {
                    "actions": 458,
                    "members": 119116,
                    "series": 6400,
                    "points": 79722,
                    "distinct_official_names": 490,
                    "all_indicator_series": 155435,
                    "geographies": 89,
                    "datasets": 4,
                },
                "plan_counts": {
                    "actions": 458,
                    "series": 6400,
                    "pairs": 2865602,
                    "selected_product": 2931200,
                    "global_unfiltered_product": 71189230,
                    "base_partitions": 1205,
                    "bucket_partitions": 197196,
                    "max_bucket_partition_rows": 114,
                },
                "base_partition_distribution": base_distribution,
                "bucket_partition_distribution": bucket_distribution,
                "checkpoints": checkpoint_projection,
                "integrity": {
                    "foreign_key_errors": 0,
                    "config_input_schema_roots_pin_resume": True,
                    "batch_rows_and_checkpoint_atomic": True,
                    "streaming_keyset_no_offset": True,
                    "bounded_memory_distribution_roots": True,
                    "full_geography_partition_key": True,
                    "official_names_source_resolvable": 490,
                    "member_votes_source_resolvable": 119116,
                    "single_shard_manifest_sha256": EXPECTED_DATABASE_SHA256,
                },
                "performance": expected_performance,
                "artifacts": {
                    "database": "etl/data/staging/outcome-context-pair-plan-c2b-v1.db",
                    "report": repo_path(args.materialization_report),
                    "manifest": repo_path(args.manifest),
                },
                "unresolved_gates": {
                    "durable_remote_origin": False,
                    "public_release": False,
                    "publication_eligible_rows": 0,
                },
            }
            audit.equal(
                "complete_materialization_report_exact",
                materialization,
                expected_materialization,
            )
        finally:
            plan.close()
            source_cache.close()

    elapsed = time.monotonic() - started
    report = {
        "schema_version": REPORT_SCHEMA,
        "status": "passed",
        "passed_checks": len(audit.checks),
        "failed_checks": [],
        "pipeline_key": EXPECTED_PIPELINE_KEY,
        "counts": {
            "actions": 458, "series": 6400, "geographies": 89,
            "observations": 79722, "pairs": 2865602,
            "base_partitions": 1205, "bucket_partitions": 197196,
            "member_votes_source_resolved": 119116,
            "official_names_source_resolved": 490,
        },
        "roots": {
            "config_sha256": EXPECTED_CONFIG_SHA256,
            "input_root_sha256": EXPECTED_INPUT_ROOT_SHA256,
            "schema_root_sha256": EXPECTED_SCHEMA_ROOT_SHA256,
            "semantic_root_sha256": EXPECTED_SEMANTIC_ROOT_SHA256,
            "input_component_roots": EXPECTED_COMPONENT_ROOTS,
            "manifest_root_sha256": manifest["manifest_root_sha256"],
            "database_sha256": shard["sha256"],
        },
        "proof": {
            "independent_source_reconstruction": True,
            "streaming_keyset_queries": True,
            "offset_queries": 0,
            "fetchall_calls": 0,
            "source_transactions_read_only": True,
            "non_empty_wal_rejected": True,
            "config_input_schema_roots_pinned": True,
            "checkpoint_progress_independently_derived": True,
            "full_geography_partition_keys": True,
            "bounded_memory_row_validation": True,
            "single_shard_content_hash_verified": True,
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
            "manifest": repo_path(args.manifest),
            "report": repo_path(args.report_out),
        },
        "performance": {
            "elapsed_seconds": round(elapsed, 6),
            "max_rss_bytes": max_rss_bytes(),
            "pairs_reconstructed": 2865602,
            "pairs_per_second": round(2865602 / elapsed, 3),
            "compute_cost_proxy_seconds_per_1000_pairs": round(
                elapsed / (2865602 / 1000), 6
            ),
            "plan_database_bytes": shard["bytes"],
            "retries": 0,
            "dead_letters": 0,
        },
        "unresolved_gates": {
            "durable_remote_origin": False,
            "public_release": False,
            "publication_eligible_rows": 0,
        },
    }
    atomic_write_json(args.report_out, report)
    return report


def main() -> int:
    args = parse_args()
    try:
        report = run(args)
    except Exception as exc:
        failure = {
            "schema_version": REPORT_SCHEMA,
            "status": "failed",
            "error_code": "c2b_pair_plan_validation_failed_fail_closed",
            "error_type": type(exc).__name__,
            "success_report_invalidated": True,
            "publication_eligible_rows": 0,
        }
        atomic_write_json(args.report_out, failure)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
