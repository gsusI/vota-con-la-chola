#!/usr/bin/env python3
"""Independently validate the real C0/L1 outcome-context candidate bundle.

This module intentionally does not import the materializer.  Its SQL, JSON
projections, identities, arithmetic, and artifact checks are a second
implementation of the normative contract in ``docs/method/outcome-linking-v1.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_EVEN
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ACTIONS_DB = REPO_ROOT / "etl/data/staging/politicos-es.db"
DEFAULT_INDICATORS_DB = (
    REPO_ROOT / "etl/data/staging/indicators-eurostat-gdp-mvp.db"
)
DEFAULT_ACTOR_GRAPH_DB = REPO_ROOT / "etl/data/staging/actor-graph-v1.db"
DEFAULT_MANUAL = REPO_ROOT / "etl/data/manual/outcome_links/reviewed_links_v1.json"
DEFAULT_BUNDLE_DIR = REPO_ROOT / "etl/data/staging/outcome-context-candidates-v1"
DEFAULT_SCHEMA = REPO_ROOT / "etl/load/sqlite_schema.sql"
DEFAULT_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/"
    "outcome-context-validation.json"
)
DEFAULT_MATERIALIZATION_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/"
    "outcome-context-materialization.json"
)

VALIDATION_SCHEMA_VERSION = "outcome_context_validation_v1"
FORMAT_VERSION = "outcome_link_preproduction_candidate_input_v1"
METHOD_VERSION = "outcome_linking_v1"
ACTION_ID = "url:https://www.senado.es/legis14/votaciones/ses_17_142.xml"
ACTION_DATE = "2020-10-07"
INITIATIVE_ID = "senado:leg14:exp:621/000005"
ACTION_SOURCE_ID = "senado_votaciones"
ACTION_SNAPSHOT_DATE = "2026-02-12"
INDICATOR_RELEASE_ID = "vclc:indicator-release:408979873b81ba19e8e65169"
INDICATOR_ID = "vclc:indicator:b9225f1a836937d1e9369b12"
INDICATOR_SERIES_VERSION_ID = (
    "vclc:indicator-series-version:3589ebcf91bc85174095f0f1"
)
ACTOR_GRAPH_RELEASE_ID = (
    "e52dd7fac6f29570d23756e927e0b9cfe73d1bf2f7c30fa01de75d4dc3a6f4a5"
)
LINK_ID = "vclc:outcome-link:5874c51233074eb67d2807ed"
LINK_VERSION_ID = "vclc:outcome-link-version:193c3c8b7e5f442d0373408a"

ACTION_UNIVERSE_SHA256 = (
    "1a9860116209538c5eb0445e78b2ba09e89cab19410ab3215102208c5832a756"
)
DEFINITIONS_SHA256 = (
    "e80f36946e6f670722a5cc994afabaf2f0820a4926062bcde90e002cabc38819"
)
SERIES_UNIVERSE_SHA256 = (
    "dd3a99e71c260a17bb131dcd63e01a10558a52ec77e4d69203d2bcd81bdaa1f4"
)
ELIGIBLE_SERIES_SHA256 = (
    "37be1a070d8eaa0a95fcdfbc6c2fa160cba852c1d492e053d606562e0e178411"
)
OBSERVATION_UNIVERSE_SHA256 = (
    "9db97ee08e7bafddb3df2ab9ab094dc86a4b4cd40ecb0b85336be46d14676d23"
)
PARTICIPANT_SOURCE_SHA256 = (
    "74fd8e3efa93dbaafe3c5b305124e65e5690add43fdf47a622cfa53546f87d8e"
)
ACTOR_REFERENCE_SHA256 = (
    "b372167366b0d7899b414764e6243d94509dac94dcc982326dcf2fae85e60dd6"
)
PARTICIPANT_EXPORT_SHA256 = (
    "1d5b71858a3d5367a83f335d6a5ec8d50931666432ed55e8593e27889423c542"
)
ACTION_CLOSURE_SHA256 = (
    "76cbc30d6295225b608827cf106fe7e306187802f0d193b8170cd80a72683a0e"
)
INDICATOR_CLOSURE_SHA256 = (
    "9cf53d68068f938150f646dda99300b9967830eb50ab396a7b98fecba98fbdd3"
)
ACTOR_CLOSURE_SHA256 = (
    "a2e9c927717b5c86afef2c9ead58f0be3b243e2bb5d7d145f29c0b418ae22d59"
)
COMBINED_CLOSURE_SHA256 = (
    "87b10890f2a414c3200f03a0a253910faf2110e467844528c24d4ecd8aee2354"
)
VOTE_RECORD_SHA256 = (
    "f889017fcbf3b36d069112eeb4c680ab3da4b4863982b9dbd7f931119a601f81"
)
INITIATIVE_RECORD_SHA256 = (
    "97e7b6db4361b460a0a8f345558a007a963a1acd87bc34e0393d11fcdef8e98f"
)
INDICATOR_SOURCE_SHA256 = (
    "8584b2c144ad608be5f28e2fc028517ba7c583a6245ca65bdc87238f1e1cf491"
)
LINK_IDENTITY_SHA256 = (
    "5874c51233074eb67d2807ed9a709708a798eb94ed133773de837321d0f0d6c2"
)
LINK_VERSION_IDENTITY_SHA256 = (
    "193c3c8b7e5f442d0373408a28acde31972e19807f21c31c59955e3d770d1abc"
)
MANUAL_ARTIFACT_SHA256 = (
    "c96d9e2be844cadbd58997c519785f8402f1b75e5d929eeafdefbca238c3533a"
)
BUNDLE_SEMANTIC_SHA256 = (
    "2e04efb803623a5d96b6a2e7f6eb2464679e5014b02003cc1df175c16afcf16a"
)
ARTIFACT_SET_SHA256 = (
    "22f43918a8a6e54a3a8549f2f809abfcf98c3d04ef82dc37f634cd0fd71a980a"
)
BUNDLE_DATABASE_SHA256 = (
    "225c91d8ee53872f6ba98788363442021725aa5de95fbb6352e758721dff45c2"
)
BUNDLE_JSON_SHA256 = (
    "585986f5c2c977cc370e8efa33bb7ae88e81f78d599b9359ec17544d73a35731"
)
BUNDLE_MANIFEST_SHA256 = (
    "94382395eeb34ce63a74eac49ae08acf23e4bd8fe5b944778356e8bde7064bd1"
)
OUTCOME_SCHEMA_DDL_SHA256 = (
    "744f1e5fdff5c21bd49d5181827bf0c8015a0f149818d9a1318409523ee5c4c7"
)
DATABASE_PARITY_ROOT_SHA256 = (
    "3c97764aa0e3e17f1c165e64a4e254507960439573205de962ca14fcd4639eeb"
)
SCHEMA_COLUMN_CONTRACT_SHA256 = (
    "c457d5909cd446c9ae1ffb483050822730755071c0188fd275125ceaa90fb0e1"
)

HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
LINK_ID_RE = re.compile(r"^vclc:outcome-link:[0-9a-f]{24}$")
LINK_VERSION_ID_RE = re.compile(r"^vclc:outcome-link-version:[0-9a-f]{24}$")
OBSERVATION_REF_ID_RE = re.compile(
    r"^vclc:outcome-link-observation-ref:[0-9a-f]{24}$"
)
PARTICIPANT_REF_ID_RE = re.compile(
    r"^vclc:outcome-link-participant-ref:[0-9a-f]{24}$"
)
EVIDENCE_ID_RE = re.compile(r"^vclc:outcome-link-evidence:[0-9a-f]{24}$")


# These statements are copied from the normative method, not imported from the
# producer.  Equality checks below also prevent a manual input from silently
# substituting a broader query.
ACTION_SQL = (
    "SELECT l.vote_event_id,l.initiative_id,l.link_method,l.confidence,"
    "l.evidence_json,v.vote_date,v.legislature,v.session_number,v.vote_number,"
    "v.title,v.totals_present,v.totals_yes,v.totals_no,v.totals_abstain,"
    "v.totals_no_vote,v.totals_absent,json_extract(v.raw_payload,'$.totals_absent') "
    "AS raw_totals_absent,v.source_id,sr.source_record_id,sr.source_snapshot_date,"
    "sr.content_sha256 FROM parl_vote_event_initiatives l JOIN parl_vote_events v "
    "USING(vote_event_id) JOIN source_records sr ON sr.source_record_pk="
    "v.source_record_pk WHERE l.initiative_id=? AND v.source_id=? AND "
    "sr.source_snapshot_date=? ORDER BY v.vote_date,v.session_number,"
    "v.vote_number,l.vote_event_id"
)
PARTICIPANT_SQL = (
    "SELECT seat,member_name,person_id,group_code,vote_choice,source_id,source_url,"
    "source_snapshot_date FROM parl_vote_member_votes WHERE vote_event_id=? ORDER "
    "BY CAST(seat AS INTEGER),seat,member_name"
)
ACTOR_SQL = (
    "SELECT n.actor_id,v.node_version_id,v.release_id,v.canonical_label,"
    "v.identity_state,v.source_id,v.source_record_id,v.source_url,"
    "v.source_content_sha256,v.provenance_state,v.attributes_json FROM "
    "actor_graph_node_versions v JOIN actor_graph_nodes n USING(actor_id) WHERE "
    "v.release_id=? AND v.source_id=?"
)
DEFINITIONS_SQL = (
    "SELECT d.indicator_id,d.source_id,d.dataset_code,d.indicator_code,"
    "d.frequency_code,d.unit_code,d.methodology_version,d.revision_policy,"
    "r.indicator_release_id,r.source_snapshot_date,r.source_updated_at,r.source_url,"
    "r.source_content_sha256,r.source_bytes,r.comparison_state FROM "
    "indicator_definitions d JOIN indicator_releases r USING(indicator_id) WHERE "
    "r.indicator_release_id=? ORDER BY d.indicator_id,r.indicator_release_id"
)
SERIES_SQL = (
    "SELECT indicator_series_version_id,indicator_id,indicator_release_id,"
    "stable_series_key,geography_code,geography_name,geography_system,"
    "geography_level,geography_version,dimensions_json FROM "
    "indicator_series_versions WHERE indicator_release_id=? ORDER BY indicator_id,"
    "stable_series_key,indicator_series_version_id"
)
OBSERVATIONS_SQL = (
    "SELECT o.indicator_observation_version_id,o.period_label,o.period_start,"
    "o.period_end,o.value_decimal,o.value_text,o.source_status_code,"
    "o.uncertainty_state,o.revision_ordinal,o.revision_state,o.raw_cell_index,"
    "o.raw_value_json,e.indicator_observation_evidence_id,e.source_content_sha256,"
    "e.raw_path,e.value_json_pointer,e.status_json_pointer FROM "
    "indicator_observation_versions o JOIN indicator_observation_evidence e "
    "USING(indicator_observation_version_id) WHERE "
    "o.indicator_series_version_id=? AND o.indicator_release_id=? ORDER BY "
    "o.period_start,o.revision_ordinal DESC,o.indicator_observation_version_id"
)


class DuplicateKeyError(ValueError):
    """Raised when a JSON object contains the same key more than once."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def strict_json_loads(text: str, *, label: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, UnicodeError, ValueError) as exc:
        raise ValueError(f"{label}: invalid strict JSON: {exc}") from exc


