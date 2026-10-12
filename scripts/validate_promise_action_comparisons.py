#!/usr/bin/env python3
"""Independently validate reviewed promise/action comparisons against real sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROMISES_DB = REPO_ROOT / "etl/data/staging/promises-bng-2023.db"
DEFAULT_ACTIONS_DB = REPO_ROOT / "etl/data/staging/politicos-es.db"
DEFAULT_ACTOR_GRAPH_DB = REPO_ROOT / "etl/data/staging/actor-graph-v1.db"
DEFAULT_COMPARISON_DB = (
    REPO_ROOT / "etl/data/staging/promise-action-comparisons-v1.db"
)
DEFAULT_REVIEWED_MAPPINGS = (
    REPO_ROOT
    / "etl/data/manual/promise_action_comparisons/reviewed_mappings_v1.json"
)
DEFAULT_PUBLISHED = (
    REPO_ROOT / "etl/data/published/promise-action-comparisons-v1.json"
)
DEFAULT_PUBLIC = (
    REPO_ROOT / "ui/site/public/comparisons/data/comparisons.json"
)
DEFAULT_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/COMPARISON-ENGINE-20260820/evidence/"
    "promise-action-comparisons-validation.json"
)

SCHEMA_VERSION = "promise_action_comparison_v1"
METHOD_VERSION = "explicit_reviewed_mapping_v1"
ACTION_COVERAGE_CUTOFF = "2026-02-12"
REVIEW_FORMAT_VERSION = "promise_action_review_input_v1"
REVIEW_METHOD = "explicit_evidence_review"
ALLOWED_STATUSES = (
    "aligned",
    "conflicted",
    "insufficient_evidence",
    "ambiguous_mapping",
    "changed_framing",
    "not_comparable",
)
STRONG_STATUSES = {"aligned", "conflicted"}
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMPARISON_ID = re.compile(r"^vclc:promise-action-comparison:[0-9a-f]{32}$")
MAPPING_ID = re.compile(r"^vclc:comparison-mapping-review:[0-9a-f]{32}$")
EVIDENCE_ID = re.compile(r"^vclc:comparison-evidence:[0-9a-f]{32}$")
RELEASE_ID = re.compile(r"^vclc:comparison-release:[0-9a-f]{32}$")
NULL = "\0"
FAKE_MARKERS = (
    "example.invalid",
    "example.test",
    "fixture data",
    "generated person",
    "mock person",
    "placeholder person",
    "synthetic sample",
)
PRIVATE_MARKERS = (
    "/Users/",
    "/home/",
    "file:///",
    "Authorization: Bearer",
    "private_key",
    "cookie_jar",
)
FORBIDDEN_LINEAGE_KEYS = {
    "bytes",
    "input_files",
    "path",
    "schema",
    "sha256",
    "whole_file_sha256",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--promises-db", type=Path, default=DEFAULT_PROMISES_DB)
    parser.add_argument("--actions-db", type=Path, default=DEFAULT_ACTIONS_DB)
    parser.add_argument("--actor-graph-db", type=Path, default=DEFAULT_ACTOR_GRAPH_DB)
    parser.add_argument("--comparison-db", type=Path, default=DEFAULT_COMPARISON_DB)
    parser.add_argument(
        "--reviewed-mappings", type=Path, default=DEFAULT_REVIEWED_MAPPINGS
    )
    parser.add_argument("--published", type=Path, default=DEFAULT_PUBLISHED)
    parser.add_argument("--public", type=Path, default=DEFAULT_PUBLIC)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def report_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def input_file_fact(path: Path) -> dict[str, Any]:
    return {
        "path": report_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def has_forbidden_lineage_key(value: Any) -> bool:
    if isinstance(value, dict):
        if any(str(key) in FORBIDDEN_LINEAGE_KEYS for key in value):
            return True
        return any(has_forbidden_lineage_key(item) for item in value.values())
    if isinstance(value, list):
        return any(has_forbidden_lineage_key(item) for item in value)
    return False


def stable_id(kind: str, *parts: object) -> str:
    payload = NULL.join(
        [kind, *(str(part if part is not None else "") for part in parts)]
    )
    return f"vclc:{kind}:{sha256_bytes(payload.encode('utf-8'))[:32]}"


def normalized_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value))
    ascii_like = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return " ".join(ascii_like.casefold().split())


def open_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro", uri=True
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def rows_as_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def json_array(values: Iterable[str]) -> str:
    return canonical_json(sorted(set(str(value) for value in values)))


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def parse_json_object(value: str, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: invalid JSON: {exc}")
        return {}
    if not isinstance(parsed, dict):
        errors.append(f"{label}: must be an object")
        return {}
    return parsed


def table_rows(
    connection: sqlite3.Connection,
    table: str,
    *,
    order_by: str,
) -> list[dict[str, Any]]:
    return rows_as_dicts(connection.execute(f'SELECT * FROM "{table}" ORDER BY {order_by}'))


def fetch_claims(
    connection: sqlite3.Connection, claim_ids: set[str]
) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
          c.claim_id, c.manifesto_document_id, c.claim_extraction_run_id,
          c.party_id, c.attributed_actor_label, c.claim_kind, c.exact_text,
          c.page_start, c.page_end, c.review_status, c.claim_status,
          p.promise_id, p.commitment_strength, p.measurability_state,
          p.observation_status,
          ce.claim_evidence_id, ce.source_url AS evidence_source_url,
          ce.document_sha256, ce.quote_sha256, ce.exact_quote,
          md.source_id, md.source_record_pk, md.source_url AS document_source_url,
          md.published_date, md.snapshot_date, md.content_sha256,
          sr.source_record_id, sr.content_sha256 AS source_record_sha256
        FROM claims AS c
        JOIN promises AS p ON p.claim_id = c.claim_id
        JOIN claim_evidence AS ce
          ON ce.claim_id = c.claim_id AND ce.evidence_role = 'primary'
        JOIN manifesto_documents AS md
          ON md.manifesto_document_id = c.manifesto_document_id
        LEFT JOIN source_records AS sr
          ON sr.source_record_pk = md.source_record_pk
        WHERE c.claim_id IN (SELECT value FROM json_each(?))
        ORDER BY c.claim_id, ce.claim_evidence_id
        """,
        (json_array(claim_ids),),
    ).fetchall()
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        record = dict(row)
        claim_id = str(record["claim_id"])
        if claim_id in output:
            raise RuntimeError(f"multiple primary claim evidence rows: {claim_id}")
        output[claim_id] = record
    return output


