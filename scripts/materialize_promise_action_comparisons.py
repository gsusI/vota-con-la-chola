#!/usr/bin/env python3
"""Materialize reviewed promise/action comparisons from real official records."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import sqlite3
import sys
import tempfile
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.db import apply_schema  # noqa: E402
from publicdata_sqlite import open_db  # noqa: E402


SCHEMA_VERSION = "promise_action_comparison_v1"
METHOD_VERSION = "explicit_reviewed_mapping_v1"
DEFAULT_SNAPSHOT_DATE = "2026-08-20"
DEFAULT_SCHEMA = REPO_ROOT / "etl/load/sqlite_schema.sql"
DEFAULT_PROMISES_DB = REPO_ROOT / "etl/data/staging/promises-bng-2023.db"
DEFAULT_ACTIONS_DB = REPO_ROOT / "etl/data/staging/politicos-es.db"
DEFAULT_ACTOR_GRAPH_DB = REPO_ROOT / "etl/data/staging/actor-graph-v1.db"
DEFAULT_REVIEWED_MAPPINGS = (
    REPO_ROOT
    / "etl/data/manual/promise_action_comparisons/reviewed_mappings_v1.json"
)
DEFAULT_OUT_DB = REPO_ROOT / "etl/data/staging/promise-action-comparisons-v1.db"
DEFAULT_OUT_JSON = (
    REPO_ROOT / "etl/data/published/promise-action-comparisons-v1.json"
)
DEFAULT_PUBLIC_OUT = (
    REPO_ROOT / "ui/gh-pages-next/public/comparisons/data/comparisons.json"
)
DEFAULT_REPORT_OUT = (
    REPO_ROOT
    / "docs/etl/sprints/COMPARISON-ENGINE-20260820/evidence/"
    "comparison-materialization.json"
)
ACTION_COVERAGE_CUTOFF = "2026-02-12"
ALLOWED_STATUSES = {
    "aligned",
    "conflicted",
    "insufficient_evidence",
    "ambiguous_mapping",
    "changed_framing",
    "not_comparable",
}
STRONG_STATUSES = {"aligned", "conflicted"}
NULL = "\0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the reviewed real-data promise/action comparison slice."
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--promises-db", type=Path, default=DEFAULT_PROMISES_DB)
    parser.add_argument("--actions-db", type=Path, default=DEFAULT_ACTIONS_DB)
    parser.add_argument("--actor-graph-db", type=Path, default=DEFAULT_ACTOR_GRAPH_DB)
    parser.add_argument(
        "--reviewed-mappings", type=Path, default=DEFAULT_REVIEWED_MAPPINGS
    )
    parser.add_argument("--out-db", type=Path, default=DEFAULT_OUT_DB)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--public-out", type=Path, default=DEFAULT_PUBLIC_OUT)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT_OUT)
    parser.add_argument("--snapshot-date", default=DEFAULT_SNAPSHOT_DATE)
    parser.add_argument("--batch-size", type=int, default=10_000)
    return parser.parse_args()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def require_strictly_later_action(
    *, claim_published_date: Any, action_date: Any, action_id: str
) -> None:
    try:
        claim_day = date.fromisoformat(str(claim_published_date)[:10])
        action_day = date.fromisoformat(str(action_date)[:10])
    except ValueError as exc:
        raise RuntimeError(
            f"invalid claim/action date for temporal comparison: {action_id}"
        ) from exc
    if action_day <= claim_day:
        raise RuntimeError(
            "roll_call_vote action must be strictly later than claim publication: "
            f"{action_id} ({action_day.isoformat()} <= {claim_day.isoformat()})"
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(kind: str, *parts: object) -> str:
    payload = NULL.join([kind, *(str(part if part is not None else "") for part in parts)])
    return f"vclc:{kind}:{sha256_bytes(payload.encode('utf-8'))[:32]}"


def comparison_release_id(
    *,
    review_version: str,
    snapshot_date: str,
    promises_digest: str,
    actions_digest: str,
    action_coverage_cutoff: str,
    actors_digest: str,
    actor_graph_release_id: str,
    mappings_sha256: str,
) -> str:
    return stable_id(
        "comparison-release",
        SCHEMA_VERSION,
        METHOD_VERSION,
        review_version,
        snapshot_date,
        promises_digest,
        actions_digest,
        action_coverage_cutoff,
        actors_digest,
        actor_graph_release_id,
        mappings_sha256,
    )


def normalized_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_like = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(ascii_like.casefold().split())


def report_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def input_file_fact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing required input: {report_path(path)}")
    return {
        "path": report_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def readonly_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise RuntimeError(f"missing required real database: {report_path(path)}")
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro&immutable=1", uri=True
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def chunks(rows: Sequence[tuple[Any, ...]], size: int) -> Iterator[Sequence[tuple[Any, ...]]]:
    for offset in range(0, len(rows), size):
        yield rows[offset : offset + size]


def execute_batched(
    connection: sqlite3.Connection,
    statement: str,
    rows: Sequence[tuple[Any, ...]],
    batch_size: int,
) -> None:
    for batch in chunks(rows, batch_size):
        connection.executemany(statement, batch)


def fetch_by_ids(
    connection: sqlite3.Connection,
    sql_prefix: str,
    ids: Iterable[str],
    *,
    order_by: str,
) -> list[sqlite3.Row]:
    unique_ids = sorted(set(ids))
    if not unique_ids:
        return []
    return connection.execute(
        f"{sql_prefix} (SELECT value FROM json_each(?)) ORDER BY {order_by}",
        (canonical_json(unique_ids),),
    ).fetchall()


def load_reviewed_mappings(path: Path) -> tuple[dict[str, Any], bytes]:
    if not path.is_file():
        raise RuntimeError(f"missing reviewed mapping input: {report_path(path)}")
    raw = path.read_bytes()
    payload = json.loads(raw)
    if payload.get("format_version") != "promise_action_review_input_v1":
        raise RuntimeError("unexpected reviewed mapping format_version")
    if payload.get("review_method") != "explicit_evidence_review":
        raise RuntimeError("comparisons require explicit_evidence_review")
    reviews = payload.get("reviews")
    if not isinstance(reviews, list) or not reviews:
        raise RuntimeError("reviewed mapping input has no reviews")
    seen: set[tuple[str, str, str | None]] = set()
    for review in reviews:
        key = (review.get("claim_id"), review.get("action_kind"), review.get("action_id"))
        if key in seen:
            raise RuntimeError(f"duplicate reviewed mapping: {key}")
        seen.add(key)
        if review.get("review_outcome") not in ALLOWED_STATUSES:
            raise RuntimeError(f"invalid comparison status: {review.get('review_outcome')}")
        if review.get("review_outcome") == "changed_framing":
            raise RuntimeError(
                "changed_framing is disabled in v1 until actor-authored later-frame "
                "evidence fields and a dedicated publication gate exist"
            )
        if not review.get("reason_codes") or not review.get("material_differences"):
            raise RuntimeError("review requires reason_codes and material_differences")
        if review.get("action_kind") not in {
            "roll_call_vote",
            "bounded_action_search",
        }:
            raise RuntimeError(f"invalid action kind: {review.get('action_kind')}")
        if (
            review.get("action_kind") == "bounded_action_search"
            and review.get("action_id") is not None
        ):
            raise RuntimeError("bounded_action_search cannot contain action_id")
        if review.get("action_kind") == "bounded_action_search":
            search = review.get("action_search")
            if not isinstance(search, dict):
                raise RuntimeError("bounded_action_search requires action_search scope")
            for field in ("member_names", "date_from", "date_to", "search_terms"):
                if not search.get(field):
                    raise RuntimeError(f"bounded_action_search missing {field}")
            if search.get("expected_matching_events") != 0:
                raise RuntimeError(
                    "v1 bounded search row is valid only when zero matching events are expected"
                )
        if review.get("action_kind") == "roll_call_vote" and not review.get("action_id"):
            raise RuntimeError("roll_call_vote review requires action_id")
        directional = bool(review.get("directional_countable"))
        if directional and review.get("review_outcome") not in STRONG_STATUSES:
            raise RuntimeError("only aligned/conflicted may be directional_countable")
        if review.get("review_outcome") in STRONG_STATUSES:
            if not directional:
                raise RuntimeError("aligned/conflicted must be directional_countable")
            if review.get("mapping_basis") != "exact_measure":
                raise RuntimeError("aligned/conflicted require exact_measure mapping")
            if review.get("action_substance_state") != "substantive":
                raise RuntimeError("aligned/conflicted require substantive action")
            if review.get("claim_direction") not in {"support", "oppose"}:
                raise RuntimeError("aligned/conflicted require clear claim direction")
            if review.get("action_direction") not in {"support", "oppose"}:
                raise RuntimeError("aligned/conflicted require clear action direction")
    return payload, raw


def load_claims(
    connection: sqlite3.Connection, claim_ids: set[str]
) -> dict[str, dict[str, Any]]:
    rows = fetch_by_ids(
        connection,
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
        WHERE c.claim_id IN
        """,
        claim_ids,
        order_by="c.claim_id, ce.claim_evidence_id",
    )
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        claim_id = str(row["claim_id"])
        if claim_id in output:
            raise RuntimeError(f"claim has multiple primary evidence rows: {claim_id}")
        record = dict(row)
        if record["review_status"] not in {"rule_confirmed", "human_confirmed"}:
            raise RuntimeError(f"unreviewed claim cannot enter comparisons: {claim_id}")
        if record["claim_status"] != "active":
            raise RuntimeError(f"inactive claim cannot enter v1 comparisons: {claim_id}")
        if record["document_sha256"] != record["content_sha256"]:
            raise RuntimeError(f"claim evidence/document hash mismatch: {claim_id}")
        if sha256_bytes(record["exact_quote"].encode("utf-8")) != record["quote_sha256"]:
            raise RuntimeError(f"claim quote hash mismatch: {claim_id}")
        output[claim_id] = record
    missing = claim_ids - output.keys()
    if missing:
        raise RuntimeError(f"reviewed claims missing from real promise DB: {sorted(missing)}")
    return output