def strict_json_file(path: Path) -> Any:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path}: UTF-8 BOM is forbidden")
    return strict_json_loads(raw.decode("utf-8"), label=path.as_posix())


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_json(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_fact(path: Path) -> dict[str, Any]:
    try:
        relative = path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        relative = path.name
    return {
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def reported_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def stable_source_database_fact(path: Path) -> dict[str, Any]:
    """Hash one real SQLite file while independently rejecting physical drift."""
    if not path.is_file():
        raise RuntimeError(f"missing real source database: {reported_path(path)}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(handle.fileno())
    path_after = path.stat()
    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    path_identity = (
        path_after.st_dev,
        path_after.st_ino,
        path_after.st_size,
        path_after.st_mtime_ns,
        path_after.st_ctime_ns,
    )
    if before_identity != after_identity or after_identity != path_identity:
        raise RuntimeError(
            f"source database changed while validator hashed it: {reported_path(path)}"
        )
    wal_path = Path(f"{path}-wal")
    wal_bytes = wal_path.stat().st_size if wal_path.exists() else 0
    if wal_bytes:
        raise RuntimeError(
            f"source database has non-empty WAL: {reported_path(path)}"
        )
    stat_identity_sha256 = sha256_bytes(
        canonical_json_bytes(
            {
                "device": before.st_dev,
                "inode": before.st_ino,
                "size": before.st_size,
                "mtime_ns": before.st_mtime_ns,
                "ctime_ns": before.st_ctime_ns,
            }
        )
    )
    return {
        "path": reported_path(path),
        "bytes": before.st_size,
        "sha256": digest.hexdigest(),
        "stat_identity_sha256": stat_identity_sha256,
        "wal_bytes": wal_bytes,
    }


def portable_source_database_fact(fact: dict[str, Any]) -> dict[str, Any]:
    """Project a same-run SQLite fact onto its cross-runtime content identity."""

    if set(fact) != {
        "path",
        "bytes",
        "sha256",
        "stat_identity_sha256",
        "wal_bytes",
    }:
        raise RuntimeError("source database fact keys differ from the contract")
    if not isinstance(fact["stat_identity_sha256"], str) or not HEX64_RE.fullmatch(
        fact["stat_identity_sha256"]
    ):
        raise RuntimeError("source database stat identity is not a SHA-256")
    return {
        "path": fact["path"],
        "bytes": fact["bytes"],
        "sha256": fact["sha256"],
        "wal_bytes": fact["wal_bytes"],
    }


def open_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro", uri=True
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def rows_as_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def sql_sha256(statement: str) -> str:
    return sha256_bytes(statement.encode("utf-8"))


def assert_repo_relative(path_value: Any) -> bool:
    if path_value is None:
        return True
    value = str(path_value)
    return not (
        value.startswith("/")
        or value.startswith("file://")
        or re.match(r"^[A-Za-z]:[\\/]", value) is not None
        or "/Users/" in value
        or "/home/" in value
    )


def json_pointer_get(document: Any, pointer: str) -> Any:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ValueError(f"invalid RFC 6901 pointer: {pointer}")
    current = document
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if token == "-" or not token.isdigit():
                raise ValueError(f"invalid list token in pointer {pointer}: {token}")
            current = current[int(token)]
        elif isinstance(current, dict):
            current = current[token]
        else:
            raise ValueError(f"pointer traverses scalar: {pointer}")
    return current


def decimal_display(value: Fraction, places: int = 6) -> str:
    decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
    quantum = Decimal(1).scaleb(-places)
    return format(decimal_value.quantize(quantum, rounding=ROUND_HALF_EVEN), "f")


def nested_physical_database_identity_key(value: Any) -> bool:
    forbidden = {
        "database_sha256",
        "database_bytes",
        "sqlite_sha256",
        "sqlite_bytes",
        "physical_database_sha256",
        "physical_database_bytes",
        "input_file_facts",
    }
    if isinstance(value, dict):
        if any(str(key) in forbidden for key in value):
            return True
        return any(nested_physical_database_identity_key(item) for item in value.values())
    if isinstance(value, list):
        return any(nested_physical_database_identity_key(item) for item in value)
    return False


def bundle_semantic_identity_preimage(semantic: dict[str, Any]) -> dict[str, Any]:
    """Rebuild semantic identity without producer runtime metadata."""
    return {
        "identity_contract_version": "outcome_context_bundle_semantic_identity_v1",
        "method_version": semantic["method_version"],
        "scope_truth": semantic["scope_truth"],
        "policy": semantic["policy"],
        "counts": semantic["counts"],
        "scope_closures": semantic["scope_closures"],
        "links": semantic["links"],
        "link_versions": semantic["link_versions"],
        "observation_refs": semantic["observation_refs"],
        "participant_refs": semantic["participant_refs"],
        "evidence": semantic["evidence"],
        "reviews": semantic["reviews"],
        "releases": semantic["releases"],
        "release_memberships": semantic["release_memberships"],
    }


@dataclass
class Audit:
    checks: dict[str, bool] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    def check(self, name: str, condition: bool, detail: str | None = None) -> None:
        if name in self.checks:
            raise RuntimeError(f"duplicate validation check name: {name}")
        passed = bool(condition)
        self.checks[name] = passed
        if not passed:
            self.failures.append(detail or name)

    def equal(self, name: str, actual: Any, expected: Any) -> None:
        detail = None
        if actual != expected:
            actual_text = repr(actual)
            expected_text = repr(expected)
            if len(actual_text) > 700:
                actual_text = actual_text[:700] + "..."
            if len(expected_text) > 700:
                expected_text = expected_text[:700] + "..."
            detail = f"{name}: actual={actual_text}; expected={expected_text}"
        self.check(name, actual == expected, detail)


@dataclass(frozen=True)
class SourceTruth:
    action_universe: list[dict[str, Any]]
    selected_action: dict[str, Any]
    vote_source_record: dict[str, Any]
    initiative_source_record: dict[str, Any]
    participant_source_rows: list[dict[str, Any]]
    actor_reference_rows: list[dict[str, Any]]
    participant_export_rows: list[dict[str, Any]]
    definitions: list[dict[str, Any]]
    series: list[dict[str, Any]]
    eligible_series: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    selected_observations: dict[str, Any]
    indicator_raw_path: Path
    indicator_raw_document: Any
    actor_query_plan: tuple[str, ...]
    actor_release_source_index_present: bool
    actor_source_query_scale_gate: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actions-db", type=Path, default=DEFAULT_ACTIONS_DB)
    parser.add_argument("--indicators-db", type=Path, default=DEFAULT_INDICATORS_DB)
    parser.add_argument("--actor-graph-db", type=Path, default=DEFAULT_ACTOR_GRAPH_DB)
    parser.add_argument("--manual", type=Path, default=DEFAULT_MANUAL)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--bundle-root", type=Path, default=DEFAULT_BUNDLE_DIR)
    parser.add_argument(
        "--materialization-report",
        type=Path,
        default=DEFAULT_MATERIALIZATION_REPORT,
    )
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def _action_projection(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "action_id": row["vote_event_id"],
        "initiative_id": row["initiative_id"],
        "link_method": row["link_method"],
        "link_confidence_decimal": format(row["confidence"], ".1f"),
        "link_evidence": strict_json_loads(
            row["evidence_json"], label=f"action {row['vote_event_id']} evidence_json"
        ),
        "vote_date": row["vote_date"],
        "legislature": row["legislature"],
        "session_number": row["session_number"],
        "vote_number": row["vote_number"],
        "title": row["title"],
        "totals": {
            "present": row["totals_present"],
            "yes": row["totals_yes"],
            "no": row["totals_no"],
            "abstain": row["totals_abstain"],
            "not_voting": row["totals_no_vote"],
            "absent_normalized": row["totals_absent"],
            "absent_source_record": row["raw_totals_absent"],
        },
        "source_id": row["source_id"],
        "source_record_id": row["source_record_id"],
        "source_snapshot_date": row["source_snapshot_date"],
        "source_record_content_sha256": row["content_sha256"],
    }


def _source_record(
    connection: sqlite3.Connection, source_id: str, source_record_id: str
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT source_record_pk, source_id, source_record_id,
               source_snapshot_date, raw_payload, content_sha256
        FROM source_records
        WHERE source_id = ? AND source_record_id = ?
        """,
        (source_id, source_record_id),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"missing source record: {source_id}/{source_record_id}")
    result = dict(row)
    result["raw_document"] = strict_json_loads(
        result["raw_payload"], label=f"source_records {source_id}/{source_record_id}"
    )
    result["payload_bytes"] = len(result["raw_payload"].encode("utf-8"))
    result["payload_sha256"] = sha256_bytes(result["raw_payload"].encode("utf-8"))
    return result


def _temporal_role(row: dict[str, Any]) -> str:
    if row["period_end"] < ACTION_DATE:
        return "strict_pre_eligible"
    if row["period_start"] > ACTION_DATE:
        return "strict_post_eligible"
    return "overlap_excluded"


def _selected_observation(
    observation: dict[str, Any], role: str
) -> dict[str, Any]:
    result = {key: value for key, value in observation.items() if key != "temporal_role"}
    result = {"role": role, **result}
    if role == "overlap_excluded":
        result["exclusion_reason"] = "annual_interval_contains_action_date"
    return result


def reconstruct_source_truth(
    *,
    actions_db: Path,
    indicators_db: Path,
    actor_graph_db: Path,
    audit: Audit,
) -> SourceTruth:
    for label, path in (
        ("actions", actions_db),
        ("indicators", indicators_db),
        ("actor_graph", actor_graph_db),
    ):
        audit.check(f"input_{label}_database_exists", path.is_file())
        if not path.is_file():
            raise RuntimeError(f"missing {label} database: {path}")

    actions = open_readonly(actions_db)
    indicators = open_readonly(indicators_db)
    actors = open_readonly(actor_graph_db)
    try:
        audit.equal("actions_integrity_check", actions.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        audit.equal(
            "indicators_integrity_check",
            indicators.execute("PRAGMA integrity_check").fetchone()[0],
            "ok",
        )
        audit.equal(
            "actor_graph_integrity_check",
            actors.execute("PRAGMA integrity_check").fetchone()[0],
            "ok",
        )
        audit.equal("actions_foreign_key_check", actions.execute("PRAGMA foreign_key_check").fetchall(), [])
        audit.equal(
            "indicators_foreign_key_check",
            indicators.execute("PRAGMA foreign_key_check").fetchall(),
            [],
        )
        audit.equal(
            "actor_graph_foreign_key_check",
            actors.execute("PRAGMA foreign_key_check").fetchall(),
            [],
        )

        action_rows = actions.execute(
            ACTION_SQL, (INITIATIVE_ID, ACTION_SOURCE_ID, ACTION_SNAPSHOT_DATE)
        ).fetchall()
        action_universe = [_action_projection(row) for row in action_rows]
        action_bytes = canonical_json_bytes(action_universe)
        audit.equal("action_universe_rows", len(action_universe), 20)
        audit.equal("action_universe_canonical_bytes", len(action_bytes), 17_309)
        audit.equal(
            "action_universe_sha256", sha256_bytes(action_bytes), ACTION_UNIVERSE_SHA256
        )
        selected_actions = [
            row for row in action_universe if row["title"] == "Resto del proyecto de ley"
        ]
        audit.equal("selected_action_count", len(selected_actions), 1)
        if len(selected_actions) != 1:
            raise RuntimeError("the exact action predicate did not select one row")
        selected_action = selected_actions[0]
        audit.equal("selected_action_id", selected_action["action_id"], ACTION_ID)
        audit.equal("selected_action_date", selected_action["vote_date"], ACTION_DATE)
        audit.equal(
            "selected_action_source_hash",
            selected_action["source_record_content_sha256"],
            VOTE_RECORD_SHA256,
        )

        vote_record = _source_record(actions, ACTION_SOURCE_ID, ACTION_ID)
        initiative_record = _source_record(actions, "senado_iniciativas", INITIATIVE_ID)
        audit.equal("vote_source_record_payload_bytes", vote_record["payload_bytes"], 39_854)
        audit.equal(
            "vote_source_record_payload_sha256",
            vote_record["payload_sha256"],
            VOTE_RECORD_SHA256,
        )
        audit.equal(
            "vote_source_record_declared_sha256",
            vote_record["content_sha256"],
            VOTE_RECORD_SHA256,
        )
        audit.equal(
            "initiative_source_record_payload_bytes",
            initiative_record["payload_bytes"],
            9_301,
        )
        audit.equal(
            "initiative_source_record_payload_sha256",
            initiative_record["payload_sha256"],
            INITIATIVE_RECORD_SHA256,
        )
        audit.equal(
            "initiative_source_record_declared_sha256",
            initiative_record["content_sha256"],
            INITIATIVE_RECORD_SHA256,
        )

        participant_source_rows = rows_as_dicts(
            actions.execute(PARTICIPANT_SQL, (ACTION_ID,))
        )
        participant_source_bytes = canonical_json_bytes(participant_source_rows)
        audit.equal("participant_source_rows", len(participant_source_rows), 264)
        audit.equal(
            "participant_source_projection_bytes", len(participant_source_bytes), 75_913
        )
        audit.equal(
            "participant_source_projection_sha256",
            sha256_bytes(participant_source_bytes),
            PARTICIPANT_SOURCE_SHA256,
        )
        audit.equal(
            "participant_vote_choice_counts",
            dict(Counter(row["vote_choice"] for row in participant_source_rows)),
            {"SÍ": 134, "NO": 101, "ABSTENCIÓN": 28, "NO VOTAN": 1},
        )
        audit.equal(
            "participant_distinct_seats",
            len({row["seat"] for row in participant_source_rows}),
            264,
        )
        audit.equal(
            "participant_distinct_names",
            len({row["member_name"] for row in participant_source_rows}),
            264,
        )
        audit.equal(
            "participant_distinct_upstream_person_ids",
            len({str(row["person_id"]) for row in participant_source_rows}),
            264,
        )
        audit.equal(
            "participant_missing_names",
            sum(not row["member_name"] for row in participant_source_rows),
            0,
        )
        audit.equal(
            "participant_missing_vote_choices",
            sum(not row["vote_choice"] for row in participant_source_rows),
            0,
        )
        audit.equal(
            "participant_sum_equals_present",
            len(participant_source_rows),
            selected_action["totals"]["present"],
        )
        audit.equal(
            "normalized_absent_remains_null",
            selected_action["totals"]["absent_normalized"],
            None,
        )
        audit.equal(
            "source_record_absent_remains_zero",
            selected_action["totals"]["absent_source_record"],
            0,
        )

        actor_query_plan = tuple(
            str(row[3])
            for row in actors.execute(
                f"EXPLAIN QUERY PLAN {ACTOR_SQL}",
                (ACTOR_GRAPH_RELEASE_ID, ACTION_SOURCE_ID),
            ).fetchall()
        )
        actor_indexes = {
            str(row[1])
            for row in actors.execute(
                "PRAGMA index_list(actor_graph_node_versions)"
            ).fetchall()
        }
        actor_release_source_index_present = (
            "idx_actor_graph_node_versions_release_source_actor" in actor_indexes
        )
        actor_source_query_scale_gate = actor_release_source_index_present and any(
            "idx_actor_graph_node_versions_release_source_actor" in detail
            for detail in actor_query_plan
        )
        audit.check(
            "actor_query_uses_indexed_release_predicate",
            any("INDEX" in detail and "release" in detail.casefold() for detail in actor_query_plan),
        )
        actor_rows = rows_as_dicts(
            actors.execute(ACTOR_SQL, (ACTOR_GRAPH_RELEASE_ID, ACTION_SOURCE_ID))
        )
        actor_by_legacy_person: dict[str, tuple[dict[str, Any], Any]] = {}
        for actor_row in actor_rows:
            attributes = strict_json_loads(
                actor_row.pop("attributes_json"),
                label=f"actor {actor_row['actor_id']} attributes_json",
            )
            if not isinstance(attributes, dict) or "legacy_person_id" not in attributes:
                continue
            legacy_person_id = attributes["legacy_person_id"]
            match_key = str(legacy_person_id)
            if match_key in actor_by_legacy_person:
                raise RuntimeError(f"duplicate actor legacy_person_id in pinned release: {match_key}")
            actor_by_legacy_person[match_key] = (actor_row, legacy_person_id)

        raw_member_votes = vote_record["raw_document"].get("member_votes")
        if not isinstance(raw_member_votes, list):
            raise RuntimeError("vote source record member_votes is not an array")
        raw_locator_by_key: dict[tuple[str, str, str, str], int] = {}
        for index, raw_vote in enumerate(raw_member_votes):
            if not isinstance(raw_vote, dict):
                raise RuntimeError(f"raw member_votes/{index} is not an object")
            key = (
                str(raw_vote.get("seat")),
                str(raw_vote.get("member_name")),
                str(raw_vote.get("group")),
                str(raw_vote.get("vote_choice")),
            )
            if key in raw_locator_by_key:
                raise RuntimeError(f"duplicate exact raw ballot occurrence: {key}")
            raw_locator_by_key[key] = index
        audit.equal("raw_participant_array_rows", len(raw_member_votes), 264)
        audit.equal("raw_participant_exact_keys", len(raw_locator_by_key), 264)

        actor_reference_rows: list[dict[str, Any]] = []
        participant_export_rows: list[dict[str, Any]] = []
        locator_indices: list[int] = []
        for participant in participant_source_rows:
            actor_match = actor_by_legacy_person.get(str(participant["person_id"]))
            if actor_match is None:
                raise RuntimeError(
                    f"participant {participant['person_id']} has no actor in pinned release"
                )
            actor, legacy_person_id = actor_match
            raw_key = (
                str(participant["seat"]),
                str(participant["member_name"]),
                str(participant["group_code"]),
                str(participant["vote_choice"]),
            )
            if raw_key not in raw_locator_by_key:
                raise RuntimeError(f"participant has no exact raw ballot locator: {raw_key}")
            raw_index = raw_locator_by_key[raw_key]
            locator_indices.append(raw_index)
            actor_reference_rows.append(
                {
                    "seat": participant["seat"],
                    "official_member_name": participant["member_name"],
                    "legacy_person_id": legacy_person_id,
                    "vote_choice": participant["vote_choice"],
                    "official_group_code": participant["group_code"],
                    "actor_id": actor["actor_id"],
                    "node_version_id": actor["node_version_id"],
                    "release_id": actor["release_id"],
                    "canonical_label": actor["canonical_label"],
                    "identity_state": actor["identity_state"],
                    "source_id": actor["source_id"],
                    "source_record_id": actor["source_record_id"],
                    "source_url": actor["source_url"],
                    "source_content_sha256": actor["source_content_sha256"],
                    "provenance_state": actor["provenance_state"],
                }
            )
            participant_export_rows.append(
                {
                    "seat": participant["seat"],
                    "official_member_name": participant["member_name"],
                    "upstream_person_id": str(participant["person_id"]),
                    "official_group_code": participant["group_code"],
                    "official_vote_choice": participant["vote_choice"],
                    "actor_graph_release_id": actor["release_id"],
                    "actor_id": actor["actor_id"],
                    "actor_node_version_id": actor["node_version_id"],
                    "actor_canonical_label": actor["canonical_label"],
                    "actor_identity_state": actor["identity_state"],
                    "actor_provenance_state": actor["provenance_state"],
                    "actor_source_record_id": actor["source_record_id"],
                    "actor_source_url": actor["source_url"],
                    "actor_source_content_sha256": actor["source_content_sha256"],
                    "vote_source_record_id": vote_record["source_record_id"],
                    "vote_source_record_content_sha256": vote_record["content_sha256"],
                    "vote_source_locator": f"/member_votes/{raw_index}",
                    "vote_source_id": participant["source_id"],
                    "vote_source_url": participant["source_url"],
                    "vote_source_snapshot_date": participant["source_snapshot_date"],
                }
            )

        audit.equal("participant_raw_locator_bijection", sorted(locator_indices), list(range(264)))
        actor_reference_bytes = canonical_json_bytes(actor_reference_rows)
        audit.equal("actor_reference_rows", len(actor_reference_rows), 264)
        audit.equal("actor_reference_projection_bytes", len(actor_reference_bytes), 220_798)
        audit.equal(
            "actor_reference_projection_sha256",
            sha256_bytes(actor_reference_bytes),
            ACTOR_REFERENCE_SHA256,
        )
        participant_export_bytes = canonical_json_bytes(participant_export_rows)
        audit.equal("participant_export_rows", len(participant_export_rows), 264)
        audit.equal(
            "participant_export_projection_bytes", len(participant_export_bytes), 330_512
        )
        audit.equal(
            "participant_export_projection_sha256",
            sha256_bytes(participant_export_bytes),
            PARTICIPANT_EXPORT_SHA256,
        )
        audit.equal(
            "actor_label_mismatch_count",
            sum(
                row["official_member_name"] != row["actor_canonical_label"]
                for row in participant_export_rows
            ),
            2,
        )

        definitions = rows_as_dicts(
            indicators.execute(DEFINITIONS_SQL, (INDICATOR_RELEASE_ID,))
        )
        definitions_bytes = canonical_json_bytes(definitions)
        audit.equal("indicator_definitions_and_releases_rows", len(definitions), 1)
        audit.equal("indicator_definitions_and_releases_bytes", len(definitions_bytes), 809)
        audit.equal(
            "indicator_definitions_and_releases_sha256",
            sha256_bytes(definitions_bytes),
            DEFINITIONS_SHA256,
        )

        series: list[dict[str, Any]] = []
        for row in indicators.execute(SERIES_SQL, (INDICATOR_RELEASE_ID,)):
            record = dict(row)
            record["dimensions"] = strict_json_loads(
                record.pop("dimensions_json"),
                label=f"series {record['indicator_series_version_id']} dimensions_json",
            )
            series.append(record)
        series_bytes = canonical_json_bytes(series)
        audit.equal("indicator_series_universe_rows", len(series), 86)
        audit.equal("indicator_series_universe_bytes", len(series_bytes), 42_340)
        audit.equal(
            "indicator_series_universe_sha256",
            sha256_bytes(series_bytes),
            SERIES_UNIVERSE_SHA256,
        )
        eligible_series = [
            row
            for row in series
            if row["geography_code"] == "ES" and row["geography_level"] == "country"
        ]
        eligible_bytes = canonical_json_bytes(eligible_series)
        audit.equal("eligible_indicator_series_rows", len(eligible_series), 1)
        audit.equal("eligible_indicator_series_bytes", len(eligible_bytes), 483)
        audit.equal(
            "eligible_indicator_series_sha256",
            sha256_bytes(eligible_bytes),
            ELIGIBLE_SERIES_SHA256,
        )
        if len(eligible_series) != 1:
            raise RuntimeError("exact ES/country filter did not select one series")
        audit.equal(
            "selected_indicator_series_version_id",
            eligible_series[0]["indicator_series_version_id"],
            INDICATOR_SERIES_VERSION_ID,
        )

        observations: list[dict[str, Any]] = []
        for row in indicators.execute(
            OBSERVATIONS_SQL, (INDICATOR_SERIES_VERSION_ID, INDICATOR_RELEASE_ID)
        ):
            record = dict(row)
            record["temporal_role"] = _temporal_role(record)
            observations.append(record)
        observations_bytes = canonical_json_bytes(observations)
        audit.equal("indicator_observation_universe_rows", len(observations), 25)
        audit.equal("indicator_observation_universe_bytes", len(observations_bytes), 20_024)
        audit.equal(
            "indicator_observation_universe_sha256",
            sha256_bytes(observations_bytes),
            OBSERVATION_UNIVERSE_SHA256,
        )
        audit.equal(
            "indicator_observation_temporal_role_counts",
            dict(Counter(row["temporal_role"] for row in observations)),
            {
                "strict_pre_eligible": 20,
                "overlap_excluded": 1,
                "strict_post_eligible": 4,
            },
        )
        pre_rows = [row for row in observations if row["temporal_role"] == "strict_pre_eligible"]
        post_rows = [row for row in observations if row["temporal_role"] == "strict_post_eligible"]
        overlap_rows = [row for row in observations if row["temporal_role"] == "overlap_excluded"]
        latest_pre_end = max(row["period_end"] for row in pre_rows)
        latest_pre_rows = [
            row for row in pre_rows if row["period_end"] == latest_pre_end
        ]
        latest_pre_revision = max(
            row["revision_ordinal"] for row in latest_pre_rows
        )
        selected_pre = min(
            (
                row
                for row in latest_pre_rows
                if row["revision_ordinal"] == latest_pre_revision
            ),
            key=lambda row: row["indicator_observation_version_id"],
        )
        selected_post = sorted(
            post_rows,
            key=lambda row: (
                row["period_start"],
                -row["revision_ordinal"],
                row["indicator_observation_version_id"],
            ),
        )[0]
        selected_observations = {
            "pre": _selected_observation(selected_pre, "pre"),
            "overlap_excluded": [
                _selected_observation(row, "overlap_excluded") for row in overlap_rows
            ],
            "post": _selected_observation(selected_post, "post"),
        }
        audit.equal(
            "selected_pre_observation",
            selected_observations["pre"]["indicator_observation_version_id"],
            "vclc:indicator-observation-version:9a65804d28811168fbd8b41d",
        )
        audit.equal(
            "selected_overlap_observation",
            selected_observations["overlap_excluded"][0]["indicator_observation_version_id"],
            "vclc:indicator-observation-version:be05c6fbcc661b89fb8b6698",
        )
        audit.equal(
            "selected_post_observation",
            selected_observations["post"]["indicator_observation_version_id"],
            "vclc:indicator-observation-version:ee0bd4e628bf3c0f64a7a6f7",
        )

        raw_path_value = definitions[0]["source_content_sha256"]
        indicator_release = indicators.execute(
            """
            SELECT source_bytes, raw_path, source_content_sha256
            FROM indicator_releases
            WHERE indicator_release_id = ?
            """,
            (INDICATOR_RELEASE_ID,),
        ).fetchone()
        if indicator_release is None:
            raise RuntimeError("pinned indicator release disappeared")
        indicator_raw_path = REPO_ROOT / indicator_release["raw_path"]
        audit.check("indicator_raw_path_repo_relative", assert_repo_relative(indicator_release["raw_path"]))
        audit.check("indicator_raw_file_exists", indicator_raw_path.is_file())
        if not indicator_raw_path.is_file():
            raise RuntimeError(f"missing indicator raw file: {indicator_raw_path}")
        audit.equal("indicator_raw_file_bytes", indicator_raw_path.stat().st_size, 4_763_587)
        audit.equal("indicator_raw_file_sha256", sha256_file(indicator_raw_path), INDICATOR_SOURCE_SHA256)
        audit.equal("indicator_release_source_bytes", indicator_release["source_bytes"], 4_763_587)
        audit.equal(
            "indicator_release_source_sha256",
            indicator_release["source_content_sha256"],
            INDICATOR_SOURCE_SHA256,
        )
        audit.equal("indicator_definition_source_hash", raw_path_value, INDICATOR_SOURCE_SHA256)
        indicator_raw_document = strict_json_file(indicator_raw_path)
        for role, selected in (
            ("pre", selected_observations["pre"]),
            ("overlap", selected_observations["overlap_excluded"][0]),
            ("post", selected_observations["post"]),
        ):
            pointed = json_pointer_get(indicator_raw_document, selected["value_json_pointer"])
            audit.equal(f"indicator_{role}_raw_pointer_value", str(pointed), selected["raw_value_json"])

        return SourceTruth(
            action_universe=action_universe,
            selected_action=selected_action,
            vote_source_record=vote_record,
            initiative_source_record=initiative_record,
            participant_source_rows=participant_source_rows,
            actor_reference_rows=actor_reference_rows,
            participant_export_rows=participant_export_rows,
            definitions=definitions,
            series=series,
            eligible_series=eligible_series,
            observations=observations,
            selected_observations=selected_observations,
            indicator_raw_path=indicator_raw_path,
            indicator_raw_document=indicator_raw_document,
            actor_query_plan=actor_query_plan,
            actor_release_source_index_present=actor_release_source_index_present,
            actor_source_query_scale_gate=actor_source_query_scale_gate,
        )
    finally:
        actions.close()
        indicators.close()
        actors.close()


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def _validate_query_contracts(manual: dict[str, Any], audit: Audit) -> None:
    closures = manual["selection_closure"]
    action_contract = closures["action_scope"]["preimage"]["query_contract"]
    audit.equal("manual_action_sql_exact", action_contract["sql_utf8"], ACTION_SQL)
    audit.equal(
        "manual_action_sql_sha256",
        action_contract["sql_sha256"],
        sql_sha256(ACTION_SQL),
    )
    audit.equal(
        "manual_action_parameters_exact",
        action_contract["parameters"],
        [INITIATIVE_ID, ACTION_SOURCE_ID, ACTION_SNAPSHOT_DATE],
    )

    indicator_contract = closures["indicator_scope"]["preimage"]["query_contract"]
    for prefix, sql_key, sha_key, statement in (
        (
            "definitions",
            "definitions_and_releases_sql_utf8",
            "definitions_and_releases_sql_sha256",
            DEFINITIONS_SQL,
        ),
        ("series", "series_sql_utf8", "series_sql_sha256", SERIES_SQL),
        (
            "observations",
            "observations_sql_utf8",
            "observations_sql_sha256",
            OBSERVATIONS_SQL,
        ),
    ):
        audit.equal(f"manual_{prefix}_sql_exact", indicator_contract[sql_key], statement)
        audit.equal(
            f"manual_{prefix}_sql_sha256",
            indicator_contract[sha_key],
            sql_sha256(statement),
        )
    audit.equal(
        "manual_definition_release_parameters",
        indicator_contract["definitions_and_releases_parameters"],
        [INDICATOR_RELEASE_ID],
    )
    audit.equal(
        "manual_series_release_parameters",
        indicator_contract["series_parameters"],
        [INDICATOR_RELEASE_ID],
    )
    audit.equal(
        "manual_observation_release_parameters",
        indicator_contract["observation_parameters"],
        [INDICATOR_SERIES_VERSION_ID, INDICATOR_RELEASE_ID],
    )

    actor_contract = closures["actor_reference_scope"]["preimage"]["query_contract"]
    audit.equal("manual_participant_sql_exact", actor_contract["participant_sql_utf8"], PARTICIPANT_SQL)
    audit.equal(
        "manual_participant_sql_sha256",
        actor_contract["participant_sql_sha256"],
        sql_sha256(PARTICIPANT_SQL),
    )
    audit.equal("manual_actor_sql_exact", actor_contract["actor_sql_utf8"], ACTOR_SQL)
    audit.equal(
        "manual_actor_sql_sha256", actor_contract["actor_sql_sha256"], sql_sha256(ACTOR_SQL)
    )
    audit.equal("manual_participant_parameters", actor_contract["participant_parameters"], [ACTION_ID])
    audit.equal(
        "manual_actor_parameters",
        actor_contract["actor_parameters"],
        [ACTOR_GRAPH_RELEASE_ID, ACTION_SOURCE_ID],
    )


def _validate_closures(manual: dict[str, Any], audit: Audit) -> None:
    closures = manual["selection_closure"]
    expected = {
        "action_scope": (ACTION_CLOSURE_SHA256, 2_362),
        "indicator_scope": (INDICATOR_CLOSURE_SHA256, 5_780),
        "actor_reference_scope": (ACTOR_CLOSURE_SHA256, 2_431),
        "combined_scope": (COMBINED_CLOSURE_SHA256, 628),
    }
    for key, (expected_sha, expected_bytes) in expected.items():
        closure = closures[key]
        preimage_bytes = canonical_json_bytes(closure["preimage"])
        audit.equal(f"manual_{key}_canonical_bytes", closure["canonical_bytes"], len(preimage_bytes))
        audit.equal(f"manual_{key}_expected_canonical_bytes", len(preimage_bytes), expected_bytes)
        audit.equal(f"manual_{key}_sha256_recomputed", closure["sha256"], sha256_bytes(preimage_bytes))
        audit.equal(f"manual_{key}_sha256_expected", closure["sha256"], expected_sha)
        audit.check(
            f"manual_{key}_physical_database_hashes_excluded",
            not nested_physical_database_identity_key(closure["preimage"]),
        )

    action = closures["action_scope"]["preimage"]
    indicator = closures["indicator_scope"]["preimage"]
    actor = closures["actor_reference_scope"]["preimage"]
    combined = closures["combined_scope"]["preimage"]
    audit.equal("manual_action_candidate_count", action["candidate_count"], 20)
    audit.equal("manual_action_candidate_universe_bytes", action["candidate_universe_canonical_bytes"], 17_309)
    audit.equal("manual_action_candidate_universe_sha256", action["candidate_universe_sha256"], ACTION_UNIVERSE_SHA256)
    audit.equal("manual_action_selected_count", action["selected_count"], 1)
    audit.equal("manual_action_excluded_count", action["excluded_count"], 19)
    audit.equal("manual_action_selected_ids", action["selected_action_ids"], [ACTION_ID])
    audit.equal("manual_action_bounded_complete", action["bounded_scope_complete"], True)
    audit.equal("manual_action_global_search_false", action["all_possible_actions_searched"], False)

    for name, actual, expected_value in (
        ("definition_count", indicator["definitions_and_releases_count"], 1),
        ("definition_bytes", indicator["definitions_and_releases_canonical_bytes"], 809),
        ("definition_sha", indicator["definitions_and_releases_sha256"], DEFINITIONS_SHA256),
        ("series_count", indicator["series_count"], 86),
        ("series_bytes", indicator["series_universe_canonical_bytes"], 42_340),
        ("series_sha", indicator["series_universe_sha256"], SERIES_UNIVERSE_SHA256),
        ("eligible_count", indicator["geography_eligible_series_count"], 1),
        ("eligible_bytes", indicator["geography_eligible_series_canonical_bytes"], 483),
        ("eligible_sha", indicator["geography_eligible_series_sha256"], ELIGIBLE_SERIES_SHA256),
        ("observation_count", indicator["observation_count"], 25),
        ("observation_bytes", indicator["observation_role_universe_canonical_bytes"], 20_024),
        ("observation_sha", indicator["observation_role_universe_sha256"], OBSERVATION_UNIVERSE_SHA256),
        ("pre_count", indicator["strict_pre_eligible_count"], 20),
        ("overlap_count", indicator["overlap_excluded_count"], 1),
        ("post_count", indicator["strict_post_eligible_count"], 4),
    ):
        audit.equal(f"manual_indicator_{name}", actual, expected_value)
    audit.equal("manual_indicator_bounded_complete", indicator["bounded_scope_complete"], True)
    audit.equal("manual_indicator_representative_codebook_false", indicator["representative_indicator_codebook"], False)
    audit.equal("manual_indicator_global_search_false", indicator["all_possible_indicators_searched"], False)

    audit.equal("manual_actor_reference_count", actor["actor_reference_count"], 264)
    audit.equal("manual_actor_reference_bytes", actor["actor_reference_canonical_bytes"], 220_798)
    audit.equal("manual_actor_reference_sha256", actor["actor_reference_sha256"], ACTOR_REFERENCE_SHA256)
    audit.equal("manual_actor_label_mismatch_count", actor["official_actor_label_mismatch_count"], 2)
    audit.equal("manual_actor_bounded_complete", actor["bounded_scope_complete"], True)
    audit.equal("manual_actor_global_search_false", actor["all_possible_actor_sources_searched"], False)

    audit.equal("manual_combined_action_scope", combined["action_scope_sha256"], ACTION_CLOSURE_SHA256)
    audit.equal("manual_combined_indicator_scope", combined["indicator_scope_sha256"], INDICATOR_CLOSURE_SHA256)
    audit.equal("manual_combined_actor_scope", combined["actor_reference_scope_sha256"], ACTOR_CLOSURE_SHA256)
    audit.equal("manual_combined_candidate_pairs", combined["candidate_pairs_in_bounded_scope"], 20)
    audit.equal("manual_combined_machine_candidates", combined["machine_audited_preproduction_candidates"], 1)
    audit.equal("manual_combined_human_reviews_zero", combined["human_reviewed_pairs"], 0)
    audit.equal("manual_combined_publications_zero", combined["published_links"], 0)
    audit.equal("manual_combined_bounded_complete", combined["bounded_scope_complete"], True)
    audit.equal("manual_combined_all_actions_false", combined["all_possible_actions_searched"], False)
    audit.equal("manual_combined_all_indicators_false", combined["all_possible_indicators_searched"], False)
    audit.equal(
        "manual_combined_all_pairs_false",
        combined["all_possible_action_indicator_pairs_searched"],
        False,
    )


def _validate_exact_math(candidate: dict[str, Any], truth: SourceTruth, audit: Audit) -> None:
    selected = truth.selected_observations
    pre_decimal = Decimal(selected["pre"]["value_decimal"])
    post_decimal = Decimal(selected["post"]["value_decimal"])
    audit.check("calculation_inputs_are_integral_real_values", pre_decimal == pre_decimal.to_integral() and post_decimal == post_decimal.to_integral())
    pre = int(pre_decimal)
    post = int(post_decimal)
    difference = Fraction(post - pre, 1)
    ratio = Fraction(post, pre)
    relative = Fraction(post - pre, pre)
    percent = relative * 100
    basis_points = relative * 10_000
    calculation = candidate["calculation"]
    audit.equal("calculation_pre_value", calculation["pre_value_decimal"], str(pre))
    audit.equal("calculation_post_value", calculation["post_value_decimal"], str(post))
    expected_rationals = {
        "absolute_difference": (difference, "PPS_EU27_2020_HAB"),
        "post_to_pre_ratio": (ratio, "ratio"),
        "relative_change": (relative, "ratio"),
        "percent_change": (percent, "percent"),
        "basis_point_change": (basis_points, "basis_points"),
    }
    for key, (fraction, unit) in expected_rationals.items():
        value = calculation[key]
        audit.equal(f"calculation_{key}_numerator", value["numerator"], str(fraction.numerator))
        audit.equal(f"calculation_{key}_denominator", value["denominator"], str(fraction.denominator))
        audit.equal(f"calculation_{key}_unit", value["unit"], unit)
        if key == "absolute_difference":
            audit.equal("calculation_absolute_difference_decimal", value["exact_decimal"], "-400")
        else:
            audit.equal(f"calculation_{key}_places", value["rounded_decimal_places"], 6)
            audit.equal(f"calculation_{key}_rounding", value["rounding_mode"], "ROUND_HALF_EVEN")
            audit.equal(f"calculation_{key}_display", value["rounded_decimal"], decimal_display(fraction))
    audit.equal("calculation_exact_rationals_authoritative", calculation["exact_rationals_authoritative"], True)
    audit.equal("calculation_rounded_not_authoritative", calculation["rounded_decimals_authoritative"], False)
    audit.equal("calculation_no_statistical_test", calculation["statistical_test"], "not_performed")
    audit.equal("calculation_no_association_claim", calculation["association_claim"], "none")
    audit.equal("calculation_no_causal_claim", calculation["causal_claim"], "none")
    audit.equal("calculation_no_effect_estimate", calculation["effect_estimate"], "not_computed")


def _validate_manual_action_and_indicator(
    candidate: dict[str, Any], truth: SourceTruth, audit: Audit
) -> None:
    action = candidate["action"]
    source_action = truth.selected_action
    expected_action_fields = {
        "action_id": source_action["action_id"],
        "action_occurred_at": source_action["vote_date"],
        "legislature": source_action["legislature"],
        "session_number": source_action["session_number"],
        "vote_number": source_action["vote_number"],
        "vote_title": source_action["title"],
        "initiative_id": source_action["initiative_id"],
        "initiative_link_method": source_action["link_method"],
        "initiative_link_confidence_decimal": source_action["link_confidence_decimal"],
        "initiative_link_evidence": source_action["link_evidence"],
        "source_id": source_action["source_id"],
        "source_record_id": source_action["source_record_id"],
        "source_snapshot_date": source_action["source_snapshot_date"],
        "normalized_source_record_payload_sha256": source_action["source_record_content_sha256"],
        "normalized_source_record_payload_bytes": truth.vote_source_record["payload_bytes"],
        "initiative_source_record_id": truth.initiative_source_record["source_record_id"],
        "initiative_source_snapshot_date": truth.initiative_source_record["source_snapshot_date"],
        "initiative_normalized_source_record_payload_sha256": truth.initiative_source_record["content_sha256"],
        "initiative_normalized_source_record_payload_bytes": truth.initiative_source_record["payload_bytes"],
    }
    for key, expected in expected_action_fields.items():
        audit.equal(f"manual_action_{key}", action[key], expected)
    initiative_raw = truth.initiative_source_record["raw_document"]
    audit.equal("manual_action_initiative_title", action["initiative_title"], initiative_raw["iniciativa_title"])
    audit.equal("manual_action_initiative_expediente", action["initiative_expediente"], initiative_raw["expediente"])
    audit.equal("manual_action_vote_file_url", action["official_vote_file_url"], truth.vote_source_record["raw_document"]["vote_file_url"])
    audit.equal("manual_action_session_file_url", action["official_session_file_url"], truth.vote_source_record["raw_document"]["session_vote_file_url"])
    audit.equal("manual_action_vote_page_url", action["official_vote_page_url"], truth.vote_source_record["raw_document"]["vote_url"])
    audit.equal("manual_action_initiative_url", action["official_initiative_url"], initiative_raw["iniciativa_url"])
    audit.equal(
        "manual_action_original_xml_gap",
        action["original_vote_xml"],
        {
            "content_sha256": None,
            "bytes": None,
            "capture_state": "absent_from_current_snapshot",
            "normalized_source_record_is_original_bytes": False,
            "gap": "Official URLs and normalized source record exist, but no independently content-addressed copy of original vote-specific XML bytes exists.",
        },
    )
    audit.equal(
        "manual_action_ballot_counts",
        action["totals"]["source_ballot_label_counts"],
        {"SÍ": 134, "NO": 101, "ABSTENCIÓN": 28, "NO VOTAN": 1},
    )
    audit.equal("manual_action_absent_normalized", action["totals"]["absent_normalized_database_column"], None)
    audit.equal("manual_action_absent_source", action["totals"]["absent_source_record_payload"], 0)

    indicator = candidate["indicator"]
    definition = truth.definitions[0]
    series = truth.eligible_series[0]
    for key in (
        "source_id",
        "dataset_code",
        "indicator_id",
        "indicator_code",
        "frequency_code",
        "unit_code",
        "methodology_version",
        "revision_policy",
        "indicator_release_id",
        "source_snapshot_date",
        "source_updated_at",
        "source_url",
        "source_content_sha256",
        "source_bytes",
        "comparison_state",
    ):
        audit.equal(f"manual_indicator_{key}_source_parity", indicator[key], definition[key])
    for key in (
        "indicator_series_version_id",
        "stable_series_key",
        "geography_code",
        "geography_name",
        "geography_system",
        "geography_level",
        "geography_version",
        "dimensions",
    ):
        audit.equal(f"manual_indicator_{key}_series_parity", indicator[key], series[key])
    audit.equal("manual_indicator_raw_path", indicator["raw_path"], truth.indicator_raw_path.relative_to(REPO_ROOT).as_posix())
    audit.equal("manual_selected_observations_source_parity", candidate["temporal_assessment"]["selected_observations"], truth.selected_observations)


def _validate_candidate_identity(candidate: dict[str, Any], audit: Audit) -> None:
    identity = candidate["identity"]
    link_preimage = identity["outcome_link_identity_preimage"]
    link_bytes = canonical_json_bytes(link_preimage)
    audit.equal("link_identity_canonical_bytes", identity["outcome_link_identity_canonical_bytes"], len(link_bytes))
    audit.equal("link_identity_expected_bytes", len(link_bytes), 406)
    audit.equal("link_identity_sha256_recomputed", identity["outcome_link_identity_sha256"], sha256_bytes(link_bytes))
    audit.equal("link_identity_sha256_expected", identity["outcome_link_identity_sha256"], LINK_IDENTITY_SHA256)
    audit.equal("link_id_from_full_identity_sha", candidate["outcome_link_id"], f"vclc:outcome-link:{sha256_bytes(link_bytes)[:24]}")
    audit.check("link_id_format", LINK_ID_RE.fullmatch(candidate["outcome_link_id"]) is not None)
    audit.equal("link_id_expected", candidate["outcome_link_id"], LINK_ID)

    version_preimage = identity["outcome_link_version_identity_preimage"]
    version_bytes = canonical_json_bytes(version_preimage)
    audit.equal("link_version_identity_canonical_bytes", identity["outcome_link_version_identity_canonical_bytes"], len(version_bytes))
    audit.equal("link_version_identity_expected_bytes", len(version_bytes), 11_270)
    audit.equal("link_version_identity_sha256_recomputed", identity["outcome_link_version_identity_sha256"], sha256_bytes(version_bytes))
    audit.equal("link_version_identity_sha256_expected", identity["outcome_link_version_identity_sha256"], LINK_VERSION_IDENTITY_SHA256)
    audit.equal("link_version_id_from_full_identity_sha", candidate["outcome_link_version_id"], f"vclc:outcome-link-version:{sha256_bytes(version_bytes)[:24]}")
    audit.check("link_version_id_format", LINK_VERSION_ID_RE.fullmatch(candidate["outcome_link_version_id"]) is not None)
    audit.equal("link_version_id_expected", candidate["outcome_link_version_id"], LINK_VERSION_ID)
    audit.check("link_version_identity_has_no_physical_db_fact", not nested_physical_database_identity_key(version_preimage))
    audit.equal("generated_at_excluded_from_identity", identity["generated_at_included_in_identity"], False)
    audit.equal("physical_database_hashes_excluded_from_identity", identity["physical_database_hashes_included_in_identity"], False)
    audit.equal("review_result_excluded_from_identity", identity["review_result_included_in_version_identity"], False)

    audit.equal("identity_link_kind_parity", link_preimage["link_kind"], candidate["link_kind"])
    audit.equal("identity_action_id_parity", link_preimage["action_id"], candidate["action"]["action_id"])
    audit.equal("identity_indicator_id_parity", link_preimage["indicator_id"], candidate["indicator"]["indicator_id"])
    audit.equal("identity_series_key_parity", link_preimage["stable_series_key"], candidate["indicator"]["stable_series_key"])
    audit.equal(
        "identity_geography_parity",
        link_preimage["geography_scope"],
        {
            "geography_code": candidate["indicator"]["geography_code"],
            "geography_level": candidate["indicator"]["geography_level"],
            "geography_system": candidate["indicator"]["geography_system"],
        },
    )
    audit.equal("version_identity_link_id_parity", version_preimage["outcome_link_id"], candidate["outcome_link_id"])
    audit.equal("version_identity_state_parity", version_preimage["version_state"], candidate["version_state"])
    audit.equal("version_identity_level_parity", version_preimage["evidence_level"], candidate["evidence_level"])
    audit.equal("version_identity_candidate_status_parity", version_preimage["candidate_status"], candidate["candidate_status"])
    audit.equal("version_identity_supersession_parity", version_preimage["supersedes_outcome_link_version_id"], candidate["supersedes_outcome_link_version_id"])
    audit.equal("version_identity_temporal_parity", version_preimage["temporal_assessment"], candidate["temporal_assessment"])
    audit.equal("version_identity_semantic_parity", version_preimage["semantic_assessment"], candidate["semantic_assessment"])
    audit.equal("version_identity_geography_parity", version_preimage["geography_assessment"], candidate["geography_assessment"])
    audit.equal("version_identity_calculation_parity", version_preimage["calculation"], candidate["calculation"])
    audit.equal("version_identity_claim_policy_parity", version_preimage["claim_policy"], candidate["claim_policy"])
    audit.equal("version_identity_wording_parity", version_preimage["reader_wording"], candidate["reader_wording"])
    audit.equal("version_identity_reason_codes_parity", version_preimage["reason_codes"], candidate["reason_codes"])
    audit.equal("version_identity_limitations_parity", version_preimage["limitations"], candidate["limitations"])
    audit.equal("version_identity_machine_state_parity", version_preimage["machine_audit_state"], candidate["machine_audit_state"])


def validate_manual(manual_path: Path, truth: SourceTruth, audit: Audit) -> dict[str, Any]:
    audit.check("manual_artifact_exists", manual_path.is_file())
    if not manual_path.is_file():
        raise RuntimeError(f"missing canonical manual input: {manual_path}")
    manual = strict_json_file(manual_path)
    if not isinstance(manual, dict):
        raise RuntimeError("manual outcome context input must be one JSON object")
    audit.equal("manual_artifact_bytes", manual_path.stat().st_size, 463_383)
    audit.equal("manual_artifact_sha256", sha256_file(manual_path), MANUAL_ARTIFACT_SHA256)
    audit.equal(
        "manual_top_level_keys",
        list(manual),
        [
            "format_version",
            "method_version",
            "generated_at",
            "generated_at_source",
            "generated_at_identity_authority",
            "scope_truth",
            "policy",
            "selection_closure",
            "candidates",
        ],
    )
    audit.equal("manual_format_version", manual["format_version"], FORMAT_VERSION)
    audit.equal("manual_method_version", manual["method_version"], METHOD_VERSION)
    audit.equal("manual_generated_at", manual["generated_at"], "2026-08-20T00:00:00Z")
    audit.equal("manual_generated_at_identity_authority_false", manual["generated_at_identity_authority"], False)
    audit.equal("manual_candidate_count", len(manual["candidates"]), 1)
    if len(manual["candidates"]) != 1:
        raise RuntimeError("manual input must contain exactly one current C0 candidate")

    scope = manual["scope_truth"]
    audit.equal("manual_scale_stage_c0", scope["scale_stage"], "C0")
    audit.equal("manual_bounded_candidate_pairs", scope["bounded_candidate_pairs"], 20)
    audit.equal("manual_machine_candidates", scope["machine_audited_preproduction_candidates"], 1)
    audit.equal("manual_human_reviewed_pairs_zero", scope["human_reviewed_pairs"], 0)
    audit.equal("manual_published_links_zero", scope["published_links"], 0)
    audit.equal("manual_scope_bounded_complete", scope["bounded_scope_complete"], True)
    audit.equal("manual_scope_all_actions_false", scope["all_possible_actions_searched"], False)
    audit.equal("manual_scope_all_indicators_false", scope["all_possible_indicators_searched"], False)
    audit.equal("manual_scope_all_pairs_false", scope["all_possible_action_indicator_pairs_searched"], False)

    _validate_query_contracts(manual, audit)
    _validate_closures(manual, audit)
    candidate = manual["candidates"][0]
    audit.equal("candidate_link_id", candidate["outcome_link_id"], LINK_ID)
    audit.equal("candidate_link_version_id", candidate["outcome_link_version_id"], LINK_VERSION_ID)
    audit.equal("candidate_version_state", candidate["version_state"], "preproduction_candidate")
    audit.equal("candidate_evidence_level_l1", candidate["evidence_level"], "L1")
    audit.equal("candidate_status_pending", candidate["candidate_status"], "pending_human_review")
    audit.equal("candidate_human_review_required", candidate["human_review_required"], True)
    audit.equal("candidate_human_review_not_completed", candidate["human_review_completed"], False)
    audit.equal("candidate_not_published", candidate["published"], False)
    audit.equal("candidate_not_directional_countable", candidate["directional_countable"], False)
    audit.equal("candidate_not_ranking_eligible", candidate["ranking_eligible"], False)
    audit.equal("candidate_no_supersession", candidate["supersedes_outcome_link_version_id"], None)
    audit.equal(
        "candidate_review_null_state",
        candidate["review"],
        {
            "status": "not_performed",
            "review_version_id": None,
            "review_identity_sha256": None,
            "review_identity_preimage": None,
            "reviewer_public_id": None,
            "reviewed_at": None,
            "review_method": None,
            "decision": None,
            "signoff": None,
            "supersedes_review_version_id": None,
        },
    )
    audit.equal(
        "candidate_release_membership_null_state",
        candidate["release_membership"],
        {
            "outcome_link_release_id": None,
            "membership_id": None,
            "membership_state": "not_released",
            "published": False,
            "supersedes_membership_id": None,
        },
    )
    audit.equal("candidate_machine_audit_state", candidate["machine_audit_state"], "machine_validated")

    _validate_manual_action_and_indicator(candidate, truth, audit)
    participants = candidate["participants"]
    audit.equal("manual_participant_records_total", participants["records_total"], 264)
    audit.equal("manual_participant_records_exact_source_reconstruction", participants["records"], truth.participant_export_rows)
    audit.equal("manual_participant_source_projection_sha", participants["source_projection_sha256"], PARTICIPANT_SOURCE_SHA256)
    audit.equal("manual_participant_export_projection_sha", participants["export_projection_sha256"], PARTICIPANT_EXPORT_SHA256)
    audit.equal("manual_participant_actor_projection_sha", participants["actor_reference_projection_sha256"], ACTOR_REFERENCE_SHA256)
    audit.equal("manual_participant_identity_retained", participants["pseudonymization_forbidden"], True)
    audit.equal("manual_participant_aggregation_not_substitute", participants["aggregation_only_publication_forbidden"], True)
    audit.equal("manual_official_ballot_labels_authoritative", participants["official_names_and_ballot_labels_authoritative"], True)
    audit.equal("manual_actor_labels_do_not_replace_official", participants["actor_labels_replace_official_labels"], False)

    _validate_exact_math(candidate, truth, audit)
    _validate_candidate_identity(candidate, audit)

    semantic = candidate["semantic_assessment"]
    geography = candidate["geography_assessment"]
    audit.equal("semantic_status_pending_human_review", semantic["status"], "pending_human_review")
    audit.equal("semantic_decision_null", semantic["decision"], None)
    audit.equal("semantic_target_outcome_match_null", semantic["target_outcome_match"], None)
    audit.equal("semantic_mechanism_verified_null", semantic["mechanism_verified"], None)
    audit.equal("geography_status_pending_human_review", geography["status"], "pending_human_review")
    audit.equal("geography_decision_null", geography["decision"], None)
    audit.equal("geography_match_null", geography["geography_match"], None)

    policy = candidate["claim_policy"]
    audit.equal("claim_policy_real_data_only", policy["real_data_only"], True)
    audit.equal("claim_policy_synthetic_mock_zero", policy["synthetic_or_mock_rows"], 0)
    audit.equal("claim_policy_no_association", policy["statistical_association_claim"], "none")
    audit.equal("claim_policy_no_causality", policy["causal_claim"], "none")
    audit.equal("claim_policy_no_effect", policy["effect_estimate"], "not_computed")
    audit.equal("claim_policy_no_merit_blame", policy["political_merit_or_blame"], "not_assessed")
    audit.equal("claim_policy_no_success_failure", policy["success_or_failure_assessment"], "not_assessed")
    audit.equal("claim_policy_no_corruption", policy["corruption_assessment"], "not_assessed")
    audit.equal("claim_policy_reject_l3_l5", policy["v1_hard_rejected_levels"], ["L3", "L4", "L5"])

    bad_local_strings = [
        text
        for text in _walk_strings(manual)
        if "/Users/" in text or "/home/" in text or text.startswith("file:///")
    ]
    audit.equal("manual_has_no_workstation_paths", bad_local_strings, [])
    bad_secret_strings = [
        text
        for text in _walk_strings(manual)
        if "Authorization: Bearer" in text
        or "BEGIN PRIVATE KEY" in text
        or "cookie_jar" in text.casefold()
    ]
    audit.equal("manual_has_no_secret_or_session_material", bad_secret_strings, [])
    urls = [text for text in _walk_strings(manual) if text.startswith(("http://", "https://"))]
    bad_urls = [
        url
        for url in urls
        if urlparse(url).scheme != "https"
        or urlparse(url).hostname not in {"www.senado.es", "ec.europa.eu"}
    ]
    audit.equal("manual_source_urls_are_real_official_hosts", bad_urls, [])
    return manual


def _strict_json_column(row: dict[str, Any], key: str, *, table: str) -> Any:
    value = row[key]
    if not isinstance(value, str):
        raise ValueError(f"{table}.{key}: expected JSON TEXT")
    return strict_json_loads(value, label=f"{table}.{key}")


def _observation_identity_preimage(
    candidate: dict[str, Any], observation: dict[str, Any]
) -> dict[str, Any]:
    return {
        "identity_contract_version": "outcome_link_observation_ref_identity_v1",
        "outcome_link_version_id": candidate["outcome_link_version_id"],
        "role": observation["role"],
        "exclusion_reason": observation.get("exclusion_reason"),
        "indicator_id": candidate["indicator"]["indicator_id"],
        "indicator_release_id": candidate["indicator"]["indicator_release_id"],
        "indicator_series_version_id": candidate["indicator"]["indicator_series_version_id"],
        "indicator_observation_version_id": observation["indicator_observation_version_id"],
        "indicator_observation_evidence_id": observation["indicator_observation_evidence_id"],
        "period_label": observation["period_label"],
        "period_start": observation["period_start"],
        "period_end": observation["period_end"],
        "value_decimal": observation["value_decimal"],
        "value_text": observation["value_text"],
        "source_status_code": observation["source_status_code"],
        "uncertainty_state": observation["uncertainty_state"],
        "revision_ordinal": observation["revision_ordinal"],
        "revision_state": observation["revision_state"],
        "source_content_sha256": observation["source_content_sha256"],
        "raw_path": observation["raw_path"],
        "value_json_pointer": observation["value_json_pointer"],
        "status_json_pointer": observation["status_json_pointer"],
    }


def _participant_identity_preimage(
    candidate: dict[str, Any], participant: dict[str, Any]
) -> dict[str, Any]:
    return {
        "identity_contract_version": "outcome_link_participant_ref_identity_v1",
        "outcome_link_version_id": candidate["outcome_link_version_id"],
        "action_id": candidate["action"]["action_id"],
        "seat": participant["seat"],
        "official_member_name": participant["official_member_name"],
        "upstream_person_id_text": participant["upstream_person_id"],
        "official_group_code": participant["official_group_code"],
        "official_vote_choice": participant["official_vote_choice"],
        "vote_source_id": participant["vote_source_id"],
        "vote_source_url": participant["vote_source_url"],
        "vote_source_snapshot_date": participant["vote_source_snapshot_date"],
        "vote_source_record_id": participant["vote_source_record_id"],
        "vote_source_record_content_sha256": participant["vote_source_record_content_sha256"],
        "vote_source_locator": participant["vote_source_locator"],
        "actor_graph_release_id": participant["actor_graph_release_id"],
        "actor_id": participant["actor_id"],
        "actor_node_version_id": participant["actor_node_version_id"],
        "actor_canonical_label": participant["actor_canonical_label"],
        "actor_identity_state": participant["actor_identity_state"],
        "actor_provenance_state": participant["actor_provenance_state"],
        "actor_source_record_id": participant["actor_source_record_id"],
        "actor_source_url": participant["actor_source_url"],
        "actor_source_content_sha256": participant["actor_source_content_sha256"],
    }


def _db_participant_projection(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "seat": row["seat"],
        "official_member_name": row["official_member_name"],
        "upstream_person_id": row["upstream_person_id"],
        "official_group_code": row["official_group_code"],
        "official_vote_choice": row["official_vote_choice"],
        "actor_graph_release_id": row["actor_graph_release_id"],
        "actor_id": row["actor_id"],
        "actor_node_version_id": row["actor_node_version_id"],
        "actor_canonical_label": row["actor_canonical_label"],
        "actor_identity_state": row["actor_identity_state"],
        "actor_provenance_state": row["actor_provenance_state"],
        "actor_source_record_id": row["actor_source_record_id"],
        "actor_source_url": row["actor_source_url"],
        "actor_source_content_sha256": row["actor_source_content_sha256"],
        "vote_source_record_id": row["vote_source_record_id"],
        "vote_source_record_content_sha256": row["vote_source_record_content_sha256"],
        "vote_source_locator": row["vote_source_locator"],
        "vote_source_id": row["vote_source_id"],
        "vote_source_url": row["vote_source_url"],
        "vote_source_snapshot_date": row["vote_source_snapshot_date"],
    }


def _evidence_identity_preimage(
    candidate: dict[str, Any],
    *,
    evidence_role: str,
    entity_version_id: str,
    source_id: str,
    source_record_id: str | None,
    official_url: str | None,
    content_sha256: str | None,
    byte_count: int | None,
    raw_path: str | None,
    locator: str | None,
    capture_state: str,
) -> dict[str, Any]:
    return {
        "identity_contract_version": "outcome_link_evidence_identity_v1",
        "outcome_link_version_id": candidate["outcome_link_version_id"],
        "evidence_role": evidence_role,
        "entity_version_id": entity_version_id,
        "source_id": source_id,
        "source_record_id": source_record_id,
        "official_url": official_url,
        "content_sha256": content_sha256,
        "bytes": byte_count,
        "raw_path": raw_path,
        "locator": locator,
        "capture_state": capture_state,
        "normalized_record_is_original_bytes": False,
    }


def _expected_evidence_preimages(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    action = candidate["action"]
    indicator = candidate["indicator"]
    observations = candidate["temporal_assessment"]["selected_observations"]
    selected = [
        observations["pre"],
        *observations["overlap_excluded"],
        observations["post"],
    ]
    output: list[dict[str, Any]] = []
    for observation in selected:
        output.append(
            _evidence_identity_preimage(
                candidate,
                evidence_role=f"indicator_observation_{observation['role']}",
                entity_version_id=observation["indicator_observation_version_id"],
                source_id=indicator["source_id"],
                source_record_id=observation["indicator_observation_evidence_id"],
                official_url=indicator["source_url"],
                content_sha256=observation["source_content_sha256"],
                byte_count=indicator["source_bytes"],
                raw_path=observation["raw_path"],
                locator=observation["value_json_pointer"],
                capture_state="original_source_bytes_present",
            )
        )
    output.extend(
        [
            _evidence_identity_preimage(
                candidate,
                evidence_role="indicator_source_bytes",
                entity_version_id=indicator["indicator_release_id"],
                source_id=indicator["source_id"],
                source_record_id=None,
                official_url=indicator["source_url"],
                content_sha256=indicator["source_content_sha256"],
                byte_count=indicator["source_bytes"],
                raw_path=indicator["raw_path"],
                locator="/",
                capture_state="original_source_bytes_present",
            ),
            _evidence_identity_preimage(
                candidate,
                evidence_role="normalized_initiative_source_record",
                entity_version_id=action["initiative_id"],
                source_id=action["initiative_source_id"],
                source_record_id=action["initiative_source_record_id"],
                official_url=action["official_initiative_url"],
                content_sha256=action["initiative_normalized_source_record_payload_sha256"],
                byte_count=action["initiative_normalized_source_record_payload_bytes"],
                raw_path=None,
                locator=(
                    "source_records[source_id=senado_iniciativas;"
                    "source_record_id=senado:leg14:exp:621/000005;"
                    "source_snapshot_date=2026-02-12]"
                ),
                capture_state="normalized_source_record_present",
            ),
            _evidence_identity_preimage(
                candidate,
                evidence_role="normalized_vote_source_record",
                entity_version_id=action["action_id"],
                source_id=action["source_id"],
                source_record_id=action["source_record_id"],
                official_url=action["official_vote_file_url"],
                content_sha256=action["normalized_source_record_payload_sha256"],
                byte_count=action["normalized_source_record_payload_bytes"],
                raw_path=None,
                locator=(
                    "source_records[source_id=senado_votaciones;"
                    "source_record_id=url:https://www.senado.es/legis14/votaciones/"
                    "ses_17_142.xml;source_snapshot_date=2026-02-12]"
                ),
                capture_state="normalized_source_record_present",
            ),
            _evidence_identity_preimage(
                candidate,
                evidence_role="original_vote_xml_gap",
                entity_version_id=action["action_id"],
                source_id=action["source_id"],
                source_record_id=action["source_record_id"],
                official_url=action["official_vote_file_url"],
                content_sha256=None,
                byte_count=None,
                raw_path=None,
                locator=None,
                capture_state="absent_from_current_snapshot",
            ),
        ]
    )
    return sorted(
        output,
        key=lambda row: (
            row["evidence_role"],
            row["entity_version_id"],
            row["content_sha256"] or "",
            row["locator"] or "",
        ),
    )


def _table_count(connection: sqlite3.Connection, table: str) -> int:
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def _foreign_key_signatures(
    connection: sqlite3.Connection, table: str
) -> set[tuple[str, tuple[tuple[str, str], ...], str, str]]:
    """Return ordered FK groups, preserving composite-column binding."""
    grouped: dict[int, list[sqlite3.Row]] = {}
    for row in connection.execute(f'PRAGMA foreign_key_list("{table}")'):
        grouped.setdefault(int(row["id"]), []).append(row)
    return {
        (
            str(rows[0]["table"]),
            tuple(
                (str(row["from"]), str(row["to"]))
                for row in sorted(rows, key=lambda item: int(item["seq"]))
            ),
            str(rows[0]["on_update"]),
            str(rows[0]["on_delete"]),
        )
        for rows in grouped.values()
    }


def _unique_column_signatures(
    connection: sqlite3.Connection, table: str
) -> set[tuple[str, ...]]:
    signatures: set[tuple[str, ...]] = set()
    for index in connection.execute(f'PRAGMA index_list("{table}")'):
        if int(index["unique"]) != 1:
            continue
        columns = tuple(
            str(row["name"])
            for row in connection.execute(
                f'PRAGMA index_info("{str(index["name"])}")'
            )
        )
        signatures.add(columns)
    return signatures


def _normalized_ddl(value: str) -> str:
    return " ".join(value.casefold().split())


def validate_bundle_database(
    bundle_db: Path,
    manual: dict[str, Any],
    truth: SourceTruth,
    audit: Audit,
) -> dict[str, int]:
    audit.check("bundle_database_exists", bundle_db.is_file())
    if not bundle_db.is_file():
        raise RuntimeError(f"missing outcome-context bundle database: {bundle_db}")
    candidate = manual["candidates"][0]
    connection = open_readonly(bundle_db)
    expected_counts = {
        "outcome_links": 1,
        "outcome_link_versions": 1,
        "outcome_link_reviews": 0,
        "outcome_link_releases": 0,
        "outcome_link_release_memberships": 0,
        "outcome_link_observation_refs": 3,
        "outcome_link_participant_refs": 264,
        "outcome_link_evidence": 7,
        "outcome_link_scope_closures": 4,
    }
    try:
        audit.equal("bundle_database_integrity_check", connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        audit.equal("bundle_database_foreign_key_check", connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        audit.equal("bundle_database_contains_exactly_nine_outcome_tables", table_names, set(expected_counts))
        for table in expected_counts:
            audit.check(f"bundle_table_{table}_exists", table in table_names)
        if not set(expected_counts).issubset(table_names):
            raise RuntimeError("bundle database is missing required outcome-link tables")
        counts = {table: _table_count(connection, table) for table in expected_counts}
        audit.equal("bundle_database_table_counts", counts, expected_counts)
        required_indexes = {
            "idx_outcome_link_versions_link_state",
            "idx_outcome_link_versions_action",
            "idx_outcome_link_versions_indicator",
            "idx_outcome_link_reviews_version_time",
            "idx_outcome_link_memberships_release_state",
            "idx_outcome_link_observation_refs_version_role",
            "idx_outcome_link_participant_refs_action_person",
            "idx_outcome_link_participant_refs_actor",
            "idx_outcome_link_participant_refs_version_seat",
            "idx_outcome_link_evidence_version_role",
            "idx_outcome_link_scope_closures_kind_sha",
        }
        actual_indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        audit.equal("bundle_database_required_scale_indexes", actual_indexes, required_indexes)
        required_fk_signatures = {
            "outcome_link_versions": {
                (
                    "outcome_links",
                    (("outcome_link_id", "outcome_link_id"),),
                    "NO ACTION",
                    "RESTRICT",
                ),
                (
                    "outcome_link_scope_closures",
                    (
                        ("action_scope_sha256", "scope_closure_sha256"),
                        ("action_scope_kind", "scope_kind"),
                    ),
                    "NO ACTION",
                    "RESTRICT",
                ),
                (
                    "outcome_link_scope_closures",
                    (
                        ("indicator_scope_sha256", "scope_closure_sha256"),
                        ("indicator_scope_kind", "scope_kind"),
                    ),
                    "NO ACTION",
                    "RESTRICT",
                ),
                (
                    "outcome_link_scope_closures",
                    (
                        (
                            "actor_reference_scope_sha256",
                            "scope_closure_sha256",
                        ),
                        ("actor_reference_scope_kind", "scope_kind"),
                    ),
                    "NO ACTION",
                    "RESTRICT",
                ),
                (
                    "outcome_link_scope_closures",
                    (
                        ("combined_scope_sha256", "scope_closure_sha256"),
                        ("combined_scope_kind", "scope_kind"),
                    ),
                    "NO ACTION",
                    "RESTRICT",
                ),
            },
            "outcome_link_reviews": {
                (
                    "outcome_link_versions",
                    (("outcome_link_version_id", "outcome_link_version_id"),),
                    "NO ACTION",
                    "RESTRICT",
                ),
                (
                    "outcome_link_reviews",
                    (
                        (
                            "supersedes_review_version_id",
                            "outcome_link_review_version_id",
                        ),
                    ),
                    "NO ACTION",
                    "RESTRICT",
                ),
            },
            "outcome_link_release_memberships": {
                (
                    "outcome_link_releases",
                    (("outcome_link_release_id", "outcome_link_release_id"),),
                    "NO ACTION",
                    "RESTRICT",
                ),
                (
                    "outcome_link_versions",
                    (("outcome_link_version_id", "outcome_link_version_id"),),
                    "NO ACTION",
                    "RESTRICT",
                ),
                (
                    "outcome_link_reviews",
                    (
                        (
                            "outcome_link_review_version_id",
                            "outcome_link_review_version_id",
                        ),
                    ),
                    "NO ACTION",
                    "RESTRICT",
                ),
                (
                    "outcome_link_reviews",
                    (
                        (
                            "outcome_link_review_version_id",
                            "outcome_link_review_version_id",
                        ),
                        ("outcome_link_version_id", "outcome_link_version_id"),
                    ),
                    "NO ACTION",
                    "RESTRICT",
                ),
                (
                    "outcome_link_reviews",
                    (
                        (
                            "outcome_link_review_version_id",
                            "outcome_link_review_version_id",
                        ),
                        ("outcome_link_version_id", "outcome_link_version_id"),
                        ("selected_semantic_decision", "semantic_decision"),
                        ("selected_geography_decision", "geography_decision"),
                        ("selected_level", "level_decision"),
                    ),
                    "NO ACTION",
                    "RESTRICT",
                ),
            },
            "outcome_link_observation_refs": {
                (
                    "outcome_link_versions",
                    (("outcome_link_version_id", "outcome_link_version_id"),),
                    "NO ACTION",
                    "RESTRICT",
                )
            },
            "outcome_link_participant_refs": {
                (
                    "outcome_link_versions",
                    (("outcome_link_version_id", "outcome_link_version_id"),),
                    "NO ACTION",
                    "RESTRICT",
                )
            },
            "outcome_link_evidence": {
                (
                    "outcome_link_versions",
                    (("outcome_link_version_id", "outcome_link_version_id"),),
                    "NO ACTION",
                    "RESTRICT",
                )
            },
        }
        for table, expected_fks in required_fk_signatures.items():
            actual_fks = _foreign_key_signatures(connection, table)
            audit.check(
                f"bundle_database_{table}_required_foreign_keys",
                expected_fks.issubset(actual_fks),
                f"{table}: required FKs {expected_fks!r}; actual {actual_fks!r}",
            )

        review_unique_signatures = _unique_column_signatures(
            connection, "outcome_link_reviews"
        )
        audit.check(
            "bundle_database_review_version_composite_unique_key",
            (
                "outcome_link_review_version_id",
                "outcome_link_version_id",
            )
            in review_unique_signatures,
        )
        audit.check(
            "bundle_database_review_decisions_composite_unique_key",
            (
                "outcome_link_review_version_id",
                "outcome_link_version_id",
                "semantic_decision",
                "geography_decision",
                "level_decision",
            )
            in review_unique_signatures,
        )
        closure_unique_signatures = _unique_column_signatures(
            connection, "outcome_link_scope_closures"
        )
        audit.check(
            "bundle_database_scope_hash_kind_composite_unique_key",
            ("scope_closure_sha256", "scope_kind")
            in closure_unique_signatures,
        )

        trigger_rows = rows_as_dicts(
            connection.execute(
                "SELECT name,tbl_name,sql FROM sqlite_master "
                "WHERE type='trigger' ORDER BY name"
            )
        )
        expected_trigger_names = {
            f"trg_{table}_{suffix}"
            for table in expected_counts
            for suffix in ("no_update", "no_delete")
        }
        audit.equal(
            "bundle_database_exact_append_only_trigger_names",
            {row["name"] for row in trigger_rows},
            expected_trigger_names,
        )
        trigger_by_name = {row["name"]: row for row in trigger_rows}
        for table in expected_counts:
            for event, suffix in (("update", "no_update"), ("delete", "no_delete")):
                name = f"trg_{table}_{suffix}"
                row = trigger_by_name.get(name)
                normalized = _normalized_ddl(row["sql"] or "") if row else ""
                audit.check(
                    f"bundle_database_{table}_append_only_{event}_trigger",
                    row is not None
                    and row["tbl_name"] == table
                    and f"before {event} on {table}" in normalized
                    and f"raise(abort, '{table} is append-only')" in normalized,
                )

        table_ddl = {
            row["name"]: _normalized_ddl(row["sql"] or "")
            for row in connection.execute(
                "SELECT name,sql FROM sqlite_master WHERE type='table'"
            )
        }
        evidence_ddl = table_ddl["outcome_link_evidence"]
        evidence_constraint_fragments = {
            "evidence_role in (",
            "content_sha256 is null or",
            "capture_state in (",
            "normalized_record_is_original_bytes in (0, 1)",
            "normalized_record_is_original_bytes = 0",
            "raw_path is null",
            "raw_path is not null",
            "locator is null",
            "locator is not null",
            "bytes is null",
            "bytes > 0",
            "'normalized_source_record_present'",
            "'original_source_bytes_present'",
            "'absent_from_current_snapshot'",
            *{
                f"'{role}'"
                for role in (
                    "normalized_vote_source_record",
                    "normalized_initiative_source_record",
                    "original_vote_xml_gap",
                    "indicator_source_bytes",
                    "indicator_observation_pre",
                    "indicator_observation_overlap_excluded",
                    "indicator_observation_post",
                )
            },
        }
        audit.equal(
            "bundle_database_evidence_constraints_complete",
            sorted(
                fragment
                for fragment in evidence_constraint_fragments
                if fragment not in evidence_ddl
            ),
            [],
        )
        audit.check(
            "bundle_database_observation_role_exclusion_constraint",
            "role = 'overlap_excluded' and exclusion_reason is not null"
            in table_ddl["outcome_link_observation_refs"]
            and "role in ('pre', 'post') and exclusion_reason is null"
            in table_ddl["outcome_link_observation_refs"],
        )
        audit.check(
            "bundle_database_participant_official_identity_constraints",
            "official_label_authoritative = 1"
            in table_ddl["outcome_link_participant_refs"]
            and "actor_label_mismatch = (official_member_name <> actor_canonical_label)"
            in table_ddl["outcome_link_participant_refs"],
        )
        membership_ddl = table_ddl["outcome_link_release_memberships"]
        audit.check(
            "bundle_database_membership_decision_alias_constraint",
            "selected_decision is selected_semantic_decision" in membership_ddl,
        )
        membership_review_mismatch_count = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM outcome_link_release_memberships AS membership
                LEFT JOIN outcome_link_reviews AS review
                  ON review.outcome_link_review_version_id =
                     membership.outcome_link_review_version_id
                WHERE membership.outcome_link_review_version_id IS NOT NULL
                  AND (
                    review.outcome_link_review_version_id IS NULL
                    OR review.outcome_link_version_id IS NOT
                       membership.outcome_link_version_id
                    OR review.level_decision IS NOT membership.selected_level
                    OR review.semantic_decision IS NOT
                       membership.selected_semantic_decision
                    OR review.geography_decision IS NOT
                       membership.selected_geography_decision
                    OR membership.selected_decision IS NOT
                       review.semantic_decision
                  )
                """
            ).fetchone()[0]
        )
        audit.equal(
            "bundle_database_membership_review_version_decision_mismatches",
            membership_review_mismatch_count,
            0,
        )

        link = dict(connection.execute("SELECT * FROM outcome_links").fetchone())
        link_preimage = _strict_json_column(link, "identity_preimage_json", table="outcome_links")
        audit.equal("bundle_link_id", link["outcome_link_id"], candidate["outcome_link_id"])
        audit.equal(
            "bundle_link_identity_contract_version",
            link["identity_contract_version"],
            "outcome_link_logical_identity_v1",
        )
        audit.equal("bundle_link_created_at", link["created_at"], manual["generated_at"])
        audit.equal("bundle_link_identity_preimage", link_preimage, candidate["identity"]["outcome_link_identity_preimage"])
        link_bytes = canonical_json_bytes(link_preimage)
        audit.equal("bundle_link_identity_bytes", link["identity_canonical_bytes"], len(link_bytes))
        audit.equal("bundle_link_identity_sha", link["identity_sha256"], sha256_bytes(link_bytes))
        audit.equal("bundle_link_id_prefix", link["outcome_link_id"], f"vclc:outcome-link:{link['identity_sha256'][:24]}")
        for key, expected in (
            ("link_kind", candidate["link_kind"]),
            ("action_id", candidate["action"]["action_id"]),
            ("indicator_id", candidate["indicator"]["indicator_id"]),
            ("stable_series_key", candidate["indicator"]["stable_series_key"]),
            ("geography_code", candidate["indicator"]["geography_code"]),
            ("geography_level", candidate["indicator"]["geography_level"]),
            ("geography_system", candidate["indicator"]["geography_system"]),
        ):
            audit.equal(f"bundle_link_{key}", link[key], expected)

        version = dict(connection.execute("SELECT * FROM outcome_link_versions").fetchone())
        version_preimage = _strict_json_column(
            version, "version_identity_preimage_json", table="outcome_link_versions"
        )
        version_bytes = canonical_json_bytes(version_preimage)
        audit.equal("bundle_version_id", version["outcome_link_version_id"], candidate["outcome_link_version_id"])
        audit.equal("bundle_version_link_fk", version["outcome_link_id"], candidate["outcome_link_id"])
        audit.equal("bundle_version_identity_preimage", version_preimage, candidate["identity"]["outcome_link_version_identity_preimage"])
        audit.equal("bundle_version_identity_bytes", version["version_identity_canonical_bytes"], len(version_bytes))
        audit.equal("bundle_version_identity_sha", version["version_identity_sha256"], sha256_bytes(version_bytes))
        audit.equal("bundle_version_id_prefix", version["outcome_link_version_id"], f"vclc:outcome-link-version:{version['version_identity_sha256'][:24]}")
        scalar_version_expectations = {
            "identity_contract_version": "outcome_link_version_identity_v1",
            "method_version": METHOD_VERSION,
            "evidence_package_kind": "real_bounded_outcome_context_candidate_v1",
            "version_state": "preproduction_candidate",
            "evidence_level": "L1",
            "candidate_status": "pending_human_review",
            "machine_audit_state": "machine_validated",
            "human_review_required": 1,
            "human_review_completed": 0,
            "published": 0,
            "directional_countable": 0,
            "ranking_eligible": 0,
            "action_id": ACTION_ID,
            "action_occurred_at": ACTION_DATE,
            "action_source_id": ACTION_SOURCE_ID,
            "action_source_record_id": ACTION_ID,
            "action_source_snapshot_date": ACTION_SNAPSHOT_DATE,
            "action_source_record_content_sha256": VOTE_RECORD_SHA256,
            "initiative_id": INITIATIVE_ID,
            "initiative_source_id": "senado_iniciativas",
            "initiative_source_record_id": INITIATIVE_ID,
            "initiative_source_record_content_sha256": INITIATIVE_RECORD_SHA256,
            "original_vote_xml_capture_state": "absent_from_current_snapshot",
            "original_vote_xml_content_sha256": None,
            "indicator_id": INDICATOR_ID,
            "indicator_release_id": INDICATOR_RELEASE_ID,
            "indicator_series_version_id": INDICATOR_SERIES_VERSION_ID,
            "indicator_source_content_sha256": INDICATOR_SOURCE_SHA256,
            "action_scope_sha256": ACTION_CLOSURE_SHA256,
            "action_scope_kind": "action",
            "indicator_scope_sha256": INDICATOR_CLOSURE_SHA256,
            "indicator_scope_kind": "indicator",
            "actor_reference_scope_sha256": ACTOR_CLOSURE_SHA256,
            "actor_reference_scope_kind": "actor_reference",
            "combined_scope_sha256": COMBINED_CLOSURE_SHA256,
            "combined_scope_kind": "combined",
            "participant_count": 264,
            "participant_source_projection_sha256": PARTICIPANT_SOURCE_SHA256,
            "participant_export_projection_sha256": PARTICIPANT_EXPORT_SHA256,
            "actor_graph_release_id": ACTOR_GRAPH_RELEASE_ID,
            "actor_reference_projection_sha256": ACTOR_REFERENCE_SHA256,
            "actor_reference_label_mismatch_count": 2,
            "supersedes_outcome_link_version_id": None,
            "created_at": manual["generated_at"],
        }
        for key, expected in scalar_version_expectations.items():
            audit.equal(f"bundle_version_{key}", version[key], expected)
        json_version_expectations = {
            "action_json": {
                key: value
                for key, value in candidate["action"].items()
                if key
                not in {
                    "source_record_pk_audit_locator",
                    "initiative_source_record_pk_audit_locator",
                }
            },
            "indicator_json": candidate["indicator"],
            "temporal_assessment_json": candidate["temporal_assessment"],
            "semantic_assessment_json": candidate["semantic_assessment"],
            "geography_assessment_json": candidate["geography_assessment"],
            "calculation_json": candidate["calculation"],
            "claim_policy_json": candidate["claim_policy"],
            "reason_codes_json": candidate["reason_codes"],
            "limitations_json": candidate["limitations"],
            "reader_wording_json": candidate["reader_wording"],
        }
        for column, expected in json_version_expectations.items():
            audit.equal(
                f"bundle_version_{column}_parity",
                _strict_json_column(version, column, table="outcome_link_versions"),
                expected,
            )
        participant_contract = _strict_json_column(
            version, "participant_contract_json", table="outcome_link_versions"
        )
        expected_participant_contract = {
            key: value
            for key, value in candidate["participants"].items()
            if key != "records"
        }
        audit.equal("bundle_version_participant_contract", participant_contract, expected_participant_contract)

        closure_key_by_kind = {
            "action": "action_scope",
            "indicator": "indicator_scope",
            "actor_reference": "actor_reference_scope",
            "combined": "combined_scope",
        }
        closure_rows = rows_as_dicts(
            connection.execute(
                "SELECT * FROM outcome_link_scope_closures ORDER BY scope_kind"
            )
        )
        audit.equal(
            "bundle_closure_kind_to_sha_exact",
            {
                row["scope_kind"]: row["scope_closure_sha256"]
                for row in closure_rows
            },
            {
                "action": ACTION_CLOSURE_SHA256,
                "indicator": INDICATOR_CLOSURE_SHA256,
                "actor_reference": ACTOR_CLOSURE_SHA256,
                "combined": COMBINED_CLOSURE_SHA256,
            },
        )
        for row in closure_rows:
            manual_closure = manual["selection_closure"][closure_key_by_kind[row["scope_kind"]]]
            preimage = _strict_json_column(
                row, "canonical_preimage_json", table="outcome_link_scope_closures"
            )
            audit.equal(
                f"bundle_{row['scope_kind']}_closure_contract_version",
                row["closure_contract_version"],
                manual_closure["preimage"]["closure_contract_version"],
            )
            audit.equal(f"bundle_{row['scope_kind']}_closure_preimage", preimage, manual_closure["preimage"])
            audit.equal(f"bundle_{row['scope_kind']}_closure_bytes", row["canonical_bytes"], len(canonical_json_bytes(preimage)))
            audit.equal(f"bundle_{row['scope_kind']}_closure_sha", row["scope_closure_sha256"], sha256_bytes(canonical_json_bytes(preimage)))
            audit.equal(f"bundle_{row['scope_kind']}_bounded_complete", row["bounded_scope_complete"], 1)
        audit.equal(
            "bundle_closure_all_global_search_flags_false",
            [
                (
                    row["all_possible_actions_searched"],
                    row["all_possible_indicators_searched"],
                    row["all_possible_actor_sources_searched"],
                    row["all_possible_action_indicator_pairs_searched"],
                )
                for row in closure_rows
            ],
            [(0, 0, 0, 0)] * 4,
        )

        observation_rows = rows_as_dicts(
            connection.execute(
                """
                SELECT * FROM outcome_link_observation_refs
                ORDER BY CASE role WHEN 'pre' THEN 0 WHEN 'overlap_excluded' THEN 1 ELSE 2 END,
                         indicator_observation_version_id,
                         indicator_observation_evidence_id
                """
            )
        )
        expected_observations = [
            candidate["temporal_assessment"]["selected_observations"]["pre"],
            *candidate["temporal_assessment"]["selected_observations"]["overlap_excluded"],
            candidate["temporal_assessment"]["selected_observations"]["post"],
        ]
        for index, (row, expected_observation) in enumerate(
            zip(observation_rows, expected_observations, strict=True)
        ):
            expected_preimage = _observation_identity_preimage(candidate, expected_observation)
            preimage = _strict_json_column(
                row, "identity_preimage_json", table="outcome_link_observation_refs"
            )
            identity_sha = sha256_bytes(canonical_json_bytes(preimage))
            audit.equal(f"bundle_observation_{index}_preimage", preimage, expected_preimage)
            audit.equal(
                f"bundle_observation_{index}_identity_contract_version",
                row["identity_contract_version"],
                expected_preimage["identity_contract_version"],
            )
            audit.equal(f"bundle_observation_{index}_identity_sha", row["identity_sha256"], identity_sha)
            audit.equal(
                f"bundle_observation_{index}_id",
                row["outcome_link_observation_ref_id"],
                f"vclc:outcome-link-observation-ref:{identity_sha[:24]}",
            )
            audit.check(
                f"bundle_observation_{index}_id_format",
                OBSERVATION_REF_ID_RE.fullmatch(row["outcome_link_observation_ref_id"])
                is not None,
            )
            for key, expected in expected_preimage.items():
                if key in {
                    "identity_contract_version",
                    "outcome_link_version_id",
                }:
                    continue
                audit.equal(f"bundle_observation_{index}_{key}", row[key], expected)
            audit.check(f"bundle_observation_{index}_raw_path_relative", assert_repo_relative(row["raw_path"]))
            audit.equal(
                f"bundle_observation_{index}_raw_pointer",
                str(json_pointer_get(truth.indicator_raw_document, row["value_json_pointer"])),
                row["value_decimal"],
            )

        participant_rows = rows_as_dicts(
            connection.execute(
                """
                SELECT * FROM outcome_link_participant_refs
                ORDER BY action_id, CAST(seat AS INTEGER), seat,
                         official_member_name, upstream_person_id,
                         outcome_link_participant_ref_id
                """
            )
        )
        participant_projection = [_db_participant_projection(row) for row in participant_rows]
        audit.equal("bundle_participant_projection_source_parity", participant_projection, truth.participant_export_rows)
        audit.equal(
            "bundle_participant_projection_digest",
            sha256_bytes(canonical_json_bytes(participant_projection)),
            PARTICIPANT_EXPORT_SHA256,
        )
        raw_indices: list[int] = []
        for index, (row, expected_participant) in enumerate(
            zip(participant_rows, truth.participant_export_rows, strict=True)
        ):
            expected_preimage = _participant_identity_preimage(candidate, expected_participant)
            preimage = _strict_json_column(
                row, "identity_preimage_json", table="outcome_link_participant_refs"
            )
            identity_sha = sha256_bytes(canonical_json_bytes(preimage))
            audit.equal(f"bundle_participant_{index}_preimage", preimage, expected_preimage)
            audit.equal(
                f"bundle_participant_{index}_identity_contract_version",
                row["identity_contract_version"],
                expected_preimage["identity_contract_version"],
            )
            audit.equal(f"bundle_participant_{index}_semantic_sha", row["participant_row_semantic_sha256"], identity_sha)
            audit.equal(
                f"bundle_participant_{index}_id",
                row["outcome_link_participant_ref_id"],
                f"vclc:outcome-link-participant-ref:{identity_sha[:24]}",
            )
            audit.check(
                f"bundle_participant_{index}_id_format",
                PARTICIPANT_REF_ID_RE.fullmatch(row["outcome_link_participant_ref_id"])
                is not None,
            )
            audit.equal(f"bundle_participant_{index}_official_authoritative", row["official_label_authoritative"], 1)
            audit.equal(
                f"bundle_participant_{index}_actor_mismatch",
                row["actor_label_mismatch"],
                int(row["official_member_name"] != row["actor_canonical_label"]),
            )
            raw_vote = json_pointer_get(
                truth.vote_source_record["raw_document"], row["vote_source_locator"]
            )
            audit.equal(
                f"bundle_participant_{index}_raw_locator_exact",
                raw_vote,
                {
                    "group": row["official_group_code"],
                    "member_name": row["official_member_name"],
                    "seat": row["seat"],
                    "vote_choice": row["official_vote_choice"],
                },
            )
            raw_indices.append(int(row["vote_source_locator"].rsplit("/", 1)[1]))
        audit.equal("bundle_participant_raw_locator_bijection", sorted(raw_indices), list(range(264)))
        audit.equal("bundle_participant_public_name_count", len({row["official_member_name"] for row in participant_rows}), 264)
        audit.equal("bundle_participant_public_names_missing", sum(not row["official_member_name"] for row in participant_rows), 0)

        evidence_rows = rows_as_dicts(
            connection.execute(
                """
                SELECT * FROM outcome_link_evidence
                ORDER BY evidence_role, entity_version_id,
                         COALESCE(content_sha256, ''), COALESCE(locator, ''),
                         outcome_link_evidence_id
                """
            )
        )
        expected_evidence_preimages = _expected_evidence_preimages(candidate)
        audit.equal(
            "bundle_evidence_role_counts",
            dict(Counter(row["evidence_role"] for row in evidence_rows)),
            {
                "indicator_observation_post": 1,
                "indicator_observation_pre": 1,
                "indicator_observation_overlap_excluded": 1,
                "indicator_source_bytes": 1,
                "normalized_initiative_source_record": 1,
                "normalized_vote_source_record": 1,
                "original_vote_xml_gap": 1,
            },
        )
        for index, (row, expected_preimage) in enumerate(
            zip(evidence_rows, expected_evidence_preimages, strict=True)
        ):
            preimage = _strict_json_column(
                row, "identity_preimage_json", table="outcome_link_evidence"
            )
            identity_sha = sha256_bytes(canonical_json_bytes(preimage))
            audit.equal(f"bundle_evidence_{index}_preimage", preimage, expected_preimage)
            audit.equal(
                f"bundle_evidence_{index}_identity_contract_version",
                row["identity_contract_version"],
                expected_preimage["identity_contract_version"],
            )
            audit.equal(f"bundle_evidence_{index}_identity_sha", row["identity_sha256"], identity_sha)
            audit.equal(
                f"bundle_evidence_{index}_id",
                row["outcome_link_evidence_id"],
                f"vclc:outcome-link-evidence:{identity_sha[:24]}",
            )
            audit.check(
                f"bundle_evidence_{index}_id_format",
                EVIDENCE_ID_RE.fullmatch(row["outcome_link_evidence_id"]) is not None,
            )
            audit.equal(f"bundle_evidence_{index}_preimage_version", preimage["outcome_link_version_id"], LINK_VERSION_ID)
            for key in (
                "evidence_role",
                "entity_version_id",
                "source_id",
                "source_record_id",
                "official_url",
                "content_sha256",
                "bytes",
                "raw_path",
                "locator",
                "capture_state",
            ):
                audit.equal(f"bundle_evidence_{index}_{key}_preimage_parity", row[key], preimage[key])
            audit.equal(
                f"bundle_evidence_{index}_normalized_original_flag",
                row["normalized_record_is_original_bytes"],
                int(preimage["normalized_record_is_original_bytes"]),
            )
            audit.check(f"bundle_evidence_{index}_raw_path_relative", assert_repo_relative(row["raw_path"]))
        xml_gaps = [row for row in evidence_rows if row["evidence_role"] == "original_vote_xml_gap"]
        audit.equal("bundle_original_xml_gap_count", len(xml_gaps), 1)
        if xml_gaps:
            gap = xml_gaps[0]
            audit.equal("bundle_original_xml_gap_hash_null", gap["content_sha256"], None)
            audit.equal("bundle_original_xml_gap_bytes_null", gap["bytes"], None)
            audit.equal("bundle_original_xml_gap_state", gap["capture_state"], "absent_from_current_snapshot")
            audit.equal("bundle_original_xml_not_normalized_record", gap["normalized_record_is_original_bytes"], 0)
        normalized_votes = [row for row in evidence_rows if row["evidence_role"] == "normalized_vote_source_record"]
        normalized_initiatives = [row for row in evidence_rows if row["evidence_role"] == "normalized_initiative_source_record"]
        indicator_sources = [row for row in evidence_rows if row["evidence_role"] == "indicator_source_bytes"]
        if normalized_votes:
            audit.equal("bundle_vote_evidence_sha", normalized_votes[0]["content_sha256"], VOTE_RECORD_SHA256)
            audit.equal("bundle_vote_evidence_bytes", normalized_votes[0]["bytes"], 39_854)
        if normalized_initiatives:
            audit.equal("bundle_initiative_evidence_sha", normalized_initiatives[0]["content_sha256"], INITIATIVE_RECORD_SHA256)
            audit.equal("bundle_initiative_evidence_bytes", normalized_initiatives[0]["bytes"], 9_301)
        if indicator_sources:
            audit.equal("bundle_indicator_evidence_sha", indicator_sources[0]["content_sha256"], INDICATOR_SOURCE_SHA256)
            audit.equal("bundle_indicator_evidence_bytes", indicator_sources[0]["bytes"], 4_763_587)

        audit.check(
            "bundle_identity_preimages_exclude_physical_database_hashes",
            not nested_physical_database_identity_key(
                [
                    link_preimage,
                    version_preimage,
                    *[
                        _strict_json_column(row, "canonical_preimage_json", table="outcome_link_scope_closures")
                        for row in closure_rows
                    ],
                    *[
                        _strict_json_column(
                            row,
                            "identity_preimage_json",
                            table="outcome_link_observation_refs",
                        )
                        for row in observation_rows
                    ],
                    *[
                        _strict_json_column(
                            row,
                            "identity_preimage_json",
                            table="outcome_link_participant_refs",
                        )
                        for row in participant_rows
                    ],
                    *[
                        _strict_json_column(
                            row,
                            "identity_preimage_json",
                            table="outcome_link_evidence",
                        )
                        for row in evidence_rows
                    ],
                ]
            ),
        )
        return counts
    finally:
        connection.close()


def _semantic_projection_from_database(bundle_db: Path) -> dict[str, list[dict[str, Any]]]:
    """Reconstruct every semantic JSON array from the SQLite artifact."""
    connection = open_readonly(bundle_db)
    try:
        links: list[dict[str, Any]] = []
        for sqlite_row in connection.execute(
            "SELECT * FROM outcome_links ORDER BY outcome_link_id"
        ):
            row = dict(sqlite_row)
            links.append(
                {
                    "outcome_link_id": row["outcome_link_id"],
                    "identity_contract_version": row["identity_contract_version"],
                    "link_kind": row["link_kind"],
                    "action_id": row["action_id"],
                    "indicator_id": row["indicator_id"],
                    "stable_series_key": row["stable_series_key"],
                    "geography_code": row["geography_code"],
                    "geography_level": row["geography_level"],
                    "geography_system": row["geography_system"],
                    "identity_sha256": row["identity_sha256"],
                    "identity_canonical_bytes": row["identity_canonical_bytes"],
                    "identity_preimage": _strict_json_column(
                        row, "identity_preimage_json", table="outcome_links"
                    ),
                }
            )

        versions: list[dict[str, Any]] = []
        for sqlite_row in connection.execute(
            "SELECT * FROM outcome_link_versions ORDER BY outcome_link_version_id"
        ):
            row = dict(sqlite_row)
            versions.append(
                {
                    "outcome_link_version_id": row["outcome_link_version_id"],
                    "outcome_link_id": row["outcome_link_id"],
                    "version_identity_sha256": row["version_identity_sha256"],
                    "version_identity_canonical_bytes": row[
                        "version_identity_canonical_bytes"
                    ],
                    "identity_contract_version": row["identity_contract_version"],
                    "method_version": row["method_version"],
                    "evidence_package_kind": row["evidence_package_kind"],
                    "version_state": row["version_state"],
                    "evidence_level": row["evidence_level"],
                    "candidate_status": row["candidate_status"],
                    "machine_audit_state": row["machine_audit_state"],
                    "human_review_required": bool(row["human_review_required"]),
                    "human_review_completed": bool(row["human_review_completed"]),
                    "published": bool(row["published"]),
                    "directional_countable": bool(row["directional_countable"]),
                    "ranking_eligible": bool(row["ranking_eligible"]),
                    "action_scope_sha256": row["action_scope_sha256"],
                    "action_scope_kind": row["action_scope_kind"],
                    "indicator_scope_sha256": row["indicator_scope_sha256"],
                    "indicator_scope_kind": row["indicator_scope_kind"],
                    "actor_reference_scope_sha256": row[
                        "actor_reference_scope_sha256"
                    ],
                    "actor_reference_scope_kind": row[
                        "actor_reference_scope_kind"
                    ],
                    "combined_scope_sha256": row["combined_scope_sha256"],
                    "combined_scope_kind": row["combined_scope_kind"],
                    "participant_count": row["participant_count"],
                    "version_identity_preimage": _strict_json_column(
                        row,
                        "version_identity_preimage_json",
                        table="outcome_link_versions",
                    ),
                    "action": _strict_json_column(
                        row, "action_json", table="outcome_link_versions"
                    ),
                    "participant_contract": _strict_json_column(
                        row,
                        "participant_contract_json",
                        table="outcome_link_versions",
                    ),
                    "indicator": _strict_json_column(
                        row, "indicator_json", table="outcome_link_versions"
                    ),
                    "temporal_assessment": _strict_json_column(
                        row,
                        "temporal_assessment_json",
                        table="outcome_link_versions",
                    ),
                    "semantic_assessment": _strict_json_column(
                        row,
                        "semantic_assessment_json",
                        table="outcome_link_versions",
                    ),
                    "geography_assessment": _strict_json_column(
                        row,
                        "geography_assessment_json",
                        table="outcome_link_versions",
                    ),
                    "calculation": _strict_json_column(
                        row, "calculation_json", table="outcome_link_versions"
                    ),
                    "claim_policy": _strict_json_column(
                        row, "claim_policy_json", table="outcome_link_versions"
                    ),
                    "reason_codes": _strict_json_column(
                        row, "reason_codes_json", table="outcome_link_versions"
                    ),
                    "limitations": _strict_json_column(
                        row, "limitations_json", table="outcome_link_versions"
                    ),
                    "reader_wording": _strict_json_column(
                        row, "reader_wording_json", table="outcome_link_versions"
                    ),
                    "supersedes_outcome_link_version_id": row[
                        "supersedes_outcome_link_version_id"
                    ],
                }
            )

        observation_refs: list[dict[str, Any]] = []
        for sqlite_row in connection.execute(
            """
            SELECT * FROM outcome_link_observation_refs
            ORDER BY CASE role WHEN 'pre' THEN 0 WHEN 'overlap_excluded' THEN 1 ELSE 2 END,
                     indicator_observation_version_id,
                     indicator_observation_evidence_id
            """
        ):
            row = dict(sqlite_row)
            observation_refs.append(
                {
                    key: (
                        _strict_json_column(
                            row,
                            "identity_preimage_json",
                            table="outcome_link_observation_refs",
                        )
                        if key == "identity_preimage"
                        else row[key]
                    )
                    for key in (
                        "outcome_link_observation_ref_id",
                        "outcome_link_version_id",
                        "identity_sha256",
                        "identity_contract_version",
                        "role",
                        "exclusion_reason",
                        "indicator_id",
                        "indicator_release_id",
                        "indicator_series_version_id",
                        "indicator_observation_version_id",
                        "indicator_observation_evidence_id",
                        "period_label",
                        "period_start",
                        "period_end",
                        "value_decimal",
                        "value_text",
                        "source_status_code",
                        "uncertainty_state",
                        "revision_ordinal",
                        "revision_state",
                        "source_content_sha256",
                        "raw_path",
                        "value_json_pointer",
                        "status_json_pointer",
                        "identity_preimage",
                    )
                }
            )

        participant_refs: list[dict[str, Any]] = []
        for sqlite_row in connection.execute(
            """
            SELECT * FROM outcome_link_participant_refs
            ORDER BY action_id, CAST(seat AS INTEGER), seat, official_member_name,
                     upstream_person_id, outcome_link_participant_ref_id
            """
        ):
            row = dict(sqlite_row)
            item = {
                key: row[key]
                for key in (
                    "outcome_link_participant_ref_id",
                    "outcome_link_version_id",
                    "participant_row_semantic_sha256",
                    "identity_contract_version",
                    "action_id",
                    "seat",
                    "official_member_name",
                    "upstream_person_id",
                    "official_group_code",
                    "official_vote_choice",
                    "actor_graph_release_id",
                    "actor_id",
                    "actor_node_version_id",
                    "actor_canonical_label",
                    "actor_identity_state",
                    "actor_provenance_state",
                    "actor_source_record_id",
                    "actor_source_url",
                    "actor_source_content_sha256",
                    "vote_source_id",
                    "vote_source_url",
                    "vote_source_snapshot_date",
                    "vote_source_record_id",
                    "vote_source_record_content_sha256",
                    "vote_source_locator",
                )
            }
            item["official_label_authoritative"] = bool(
                row["official_label_authoritative"]
            )
            item["actor_label_mismatch"] = bool(row["actor_label_mismatch"])
            item["identity_preimage"] = _strict_json_column(
                row,
                "identity_preimage_json",
                table="outcome_link_participant_refs",
            )
            participant_refs.append(item)

        evidence: list[dict[str, Any]] = []
        for sqlite_row in connection.execute(
            """
            SELECT * FROM outcome_link_evidence
            ORDER BY evidence_role, entity_version_id, COALESCE(content_sha256, ''),
                     COALESCE(locator, ''), outcome_link_evidence_id
            """
        ):
            row = dict(sqlite_row)
            item = {
                key: row[key]
                for key in (
                    "outcome_link_evidence_id",
                    "outcome_link_version_id",
                    "identity_sha256",
                    "identity_contract_version",
                    "evidence_role",
                    "entity_version_id",
                    "source_id",
                    "source_record_id",
                    "official_url",
                    "content_sha256",
                    "bytes",
                    "raw_path",
                    "locator",
                    "capture_state",
                )
            }
            item["normalized_record_is_original_bytes"] = bool(
                row["normalized_record_is_original_bytes"]
            )
            item["identity_preimage"] = _strict_json_column(
                row, "identity_preimage_json", table="outcome_link_evidence"
            )
            evidence.append(item)

        closures: list[dict[str, Any]] = []
        for sqlite_row in connection.execute(
            """
            SELECT * FROM outcome_link_scope_closures
            ORDER BY CASE scope_kind
              WHEN 'action' THEN 0
              WHEN 'indicator' THEN 1
              WHEN 'actor_reference' THEN 2
              WHEN 'combined' THEN 3
              ELSE 4 END
            """
        ):
            row = dict(sqlite_row)
            closures.append(
                {
                    "scope_closure_sha256": row["scope_closure_sha256"],
                    "scope_kind": row["scope_kind"],
                    "closure_contract_version": row["closure_contract_version"],
                    "canonical_preimage": _strict_json_column(
                        row,
                        "canonical_preimage_json",
                        table="outcome_link_scope_closures",
                    ),
                    "canonical_bytes": row["canonical_bytes"],
                    "bounded_scope_complete": bool(row["bounded_scope_complete"]),
                    "all_possible_actions_searched": bool(
                        row["all_possible_actions_searched"]
                    ),
                    "all_possible_indicators_searched": bool(
                        row["all_possible_indicators_searched"]
                    ),
                    "all_possible_actor_sources_searched": bool(
                        row["all_possible_actor_sources_searched"]
                    ),
                    "all_possible_action_indicator_pairs_searched": bool(
                        row["all_possible_action_indicator_pairs_searched"]
                    ),
                }
            )
        return {
            "links": links,
            "link_versions": versions,
            "reviews": [],
            "releases": [],
            "release_memberships": [],
            "observation_refs": observation_refs,
            "participant_refs": participant_refs,
            "evidence": evidence,
            "scope_closures": closures,
        }
    finally:
        connection.close()


def _outcome_schema_ddl(schema_path: Path) -> str:
    text = schema_path.read_text(encoding="utf-8")
    begin = "-- BEGIN OUTCOME LINKING V1 SCHEMA"
    end = "-- END OUTCOME LINKING V1 SCHEMA"
    if text.count(begin) != 1 or text.count(end) != 1:
        raise RuntimeError("outcome schema markers must each occur exactly once")
    start = text.index(begin) + len(begin)
    stop = text.index(end, start)
    ddl = text[start:stop].strip()
    if ddl.count("CREATE TABLE IF NOT EXISTS outcome_") != 9:
        raise RuntimeError("outcome schema marker block must contain exactly nine tables")
    return ddl


def _semantic_counts() -> dict[str, int]:
    return {
        "scope_closures": 4,
        "links": 1,
        "link_versions": 1,
        "observation_refs": 3,
        "participant_refs": 264,
        "evidence": 7,
        "reviews": 0,
        "releases": 0,
        "release_memberships": 0,
        "human_reviewed_pairs": 0,
        "published_links": 0,
        "synthetic_or_mock_rows": 0,
    }


def validate_pointer_manifest_and_semantic_artifact(
    *,
    bundle_root: Path,
    schema_path: Path,
    manual: dict[str, Any],
    audit: Audit,
) -> tuple[Path, Path, Path, Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    canonical_bundle = bundle_root.resolve() == DEFAULT_BUNDLE_DIR.resolve()
    latest_path = bundle_root / "latest.json"
    audit.check("bundle_latest_pointer_exists", latest_path.is_file())
    if not latest_path.is_file():
        raise RuntimeError(f"missing bundle pointer: {latest_path}")
    pointer = strict_json_file(latest_path)
    if not isinstance(pointer, dict):
        raise RuntimeError("bundle latest pointer must be a JSON object")
    audit.equal(
        "bundle_pointer_keys",
        set(pointer),
        {
            "format_version",
            "generated_at",
            "candidate_version_id",
            "candidate_version_identity_sha256",
            "bundle_semantic_sha256",
            "artifact_set_sha256",
            "immutable_bundle_path",
            "manifest_sha256",
            "publication_state",
        },
    )
    pointer_expectations = {
        "format_version": "outcome_context_candidate_pointer_v1",
        "generated_at": "2026-08-20T00:00:00Z",
        "candidate_version_id": LINK_VERSION_ID,
        "candidate_version_identity_sha256": LINK_VERSION_IDENTITY_SHA256,
        "bundle_semantic_sha256": BUNDLE_SEMANTIC_SHA256,
        "publication_state": "not_released",
    }
    for key, expected in pointer_expectations.items():
        audit.equal(f"bundle_pointer_{key}", pointer[key], expected)
    audit.check("bundle_pointer_manifest_sha_format", HEX64_RE.fullmatch(pointer["manifest_sha256"]) is not None)
    audit.check("bundle_pointer_artifact_set_sha_format", HEX64_RE.fullmatch(pointer["artifact_set_sha256"]) is not None)
    audit.check("bundle_pointer_semantic_sha_format", HEX64_RE.fullmatch(pointer["bundle_semantic_sha256"]) is not None)
    if canonical_bundle:
        audit.equal(
            "canonical_bundle_pointer_artifact_set_sha",
            pointer["artifact_set_sha256"],
            ARTIFACT_SET_SHA256,
        )
        audit.equal(
            "canonical_bundle_pointer_manifest_sha",
            pointer["manifest_sha256"],
            BUNDLE_MANIFEST_SHA256,
        )

    immutable_relative = Path(pointer["immutable_bundle_path"])
    audit.check(
        "bundle_pointer_path_is_relative_and_canonical",
        not immutable_relative.is_absolute()
        and ".." not in immutable_relative.parts
        and "." not in immutable_relative.parts
        and immutable_relative.as_posix() == pointer["immutable_bundle_path"],
    )
    immutable_dir = (bundle_root / immutable_relative).resolve()
    try:
        immutable_dir.relative_to(bundle_root.resolve())
        inside_root = True
    except ValueError:
        inside_root = False
    audit.check("bundle_pointer_path_cannot_escape_root", inside_root)
    expected_relative = (
        f"versions/{LINK_VERSION_IDENTITY_SHA256}/{pointer['artifact_set_sha256']}"
    )
    audit.equal("bundle_pointer_immutable_path_exact", pointer["immutable_bundle_path"], expected_relative)
    audit.check("bundle_pointer_immutable_directory_exists", immutable_dir.is_dir())
    if not inside_root or not immutable_dir.is_dir():
        raise RuntimeError("latest pointer does not resolve to an immutable bundle directory")
    audit.equal("bundle_version_directory_matches_semantic_version", immutable_dir.parent.name, pointer["candidate_version_identity_sha256"])
    audit.equal("bundle_artifact_directory_matches_artifact_set", immutable_dir.name, pointer["artifact_set_sha256"])

    manifest_path = immutable_dir / "manifest.json"
    audit.check("bundle_manifest_exists", manifest_path.is_file())
    if not manifest_path.is_file():
        raise RuntimeError("immutable bundle manifest is missing")
    audit.equal("bundle_manifest_pointer_sha", sha256_file(manifest_path), pointer["manifest_sha256"])
    if canonical_bundle:
        audit.equal(
            "canonical_bundle_manifest_sha",
            sha256_file(manifest_path),
            BUNDLE_MANIFEST_SHA256,
        )
    manifest = strict_json_file(manifest_path)
    if not isinstance(manifest, dict):
        raise RuntimeError("bundle manifest must be a JSON object")
    audit.equal(
        "bundle_manifest_keys",
        set(manifest),
        {
            "format_version",
            "method_version",
            "generated_at",
            "artifact_role",
            "candidate_version_id",
            "candidate_version_identity_sha256",
            "bundle_semantic_identity_contract_version",
            "bundle_semantic_sha256",
            "artifact_set_sha256",
            "artifact_set_descriptor",
            "combined_scope_sha256",
            "counts",
            "artifacts",
            "physical_artifact_facts_are_semantic_identity_inputs",
            "human_review_completed",
            "release_created",
            "published",
        },
    )
    manifest_expectations = {
        "format_version": "outcome_context_candidate_bundle_manifest_v1",
        "method_version": METHOD_VERSION,
        "generated_at": "2026-08-20T00:00:00Z",
        "artifact_role": "internal_preproduction_candidate_bundle_not_a_release",
        "candidate_version_id": LINK_VERSION_ID,
        "candidate_version_identity_sha256": LINK_VERSION_IDENTITY_SHA256,
        "bundle_semantic_identity_contract_version": (
            "outcome_context_bundle_semantic_identity_v1"
        ),
        "bundle_semantic_sha256": BUNDLE_SEMANTIC_SHA256,
        "artifact_set_sha256": pointer["artifact_set_sha256"],
        "combined_scope_sha256": COMBINED_CLOSURE_SHA256,
        "physical_artifact_facts_are_semantic_identity_inputs": False,
        "human_review_completed": False,
        "release_created": False,
        "published": False,
    }
    for key, expected in manifest_expectations.items():
        audit.equal(f"bundle_manifest_{key}", manifest[key], expected)
    audit.equal("bundle_manifest_counts", manifest["counts"], _semantic_counts())

    artifacts = manifest["artifacts"]
    audit.equal("bundle_manifest_artifact_kinds", set(artifacts), {"database", "semantic_json"})
    db_path = immutable_dir / artifacts["database"]["path"]
    semantic_json_path = immutable_dir / artifacts["semantic_json"]["path"]
    audit.equal("bundle_database_artifact_basename", artifacts["database"]["path"], "outcome-context-candidates-v1.db")
    audit.equal("bundle_json_artifact_basename", artifacts["semantic_json"]["path"], "outcome-context-candidates-v1.json")
    for kind, path in (("database", db_path), ("semantic_json", semantic_json_path)):
        audit.check(f"bundle_{kind}_artifact_inside_immutable_dir", path.resolve().parent == immutable_dir)
        audit.check(f"bundle_{kind}_artifact_exists", path.is_file())
        if not path.is_file():
            raise RuntimeError(f"manifest artifact is missing: {kind}")
        audit.equal(f"bundle_{kind}_artifact_bytes", path.stat().st_size, artifacts[kind]["bytes"])
        audit.equal(f"bundle_{kind}_artifact_sha", sha256_file(path), artifacts[kind]["sha256"])
    if canonical_bundle:
        audit.equal(
            "canonical_bundle_database_sha",
            artifacts["database"]["sha256"],
            BUNDLE_DATABASE_SHA256,
        )
        audit.equal(
            "canonical_bundle_semantic_json_sha",
            artifacts["semantic_json"]["sha256"],
            BUNDLE_JSON_SHA256,
        )

    semantic_raw = semantic_json_path.read_bytes()
    audit.check("bundle_semantic_json_has_single_final_lf", semantic_raw.endswith(b"\n") and not semantic_raw.endswith(b"\n\n"))
    semantic = strict_json_loads(semantic_raw.decode("utf-8"), label=semantic_json_path.as_posix())
    audit.equal("bundle_semantic_json_canonical_bytes", semantic_raw, canonical_json_bytes(semantic) + b"\n")
    semantic_identity_preimage = bundle_semantic_identity_preimage(semantic)
    bundle_semantic_sha = sha256_bytes(
        canonical_json_bytes(semantic_identity_preimage)
    )
    audit.check(
        "bundle_semantic_identity_excludes_generated_at",
        "generated_at" not in semantic_identity_preimage,
    )
    audit.check(
        "bundle_semantic_identity_excludes_runtime_artifact_metadata",
        not {
            "format_version",
            "generated_at_identity_authority",
            "artifact_role",
        }.intersection(semantic_identity_preimage),
    )
    audit.equal("bundle_semantic_json_sha", bundle_semantic_sha, pointer["bundle_semantic_sha256"])
    audit.equal("bundle_semantic_json_sha_manifest", bundle_semantic_sha, manifest["bundle_semantic_sha256"])

    ddl = _outcome_schema_ddl(schema_path)
    ddl_sha = sha256_bytes(ddl.encode("utf-8"))
    audit.equal("bundle_outcome_schema_ddl_sha", ddl_sha, OUTCOME_SCHEMA_DDL_SHA256)
    artifact_set_descriptor = manifest["artifact_set_descriptor"]
    expected_descriptor = {
        "identity_contract_version": "outcome_context_artifact_set_identity_v1",
        "schema_version": "outcome_context_candidate_bundle_v1",
        "method_version": METHOD_VERSION,
        "outcome_schema_ddl_sha256": ddl_sha,
        "candidate_version_identity_sha256": LINK_VERSION_IDENTITY_SHA256,
        "bundle_semantic_identity_contract_version": (
            "outcome_context_bundle_semantic_identity_v1"
        ),
        "bundle_semantic_sha256": bundle_semantic_sha,
        "artifacts": [
            {
                "artifact_kind": artifact_kind,
                "bytes": artifacts[artifact_kind]["bytes"],
                "sha256": artifacts[artifact_kind]["sha256"],
            }
            for artifact_kind in sorted(artifacts)
        ],
    }
    audit.equal("bundle_artifact_set_descriptor_exact", artifact_set_descriptor, expected_descriptor)
    artifact_set_sha = sha256_bytes(canonical_json_bytes(artifact_set_descriptor))
    audit.equal("bundle_artifact_set_sha_recomputed", artifact_set_sha, manifest["artifact_set_sha256"])
    audit.equal("bundle_artifact_set_sha_pointer", artifact_set_sha, pointer["artifact_set_sha256"])

    semantic_expectations = {
        "format_version": "outcome_context_candidate_bundle_v1",
        "method_version": METHOD_VERSION,
        "generated_at": "2026-08-20T00:00:00Z",
        "generated_at_identity_authority": False,
        "artifact_role": "internal_preproduction_candidate_bundle_not_a_release",
        "scope_truth": manual["scope_truth"],
        "policy": manual["policy"],
        "counts": _semantic_counts(),
    }
    for key, expected in semantic_expectations.items():
        audit.equal(f"bundle_semantic_{key}", semantic[key], expected)
    projection = _semantic_projection_from_database(db_path)
    for key, expected in projection.items():
        audit.equal(f"bundle_semantic_database_parity_{key}", semantic[key], expected)

    audit.check(
        "bundle_semantic_has_no_physical_database_identity_facts",
        not nested_physical_database_identity_key(semantic),
    )
    bad_local_strings = [
        text
        for text in _walk_strings(semantic)
        if "/Users/" in text or "/home/" in text or text.startswith("file:///")
    ]
    audit.equal("bundle_semantic_has_no_workstation_paths", bad_local_strings, [])
    bad_secret_strings = [
        text
        for text in _walk_strings(semantic)
        if "Authorization: Bearer" in text
        or "BEGIN PRIVATE KEY" in text
        or "cookie_jar" in text.casefold()
    ]
    audit.equal("bundle_semantic_has_no_secret_or_session_material", bad_secret_strings, [])
    audit.equal(
        "bundle_semantic_retains_all_official_names",
        len({row["official_member_name"] for row in semantic["participant_refs"]}),
        264,
    )
    audit.equal(
        "bundle_semantic_retains_all_ballot_occurrences",
        len(semantic["participant_refs"]),
        264,
    )
    return (
        latest_path,
        manifest_path,
        db_path,
        semantic_json_path,
        pointer,
        manifest,
        semantic,
    )


def validate_materialization_report(
    *,
    args: argparse.Namespace,
    truth: SourceTruth,
    latest_path: Path,
    manifest_path: Path,
    bundle_db: Path,
    bundle_json: Path,
    pointer: dict[str, Any],
    database_counts: dict[str, int],
    audit: Audit,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Validate producer execution evidence without trusting producer code."""
    path = args.materialization_report
    audit.check("materialization_report_exists", path.is_file())
    if not path.is_file():
        raise RuntimeError(f"missing materialization report: {reported_path(path)}")
    materialization = strict_json_file(path)
    if not isinstance(materialization, dict):
        raise RuntimeError("materialization report must be one JSON object")
    audit.equal(
        "materialization_report_top_level_keys",
        set(materialization),
        {
            "schema_version",
            "method_version",
            "status",
            "generated_at",
            "truth",
            "semantic",
            "source_replay",
            "database",
            "inputs",
            "outputs",
            "promotion",
            "scale",
            "execution",
        },
    )
    audit.equal(
        "materialization_report_schema_version",
        materialization["schema_version"],
        "outcome_context_materialization_report_v1",
    )
    audit.equal(
        "materialization_report_method_version",
        materialization["method_version"],
        METHOD_VERSION,
    )
    audit.equal("materialization_report_status", materialization["status"], "passed")
    audit.equal(
        "materialization_report_generated_at",
        materialization["generated_at"],
        "2026-08-20T00:00:00Z",
    )
    expected_truth = {
        "scale_stage": "C0",
        "evidence_level": "L1",
        "candidate_status": "pending_human_review",
        "human_reviews": 0,
        "releases": 0,
        "release_memberships": 0,
        "publications": 0,
        "synthetic_or_mock_rows": 0,
        "official_public_names_retained": 264,
    }
    audit.equal(
        "materialization_report_truth_exact",
        materialization["truth"],
        expected_truth,
    )
    expected_evidence_roles = [
        "indicator_observation_overlap_excluded",
        "indicator_observation_post",
        "indicator_observation_pre",
        "indicator_source_bytes",
        "normalized_initiative_source_record",
        "normalized_vote_source_record",
        "original_vote_xml_gap",
    ]
    expected_semantic = {
        "outcome_link_id": LINK_ID,
        "outcome_link_version_id": LINK_VERSION_ID,
        "outcome_link_version_identity_sha256": LINK_VERSION_IDENTITY_SHA256,
        "bundle_semantic_identity_contract_version": (
            "outcome_context_bundle_semantic_identity_v1"
        ),
        "bundle_semantic_projection_excludes_generated_at": True,
        "reference_identity_preimages_include_contract_version": True,
        "bundle_semantic_sha256": pointer["bundle_semantic_sha256"],
        "artifact_set_sha256": pointer["artifact_set_sha256"],
        "combined_scope_sha256": COMBINED_CLOSURE_SHA256,
        "counts": _semantic_counts(),
        "evidence_roles": expected_evidence_roles,
    }
    audit.equal(
        "materialization_report_semantic_exact",
        materialization["semantic"],
        expected_semantic,
    )
    expected_source_replay = {
        "action_candidate_rows": len(truth.action_universe),
        "indicator_observation_rows": len(truth.observations),
        "actor_reference_rows": len(truth.actor_reference_rows),
        "participant_rows": len(truth.participant_export_rows),
        "source_databases_opened_read_only": True,
        "source_databases_opened_with_explicit_read_transactions": True,
        "source_pre_post_physical_facts_match": True,
        "exact_fraction_decimal_calculation_recomputed": True,
        "complete_participant_contract_recomputed": True,
        "source_ballot_counts_recomputed_from_named_participants": True,
    }
    audit.equal(
        "materialization_report_source_replay_exact",
        materialization["source_replay"],
        expected_source_replay,
    )

    current_source_facts = {
        "actions_database": stable_source_database_fact(args.actions_db),
        "indicator_database": stable_source_database_fact(args.indicators_db),
        "actor_database": stable_source_database_fact(args.actor_graph_db),
    }
    inputs = materialization["inputs"]
    audit.equal(
        "materialization_report_input_keys",
        set(inputs),
        {
            "manual_input",
            "indicator_raw_source",
            "actions_database",
            "indicator_database",
            "actor_database",
            "source_database_stability",
        },
    )
    audit.equal(
        "materialization_report_manual_input_fact",
        inputs["manual_input"],
        file_fact(args.manual),
    )
    audit.equal(
        "materialization_report_indicator_raw_fact",
        inputs["indicator_raw_source"],
        file_fact(truth.indicator_raw_path),
    )
    for key, expected in current_source_facts.items():
        audit.equal(
            f"materialization_report_{key}_current_fact",
            portable_source_database_fact(inputs[key]),
            portable_source_database_fact(expected),
        )
    stability = inputs["source_database_stability"]
    audit.equal(
        "materialization_report_source_stability_keys",
        set(stability),
        {
            "fingerprint_contract_version",
            "pre_query",
            "post_query",
            "pre_post_exact_match",
            "content_hashes_and_stat_identities_checked",
            "non_empty_wal_rejected",
        },
    )
    audit.equal(
        "materialization_report_source_fingerprint_contract",
        stability["fingerprint_contract_version"],
        "sqlite_source_file_fingerprint_v1",
    )
    audit.equal(
        "materialization_report_source_pre_query_facts",
        {
            key: portable_source_database_fact(value)
            for key, value in stability["pre_query"].items()
        },
        {
            key: portable_source_database_fact(value)
            for key, value in current_source_facts.items()
        },
    )
    audit.equal(
        "materialization_report_source_post_query_facts",
        {
            key: portable_source_database_fact(value)
            for key, value in stability["post_query"].items()
        },
        {
            key: portable_source_database_fact(value)
            for key, value in current_source_facts.items()
        },
    )
    audit.equal(
        "materialization_report_source_pre_post_exact",
        stability["pre_query"],
        stability["post_query"],
    )
    for flag in (
        "pre_post_exact_match",
        "content_hashes_and_stat_identities_checked",
        "non_empty_wal_rejected",
    ):
        audit.equal(f"materialization_report_source_{flag}", stability[flag], True)

    expected_table_facts = {
        "outcome_link_evidence": {
            "rows": 7,
            "ordered_rows_sha256": (
                "b56dcfcb5d6ad360d10e0f897016d487a5ad95570dbbf49f50b573c9416219d7"
            ),
        },
        "outcome_link_observation_refs": {
            "rows": 3,
            "ordered_rows_sha256": (
                "4be3aeb998152ccc7126e822d45a628b0492eb381270ba240e157e8d0a955f1a"
            ),
        },
        "outcome_link_participant_refs": {
            "rows": 264,
            "ordered_rows_sha256": (
                "ffea94a6366c7714e116e7c723833f13eab1fb2485160dd91bbf54827721ef56"
            ),
        },
        "outcome_link_release_memberships": {
            "rows": 0,
            "ordered_rows_sha256": (
                "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
            ),
        },
        "outcome_link_releases": {
            "rows": 0,
            "ordered_rows_sha256": (
                "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
            ),
        },
        "outcome_link_reviews": {
            "rows": 0,
            "ordered_rows_sha256": (
                "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
            ),
        },
        "outcome_link_scope_closures": {
            "rows": 4,
            "ordered_rows_sha256": (
                "755d2b46dea71d6e3a41c849d8c1ca508a728c53a7681e29497ae9b2b5d9d2aa"
            ),
        },
        "outcome_link_versions": {
            "rows": 1,
            "ordered_rows_sha256": (
                "fce5eee4df1f99ef9d96820221bf2f85b5eb3aaeb688405c4a817f0fd8a40c4c"
            ),
        },
        "outcome_links": {
            "rows": 1,
            "ordered_rows_sha256": (
                "e4bce7afa4b5ac147f20dbbb17adb3c1bb613016641a0f37108d84e764718a29"
            ),
        },
    }
    database = materialization["database"]
    audit.equal("materialization_report_database_integrity", database["integrity_check"], "ok")
    audit.equal(
        "materialization_report_database_fk_violations",
        database["foreign_key_violations"],
        0,
    )
    audit.equal(
        "materialization_report_database_table_counts",
        database["table_counts"],
        database_counts,
    )
    parity = database["db_json_parity"]
    audit.equal("materialization_report_database_parity_status", parity["status"], "passed")
    audit.equal("materialization_report_database_parity_table_count", parity["tables_checked"], 9)
    audit.equal(
        "materialization_report_database_parity_table_facts",
        parity["table_facts"],
        expected_table_facts,
    )
    audit.equal(
        "materialization_report_database_parity_root",
        parity["whole_projection_sha256"],
        DATABASE_PARITY_ROOT_SHA256,
    )
    expected_trigger_names = sorted(
        f"trg_{table}_{suffix}"
        for table in database_counts
        for suffix in ("no_update", "no_delete")
    )
    schema_contract = database["schema_contract"]
    audit.equal(
        "materialization_report_schema_contract",
        schema_contract,
        {
            "table_count": 9,
            "table_names": sorted(database_counts),
            "column_contract_sha256": SCHEMA_COLUMN_CONTRACT_SHA256,
            "append_only_trigger_count": 18,
            "append_only_trigger_names": expected_trigger_names,
        },
    )

    expected_outputs = {
        "latest.json": {
            **file_fact(latest_path),
            "fact_state": "payload_precomputed_before_final_atomic_write",
        },
        "manifest.json": file_fact(manifest_path),
        "outcome-context-candidates-v1.db": file_fact(bundle_db),
        "outcome-context-candidates-v1.json": file_fact(bundle_json),
    }
    audit.equal(
        "materialization_report_output_facts_exact",
        materialization["outputs"],
        expected_outputs,
    )
    promotion = materialization["promotion"]
    audit.equal(
        "materialization_report_promotion_keys",
        set(promotion),
        {
            "immutable_version_path",
            "immutable_version_reused_after_byte_parity",
            "atomic_latest_pointer",
            "directory_replace_gap_used",
            "fsync_before_promotion",
            "report_fsynced_before_latest_pointer",
            "latest_pointer_is_final_materialization_operation",
            "failure_prone_work_after_latest_pointer",
        },
    )
    audit.equal(
        "materialization_report_immutable_path",
        promotion["immutable_version_path"],
        reported_path(manifest_path.parent),
    )
    audit.check(
        "materialization_report_reuse_flag_boolean",
        type(promotion["immutable_version_reused_after_byte_parity"]) is bool,
    )
    audit.equal(
        "materialization_report_atomic_pointer_path",
        promotion["atomic_latest_pointer"],
        reported_path(latest_path),
    )
    for key, expected in (
        ("directory_replace_gap_used", False),
        ("fsync_before_promotion", True),
        ("report_fsynced_before_latest_pointer", True),
        ("latest_pointer_is_final_materialization_operation", True),
        ("failure_prone_work_after_latest_pointer", False),
    ):
        audit.equal(f"materialization_report_promotion_{key}", promotion[key], expected)
    audit.check(
        "materialization_report_not_newer_than_final_pointer",
        path.stat().st_mtime_ns <= latest_path.stat().st_mtime_ns,
    )

    scale = materialization["scale"]
    audit.equal(
        "materialization_report_scale_keys",
        set(scale),
        {
            "multi_candidate_supported",
            "source_reads_streaming",
            "source_reads_use_fetchall",
            "semantic_json_monolithic",
            "resume_or_checkpoint_supported",
            "batch_size_bounds_source_reads",
            "batch_size_bounds_sqlite_writes_only",
            "million_scale_ready",
            "actor_lookup",
        },
    )
    for key, expected in (
        ("multi_candidate_supported", False),
        ("source_reads_streaming", False),
        ("source_reads_use_fetchall", True),
        ("semantic_json_monolithic", True),
        ("resume_or_checkpoint_supported", False),
        ("batch_size_bounds_source_reads", False),
        ("batch_size_bounds_sqlite_writes_only", True),
        ("million_scale_ready", False),
    ):
        audit.equal(f"materialization_report_scale_{key}", scale[key], expected)
    actor_lookup = scale["actor_lookup"]
    audit.equal(
        "materialization_report_actor_lookup_required_index",
        actor_lookup["required_index"],
        "idx_actor_graph_node_versions_release_source_actor",
    )
    audit.equal(
        "materialization_report_actor_lookup_schema_declaration",
        actor_lookup["required_index_declared_in_repository_schema"],
        "idx_actor_graph_node_versions_release_source_actor"
        in args.schema.read_text(encoding="utf-8"),
    )
    audit.equal(
        "materialization_report_actor_lookup_index_present",
        actor_lookup["required_index_present_in_current_source_database"],
        truth.actor_release_source_index_present,
    )
    audit.equal(
        "materialization_report_actor_lookup_plan_uses_required_index",
        actor_lookup["query_plan_uses_required_index"],
        truth.actor_source_query_scale_gate,
    )
    audit.equal(
        "materialization_report_actor_lookup_scale_gate",
        actor_lookup["current_source_actor_lookup_scale_gate_passed"],
        truth.actor_source_query_scale_gate,
    )
    audit.equal(
        "materialization_report_actor_lookup_query_plan",
        [row["detail"] for row in actor_lookup["query_plan"]],
        list(truth.actor_query_plan),
    )

    execution = materialization["execution"]
    audit.equal(
        "materialization_report_execution_keys",
        set(execution),
        {
            "batch_size",
            "single_sqlite_writer",
            "current_slice_uses_bulk_participant_reads",
            "write_batching_does_not_bound_source_read_memory",
            "pre_pointer_wall_time_seconds",
            "peak_rss_mb",
            "physical_database_hashes_are_semantic_identity_inputs",
        },
    )
    audit.check(
        "materialization_report_positive_batch_size",
        type(execution["batch_size"]) is int and execution["batch_size"] > 0,
    )
    for key, expected in (
        ("single_sqlite_writer", True),
        ("current_slice_uses_bulk_participant_reads", True),
        ("write_batching_does_not_bound_source_read_memory", True),
        ("physical_database_hashes_are_semantic_identity_inputs", False),
    ):
        audit.equal(f"materialization_report_execution_{key}", execution[key], expected)
    audit.check(
        "materialization_report_positive_wall_time",
        isinstance(execution["pre_pointer_wall_time_seconds"], (int, float))
        and execution["pre_pointer_wall_time_seconds"] > 0,
    )
    audit.check(
        "materialization_report_positive_peak_rss",
        isinstance(execution["peak_rss_mb"], (int, float))
        and execution["peak_rss_mb"] > 0,
    )
    bad_local_strings = [
        value
        for value in _walk_strings(materialization)
        if not assert_repo_relative(value)
    ]
    audit.equal("materialization_report_has_no_workstation_paths", bad_local_strings, [])
    bad_secret_strings = [
        value
        for value in _walk_strings(materialization)
        if "Authorization: Bearer" in value
        or "BEGIN PRIVATE KEY" in value
        or "cookie_jar" in value.casefold()
    ]
    audit.equal("materialization_report_has_no_secret_material", bad_secret_strings, [])
    return materialization, current_source_facts


def build_validation_report(
    *,
    args: argparse.Namespace,
    audit: Audit,
    truth: SourceTruth,
    manual: dict[str, Any],
    latest_path: Path,
    manifest_path: Path,
    bundle_db: Path,
    bundle_json: Path,
    pointer: dict[str, Any],
    manifest: dict[str, Any],
    database_counts: dict[str, int],
    materialization: dict[str, Any],
    current_source_facts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    counts = {
        "bounded_candidate_pairs": 20,
        "machine_audited_preproduction_candidates": 1,
        "links": 1,
        "link_versions": 1,
        "versions": 1,
        "observation_refs": 3,
        "observations": 3,
        "participant_refs": 264,
        "participants": 264,
        "evidence": 7,
        "scope_closures": 4,
        "human_reviewed_pairs": 0,
        "reviews": 0,
        "releases": 0,
        "release_memberships": 0,
        "memberships": 0,
        "published_links": 0,
        "publications": 0,
        "synthetic_or_mock_rows": 0,
    }
    truth_summary = {
        "scale_stage": "C0",
        "evidence_level": "L1",
        "candidate_status": "pending_human_review",
        "human_reviews": 0,
        "releases": 0,
        "release_memberships": 0,
        "publications": 0,
        "official_public_names_retained": 264,
        "synthetic_or_mock_rows": 0,
    }
    semantic_fingerprint_preimage = {
        "validation_contract_version": VALIDATION_SCHEMA_VERSION,
        "outcome_link_id": LINK_ID,
        "outcome_link_version_id": LINK_VERSION_ID,
        "outcome_link_version_identity_sha256": LINK_VERSION_IDENTITY_SHA256,
        "bundle_semantic_identity_contract_version": (
            "outcome_context_bundle_semantic_identity_v1"
        ),
        "bundle_semantic_sha256": pointer["bundle_semantic_sha256"],
        "combined_scope_sha256": COMBINED_CLOSURE_SHA256,
        "action_universe_sha256": ACTION_UNIVERSE_SHA256,
        "indicator_observation_universe_sha256": OBSERVATION_UNIVERSE_SHA256,
        "actor_reference_projection_sha256": ACTOR_REFERENCE_SHA256,
        "participant_export_projection_sha256": PARTICIPANT_EXPORT_SHA256,
        "counts": counts,
        "truth": truth_summary,
    }
    report = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "status": "passed" if not audit.failures else "failed",
        "generated_at": manual["generated_at"],
        "truth": truth_summary,
        "counts": counts,
        "semantic": {
            "outcome_link_id": LINK_ID,
            "outcome_link_version_id": LINK_VERSION_ID,
            "outcome_link_version_identity_sha256": LINK_VERSION_IDENTITY_SHA256,
            "bundle_semantic_sha256": pointer["bundle_semantic_sha256"],
            "bundle_semantic_identity_contract_version": (
                "outcome_context_bundle_semantic_identity_v1"
            ),
            "bundle_semantic_projection_excludes_generated_at": True,
            "artifact_set_sha256": pointer["artifact_set_sha256"],
            "combined_scope_sha256": COMBINED_CLOSURE_SHA256,
            "physical_database_hashes_are_semantic_identity_inputs": False,
            "physical_artifact_facts_are_semantic_identity_inputs": False,
        },
        "source_reconstruction": {
            "action_candidate_rows": len(truth.action_universe),
            "action_universe_canonical_bytes": len(
                canonical_json_bytes(truth.action_universe)
            ),
            "action_universe_sha256": sha256_bytes(
                canonical_json_bytes(truth.action_universe)
            ),
            "indicator_definitions_and_releases": len(truth.definitions),
            "indicator_definitions_and_releases_sha256": sha256_bytes(
                canonical_json_bytes(truth.definitions)
            ),
            "indicator_series": len(truth.series),
            "indicator_series_sha256": sha256_bytes(
                canonical_json_bytes(truth.series)
            ),
            "eligible_indicator_series": len(truth.eligible_series),
            "eligible_indicator_series_sha256": sha256_bytes(
                canonical_json_bytes(truth.eligible_series)
            ),
            "indicator_observations": len(truth.observations),
            "indicator_observations_sha256": sha256_bytes(
                canonical_json_bytes(truth.observations)
            ),
            "indicator_temporal_role_counts": dict(
                Counter(row["temporal_role"] for row in truth.observations)
            ),
            "participant_source_rows": len(truth.participant_source_rows),
            "participant_source_projection_sha256": sha256_bytes(
                canonical_json_bytes(truth.participant_source_rows)
            ),
            "actor_reference_rows": len(truth.actor_reference_rows),
            "actor_reference_projection_sha256": sha256_bytes(
                canonical_json_bytes(truth.actor_reference_rows)
            ),
            "participant_export_rows": len(truth.participant_export_rows),
            "participant_export_projection_sha256": sha256_bytes(
                canonical_json_bytes(truth.participant_export_rows)
            ),
            "vote_source_record_content_sha256": truth.vote_source_record[
                "payload_sha256"
            ],
            "initiative_source_record_content_sha256": truth.initiative_source_record[
                "payload_sha256"
            ],
            "indicator_source_content_sha256": sha256_file(
                truth.indicator_raw_path
            ),
            "official_public_names_retained": len(
                {row["official_member_name"] for row in truth.participant_export_rows}
            ),
            "participant_raw_locator_indices_covered": 264,
            "actor_label_mismatches_preserved": sum(
                row["official_member_name"] != row["actor_canonical_label"]
                for row in truth.participant_export_rows
            ),
            "original_vote_xml_capture_state": "absent_from_current_snapshot",
            "actor_query_plan": list(truth.actor_query_plan),
            "actor_release_source_index_present": truth.actor_release_source_index_present,
            "actor_source_query_scale_gate": truth.actor_source_query_scale_gate,
        },
        "scale_evidence": {
            "current_scale_stage": "C0",
            "single_candidate_materialization": True,
            "source_queries_materialized_with_fetchall_or_in_memory_lists": True,
            "semantic_json_layout": "monolithic",
            "bounded_candidate_pairs_physically_processed": 20,
            "million_candidate_physical_run_proven": False,
            "million_participant_reference_run_proven": False,
            "partitioned_artifact_set_proven": False,
            "clean_restore_proven": False,
            "fault_injection_resume_proven": False,
            "durable_public_origin_proven": False,
            "actor_release_source_lookup_scale_gate": truth.actor_source_query_scale_gate,
            "materialization_report_independently_validated": True,
            "source_pre_post_physical_facts_match": True,
            "report_fsynced_before_latest_pointer": True,
            "latest_pointer_is_final_materialization_operation": True,
        },
        "artifacts": {
            "immutable_bundle_path": pointer["immutable_bundle_path"],
            "candidate_version_id": pointer["candidate_version_id"],
            "candidate_version_identity_sha256": pointer[
                "candidate_version_identity_sha256"
            ],
            "bundle_semantic_sha256": pointer["bundle_semantic_sha256"],
            "artifact_set_sha256": pointer["artifact_set_sha256"],
            "manifest_sha256": pointer["manifest_sha256"],
            "latest": file_fact(latest_path),
            "manifest": file_fact(manifest_path),
            "database": file_fact(bundle_db),
            "semantic_json": file_fact(bundle_json),
            "materialization_report": {
                "path": reported_path(args.materialization_report),
                "schema_version": materialization["schema_version"],
                "status": materialization["status"],
                "whole_report_hash_is_authoritative": False,
            },
            "database_counts": database_counts,
            "manifest_counts": manifest["counts"],
            "promotion": {
                key: materialization["promotion"][key]
                for key in (
                    "report_fsynced_before_latest_pointer",
                    "latest_pointer_is_final_materialization_operation",
                    "failure_prone_work_after_latest_pointer",
                )
            },
        },
        "inputs": {
            "manual": file_fact(args.manual),
            "indicator_raw_source": file_fact(truth.indicator_raw_path),
            "physical_database_facts_report_only": {
                "actions": {
                    key: current_source_facts["actions_database"][key]
                    for key in ("path", "bytes", "sha256")
                },
                "indicators": {
                    key: current_source_facts["indicator_database"][key]
                    for key in ("path", "bytes", "sha256")
                },
                "actor_graph": {
                    key: current_source_facts["actor_database"][key]
                    for key in ("path", "bytes", "sha256")
                },
            },
            "physical_database_hashes_are_semantic_identity_inputs": False,
        },
        "checks": audit.checks,
        "check_count": len(audit.checks),
        "failed_checks": audit.failures,
        "deterministic_fingerprint": sha256_bytes(
            canonical_json_bytes(semantic_fingerprint_preimage)
        ),
    }
    return report


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(report) + b"\n")


def run_validation(args: argparse.Namespace) -> dict[str, Any]:
    audit = Audit()
    truth = reconstruct_source_truth(
        actions_db=args.actions_db,
        indicators_db=args.indicators_db,
        actor_graph_db=args.actor_graph_db,
        audit=audit,
    )
    manual = validate_manual(args.manual, truth, audit)
    (
        latest_path,
        manifest_path,
        bundle_db,
        bundle_json,
        pointer,
        manifest,
        _semantic,
    ) = validate_pointer_manifest_and_semantic_artifact(
        bundle_root=args.bundle_root,
        schema_path=args.schema,
        manual=manual,
        audit=audit,
    )
    database_counts = validate_bundle_database(
        bundle_db, manual, truth, audit
    )
    materialization, current_source_facts = validate_materialization_report(
        args=args,
        truth=truth,
        latest_path=latest_path,
        manifest_path=manifest_path,
        bundle_db=bundle_db,
        bundle_json=bundle_json,
        pointer=pointer,
        database_counts=database_counts,
        audit=audit,
    )
    report = build_validation_report(
        args=args,
        audit=audit,
        truth=truth,
        manual=manual,
        latest_path=latest_path,
        manifest_path=manifest_path,
        bundle_db=bundle_db,
        bundle_json=bundle_json,
        pointer=pointer,
        manifest=manifest,
        database_counts=database_counts,
        materialization=materialization,
        current_source_facts=current_source_facts,
    )
    write_report(args.report_out, report)
    return report


def main() -> int:
    args = parse_args()
    try:
        report = run_validation(args)
    except (
        OSError,
        UnicodeError,
        ValueError,
        KeyError,
        IndexError,
        sqlite3.Error,
        RuntimeError,
    ) as exc:
        failed = {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "method_version": METHOD_VERSION,
            "status": "failed",
            "failed_checks": [f"validator_exception: {type(exc).__name__}: {exc}"],
        }
        try:
            write_report(args.report_out, failed)
        except OSError:
            pass
        print(canonical_json(failed), file=sys.stderr)
        return 2
    print(canonical_json(report))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