def fetch_actions(
    connection: sqlite3.Connection, reviews: list[dict[str, Any]]
) -> dict[tuple[str, str], dict[str, Any]]:
    roll_calls = [
        review for review in reviews if review.get("action_kind") == "roll_call_vote"
    ]
    action_ids = {str(review["action_id"]) for review in roll_calls}
    member_names = {str(review["expected_member_name"]) for review in roll_calls}
    rows = connection.execute(
        """
        SELECT
          e.vote_event_id, e.vote_date, e.vote_number, e.title,
          e.expediente_text, e.subgroup_title, e.subgroup_text,
          e.source_id, e.source_url, e.source_record_pk,
          e.source_snapshot_date,
          v.member_vote_id, v.member_name, v.vote_choice, v.group_code,
          v.person_id, v.source_url AS member_vote_source_url,
          i.initiative_id, i.title AS initiative_title,
          i.source_url AS initiative_url,
          vei.link_method AS initiative_link_method,
          vei.confidence AS initiative_link_confidence,
          sr.source_record_id, sr.content_sha256 AS source_record_sha256
        FROM parl_vote_events AS e
        JOIN parl_vote_member_votes AS v ON v.vote_event_id = e.vote_event_id
        LEFT JOIN parl_vote_event_initiatives AS vei
          ON vei.vote_event_id = e.vote_event_id
        LEFT JOIN parl_initiatives AS i ON i.initiative_id = vei.initiative_id
        LEFT JOIN source_records AS sr ON sr.source_record_pk = e.source_record_pk
        WHERE e.vote_event_id IN (SELECT value FROM json_each(?))
          AND v.member_name IN (SELECT value FROM json_each(?))
        ORDER BY e.vote_event_id, v.member_name, i.initiative_id
        """,
        (json_array(action_ids), json_array(member_names)),
    ).fetchall()
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        record = dict(row)
        key = (str(record["vote_event_id"]), str(record["member_name"]))
        if key in output:
            raise RuntimeError(f"ambiguous action/member join: {key}")
        output[key] = record
    return output


def fetch_actor_scope(
    connection: sqlite3.Connection,
    mapping_payload: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    actor_ids = {str(mapping_payload.get("claim_actor", {}).get("actor_id", ""))}
    relationship_ids: set[str] = set()
    for review in mapping_payload.get("reviews", []):
        for field in (
            "action_actor_id",
            "action_registry_actor_id",
            "action_party_actor_id",
        ):
            if review.get(field):
                actor_ids.add(str(review[field]))
        if review.get("affiliation_relationship_id"):
            relationship_ids.add(str(review["affiliation_relationship_id"]))
    actor_rows = connection.execute(
        """
        SELECT
          n.actor_id, n.actor_kind, n.actor_subtype, n.identity_scope,
          n.source_scope_id, n.stable_source_key,
          nv.canonical_label, nv.normalized_label, nv.identity_state,
          nv.valid_from, nv.valid_to, nv.observed_at,
          nv.source_id, nv.source_record_id, nv.source_url,
          nv.source_content_sha256, nv.provenance_state, nv.release_id
        FROM actor_graph_nodes AS n
        JOIN actor_graph_node_versions AS nv ON nv.actor_id = n.actor_id
        WHERE n.actor_id IN (SELECT value FROM json_each(?))
        ORDER BY n.actor_id, nv.release_id
        """,
        (json_array(actor_ids),),
    ).fetchall()
    actors: dict[str, dict[str, Any]] = {}
    for row in actor_rows:
        record = dict(row)
        actor_id = str(record["actor_id"])
        if actor_id in actors:
            raise RuntimeError(f"multiple actor versions in comparison scope: {actor_id}")
        actors[actor_id] = record
    relationship_rows = connection.execute(
        """
        SELECT
          r.relationship_id, r.subject_actor_id, r.relationship_type,
          r.object_actor_id, r.context_kind, r.context_id,
          rv.valid_from, rv.valid_to, rv.observed_at, rv.resolution_state,
          rv.source_id, rv.source_record_id, rv.source_url,
          rv.source_content_sha256, rv.release_id,
          sv.canonical_label AS subject_label,
          ov.canonical_label AS object_label
        FROM actor_graph_relationships AS r
        JOIN actor_graph_relationship_versions AS rv
          ON rv.relationship_id = r.relationship_id
        JOIN actor_graph_node_versions AS sv
          ON sv.actor_id = r.subject_actor_id AND sv.release_id = rv.release_id
        JOIN actor_graph_node_versions AS ov
          ON ov.actor_id = r.object_actor_id AND ov.release_id = rv.release_id
        WHERE r.relationship_id IN (SELECT value FROM json_each(?))
        ORDER BY r.relationship_id, rv.release_id
        """,
        (json_array(relationship_ids),),
    ).fetchall()
    relationships: dict[str, dict[str, Any]] = {}
    for row in relationship_rows:
        record = dict(row)
        relationship_id = str(record["relationship_id"])
        if relationship_id in relationships:
            raise RuntimeError(
                f"multiple relationship versions in comparison scope: {relationship_id}"
            )
        relationships[relationship_id] = record
    return actors, relationships


def bounded_search_scope(
    connection: sqlite3.Connection, review: dict[str, Any]
) -> dict[str, Any]:
    configured = review.get("action_search") or {}
    rows = connection.execute(
        """
        SELECT
          e.vote_event_id, e.vote_date, e.title, e.expediente_text,
          e.source_id, e.source_url, v.member_name, v.vote_choice
        FROM parl_vote_member_votes AS v
        JOIN parl_vote_events AS e ON e.vote_event_id = v.vote_event_id
        WHERE v.member_name IN (SELECT value FROM json_each(?))
          AND e.vote_date >= ? AND e.vote_date <= ?
        ORDER BY e.vote_event_id, v.member_name
        """,
        (
            json_array(configured.get("member_names", [])),
            configured.get("date_from"),
            configured.get("date_to"),
        ),
    ).fetchall()
    candidates = rows_as_dicts(rows)
    candidates.sort(
        key=lambda row: (str(row["vote_event_id"]), str(row["member_name"]))
    )
    terms = [normalized_name(value) for value in configured.get("search_terms", [])]
    matching = []
    for row in candidates:
        haystack = normalized_name(
            f"{row.get('title') or ''} {row.get('expediente_text') or ''}"
        )
        if any(term in haystack for term in terms):
            matching.append(row)
    return {
        **configured,
        "candidate_vote_rows_scanned": len(candidates),
        "candidate_events_scanned": len(
            {str(row["vote_event_id"]) for row in candidates}
        ),
        "candidate_rows_sha256": sha256_bytes(
            canonical_json(candidates).encode("utf-8")
        ),
        "matching_event_ids": sorted(
            {str(row["vote_event_id"]) for row in matching}
        ),
        "result_state": "no_reviewed_action_found",
    }


def public_evidence_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "comparison_evidence_id": row["comparison_evidence_id"],
        "evidence_side": row["evidence_side"],
        "evidence_role": row["evidence_role"],
        "source_id": row["source_id"],
        "source_record_id": row["source_record_id"],
        "source_url": row["source_url"],
        "content_sha256": row["content_sha256"],
        "exact_quote": row["exact_quote"],
        "observed_at": row["observed_at"],
        "metadata": json.loads(row["metadata_json"]),
    }