def load_actions(
    connection: sqlite3.Connection, reviews: list[dict[str, Any]]
) -> tuple[
    dict[tuple[str, str], dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
]:
    action_reviews = [row for row in reviews if row["action_kind"] == "roll_call_vote"]
    action_ids = sorted({str(row["action_id"]) for row in action_reviews})
    member_names = sorted({str(row["expected_member_name"]) for row in action_reviews})
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
        (canonical_json(action_ids), canonical_json(member_names)),
    ).fetchall()
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row["vote_event_id"]), str(row["member_name"]))
        if key in output:
            raise RuntimeError(f"ambiguous action/member join: {key}")
        output[key] = dict(row)
    for review in action_reviews:
        key = (str(review["action_id"]), str(review["expected_member_name"]))
        action = output.get(key)
        if action is None:
            raise RuntimeError(f"reviewed official roll call missing: {key}")
        if action["vote_choice"] != review["expected_vote_choice"]:
            raise RuntimeError(f"reviewed vote choice drift: {key}")
        if not action["source_url"] or not str(action["source_url"]).startswith("https://"):
            raise RuntimeError(f"official action source URL missing: {key}")
    bounded_reviews = [
        row for row in reviews if row["action_kind"] == "bounded_action_search"
    ]
    search_scopes: dict[tuple[str, str], dict[str, Any]] = {}
    if bounded_reviews:
        bounded_members = sorted(
            {
                str(member)
                for review in bounded_reviews
                for member in review["action_search"]["member_names"]
            }
        )
        date_from = min(str(row["action_search"]["date_from"]) for row in bounded_reviews)
        date_to = max(str(row["action_search"]["date_to"]) for row in bounded_reviews)
        candidate_rows = connection.execute(
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
            (canonical_json(bounded_members), date_from, date_to),
        ).fetchall()
        candidates = [dict(row) for row in candidate_rows]
        for review in bounded_reviews:
            configured = review["action_search"]
            scoped_members = {str(value) for value in configured["member_names"]}
            scoped = [
                row
                for row in candidates
                if row["member_name"] in scoped_members
                and str(configured["date_from"]) <= str(row["vote_date"])
                and str(row["vote_date"]) <= str(configured["date_to"])
            ]
            scoped.sort(
                key=lambda row: (str(row["vote_event_id"]), str(row["member_name"]))
            )
            terms = [normalized_name(str(value)) for value in configured["search_terms"]]
            matching = []
            for row in scoped:
                haystack = normalized_name(
                    f"{row.get('title') or ''} {row.get('expediente_text') or ''}"
                )
                if any(term in haystack for term in terms):
                    matching.append(row)
            matching_event_ids = sorted({str(row["vote_event_id"]) for row in matching})
            expected = int(configured["expected_matching_events"])
            if len(matching_event_ids) != expected:
                raise RuntimeError(
                    "bounded action search result drift for "
                    f"{review['claim_id']}: expected {expected}, "
                    f"observed {len(matching_event_ids)}"
                )
            search_scopes[(str(review["claim_id"]), str(review["action_kind"]))] = {
                **configured,
                "candidate_vote_rows_scanned": len(scoped),
                "candidate_events_scanned": len(
                    {str(row["vote_event_id"]) for row in scoped}
                ),
                "candidate_rows_sha256": sha256_bytes(
                    canonical_json(scoped).encode("utf-8")
                ),
                "matching_event_ids": matching_event_ids,
                "result_state": "no_reviewed_action_found",
            }
    return output, search_scopes