def evidence_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row["evidence_side"]),
        str(row["evidence_role"]),
        str(row["comparison_evidence_id"]),
    )


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    checks: dict[str, bool] = {}
    required_files = (
        args.promises_db,
        args.actions_db,
        args.actor_graph_db,
        args.comparison_db,
        args.reviewed_mappings,
        args.published,
        args.public,
    )
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        errors.append(f"missing required real inputs: {missing}")
        report = {
            "schema_version": "promise_action_comparison_validation_v1",
            "status": "failed",
            "failed_checks": ["required_real_inputs_present"],
            "checks": {"required_real_inputs_present": False},
            "errors": errors,
        }
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
        return 1

    input_file_facts = {
        "promises_db": input_file_fact(args.promises_db),
        "actions_db": input_file_fact(args.actions_db),
        "actor_graph_db": input_file_fact(args.actor_graph_db),
        "reviewed_mappings": input_file_fact(args.reviewed_mappings),
    }
    validated_output_file_facts = {
        "comparison_db": input_file_fact(args.comparison_db),
        "published": input_file_fact(args.published),
        "public": input_file_fact(args.public),
    }
    published_bytes = args.published.read_bytes()
    public_bytes = args.public.read_bytes()
    payload = json.loads(published_bytes)
    public_payload = json.loads(public_bytes)
    mapping_bytes = args.reviewed_mappings.read_bytes()
    mapping_payload = json.loads(mapping_bytes)
    reviews_input = mapping_payload.get("reviews") or []

    checks["required_real_inputs_present"] = True
    checks["published_public_byte_parity"] = published_bytes == public_bytes
    checks["public_json_bounded"] = 0 < len(public_bytes) <= 5 * 1024 * 1024
    checks["review_input_contract"] = (
        mapping_payload.get("format_version") == REVIEW_FORMAT_VERSION
        and mapping_payload.get("review_method") == REVIEW_METHOD
        and isinstance(reviews_input, list)
        and bool(reviews_input)
    )
    checks["review_input_hash"] = bool(
        HEX_SHA256.fullmatch(sha256_bytes(mapping_bytes))
    )

    for check, passed in list(checks.items()):
        require(passed, check.replace("_", " "), errors)

    with open_readonly(args.promises_db) as promises_connection:
        promise_integrity = promises_connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]
        promise_fk = promises_connection.execute("PRAGMA foreign_key_check").fetchall()
        claims = fetch_claims(
            promises_connection,
            {str(review.get("claim_id")) for review in reviews_input},
        )

    with open_readonly(args.actions_db) as actions_connection:
        actions_integrity = actions_connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]
        actions_fk = actions_connection.execute("PRAGMA foreign_key_check").fetchall()
        actions = fetch_actions(actions_connection, reviews_input)
        search_scopes = {
            (str(review["claim_id"]), str(review["action_kind"])): bounded_search_scope(
                actions_connection, review
            )
            for review in reviews_input
            if review.get("action_kind") == "bounded_action_search"
        }

    with open_readonly(args.actor_graph_db) as actor_connection:
        actor_integrity = actor_connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]
        actor_fk = actor_connection.execute("PRAGMA foreign_key_check").fetchall()
        actors, relationships = fetch_actor_scope(actor_connection, mapping_payload)

    with open_readonly(args.comparison_db) as comparison_connection:
        comparison_integrity = comparison_connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]
        comparison_fk = comparison_connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        releases = table_rows(
            comparison_connection,
            "comparison_releases",
            order_by="comparison_release_id",
        )
        review_rows = table_rows(
            comparison_connection,
            "comparison_mapping_reviews",
            order_by="claim_id, action_kind, COALESCE(action_id, '')",
        )
        comparison_rows = table_rows(
            comparison_connection,
            "promise_action_comparisons",
            order_by="claim_id, action_kind, COALESCE(action_id, '')",
        )
        evidence_rows_raw = table_rows(
            comparison_connection,
            "comparison_evidence",
            order_by=(
                "comparison_id, CASE evidence_side "
                "WHEN 'claim' THEN 1 WHEN 'action' THEN 2 "
                "WHEN 'actor_link' THEN 3 ELSE 4 END, comparison_evidence_id"
            ),
        )

    checks["all_sqlite_integrity"] = all(
        value == "ok"
        for value in (
            promise_integrity,
            actions_integrity,
            actor_integrity,
            comparison_integrity,
        )
    )
    checks["all_foreign_keys_clean"] = not (
        promise_fk or actions_fk or actor_fk or comparison_fk
    )
    checks["single_release"] = len(releases) == 1
    require(checks["all_sqlite_integrity"], "SQLite integrity check failed", errors)
    require(checks["all_foreign_keys_clean"], "SQLite foreign key check failed", errors)
    require(checks["single_release"], "comparison DB must contain one release", errors)
    release = releases[0] if releases else {}

    reviews_by_key = {
        (
            str(review.get("claim_id")),
            str(review.get("action_kind")),
            review.get("action_id"),
        ): review
        for review in reviews_input
    }
    checks["review_keys_unique"] = len(reviews_by_key) == len(reviews_input)
    checks["review_rows_reconcile"] = len(review_rows) == len(reviews_input)
    checks["comparison_rows_reconcile"] = len(comparison_rows) == len(reviews_input)
    checks["v1_changed_framing_disabled"] = not any(
        str(row.get("review_outcome")) == "changed_framing" for row in review_rows
    ) and not any(
        str(row.get("comparison_status")) == "changed_framing"
        for row in comparison_rows
    ) and not any(
        str(item.get("comparison_status")) == "changed_framing"
        for item in payload.get("items", [])
        if isinstance(item, dict)
    )
    require(checks["review_keys_unique"], "duplicate reviewed mapping key", errors)
    require(checks["review_rows_reconcile"], "mapping review row count drift", errors)
    require(checks["comparison_rows_reconcile"], "comparison row count drift", errors)
    require(
        checks["v1_changed_framing_disabled"],
        "changed_framing is disabled in v1 until actor-authored later-frame evidence is modeled",
        errors,
    )

    actor_graph_release_ids = {
        str(row.get("release_id")) for row in [*actors.values(), *relationships.values()]
    }
    checks["single_actor_graph_release"] = len(actor_graph_release_ids) == 1
    actor_graph_release_id = (
        next(iter(actor_graph_release_ids)) if len(actor_graph_release_ids) == 1 else ""
    )
    require(
        checks["single_actor_graph_release"],
        "actor comparison scope spans releases",
        errors,
    )

    promises_digest = sha256_bytes(
        canonical_json([claims[key] for key in sorted(claims)]).encode("utf-8")
    )
    action_scope = {
        "action_pairs": [actions[key] for key in sorted(actions)],
        "bounded_action_searches": [
            search_scopes[key] for key in sorted(search_scopes)
        ],
    }
    actions_digest = sha256_bytes(canonical_json(action_scope).encode("utf-8"))
    actors_digest = sha256_bytes(
        canonical_json(
            {
                "actors": [actors[key] for key in sorted(actors)],
                "relationships": [relationships[key] for key in sorted(relationships)],
            }
        ).encode("utf-8")
    )
    evidence_by_comparison: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence_rows_raw:
        evidence_by_comparison[str(row["comparison_id"])].append(row)
    evidence_side_order = {
        "claim": 1,
        "action": 2,
        "actor_link": 3,
        "mapping_review": 4,
    }
    # Reconstruct producer order from relational rows. The semantic hash covers
    # ordered arrays, so a validator must not trust physical SQLite row order.
    semantic_evidence_rows = [
        evidence
        for comparison in comparison_rows
        for evidence in sorted(
            evidence_by_comparison.get(str(comparison["comparison_id"]), []),
            key=lambda row: (
                evidence_side_order.get(str(row["evidence_side"]), 99),
                str(row["comparison_evidence_id"]),
            ),
        )
    ]
    semantic_sha256 = sha256_bytes(
        canonical_json(
            {
                "reviews": review_rows,
                "comparisons": comparison_rows,
                "evidence": semantic_evidence_rows,
            }
        ).encode("utf-8")
    )
    mapping_sha256 = sha256_bytes(
        canonical_json(mapping_payload).encode("utf-8")
    )
    expected_input_releases = {
        "promises": {"selected_scope_sha256": promises_digest},
        "actions": {
            "selected_scope_sha256": actions_digest,
            "coverage_cutoff": ACTION_COVERAGE_CUTOFF,
        },
        "actor_graph": {
            "release_id": actor_graph_release_id,
            "selected_scope_sha256": actors_digest,
        },
        "reviewed_mappings": {"canonical_sha256": mapping_sha256},
    }
    expected_source_manifest = {
        "claim_ids": sorted(claims),
        "action_ids": sorted({key[0] for key in actions}),
        "actor_ids": sorted(actors),
        "actor_relationship_ids": sorted(relationships),
        "bounded_action_searches": [
            search_scopes[key] for key in sorted(search_scopes)
        ],
        "input_releases": expected_input_releases,
        "real_records_only": True,
    }
    source_manifest = parse_json_object(
        release.get("source_manifest_json", "{}"), "release source manifest", errors
    )
    expected_release_id = stable_id(
        "comparison-release",
        SCHEMA_VERSION,
        METHOD_VERSION,
        mapping_payload.get("review_version"),
        release.get("snapshot_date"),
        promises_digest,
        actions_digest,
        ACTION_COVERAGE_CUTOFF,
        actors_digest,
        actor_graph_release_id,
        mapping_sha256,
    )
    checks["source_scope_hashes_reconstructed"] = (
        release.get("promises_source_scope_sha256") == promises_digest
        and release.get("actions_source_scope_sha256") == actions_digest
        and release.get("actor_source_scope_sha256") == actors_digest
        and release.get("actor_graph_release_id") == actor_graph_release_id
    )
    checks["actions_scope_hash_includes_real_bounded_searches"] = (
        bool(action_scope["bounded_action_searches"])
        and release.get("actions_source_scope_sha256") == actions_digest
    )
    checks["bounded_search_candidate_rows_hashed"] = bool(search_scopes) and all(
        HEX_SHA256.fullmatch(str(scope.get("candidate_rows_sha256") or ""))
        for scope in search_scopes.values()
    )
    checks["semantic_hash_reconstructed"] = (
        release.get("semantic_sha256") == semantic_sha256
    )
    checks["release_id_reconstructed"] = (
        release.get("comparison_release_id") == expected_release_id
    )
    checks["reviewed_mapping_hash_matches_release"] = (
        release.get("reviewed_mappings_sha256") == mapping_sha256
    )
    checks["release_contract_versions"] = (
        release.get("schema_version") == SCHEMA_VERSION
        and release.get("method_version") == METHOD_VERSION
        and release.get("mapping_review_version")
        == mapping_payload.get("review_version")
    )
    checks["source_manifest_semantic_lineage_exact"] = (
        source_manifest == expected_source_manifest
    )
    checks["source_manifest_has_no_volatile_lineage"] = not has_forbidden_lineage_key(
        source_manifest
    )
    for check in (
        "source_scope_hashes_reconstructed",
        "actions_scope_hash_includes_real_bounded_searches",
        "bounded_search_candidate_rows_hashed",
        "semantic_hash_reconstructed",
        "release_id_reconstructed",
        "reviewed_mapping_hash_matches_release",
        "release_contract_versions",
        "source_manifest_semantic_lineage_exact",
        "source_manifest_has_no_volatile_lineage",
    ):
        require(checks[check], check.replace("_", " "), errors)

    review_db_by_key = {
        (str(row["claim_id"]), str(row["action_kind"]), row["action_id"]): row
        for row in review_rows
    }
    comparisons_by_review = {
        str(row["mapping_review_id"]): row for row in comparison_rows
    }
    identity_labels: set[str] = set()
    bounded_metrics: list[dict[str, Any]] = []
    status_semantics_ok = True
    source_reconstruction_ok = True
    ids_deterministic = True
    evidence_reconstruction_ok = True
    official_identity_retained = True
    temporal_gates_ok = True
    public_items_by_id = {
        str(item.get("comparison_id")): item
        for item in payload.get("items", [])
        if isinstance(item, dict)
    }

    for key, reviewed in reviews_by_key.items():
        db_review = review_db_by_key.get(key)
        if db_review is None:
            source_reconstruction_ok = False
            errors.append(f"missing materialized review: {key}")
            continue
        claim = claims.get(str(reviewed["claim_id"]))
        if claim is None:
            source_reconstruction_ok = False
            errors.append(f"claim missing from real promise DB: {reviewed['claim_id']}")
            continue
        action = None
        if reviewed["action_kind"] == "roll_call_vote":
            action = actions.get(
                (str(reviewed["action_id"]), str(reviewed["expected_member_name"]))
            )
            if action is None:
                source_reconstruction_ok = False
                errors.append(f"roll-call action missing: {reviewed['action_id']}")
                continue
            if action["vote_choice"] != reviewed["expected_vote_choice"]:
                source_reconstruction_ok = False
                errors.append(f"official vote choice drift: {reviewed['action_id']}")
            if str(action["vote_date"]) <= str(claim["published_date"]):
                temporal_gates_ok = False
                errors.append(
                    f"action is not strictly later than assertion: {reviewed['action_id']}"
                )
        else:
            scope = search_scopes.get((str(reviewed["claim_id"]), str(reviewed["action_kind"])), {})
            bounded_metrics.append(
                {
                    "claim_id": reviewed["claim_id"],
                    "candidate_vote_rows_scanned": scope.get("candidate_vote_rows_scanned"),
                    "candidate_events_scanned": scope.get("candidate_events_scanned"),
                    "candidate_rows_sha256": scope.get("candidate_rows_sha256"),
                    "matching_events": len(scope.get("matching_event_ids", [])),
                }
            )
            if scope.get("matching_event_ids"):
                status_semantics_ok = False
                errors.append("bounded no-action search found matching official actions")

        expected_scope = search_scopes.get(
            (str(reviewed["claim_id"]), str(reviewed["action_kind"])), {}
        )
        expected_mapping_id = stable_id(
            "comparison-mapping-review",
            mapping_payload.get("review_version"),
            reviewed["claim_id"],
            reviewed["action_kind"],
            reviewed.get("action_id"),
            sha256_bytes(canonical_json(reviewed).encode("utf-8")),
        )
        if db_review["mapping_review_id"] != expected_mapping_id:
            ids_deterministic = False
            errors.append(f"mapping review ID drift: {key}")
        comparison = comparisons_by_review.get(str(db_review["mapping_review_id"]))
        if comparison is None:
            source_reconstruction_ok = False
            errors.append(f"comparison missing for review: {key}")
            continue
        expected_comparison_id = stable_id(
            "promise-action-comparison",
            reviewed["claim_id"],
            claim["promise_id"],
            reviewed["action_kind"],
            reviewed.get("action_id"),
            mapping_payload["claim_actor"]["actor_id"],
            reviewed.get("action_actor_id"),
            reviewed.get("action_party_actor_id"),
            (
                sha256_bytes(canonical_json(expected_scope).encode("utf-8"))
                if reviewed["action_kind"] == "bounded_action_search"
                else ""
            ),
        )
        if comparison["comparison_id"] != expected_comparison_id:
            ids_deterministic = False
            errors.append(f"comparison ID drift: {key}")

        expected_review_fields = {
            "claim_id": claim["claim_id"],
            "promise_id": claim["promise_id"],
            "action_kind": reviewed["action_kind"],
            "action_id": reviewed.get("action_id"),
            "claim_actor_id": mapping_payload["claim_actor"]["actor_id"],
            "action_actor_id": reviewed.get("action_actor_id"),
            "action_registry_actor_id": reviewed.get("action_registry_actor_id"),
            "action_party_actor_id": reviewed.get("action_party_actor_id"),
            "affiliation_relationship_id": reviewed.get("affiliation_relationship_id"),
            "actor_link_state": reviewed["actor_link_state"],
            "review_outcome": reviewed["review_outcome"],
            "claim_direction": reviewed["claim_direction"],
            "action_direction": reviewed["action_direction"],
            "action_substance_state": reviewed["action_substance_state"],
            "mapping_basis": reviewed["mapping_basis"],
            "review_method": mapping_payload["review_method"],
            "review_version": mapping_payload["review_version"],
            "review_rationale": reviewed["review_rationale"],
            "directional_countable": int(bool(reviewed["directional_countable"])),
            "reviewed_at": mapping_payload["reviewed_at"],
        }
        for field, expected in expected_review_fields.items():
            if db_review.get(field) != expected:
                source_reconstruction_ok = False
                errors.append(f"{key}: review field drift: {field}")
        expected_search_state = (
            "no_reviewed_action_found"
            if reviewed["action_kind"] == "bounded_action_search"
            else "not_applicable"
        )
        if db_review.get("action_search_state") != expected_search_state:
            source_reconstruction_ok = False
            errors.append(f"{key}: action search state drift")
        if parse_json_object(
            db_review.get("action_search_scope_json", "{}"),
            f"{key} review search scope",
            errors,
        ) != expected_scope:
            source_reconstruction_ok = False
            errors.append(f"{key}: action search scope drift")

        expected_comparison_fields = {
            "claim_id": claim["claim_id"],
            "promise_id": claim["promise_id"],
            "claim_kind": claim["claim_kind"],
            "claim_actor_label": claim["attributed_actor_label"],
            "claim_actor_id": mapping_payload["claim_actor"]["actor_id"],
            "claim_text": claim["exact_text"],
            "claim_page_start": claim["page_start"],
            "claim_page_end": claim["page_end"],
            "claim_published_date": claim["published_date"],
            "claim_review_status": claim["review_status"],
            "action_kind": reviewed["action_kind"],
            "action_id": reviewed.get("action_id"),
            "action_search_state": expected_search_state,
            "comparison_status": reviewed["review_outcome"],
            "directional_countable": int(bool(reviewed["directional_countable"])),
            "public_summary": reviewed["public_summary"],
            "caveat": reviewed["caveat"],
        }
        if action:
            expected_comparison_fields.update(
                {
                    "action_date": action["vote_date"],
                    "action_title": action["expediente_text"] or action["title"],
                    "action_member_name": action["member_name"],
                    "action_vote_choice": action["vote_choice"],
                    "action_actor_id": reviewed["action_actor_id"],
                    "action_party_actor_id": reviewed["action_party_actor_id"],
                    "action_source_id": action["source_id"],
                    "action_source_url": action["source_url"],
                }
            )
        else:
            expected_comparison_fields.update(
                {
                    "action_date": None,
                    "action_title": None,
                    "action_member_name": None,
                    "action_vote_choice": None,
                    "action_actor_id": None,
                    "action_party_actor_id": None,
                    "action_source_id": None,
                    "action_source_url": None,
                }
            )
        for field, expected in expected_comparison_fields.items():
            if comparison.get(field) != expected:
                source_reconstruction_ok = False
                errors.append(f"{key}: comparison field drift: {field}")
        if parse_json_object(
            comparison.get("action_search_scope_json", "{}"),
            f"{key} comparison search scope",
            errors,
        ) != expected_scope:
            source_reconstruction_ok = False
            errors.append(f"{key}: comparison search scope drift")

        status = str(comparison["comparison_status"])
        directional = int(comparison["directional_countable"]) == 1
        if status not in ALLOWED_STATUSES:
            status_semantics_ok = False
            errors.append(f"{key}: invalid comparison status")
        if status in STRONG_STATUSES:
            strong_gate = (
                reviewed["action_kind"] == "roll_call_vote"
                and reviewed["mapping_basis"] == "exact_measure"
                and reviewed["action_substance_state"] == "substantive"
                and reviewed["actor_link_state"]
                == "reviewed_official_identity_and_affiliation"
                and reviewed["claim_direction"] in {"support", "oppose"}
                and reviewed["action_direction"] in {"support", "oppose"}
                and directional
            )
            same_direction = reviewed["claim_direction"] == reviewed["action_direction"]
            strong_gate = strong_gate and (
                (status == "aligned" and same_direction)
                or (status == "conflicted" and not same_direction)
            )
            if not strong_gate:
                status_semantics_ok = False
                errors.append(f"{key}: strong status gate failed")
        elif directional:
            status_semantics_ok = False
            errors.append(f"{key}: non-strong status is directional")
        if reviewed["action_kind"] == "bounded_action_search":
            bounded_gate = (
                status == "insufficient_evidence"
                and reviewed["action_id"] is None
                and reviewed["actor_link_state"] == "claim_actor_only_no_action"
                and reviewed["action_direction"] == "not_applicable"
                and reviewed["action_substance_state"] == "not_applicable"
                and reviewed["mapping_basis"] == "bounded_search_no_reviewed_action"
                and not directional
                and not any(
                    comparison.get(field)
                    for field in (
                        "action_id",
                        "action_date",
                        "action_title",
                        "action_member_name",
                        "action_vote_choice",
                        "action_actor_id",
                        "action_party_actor_id",
                        "action_source_id",
                        "action_source_url",
                    )
                )
            )
            if not bounded_gate:
                status_semantics_ok = False
                errors.append(f"{key}: bounded-search insufficiency gate failed")
        if status == "not_comparable" and reviewed["action_substance_state"] == "procedural":
            if reviewed["mapping_basis"] != "procedural_near_match":
                status_semantics_ok = False
                errors.append(f"{key}: procedural status mapping basis drift")
        if status == "ambiguous_mapping" and reviewed["mapping_basis"] not in {
            "broad_topic_only",
            "reviewed_related_measure",
        }:
            status_semantics_ok = False
            errors.append(f"{key}: ambiguous status mapping basis drift")

        if action:
            action_actor = actors.get(str(reviewed["action_actor_id"]))
            registry_actor = actors.get(str(reviewed["action_registry_actor_id"]))
            party_actor = actors.get(str(reviewed["action_party_actor_id"]))
            relationship = relationships.get(str(reviewed["affiliation_relationship_id"]))
            if not all((action_actor, registry_actor, party_actor, relationship)):
                official_identity_retained = False
                errors.append(f"{key}: reviewed actor graph evidence missing")
            else:
                expected_name = str(reviewed["expected_member_name"])
                identity_labels.update(
                    {
                        expected_name,
                        str(action_actor["canonical_label"]),
                        str(registry_actor["canonical_label"]),
                        str(party_actor["canonical_label"]),
                    }
                )
                actor_link_ok = (
                    normalized_name(action_actor["canonical_label"])
                    == normalized_name(expected_name)
                    and normalized_name(registry_actor["canonical_label"])
                    == normalized_name(expected_name)
                    and normalized_name(action["member_name"])
                    == normalized_name(expected_name)
                    and relationship["relationship_type"] == "affiliated_with_party"
                    and relationship["subject_actor_id"]
                    == reviewed["action_registry_actor_id"]
                    and relationship["object_actor_id"]
                    == reviewed["action_party_actor_id"]
                    and (not relationship["valid_from"] or action["vote_date"] >= relationship["valid_from"])
                    and (not relationship["valid_to"] or action["vote_date"] <= relationship["valid_to"])
                )
                if not actor_link_ok:
                    official_identity_retained = False
                    errors.append(f"{key}: actor identity/capacity evidence drift")

        comparison_evidence = evidence_by_comparison.get(
            str(comparison["comparison_id"]), []
        )
        side_roles = {
            (str(row["evidence_side"]), str(row["evidence_role"]))
            for row in comparison_evidence
        }
        required_roles = {("claim", "primary"), ("mapping_review", "review")}
        if action:
            required_roles.update({("action", "primary"), ("actor_link", "identity")})
        if not required_roles.issubset(side_roles):
            evidence_reconstruction_ok = False
            errors.append(f"{key}: required evidence roles missing")
        if status in STRONG_STATUSES and not {
            ("claim", "primary"),
            ("action", "primary"),
            ("actor_link", "identity"),
            ("mapping_review", "review"),
        }.issubset(side_roles):
            status_semantics_ok = False
            errors.append(f"{key}: strong comparison evidence gate failed")
        for evidence in comparison_evidence:
            if not HEX_SHA256.fullmatch(str(evidence.get("content_sha256") or "")):
                evidence_reconstruction_ok = False
                errors.append(f"{key}: evidence hash missing/invalid")
            if evidence["evidence_side"] != "mapping_review":
                if not str(evidence.get("source_url") or "").startswith("https://"):
                    evidence_reconstruction_ok = False
                    errors.append(f"{key}: official evidence URL missing")
            if not str(evidence.get("exact_quote") or "").strip():
                evidence_reconstruction_ok = False
                errors.append(f"{key}: exact evidence text missing")
        claim_evidence = next(
            (
                row
                for row in comparison_evidence
                if row["evidence_side"] == "claim" and row["evidence_role"] == "primary"
            ),
            None,
        )
        if not claim_evidence or not (
            claim_evidence["source_url"] == claim["evidence_source_url"]
            and claim_evidence["content_sha256"] == claim["document_sha256"]
            and claim_evidence["exact_quote"] == claim["exact_quote"]
            and sha256_bytes(claim_evidence["exact_quote"].encode("utf-8"))
            == claim["quote_sha256"]
        ):
            evidence_reconstruction_ok = False
            errors.append(f"{key}: claim evidence does not reconstruct")
        review_evidence = next(
            (
                row
                for row in comparison_evidence
                if row["evidence_side"] == "mapping_review"
                and row["evidence_role"] == "review"
            ),
            None,
        )
        if not review_evidence or not (
            review_evidence["exact_quote"] == reviewed["review_rationale"]
            and review_evidence["content_sha256"]
            == sha256_bytes(canonical_json(reviewed).encode("utf-8"))
        ):
            evidence_reconstruction_ok = False
            errors.append(f"{key}: mapping review evidence does not reconstruct")
        if action:
            action_evidence = next(
                (
                    row
                    for row in comparison_evidence
                    if row["evidence_side"] == "action"
                    and row["evidence_role"] == "primary"
                ),
                None,
            )
            expected_action_quote = action["expediente_text"] or action["title"]
            if not action_evidence or not (
                action_evidence["source_id"] == action["source_id"]
                and action_evidence["source_url"] == action["source_url"]
                and action_evidence["exact_quote"] == expected_action_quote
                and action_evidence["content_sha256"]
                == action["source_record_sha256"]
            ):
                evidence_reconstruction_ok = False
                errors.append(f"{key}: action evidence does not reconstruct")

        public_item = public_items_by_id.get(str(comparison["comparison_id"]))
        if public_item is None:
            official_identity_retained = False
            errors.append(f"{key}: comparison missing from public JSON")
        else:
            if public_item.get("comparison_status") != comparison["comparison_status"]:
                source_reconstruction_ok = False
                errors.append(f"{key}: public status drift")
            public_claim = public_item.get("claim") or {}
            if not (
                public_claim.get("claim_id") == claim["claim_id"]
                and public_claim.get("promise_id") == claim["promise_id"]
                and public_claim.get("actor_label") == claim["attributed_actor_label"]
                and public_claim.get("exact_text") == claim["exact_text"]
                and public_claim.get("page_start") == claim["page_start"]
                and public_claim.get("page_end") == claim["page_end"]
            ):
                official_identity_retained = False
                errors.append(f"{key}: public claim identity/text drift")
            public_action = public_item.get("action")
            if action and not (
                isinstance(public_action, dict)
                and public_action.get("action_id") == action["vote_event_id"]
                and public_action.get("member_name") == action["member_name"]
                and public_action.get("vote_choice") == action["vote_choice"]
                and public_action.get("source_url") == action["source_url"]
            ):
                official_identity_retained = False
                errors.append(f"{key}: public action identity drift")
            if not action and public_action is not None:
                source_reconstruction_ok = False
                errors.append(f"{key}: bounded search published a fabricated action")
            public_evidence = sorted(
                public_item.get("evidence") or [], key=evidence_key
            )
            expected_public_evidence = sorted(
                [public_evidence_row(row) for row in comparison_evidence],
                key=evidence_key,
            )
            if public_evidence != expected_public_evidence:
                evidence_reconstruction_ok = False
                errors.append(f"{key}: public evidence projection drift")

    checks["source_rows_reconstructed"] = source_reconstruction_ok
    checks["status_semantics_fail_closed"] = status_semantics_ok
    checks["temporal_order_valid"] = temporal_gates_ok
    checks["deterministic_ids"] = ids_deterministic
    checks["evidence_reconstructed"] = evidence_reconstruction_ok
    checks["official_public_identity_retained"] = official_identity_retained
    for check in (
        "source_rows_reconstructed",
        "status_semantics_fail_closed",
        "temporal_order_valid",
        "deterministic_ids",
        "evidence_reconstructed",
        "official_public_identity_retained",
    ):
        require(checks[check], check.replace("_", " "), errors)

    status_counts = Counter(str(row["comparison_status"]) for row in comparison_rows)
    complete_status_counts = {
        status: int(status_counts.get(status, 0)) for status in ALLOWED_STATUSES
    }
    public_status_counts = payload.get("status_counts") or {}
    input_releases = payload.get("input_releases") or {}
    methodology = payload.get("methodology") or {}
    checks["public_input_releases_semantic_lineage_exact"] = (
        input_releases == expected_input_releases
    )
    checks["public_input_releases_have_no_volatile_lineage"] = (
        not has_forbidden_lineage_key(input_releases)
    )
    checks["public_release_metadata_matches"] = (
        payload.get("schema_version") == release.get("schema_version")
        and payload.get("release_id") == release.get("comparison_release_id")
        and payload.get("snapshot_date") == release.get("snapshot_date")
        and payload.get("as_of_date") == release.get("snapshot_date")
        and payload.get("generated_at") == release.get("generated_at")
        and payload.get("semantic_sha256") == release.get("semantic_sha256")
        and methodology.get("method_version") == release.get("method_version")
        and methodology.get("mapping_review_version")
        == release.get("mapping_review_version")
        and (input_releases.get("reviewed_mappings") or {}).get("canonical_sha256")
        == release.get("reviewed_mappings_sha256")
        and (input_releases.get("actor_graph") or {}).get("release_id")
        == release.get("actor_graph_release_id")
        and (input_releases.get("promises") or {}).get("selected_scope_sha256")
        == promises_digest
        and (input_releases.get("actions") or {}).get("selected_scope_sha256")
        == actions_digest
        and (input_releases.get("actor_graph") or {}).get("selected_scope_sha256")
        == actors_digest
        and int((payload.get("counts") or {}).get("comparisons_total", -1))
        == len(comparison_rows)
        and int((payload.get("counts") or {}).get("evidence_total", -1))
        == len(evidence_rows_raw)
    )
    checks["public_status_counts_complete"] = all(
        int(public_status_counts.get(status, 0)) == count
        for status, count in complete_status_counts.items()
    ) and set(public_status_counts).issubset(ALLOWED_STATUSES)
    checks["public_real_only_policy"] = (
        payload.get("real_data_only") is True
        and payload.get("synthetic_or_mock") is False
        and payload.get("public_domain_information_policy")
        == "retain_official_public_identity_exclude_only_secrets_private_session_state_and_workstation_traces"
    )
    checks["public_method_states_present"] = all(
        isinstance(payload.get(field), dict) and bool(payload.get(field))
        for field in ("methodology", "coverage", "freshness")
    )
    checks["public_item_uncertainty_present"] = all(
        isinstance(item.get("mapping_review"), dict)
        and bool(item["mapping_review"].get("mapping_state"))
        and isinstance(item.get("confidence"), dict)
        and isinstance(item.get("coverage"), dict)
        and isinstance(item.get("freshness"), dict)
        and isinstance(item.get("counterevidence"), dict)
        and bool(item["counterevidence"].get("search_state"))
        and isinstance(item.get("frame"), dict)
        and isinstance(item.get("actor_capacity"), dict)
        and bool(item["actor_capacity"].get("assertion_capacity"))
        and bool(item["actor_capacity"].get("attribution_unit"))
        for item in payload.get("items", [])
    )
    checks["public_comparison_ids_exact"] = (
        set(public_items_by_id) == {str(row["comparison_id"]) for row in comparison_rows}
    )
    serialized_payload = json.dumps(payload, ensure_ascii=False)
    folded_payload = serialized_payload.casefold()
    checks["no_fake_markers"] = not any(
        marker.casefold() in folded_payload for marker in FAKE_MARKERS
    )
    checks["no_private_or_workstation_markers"] = not any(
        marker.casefold() in folded_payload for marker in PRIVATE_MARKERS
    )
    checks["zero_strong_v1_truth"] = (
        complete_status_counts["aligned"] == 0
        and complete_status_counts["conflicted"] == 0
        and all(not bool(row["directional_countable"]) for row in comparison_rows)
    )
    checks["no_claim_fulfillment_inference"] = all(
        claim.get("observation_status") == "not_assessed" for claim in claims.values()
    )
    for check in (
        "public_input_releases_semantic_lineage_exact",
        "public_input_releases_have_no_volatile_lineage",
        "public_release_metadata_matches",
        "public_status_counts_complete",
        "public_real_only_policy",
        "public_method_states_present",
        "public_item_uncertainty_present",
        "public_comparison_ids_exact",
        "no_fake_markers",
        "no_private_or_workstation_markers",
        "zero_strong_v1_truth",
        "no_claim_fulfillment_inference",
    ):
        require(checks[check], check.replace("_", " "), errors)

    checks["release_counts_reconcile"] = (
        int(release.get("comparison_count", -1)) == len(comparison_rows)
        and int(release.get("evidence_count", -1)) == len(evidence_rows_raw)
        and parse_json_object(
            release.get("status_counts_json", "{}"), "release status counts", errors
        )
        == {status: count for status, count in complete_status_counts.items() if count}
    )
    checks["release_ids_well_formed"] = bool(
        RELEASE_ID.fullmatch(str(release.get("comparison_release_id") or ""))
    )
    checks["row_ids_well_formed"] = (
        all(COMPARISON_ID.fullmatch(str(row["comparison_id"])) for row in comparison_rows)
        and all(MAPPING_ID.fullmatch(str(row["mapping_review_id"])) for row in review_rows)
        and all(EVIDENCE_ID.fullmatch(str(row["comparison_evidence_id"])) for row in evidence_rows_raw)
    )
    for check in (
        "release_counts_reconcile",
        "release_ids_well_formed",
        "row_ids_well_formed",
    ):
        require(checks[check], check.replace("_", " "), errors)

    failed_checks = sorted(check for check, passed in checks.items() if not passed)
    report = {
        "schema_version": "promise_action_comparison_validation_v1",
        "status": "passed" if not errors and not failed_checks else "failed",
        "validated_release_id": release.get("comparison_release_id"),
        "snapshot_date": release.get("snapshot_date"),
        "artifact": {
            "bytes": len(published_bytes),
            "sha256": sha256_bytes(published_bytes),
            "published_public_byte_parity": published_bytes == public_bytes,
        },
        "database": {
            "bytes": args.comparison_db.stat().st_size,
            "sha256": sha256_file(args.comparison_db),
            "integrity_check": comparison_integrity,
            "foreign_key_violations": len(comparison_fk),
        },
        "input_file_facts": input_file_facts,
        "validated_output_file_facts": validated_output_file_facts,
        "source_scope_sha256": {
            "promises": promises_digest,
            "actions": actions_digest,
            "actors": actors_digest,
        },
        "reviewed_mappings_sha256": mapping_sha256,
        "semantic_sha256": semantic_sha256,
        "counts": {
            "comparisons": len(comparison_rows),
            "mapping_reviews": len(review_rows),
            "evidence": len(evidence_rows_raw),
            "claims": len(claims),
            "roll_call_actions": len(actions),
            "actor_nodes": len(actors),
            "actor_relationships": len(relationships),
            "official_identity_labels_retained": len(identity_labels),
        },
        "status_counts": complete_status_counts,
        "strong_comparisons": (
            complete_status_counts["aligned"]
            + complete_status_counts["conflicted"]
        ),
        "bounded_action_searches": bounded_metrics,
        "policy": {
            "real_data_only": True,
            "synthetic_or_mock": False,
            "official_public_domain_information_retained": True,
            "absence_is_not_nonfulfillment": True,
            "confidence_is_quality_not_truth": True,
            "no_causality_or_corruption_inference": True,
        },
        "checks": dict(sorted(checks.items())),
        "failed_checks": failed_checks,
        "errors": errors,
    }
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