def load_actor_scope(
    connection: sqlite3.Connection,
    mapping_payload: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], str]:
    reviews = mapping_payload["reviews"]
    actor_ids = {str(mapping_payload["claim_actor"]["actor_id"])}
    relationship_ids: set[str] = set()
    for review in reviews:
        for field in (
            "action_actor_id",
            "action_registry_actor_id",
            "action_party_actor_id",
        ):
            if review.get(field):
                actor_ids.add(str(review[field]))
        if review.get("affiliation_relationship_id"):
            relationship_ids.add(str(review["affiliation_relationship_id"]))
    actors = fetch_by_ids(
        connection,
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
        WHERE n.actor_id IN
        """,
        actor_ids,
        order_by="n.actor_id, nv.release_id",
    )
    actor_by_id: dict[str, dict[str, Any]] = {}
    for row in actors:
        actor_id = str(row["actor_id"])
        if actor_id in actor_by_id:
            raise RuntimeError(f"multiple actor versions not supported in v1 slice: {actor_id}")
        actor_by_id[actor_id] = dict(row)
    missing_actors = actor_ids - actor_by_id.keys()
    if missing_actors:
        raise RuntimeError(f"reviewed actor IDs missing: {sorted(missing_actors)}")
    relationships = fetch_by_ids(
        connection,
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
        WHERE r.relationship_id IN
        """,
        relationship_ids,
        order_by="r.relationship_id, rv.release_id",
    )
    relationship_by_id: dict[str, dict[str, Any]] = {}
    for row in relationships:
        relationship_id = str(row["relationship_id"])
        if relationship_id in relationship_by_id:
            raise RuntimeError(
                f"multiple relationship versions not supported in v1 slice: {relationship_id}"
            )
        relationship_by_id[relationship_id] = dict(row)
    missing_relationships = relationship_ids - relationship_by_id.keys()
    if missing_relationships:
        raise RuntimeError(f"reviewed actor relationships missing: {sorted(missing_relationships)}")
    release_ids = {str(row["release_id"]) for row in actor_by_id.values()}
    release_ids.update(str(row["release_id"]) for row in relationship_by_id.values())
    if len(release_ids) != 1:
        raise RuntimeError(f"actor evidence spans multiple releases: {sorted(release_ids)}")
    return actor_by_id, relationship_by_id, next(iter(release_ids))


def date_within(value: str, start: str | None, end: str | None) -> bool:
    return (not start or value >= start) and (not end or value <= end)


def validate_actor_link(
    review: dict[str, Any],
    action: dict[str, Any] | None,
    actors: dict[str, dict[str, Any]],
    relationships: dict[str, dict[str, Any]],
    claim_actor_id: str,
) -> None:
    claim_actor = actors[claim_actor_id]
    if claim_actor["actor_kind"] != "organization":
        raise RuntimeError("claim actor must be an organization")
    if review["action_kind"] == "bounded_action_search":
        if review["actor_link_state"] != "claim_actor_only_no_action":
            raise RuntimeError(
                "bounded_action_search requires claim_actor_only_no_action"
            )
        return
    if action is None:
        raise RuntimeError("roll-call actor validation requires action")
    if review["actor_link_state"] != "reviewed_official_identity_and_affiliation":
        raise RuntimeError("roll-call comparison requires reviewed actor link")
    rollcall_actor = actors[str(review["action_actor_id"])]
    registry_actor = actors[str(review["action_registry_actor_id"])]
    party_actor = actors[str(review["action_party_actor_id"])]
    relationship = relationships[str(review["affiliation_relationship_id"])]
    expected_name = str(review["expected_member_name"])
    if normalized_name(str(rollcall_actor["canonical_label"])) != normalized_name(expected_name):
        raise RuntimeError("roll-call actor name does not match official vote")
    if normalized_name(str(registry_actor["canonical_label"])) != normalized_name(expected_name):
        raise RuntimeError("registry actor name does not match official vote")
    if normalized_name(str(action["member_name"])) != normalized_name(expected_name):
        raise RuntimeError("action member name drift")
    if relationship["relationship_type"] != "affiliated_with_party":
        raise RuntimeError("reviewed actor relationship is not party affiliation")
    if relationship["subject_actor_id"] != review["action_registry_actor_id"]:
        raise RuntimeError("party affiliation subject drift")
    if relationship["object_actor_id"] != review["action_party_actor_id"]:
        raise RuntimeError("party affiliation object drift")
    if party_actor["actor_kind"] != "organization":
        raise RuntimeError("action party actor must be organization")
    if normalized_name(str(party_actor["canonical_label"])) not in {
        "bng",
        "bloque nacionalista galego",
    }:
        raise RuntimeError("reviewed action party is not BNG")
    if not date_within(
        str(action["vote_date"]), relationship["valid_from"], relationship["valid_to"]
    ):
        raise RuntimeError("action date falls outside reviewed official affiliation")


def materialize_records(
    mapping_payload: dict[str, Any],
    mappings_sha256: str,
    claims: dict[str, dict[str, Any]],
    actions: dict[tuple[str, str], dict[str, Any]],
    actors: dict[str, dict[str, Any]],
    relationships: dict[str, dict[str, Any]],
    action_search_scopes: dict[tuple[str, str], dict[str, Any]],
    actor_graph_release_id: str,
    snapshot_date: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    claim_actor_id = str(mapping_payload["claim_actor"]["actor_id"])
    review_version = str(mapping_payload["review_version"])
    reviewed_at = str(mapping_payload["reviewed_at"])
    claim_scope = [claims[key] for key in sorted(claims)]
    action_scope = {
        "action_pairs": [actions[key] for key in sorted(actions)],
        "bounded_action_searches": [
            action_search_scopes[key] for key in sorted(action_search_scopes)
        ],
    }
    actor_scope = [actors[key] for key in sorted(actors)]
    relationship_scope = [relationships[key] for key in sorted(relationships)]
    promises_digest = sha256_bytes(canonical_json(claim_scope).encode("utf-8"))
    actions_digest = sha256_bytes(canonical_json(action_scope).encode("utf-8"))
    actors_digest = sha256_bytes(
        canonical_json({"actors": actor_scope, "relationships": relationship_scope}).encode(
            "utf-8"
        )
    )
    input_releases = {
        "promises": {"selected_scope_sha256": promises_digest},
        "actions": {
            "selected_scope_sha256": actions_digest,
            "coverage_cutoff": ACTION_COVERAGE_CUTOFF,
        },
        "actor_graph": {
            "release_id": actor_graph_release_id,
            "selected_scope_sha256": actors_digest,
        },
        "reviewed_mappings": {"canonical_sha256": mappings_sha256},
    }
    release_id = comparison_release_id(
        review_version=review_version,
        snapshot_date=snapshot_date,
        promises_digest=promises_digest,
        actions_digest=actions_digest,
        action_coverage_cutoff=ACTION_COVERAGE_CUTOFF,
        actors_digest=actors_digest,
        actor_graph_release_id=actor_graph_release_id,
        mappings_sha256=mappings_sha256,
    )
    reviews_out: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    for review in sorted(
        mapping_payload["reviews"],
        key=lambda row: (row["claim_id"], row["action_kind"], row.get("action_id") or ""),
    ):
        claim = claims[str(review["claim_id"])]
        action_key = (
            str(review.get("action_id") or ""),
            str(review.get("expected_member_name") or ""),
        )
        action = actions.get(action_key) if review["action_kind"] == "roll_call_vote" else None
        if action is not None:
            require_strictly_later_action(
                claim_published_date=claim["published_date"],
                action_date=action["vote_date"],
                action_id=str(review["action_id"]),
            )
        action_search_scope = action_search_scopes.get(
            (str(review["claim_id"]), str(review["action_kind"])), {}
        )
        action_search_state = (
            "no_reviewed_action_found"
            if review["action_kind"] == "bounded_action_search"
            else "not_applicable"
        )
        validate_actor_link(
            review, action, actors, relationships, claim_actor_id
        )
        review_digest = sha256_bytes(canonical_json(review).encode("utf-8"))
        mapping_review_id = stable_id(
            "comparison-mapping-review",
            review_version,
            review["claim_id"],
            review["action_kind"],
            review.get("action_id"),
            review_digest,
        )
        search_scope_digest = (
            sha256_bytes(canonical_json(action_search_scope).encode("utf-8"))
            if review["action_kind"] == "bounded_action_search"
            else ""
        )
        comparison_id = stable_id(
            "promise-action-comparison",
            review["claim_id"],
            claim["promise_id"],
            review["action_kind"],
            review.get("action_id"),
            claim_actor_id,
            review.get("action_actor_id"),
            review.get("action_party_actor_id"),
            search_scope_digest,
        )
        review_record = {
            "mapping_review_id": mapping_review_id,
            "comparison_release_id": release_id,
            "claim_id": claim["claim_id"],
            "promise_id": claim["promise_id"],
            "action_kind": review["action_kind"],
            "action_id": review.get("action_id"),
            "action_search_state": action_search_state,
            "action_search_scope_json": canonical_json(action_search_scope),
            "claim_actor_id": claim_actor_id,
            "action_actor_id": review.get("action_actor_id"),
            "action_registry_actor_id": review.get("action_registry_actor_id"),
            "action_party_actor_id": review.get("action_party_actor_id"),
            "affiliation_relationship_id": review.get("affiliation_relationship_id"),
            "actor_link_state": review["actor_link_state"],
            "review_outcome": review["review_outcome"],
            "claim_direction": review["claim_direction"],
            "action_direction": review["action_direction"],
            "action_substance_state": review["action_substance_state"],
            "mapping_basis": review["mapping_basis"],
            "review_method": mapping_payload["review_method"],
            "review_version": review_version,
            "review_rationale": review["review_rationale"],
            "directional_countable": int(bool(review["directional_countable"])),
            "reviewed_at": reviewed_at,
            "created_at": reviewed_at,
        }
        reviews_out.append(review_record)
        action_title = None
        if action:
            action_title = action["expediente_text"] or action["title"]
        comparison = {
            "comparison_id": comparison_id,
            "comparison_release_id": release_id,
            "mapping_review_id": mapping_review_id,
            "claim_id": claim["claim_id"],
            "promise_id": claim["promise_id"],
            "claim_kind": claim["claim_kind"],
            "claim_actor_label": claim["attributed_actor_label"],
            "claim_actor_id": claim_actor_id,
            "claim_text": claim["exact_text"],
            "claim_page_start": claim["page_start"],
            "claim_page_end": claim["page_end"],
            "claim_published_date": claim["published_date"],
            "claim_review_status": claim["review_status"],
            "action_kind": review["action_kind"],
            "action_id": review.get("action_id"),
            "action_search_state": action_search_state,
            "action_search_scope_json": canonical_json(action_search_scope),
            "action_date": action["vote_date"] if action else None,
            "action_title": action_title,
            "action_member_name": action["member_name"] if action else None,
            "action_vote_choice": action["vote_choice"] if action else None,
            "action_actor_id": review.get("action_actor_id"),
            "action_party_actor_id": review.get("action_party_actor_id"),
            "action_source_id": action["source_id"] if action else None,
            "action_source_url": action["source_url"] if action else None,
            "comparison_status": review["review_outcome"],
            "directional_countable": int(bool(review["directional_countable"])),
            "public_summary": review["public_summary"],
            "caveat": review["caveat"],
            "decided_at": reviewed_at,
            "created_at": reviewed_at,
        }
        comparisons.append(comparison)
        claim_evidence = {
            "comparison_evidence_id": stable_id(
                "comparison-evidence", comparison_id, "claim", claim["claim_evidence_id"]
            ),
            "comparison_id": comparison_id,
            "evidence_side": "claim",
            "evidence_role": "primary",
            "source_id": claim["source_id"],
            "source_record_id": claim["source_record_id"] or claim["claim_evidence_id"],
            "source_url": claim["evidence_source_url"],
            "content_sha256": claim["document_sha256"],
            "exact_quote": claim["exact_quote"],
            "observed_at": claim["snapshot_date"],
            "metadata_json": canonical_json(
                {
                    "claim_evidence_id": claim["claim_evidence_id"],
                    "manifesto_document_id": claim["manifesto_document_id"],
                    "page_start": claim["page_start"],
                    "page_end": claim["page_end"],
                    "quote_sha256": claim["quote_sha256"],
                }
            ),
            "created_at": reviewed_at,
        }
        evidence_rows.append(claim_evidence)
        if action:
            action_record_digest = sha256_bytes(canonical_json(action).encode("utf-8"))
            evidence_rows.append(
                {
                    "comparison_evidence_id": stable_id(
                        "comparison-evidence",
                        comparison_id,
                        "action",
                        action["vote_event_id"],
                        action["member_vote_id"],
                    ),
                    "comparison_id": comparison_id,
                    "evidence_side": "action",
                    "evidence_role": "primary",
                    "source_id": action["source_id"],
                    "source_record_id": action["source_record_id"] or action["vote_event_id"],
                    "source_url": action["source_url"],
                    "content_sha256": action["source_record_sha256"] or action_record_digest,
                    "exact_quote": action_title,
                    "observed_at": action["source_snapshot_date"],
                    "metadata_json": canonical_json(
                        {
                            "vote_event_id": action["vote_event_id"],
                            "member_vote_id": action["member_vote_id"],
                            "member_name": action["member_name"],
                            "vote_choice": action["vote_choice"],
                            "group_code": action["group_code"],
                            "initiative_id": action["initiative_id"],
                            "initiative_url": action["initiative_url"],
                            "initiative_link_method": action["initiative_link_method"],
                            "initiative_link_confidence": action[
                                "initiative_link_confidence"
                            ],
                        }
                    ),
                    "created_at": reviewed_at,
                }
            )
            relationship = relationships[str(review["affiliation_relationship_id"])]
            actor_link_digest = sha256_bytes(
                canonical_json(
                    {
                        "rollcall_actor": actors[str(review["action_actor_id"])],
                        "registry_actor": actors[str(review["action_registry_actor_id"])],
                        "party_actor": actors[str(review["action_party_actor_id"])],
                        "relationship": relationship,
                    }
                ).encode("utf-8")
            )
            evidence_rows.append(
                {
                    "comparison_evidence_id": stable_id(
                        "comparison-evidence",
                        comparison_id,
                        "actor-link",
                        relationship["relationship_id"],
                    ),
                    "comparison_id": comparison_id,
                    "evidence_side": "actor_link",
                    "evidence_role": "identity",
                    "source_id": relationship["source_id"],
                    "source_record_id": relationship["source_record_id"]
                    or relationship["relationship_id"],
                    "source_url": relationship["source_url"],
                    "content_sha256": relationship["source_content_sha256"]
                    or actor_link_digest,
                    "exact_quote": (
                        f"{relationship['subject_label']} — afiliación oficial — "
                        f"{relationship['object_label']}"
                    ),
                    "observed_at": relationship["observed_at"],
                    "metadata_json": canonical_json(
                        {
                            "claim_actor_id": claim_actor_id,
                            "rollcall_actor_id": review["action_actor_id"],
                            "registry_actor_id": review["action_registry_actor_id"],
                            "party_actor_id": review["action_party_actor_id"],
                            "relationship_id": relationship["relationship_id"],
                            "valid_from": relationship["valid_from"],
                            "valid_to": relationship["valid_to"],
                            "resolution_state": relationship["resolution_state"],
                            "scope_note": "bounded_review_not_global_actor_merge",
                        }
                    ),
                    "created_at": reviewed_at,
                }
            )
        evidence_rows.append(
            {
                "comparison_evidence_id": stable_id(
                    "comparison-evidence", comparison_id, "mapping-review", review_digest
                ),
                "comparison_id": comparison_id,
                "evidence_side": "mapping_review",
                "evidence_role": "review",
                "source_id": "comparison_review",
                "source_record_id": mapping_review_id,
                "source_url": None,
                "content_sha256": review_digest,
                "exact_quote": review["review_rationale"],
                "observed_at": reviewed_at,
                "metadata_json": canonical_json(
                    {
                        "review_method": mapping_payload["review_method"],
                        "review_version": review_version,
                        "mapping_basis": review["mapping_basis"],
                        "claim_direction": review["claim_direction"],
                        "action_direction": review["action_direction"],
                            "action_substance_state": review["action_substance_state"],
                            "directional_countable": bool(review["directional_countable"]),
                            "reason_codes": list(review["reason_codes"]),
                            "material_differences": list(
                                review["material_differences"]
                            ),
                            "action_search_state": action_search_state,
                            "action_search_scope": action_search_scope,
                    }
                ),
                "created_at": reviewed_at,
            }
        )
    semantic_sha256 = sha256_bytes(
        canonical_json(
            {
                "reviews": reviews_out,
                "comparisons": comparisons,
                "evidence": evidence_rows,
            }
        ).encode("utf-8")
    )
    status_counts = dict(sorted(Counter(row["comparison_status"] for row in comparisons).items()))
    generated_at = f"{snapshot_date}T00:00:00Z"
    release = {
        "comparison_release_id": release_id,
        "schema_version": SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "mapping_review_version": review_version,
        "snapshot_date": snapshot_date,
        "generated_at": generated_at,
        "promises_source_scope_sha256": promises_digest,
        "actions_source_scope_sha256": actions_digest,
        "actor_source_scope_sha256": actors_digest,
        "actor_graph_release_id": actor_graph_release_id,
        "reviewed_mappings_sha256": mappings_sha256,
        "semantic_sha256": semantic_sha256,
        "comparison_count": len(comparisons),
        "evidence_count": len(evidence_rows),
        "status_counts_json": canonical_json(status_counts),
        "source_manifest_json": canonical_json(
            {
                "claim_ids": sorted(claims),
                "action_ids": sorted({key[0] for key in actions}),
                "actor_ids": sorted(actors),
                "actor_relationship_ids": sorted(relationships),
                "bounded_action_searches": [
                    action_search_scopes[key] for key in sorted(action_search_scopes)
                ],
                "input_releases": input_releases,
                "real_records_only": True,
            }
        ),
        "created_at": generated_at,
    }
    return release, reviews_out, comparisons, evidence_rows


def create_database(
    path: Path,
    schema: Path,
    release: dict[str, Any],
    reviews: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    batch_size: int,
) -> None:
    connection = open_db(path)
    try:
        apply_schema(connection, schema)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO comparison_releases (
              comparison_release_id, schema_version, method_version,
              mapping_review_version, snapshot_date, generated_at,
              promises_source_scope_sha256, actions_source_scope_sha256,
              actor_source_scope_sha256, actor_graph_release_id,
              reviewed_mappings_sha256, semantic_sha256, comparison_count,
              evidence_count, status_counts_json, source_manifest_json, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            tuple(release.values()),
        )
        review_columns = list(reviews[0])
        comparison_columns = list(comparisons[0])
        evidence_columns = list(evidence[0])
        execute_batched(
            connection,
            f"INSERT INTO comparison_mapping_reviews ({','.join(review_columns)}) "
            f"VALUES ({','.join('?' for _ in review_columns)})",
            [tuple(row[column] for column in review_columns) for row in reviews],
            batch_size,
        )
        execute_batched(
            connection,
            f"INSERT INTO promise_action_comparisons ({','.join(comparison_columns)}) "
            f"VALUES ({','.join('?' for _ in comparison_columns)})",
            [tuple(row[column] for column in comparison_columns) for row in comparisons],
            batch_size,
        )
        execute_batched(
            connection,
            f"INSERT INTO comparison_evidence ({','.join(evidence_columns)}) "
            f"VALUES ({','.join('?' for _ in evidence_columns)})",
            [tuple(row[column] for column in evidence_columns) for row in evidence],
            batch_size,
        )
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("comparison database foreign_key_check failed")
        connection.commit()
        connection.execute("PRAGMA optimize")
        connection.execute("PRAGMA journal_mode = DELETE")
    finally:
        connection.close()


def public_payload(
    release: dict[str, Any],
    reviews: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    mapping_payload: dict[str, Any],
) -> dict[str, Any]:
    reviews_by_id = {row["mapping_review_id"]: row for row in reviews}
    review_inputs = {
        (row["claim_id"], row["action_kind"], row.get("action_id")): row
        for row in mapping_payload["reviews"]
    }
    evidence_by_comparison: dict[str, list[dict[str, Any]]] = {}
    for row in evidence:
        public_evidence = {
            key: value
            for key, value in row.items()
            if key not in {"comparison_id", "created_at"}
        }
        public_evidence["metadata"] = json.loads(public_evidence.pop("metadata_json"))
        evidence_by_comparison.setdefault(row["comparison_id"], []).append(public_evidence)
    public_comparisons: list[dict[str, Any]] = []
    for row in comparisons:
        review = reviews_by_id[row["mapping_review_id"]]
        review_input = review_inputs[
            (row["claim_id"], row["action_kind"], row.get("action_id"))
        ]
        action_exists = row["action_kind"] == "roll_call_vote"
        mapping_state = {
            "ambiguous_mapping": "ambiguous",
            "not_comparable": "human_rejected",
            "insufficient_evidence": "needs_context",
            "changed_framing": "human_confirmed",
            "aligned": "human_confirmed",
            "conflicted": "human_confirmed",
        }[row["comparison_status"]]
        zero_component_reasons = {
            "identity_quality": (
                "La identidad y afiliación están revisadas solo para este enlace; "
                "el actor graph sigue source-scoped y no convierte el voto individual "
                "en posición colectiva del partido."
                if action_exists
                else "No existe actor de acción en la assessment acotada."
            ),
            "mapping_quality": "El mapping no está confirmado como mismo frame exacto.",
            "action_effect_quality": (
                "Falta efecto material exacto comparable o la acción es procesal."
                if action_exists
                else "No se localizó acción revisada dentro del alcance acotado."
            ),
            "coverage_quality": "No existe búsqueda exhaustiva y completa de todas las acciones y contraevidencias posibles.",
        }
        confidence_components = {
            "method": "categorical_gate_projection_v1",
            "aggregate_rule": "minimum_required_component",
            "aggregate_value": 0.0,
            "label": "sin_confianza_util",
            "components": {
                "assertion_quality": {
                    "value": 1.0,
                    "reason": "Claim rule_confirmed con cita primaria exacta y SHA-256 documental.",
                },
                "identity_quality": {
                    "value": 0.0,
                    "reason": zero_component_reasons["identity_quality"],
                },
                "mapping_quality": {
                    "value": 0.0,
                    "reason": zero_component_reasons["mapping_quality"],
                },
                "action_effect_quality": {
                    "value": 0.0,
                    "reason": zero_component_reasons["action_effect_quality"],
                },
                "evidence_quality": {
                    "value": 0.0,
                    "reason": "La evidencia oficial preservada no completa todos los eslabones necesarios para un veredicto fuerte.",
                },
                "coverage_quality": {
                    "value": 0.0,
                    "reason": zero_component_reasons["coverage_quality"],
                },
                "temporal_quality": {
                    "value": 1.0 if action_exists else 0.0,
                    "reason": (
                        "Assertion y acción tienen fechas observadas y la acción es posterior."
                        if action_exists
                        else "No existe fecha de acción porque no se localizó una acción revisada."
                    ),
                },
            },
        }
        comparison_evidence = sorted(
            evidence_by_comparison[row["comparison_id"]],
            key=lambda item: (
                item["evidence_side"],
                item["evidence_role"],
                item["comparison_evidence_id"],
            ),
        )
        action_search_scope = json.loads(row["action_search_scope_json"])
        public_comparisons.append(
            {
                "comparison_id": row["comparison_id"],
                "mapping_review_id": row["mapping_review_id"],
                "comparison_status": row["comparison_status"],
                "directional_countable": bool(row["directional_countable"]),
                "reason_codes": list(review_input["reason_codes"]),
                "public_summary": row["public_summary"],
                "caveat": row["caveat"],
                "claim": {
                    "claim_id": row["claim_id"],
                    "promise_id": row["promise_id"],
                    "claim_kind": row["claim_kind"],
                    "actor_id": row["claim_actor_id"],
                    "actor_label": row["claim_actor_label"],
                    "exact_text": row["claim_text"],
                    "page_start": row["claim_page_start"],
                    "page_end": row["claim_page_end"],
                    "published_date": row["claim_published_date"],
                    "review_status": row["claim_review_status"],
                    "responsible_capacity": "party_manifesto_publisher",
                },
                "action": None
                if not action_exists
                else {
                    "action_kind": row["action_kind"],
                    "action_id": row["action_id"],
                    "action_date": row["action_date"],
                    "title": row["action_title"],
                    "member_name": row["action_member_name"],
                    "vote_choice": row["action_vote_choice"],
                    "actor_id": row["action_actor_id"],
                    "party_actor_id": row["action_party_actor_id"],
                    "source_id": row["action_source_id"],
                    "source_url": row["action_source_url"],
                    "responsible_capacity": "individual_legislator_roll_call",
                },
                "action_search": {
                    "state": row["action_search_state"],
                    "scope": action_search_scope,
                },
                "actor_capacity": {
                    "assertion_capacity": "party_manifesto_publisher",
                    "action_capacity": (
                        "individual_legislator_roll_call" if action_exists else None
                    ),
                    "actor_link_state": review["actor_link_state"],
                    "attribution_unit": (
                        "party_assertion_vs_individual_representative_action"
                        if action_exists
                        else "party_assertion_bounded_action_search"
                    ),
                    "collective_party_position_inferred": False,
                    "global_cross_source_actor_merge_used": False,
                },
                "mapping_review": {
                    "mapping_review_id": review["mapping_review_id"],
                    "review_method": review["review_method"],
                    "review_version": review["review_version"],
                    "reviewed_at": review["reviewed_at"],
                    "actor_link_state": review["actor_link_state"],
                    "mapping_basis": review["mapping_basis"],
                    "claim_direction": review["claim_direction"],
                    "action_direction": review["action_direction"],
                    "action_substance_state": review["action_substance_state"],
                    "review_rationale": review["review_rationale"],
                    "mapping_state": mapping_state,
                    "reason_codes": list(review_input["reason_codes"]),
                    "material_differences": list(
                        review_input["material_differences"]
                    ),
                },
                "frame": {
                    "normalization_state": "reviewed_difference_only_not_fully_normalized",
                    "claim_source_text": row["claim_text"],
                    "action_source_text": row["action_title"],
                    "material_differences": list(
                        review_input["material_differences"]
                    ),
                    "same_exact_frame_confirmed": False,
                },
                "confidence": confidence_components,
                "coverage": {
                    "state": (
                        "searched_bounded_scope"
                        if row["action_kind"] == "bounded_action_search"
                        else "pair_review_only_not_exhaustive"
                    ),
                    "action_search_scope": action_search_scope,
                    "exhaustive": False,
                },
                "freshness": {
                    "tier": "stale",
                    "should_warn": True,
                    "as_of_date": release["snapshot_date"],
                    "action_corpus_cutoff": ACTION_COVERAGE_CUTOFF,
                    "ranking_eligible": False,
                    "reason": "El corte de votaciones usado termina el 2026-02-12 y no representa todas las acciones posteriores posibles.",
                },
                "counterevidence": {
                    "search_state": (
                        "searched_bounded_scope"
                        if row["action_kind"] == "bounded_action_search"
                        else "not_searched"
                    ),
                    "items": [],
                    "exhaustive": False,
                },
                "evidence": comparison_evidence,
                "evidence_links": sorted(
                    {
                        evidence_row["source_url"]
                        for evidence_row in comparison_evidence
                        if evidence_row.get("source_url")
                    }
                ),
            }
        )
    status_counts = json.loads(release["status_counts_json"])
    source_manifest = json.loads(release["source_manifest_json"])
    return {
        "schema_version": release["schema_version"],
        "release_id": release["comparison_release_id"],
        "snapshot_date": release["snapshot_date"],
        "as_of_date": release["snapshot_date"],
        "generated_at": release["generated_at"],
        "real_data_only": True,
        "synthetic_or_mock": False,
        "public_domain_information_policy": "retain_official_public_identity_exclude_only_secrets_private_session_state_and_workstation_traces",
        "methodology": {
            "method_version": release["method_version"],
            "mapping_review_version": release["mapping_review_version"],
            "contract_path": "docs/method/comparison-engine-v1.md",
            "directional_verdict_gate": (
                "aligned/conflicted require explicit exact-measure review, "
                "clear directions, substantive action, and primary evidence"
            ),
            "topic_overlap_is_proof": False,
        },
        "input_releases": source_manifest["input_releases"],
        "semantic_sha256": release["semantic_sha256"],
        "counts": {
            "comparisons_total": release["comparison_count"],
            "action_pairs_total": sum(
                1 for row in comparisons if row["action_kind"] == "roll_call_vote"
            ),
            "bounded_action_search_assessments_total": sum(
                1
                for row in comparisons
                if row["action_kind"] == "bounded_action_search"
            ),
            "strong_pairs_total": sum(
                status_counts.get(status, 0) for status in STRONG_STATUSES
            ),
            "unique_claims_total": len({row["claim_id"] for row in comparisons}),
            "evidence_total": release["evidence_count"],
        },
        "status_counts": status_counts,
        "coverage": {
            "state": "bounded_non_exhaustive",
            "strong_pairs_total": sum(
                status_counts.get(status, 0) for status in STRONG_STATUSES
            ),
            "ranking_state": "hidden",
            "ranking_reason": "Ranking oculto: la muestra comparable no alcanza el mínimo para una lectura responsable.",
            "bounded_action_searches": source_manifest.get(
                "bounded_action_searches", []
            ),
            "all_possible_actions_searched": False,
            "counterevidence_search_complete": False,
        },
        "freshness": {
            "tier": "stale",
            "should_warn": True,
            "generated_at": release["generated_at"],
            "as_of_date": release["snapshot_date"],
            "action_corpus_cutoff": ACTION_COVERAGE_CUTOFF,
            "ranking_eligible": False,
            "reason": "El corpus de acciones queda cortado el 2026-02-12; la release es reciente, pero su cobertura de acciones no lo es.",
        },
        "items": public_comparisons,
        "hash_contract": {
            "canonicalization": "UTF-8 JSON with sorted keys and compact separators",
            "semantic_sha256": release["semantic_sha256"],
            "reviewed_mappings_canonical_sha256": release[
                "reviewed_mappings_sha256"
            ],
            "full_artifact_sha256_location": "producer report; excluded from artifact to avoid a circular self-hash",
        },
        "scale_contract": {
            "source_lookup": "bulk indexed selection via json_each sets",
            "write_mode": "bounded executemany batches",
            "per_file_atomic_replacement": True,
            "artifact_set_atomic": False,
            "million_row_physical_run_proven": False,
        },
        "caveats": [
            "Este corte conserva solo cinco revisiones explícitas sobre registros oficiales reales.",
            "No hay comparaciones aligned o conflicted en v1; una coincidencia temática no autoriza ese veredicto.",
            "Un voto individual de una persona afiliada se atribuye como acción de esa representante, no como posición colectiva completa del partido.",
            "Insufficient evidence no significa incumplimiento; not comparable no significa neutralidad política.",
            "La sustitución coordinada del conjunto DB+JSON aún no es transaccional: cada archivo se reemplaza atómicamente, pero una caída entre reemplazos puede dejar releases mezcladas y exige validación antes de publicar.",
            "La arquitectura escribe por lotes, pero este corte pequeño no prueba todavía una ejecución física de un millón de comparaciones.",
        ],
    }


def temp_sibling(path: Path, suffix: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_path = tempfile.mkstemp(
        prefix=f".{path.name}.tmp-", suffix=suffix, dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(raw_path)
    temporary.unlink()
    return temporary


def peak_rss_mb() -> float:
    raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    divisor = 1024.0 * 1024.0 if sys.platform == "darwin" else 1024.0
    return round(raw / divisor, 3)


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        raise RuntimeError("--batch-size must be positive")
    if args.out_json.resolve() == args.public_out.resolve():
        raise RuntimeError("--out-json and --public-out must be distinct paths")
    mapping_payload, mapping_bytes = load_reviewed_mappings(args.reviewed_mappings)
    canonical_mapping_sha256 = sha256_bytes(
        canonical_json(mapping_payload).encode("utf-8")
    )
    input_file_facts = {
        "promises_db": input_file_fact(args.promises_db),
        "actions_db": input_file_fact(args.actions_db),
        "actor_graph_db": input_file_fact(args.actor_graph_db),
        "reviewed_mappings": input_file_fact(args.reviewed_mappings),
        "schema": input_file_fact(args.schema),
    }
    reviews = mapping_payload["reviews"]
    claim_ids = {str(row["claim_id"]) for row in reviews}
    with readonly_connection(args.promises_db) as promises_connection:
        claims = load_claims(promises_connection, claim_ids)
    with readonly_connection(args.actions_db) as actions_connection:
        actions, action_search_scopes = load_actions(actions_connection, reviews)
    with readonly_connection(args.actor_graph_db) as actor_connection:
        actors, relationships, actor_graph_release_id = load_actor_scope(
            actor_connection, mapping_payload
        )
    release, review_rows, comparison_rows, evidence_rows = materialize_records(
        mapping_payload,
        canonical_mapping_sha256,
        claims,
        actions,
        actors,
        relationships,
        action_search_scopes,
        actor_graph_release_id,
        args.snapshot_date,
    )
    payload = public_payload(
        release,
        review_rows,
        comparison_rows,
        evidence_rows,
        mapping_payload,
    )
    payload_bytes = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    temporary_db = temp_sibling(args.out_db, ".db")
    temporary_json = temp_sibling(args.out_json, ".json")
    temporary_public = temp_sibling(args.public_out, ".json")
    temporary_paths = (temporary_db, temporary_json, temporary_public)
    try:
        create_database(
            temporary_db,
            args.schema,
            release,
            review_rows,
            comparison_rows,
            evidence_rows,
            args.batch_size,
        )
        temporary_json.write_bytes(payload_bytes)
        temporary_public.write_bytes(payload_bytes)
        if temporary_json.read_bytes() != temporary_public.read_bytes():
            raise RuntimeError("published/public comparison bytes diverged before promotion")
        for output in (args.out_db, args.out_json, args.public_out):
            Path(f"{output}-wal").unlink(missing_ok=True)
            Path(f"{output}-shm").unlink(missing_ok=True)
        os.replace(temporary_db, args.out_db)
        os.replace(temporary_json, args.out_json)
        os.replace(temporary_public, args.public_out)
    finally:
        for path in temporary_paths:
            path.unlink(missing_ok=True)
            Path(f"{path}-wal").unlink(missing_ok=True)
            Path(f"{path}-shm").unlink(missing_ok=True)
    result = {
        "status": "ok",
        "comparison_release_id": release["comparison_release_id"],
        "semantic_sha256": release["semantic_sha256"],
        "comparison_count": release["comparison_count"],
        "evidence_count": release["evidence_count"],
        "status_counts": json.loads(release["status_counts_json"]),
        "batch_size": args.batch_size,
        "out_db": report_path(args.out_db),
        "out_db_bytes": args.out_db.stat().st_size,
        "out_db_sha256": sha256_file(args.out_db),
        "out_json": report_path(args.out_json),
        "public_out": report_path(args.public_out),
        "json_bytes": len(payload_bytes),
        "json_sha256": sha256_bytes(payload_bytes),
        "reviewed_mappings_canonical_sha256": canonical_mapping_sha256,
        "reviewed_mappings_file_sha256": sha256_bytes(mapping_bytes),
        "input_file_facts": input_file_facts,
        "byte_identical_public_copy": args.out_json.read_bytes()
        == args.public_out.read_bytes(),
        "million_row_physical_run_proven": False,
        "peak_rss_mb": peak_rss_mb(),
        "real_data_only": True,
        "synthetic_or_mock": False,
        "artifact_set_atomic": False,
        "per_file_atomic_replacement": True,
        "bounded_action_searches": payload["coverage"][
            "bounded_action_searches"
        ],
        "input_scope_sha256": payload["input_releases"],
        "report_out": report_path(args.report_out),
    }
    report_payload = {
        "schema_version": "promise_action_comparison_materialization_report_v1",
        "status": "ok",
        **result,
    }
    report_bytes = (
        json.dumps(report_payload, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    ).encode("utf-8")
    temporary_report = temp_sibling(args.report_out, ".json")
    try:
        temporary_report.write_bytes(report_bytes)
        os.replace(temporary_report, args.report_out)
    finally:
        temporary_report.unlink(missing_ok=True)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
