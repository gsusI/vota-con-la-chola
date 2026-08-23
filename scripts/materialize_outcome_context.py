#!/usr/bin/env python3
"""Materialize a real-only C0/L1 outcome-context candidate bundle.

This producer intentionally creates no human review, release, membership, or
public artifact. It replays the four bounded source closures before writing one
release-independent candidate version and its complete evidence references.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import shutil
import sqlite3
import sys
import tempfile
import time
from collections import Counter
from contextlib import closing
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "outcome_context_candidate_bundle_v1"
METHOD_VERSION = "outcome_linking_v1"
DEFAULT_GENERATED_AT = "2026-08-20T00:00:00Z"
DEFAULT_SCHEMA = REPO_ROOT / "etl/load/sqlite_schema.sql"
DEFAULT_MANUAL_INPUT = (
    REPO_ROOT / "etl/data/manual/outcome_links/reviewed_links_v1.json"
)
DEFAULT_ACTIONS_DB = REPO_ROOT / "etl/data/staging/politicos-es.db"
DEFAULT_INDICATOR_DB = (
    REPO_ROOT / "etl/data/staging/indicators-eurostat-gdp-mvp.db"
)
DEFAULT_ACTOR_DB = REPO_ROOT / "etl/data/staging/actor-graph-v1.db"
DEFAULT_OUT_ROOT = REPO_ROOT / "etl/data/staging/outcome-context-candidates-v1"
DEFAULT_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/"
    "outcome-context-materialization.json"
)
SCHEMA_BEGIN = "-- BEGIN OUTCOME LINKING V1 SCHEMA"
SCHEMA_END = "-- END OUTCOME LINKING V1 SCHEMA"
ROLE_RANK = {"pre": 0, "overlap_excluded": 1, "post": 2}
OUTCOME_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "outcome_links": (
        "outcome_link_id", "identity_contract_version", "link_kind", "action_id",
        "indicator_id", "stable_series_key", "geography_code", "geography_level",
        "geography_system", "identity_sha256", "identity_canonical_bytes",
        "identity_preimage_json", "created_at",
    ),
    "outcome_link_versions": (
        "outcome_link_version_id", "outcome_link_id", "version_identity_sha256",
        "version_identity_canonical_bytes", "identity_contract_version", "method_version",
        "evidence_package_kind", "version_state", "evidence_level", "candidate_status",
        "machine_audit_state", "human_review_required", "human_review_completed",
        "published", "directional_countable", "ranking_eligible", "action_id",
        "action_occurred_at", "action_source_id", "action_source_record_id",
        "action_source_snapshot_date", "action_source_record_content_sha256",
        "initiative_id", "initiative_source_id", "initiative_source_record_id",
        "initiative_source_record_content_sha256", "original_vote_xml_capture_state",
        "original_vote_xml_content_sha256", "indicator_id", "indicator_release_id",
        "indicator_series_version_id", "indicator_source_content_sha256",
        "action_scope_sha256", "action_scope_kind", "indicator_scope_sha256",
        "indicator_scope_kind", "actor_reference_scope_sha256",
        "actor_reference_scope_kind", "combined_scope_sha256", "combined_scope_kind",
        "participant_count", "participant_source_projection_sha256",
        "participant_export_projection_sha256", "actor_graph_release_id",
        "actor_reference_projection_sha256", "actor_reference_label_mismatch_count",
        "version_identity_preimage_json", "action_json", "participant_contract_json",
        "indicator_json", "temporal_assessment_json", "semantic_assessment_json",
        "geography_assessment_json", "calculation_json", "claim_policy_json",
        "reason_codes_json", "limitations_json", "reader_wording_json",
        "supersedes_outcome_link_version_id", "created_at",
    ),
    "outcome_link_reviews": (
        "outcome_link_review_version_id", "outcome_link_version_id",
        "review_identity_sha256", "review_identity_contract_version", "reviewer_public_id",
        "reviewed_at", "review_method", "semantic_decision", "geography_decision",
        "level_decision", "evidence_examined_json", "reason_codes_json", "rationale",
        "claim_policy_json", "reader_wording_json", "signoff",
        "review_identity_preimage_json", "supersedes_review_version_id",
    ),
    "outcome_link_releases": (
        "outcome_link_release_id", "release_identity_contract_version", "schema_version",
        "method_version", "config_sha256", "as_of_date", "source_release_roots_json",
        "scope_closure_root_sha256", "membership_semantic_root_sha256", "member_count",
        "review_count_by_state_json", "level_counts_json",
        "previous_outcome_link_release_id", "release_descriptor_sha256",
        "release_descriptor_json",
    ),
    "outcome_link_release_memberships": (
        "outcome_link_release_membership_id", "outcome_link_release_id",
        "outcome_link_version_id", "outcome_link_review_version_id",
        "membership_identity_sha256", "membership_state", "selected_level",
        "selected_decision", "selected_semantic_decision", "selected_geography_decision",
        "inclusion_reason", "publication_flag", "membership_identity_preimage_json",
    ),
    "outcome_link_observation_refs": (
        "outcome_link_observation_ref_id", "outcome_link_version_id", "identity_sha256",
        "identity_contract_version", "role", "exclusion_reason", "indicator_id",
        "indicator_release_id", "indicator_series_version_id",
        "indicator_observation_version_id", "indicator_observation_evidence_id",
        "period_label", "period_start", "period_end", "value_decimal", "value_text",
        "source_status_code", "uncertainty_state", "revision_ordinal", "revision_state",
        "source_content_sha256", "raw_path", "value_json_pointer", "status_json_pointer",
        "identity_preimage_json",
    ),
    "outcome_link_participant_refs": (
        "outcome_link_participant_ref_id", "outcome_link_version_id",
        "participant_row_semantic_sha256", "identity_contract_version", "action_id", "seat",
        "official_member_name", "upstream_person_id", "official_group_code",
        "official_vote_choice", "actor_graph_release_id", "actor_id",
        "actor_node_version_id", "actor_canonical_label", "actor_identity_state",
        "actor_provenance_state", "actor_source_record_id", "actor_source_url",
        "actor_source_content_sha256", "vote_source_id", "vote_source_url",
        "vote_source_snapshot_date", "vote_source_record_id",
        "vote_source_record_content_sha256", "vote_source_locator",
        "official_label_authoritative", "actor_label_mismatch", "identity_preimage_json",
    ),
    "outcome_link_evidence": (
        "outcome_link_evidence_id", "outcome_link_version_id", "identity_sha256",
        "identity_contract_version", "evidence_role", "entity_version_id", "source_id",
        "source_record_id", "official_url", "content_sha256", "bytes", "raw_path",
        "locator", "capture_state", "normalized_record_is_original_bytes",
        "identity_preimage_json",
    ),
    "outcome_link_scope_closures": (
        "scope_closure_sha256", "scope_kind", "closure_contract_version",
        "canonical_preimage_json", "canonical_bytes", "bounded_scope_complete",
        "all_possible_actions_searched", "all_possible_indicators_searched",
        "all_possible_actor_sources_searched",
        "all_possible_action_indicator_pairs_searched",
    ),
}
APPEND_ONLY_TRIGGER_NAMES = {
    f"trg_{table}_no_{operation}"
    for table in OUTCOME_TABLE_COLUMNS
    for operation in ("update", "delete")
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the bounded, real-only outcome-context candidate bundle; "
            "never creates a review, release, membership, or publication."
        )
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--manual-input", type=Path, default=DEFAULT_MANUAL_INPUT)
    parser.add_argument("--actions-db", type=Path, default=DEFAULT_ACTIONS_DB)
    parser.add_argument("--indicator-db", type=Path, default=DEFAULT_INDICATOR_DB)
    parser.add_argument("--actor-db", type=Path, default=DEFAULT_ACTOR_DB)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--batch-size", type=int, default=1_000)
    return parser.parse_args()


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def report_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def file_fact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"required file missing: {report_path(path)}")
    return {
        "path": report_path(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def stable_source_file_fact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"real source database missing: {report_path(path)}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(handle.fileno())
    path_after = path.stat()
    before_identity = (
        before.st_dev, before.st_ino, before.st_size,
        before.st_mtime_ns, before.st_ctime_ns,
    )
    after_identity = (
        after.st_dev, after.st_ino, after.st_size,
        after.st_mtime_ns, after.st_ctime_ns,
    )
    path_identity = (
        path_after.st_dev, path_after.st_ino, path_after.st_size,
        path_after.st_mtime_ns, path_after.st_ctime_ns,
    )
    if before_identity != after_identity or after_identity != path_identity:
        raise RuntimeError(f"source file changed while hashing: {report_path(path)}")
    stat_identity_sha256 = sha256_bytes(
        canonical_bytes(
            {
                "device": before.st_dev,
                "inode": before.st_ino,
                "size": before.st_size,
                "mtime_ns": before.st_mtime_ns,
                "ctime_ns": before.st_ctime_ns,
            }
        )
    )
    wal = Path(f"{path}-wal")
    wal_bytes = wal.stat().st_size if wal.exists() else 0
    if wal_bytes:
        raise RuntimeError(
            f"source database has a non-empty WAL during fingerprint: {report_path(path)}"
        )
    return {
        "path": report_path(path),
        "bytes": before.st_size,
        "sha256": digest.hexdigest(),
        "stat_identity_sha256": stat_identity_sha256,
        "wal_bytes": wal_bytes,
    }


def source_database_facts(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    return {key: stable_source_file_fact(path) for key, path in paths.items()}


def assert_source_facts_stable(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]
) -> None:
    assert_equal(set(after), set(before), "source fingerprint database keys")
    for key in sorted(before):
        assert_equal(after[key], before[key], f"{key} pre/post source fingerprint")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def reject_nonfinite(value: str) -> None:
    raise ValueError(f"non-finite JSON number forbidden: {value}")


def load_strict_json(path: Path) -> tuple[dict[str, Any], bytes]:
    if not path.is_file():
        raise RuntimeError(f"manual input missing: {report_path(path)}")
    raw = path.read_bytes()
    payload = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_nonfinite,
    )
    if not isinstance(payload, dict):
        raise RuntimeError("manual input must be one JSON object")
    return payload, raw


def readonly_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise RuntimeError(f"real source database missing: {report_path(path)}")
    wal = Path(f"{path}-wal")
    if wal.exists() and wal.stat().st_size:
        raise RuntimeError(
            f"source database has a non-empty WAL; checkpoint before immutable read: "
            f"{report_path(path)}"
        )
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("BEGIN")
    connection.execute("SELECT COUNT(*) FROM sqlite_schema").fetchone()
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


def assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise RuntimeError(f"{label} drift: expected {expected!r}, got {actual!r}")


def validate_digest(value: Any, label: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise RuntimeError(f"{label} must be a lowercase SHA-256")
    return text


def validate_manual_contract(payload: dict[str, Any], generated_at: str) -> dict[str, Any]:
    assert_equal(
        payload.get("format_version"),
        "outcome_link_preproduction_candidate_input_v1",
        "manual format_version",
    )
    assert_equal(payload.get("method_version"), METHOD_VERSION, "method_version")
    assert_equal(payload.get("generated_at"), generated_at, "generated_at")
    assert_equal(
        payload.get("generated_at_source"),
        "externally_supplied_deterministic_build_parameter",
        "generated_at_source",
    )
    assert_equal(
        payload.get("generated_at_identity_authority"),
        False,
        "generated_at_identity_authority",
    )
    scope_truth = payload.get("scope_truth")
    policy = payload.get("policy")
    candidates = payload.get("candidates")
    if not isinstance(scope_truth, dict) or not isinstance(policy, dict):
        raise RuntimeError("manual input scope_truth/policy must be objects")
    if not isinstance(candidates, list) or len(candidates) != 1:
        raise RuntimeError("C0/L1 producer requires exactly one real candidate")
    expected_scope = {
        "scale_stage": "C0",
        "bounded_candidate_pairs": 20,
        "machine_audited_preproduction_candidates": 1,
        "human_reviewed_pairs": 0,
        "published_links": 0,
        "bounded_scope_complete": True,
        "all_possible_actions_searched": False,
        "all_possible_indicators_searched": False,
        "all_possible_action_indicator_pairs_searched": False,
    }
    for key, expected in expected_scope.items():
        assert_equal(scope_truth.get(key), expected, f"scope_truth.{key}")
    assert_equal(policy.get("real_data_only"), True, "policy.real_data_only")
    assert_equal(policy.get("synthetic_or_mock_rows"), 0, "synthetic_or_mock_rows")
    for key, expected in {
        "statistical_association_claim": "none",
        "causal_claim": "none",
        "effect_estimate": "not_computed",
        "political_merit_or_blame": "not_assessed",
        "success_or_failure_assessment": "not_assessed",
        "corruption_assessment": "not_assessed",
        "directional_countable": False,
        "ranking_eligible": False,
    }.items():
        assert_equal(policy.get(key), expected, f"policy.{key}")
    candidate = candidates[0]
    for key, expected in {
        "version_state": "preproduction_candidate",
        "evidence_level": "L1",
        "candidate_status": "pending_human_review",
        "machine_audit_state": "machine_validated",
        "human_review_required": True,
        "human_review_completed": False,
        "published": False,
        "directional_countable": False,
        "ranking_eligible": False,
        "supersedes_outcome_link_version_id": None,
    }.items():
        assert_equal(candidate.get(key), expected, f"candidate.{key}")
    review = candidate.get("review")
    membership = candidate.get("release_membership")
    if not isinstance(review, dict) or not isinstance(membership, dict):
        raise RuntimeError("candidate review/release_membership must be objects")
    expected_null_review = {
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
    }
    assert_equal(review, expected_null_review, "candidate.review")
    assert_equal(membership.get("outcome_link_release_id"), None, "release id")
    assert_equal(membership.get("membership_id"), None, "membership id")
    assert_equal(membership.get("membership_state"), "not_released", "membership state")
    assert_equal(membership.get("published"), False, "membership publication")
    return candidate


def validate_canonical_identity(
    preimage: dict[str, Any],
    expected_bytes: int,
    expected_sha256: str,
    expected_id: str | None,
    id_prefix: str | None,
    label: str,
) -> None:
    encoded = canonical_bytes(preimage)
    digest = sha256_bytes(encoded)
    assert_equal(len(encoded), expected_bytes, f"{label} canonical bytes")
    assert_equal(digest, expected_sha256, f"{label} SHA-256")
    if expected_id is not None and id_prefix is not None:
        assert_equal(expected_id, f"{id_prefix}{digest[:24]}", f"{label} ID")


def validate_closures(payload: dict[str, Any]) -> list[dict[str, Any]]:
    selection = payload.get("selection_closure")
    if not isinstance(selection, dict):
        raise RuntimeError("selection_closure must be an object")
    assert_equal(
        selection.get("physical_database_hashes_are_identity_inputs"),
        False,
        "closure physical DB identity flag",
    )
    mapping = (
        ("action_scope", "action"),
        ("indicator_scope", "indicator"),
        ("actor_reference_scope", "actor_reference"),
        ("combined_scope", "combined"),
    )
    rows: list[dict[str, Any]] = []
    for source_key, scope_kind in mapping:
        closure = selection.get(source_key)
        if not isinstance(closure, dict) or not isinstance(closure.get("preimage"), dict):
            raise RuntimeError(f"invalid {source_key}")
        validate_canonical_identity(
            closure["preimage"],
            int(closure["canonical_bytes"]),
            validate_digest(closure["sha256"], f"{source_key}.sha256"),
            None,
            None,
            source_key,
        )
        preimage = closure["preimage"]
        rows.append(
            {
                "scope_closure_sha256": closure["sha256"],
                "scope_kind": scope_kind,
                "closure_contract_version": preimage["closure_contract_version"],
                "canonical_preimage": preimage,
                "canonical_bytes": closure["canonical_bytes"],
                "bounded_scope_complete": bool(preimage["bounded_scope_complete"]),
                "all_possible_actions_searched": bool(
                    preimage.get("all_possible_actions_searched", False)
                ),
                "all_possible_indicators_searched": bool(
                    preimage.get("all_possible_indicators_searched", False)
                ),
                "all_possible_actor_sources_searched": bool(
                    preimage.get("all_possible_actor_sources_searched", False)
                ),
                "all_possible_action_indicator_pairs_searched": bool(
                    preimage.get("all_possible_action_indicator_pairs_searched", False)
                ),
            }
        )
    return rows


def verify_query_hash(sql: str, expected: str, label: str) -> None:
    assert_equal(sha256_bytes(sql.encode("utf-8")), expected, f"{label} SQL SHA-256")


def load_action_scope(
    connection: sqlite3.Connection,
    payload: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    closure = payload["selection_closure"]["action_scope"]["preimage"]
    query = closure["query_contract"]
    verify_query_hash(query["sql_utf8"], query["sql_sha256"], "action closure")
    raw_rows = connection.execute(query["sql_utf8"], query["parameters"]).fetchall()
    projected: list[dict[str, Any]] = []
    for raw in raw_rows:
        row = dict(raw)
        projected.append(
            {
                "action_id": row["vote_event_id"],
                "initiative_id": row["initiative_id"],
                "link_method": row["link_method"],
                "link_confidence_decimal": format(row["confidence"], ".1f"),
                "link_evidence": json.loads(
                    row["evidence_json"], object_pairs_hook=reject_duplicate_keys
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
        )
    encoded = canonical_bytes(projected)
    assert_equal(len(projected), closure["candidate_count"], "action candidate count")
    assert_equal(len(encoded), closure["candidate_universe_canonical_bytes"], "action universe bytes")
    assert_equal(sha256_bytes(encoded), closure["candidate_universe_sha256"], "action universe SHA-256")
    selected = [
        row
        for row in projected
        if row[closure["selection_predicate"]["field"]]
        == closure["selection_predicate"]["value"]
    ]
    assert_equal(len(selected), closure["selected_count"], "selected action count")
    assert_equal(
        [row["action_id"] for row in selected],
        closure["selected_action_ids"],
        "selected action IDs",
    )
    action = candidate["action"]
    assert_equal(selected[0]["action_id"], action["action_id"], "candidate action ID")
    assert_equal(selected[0]["source_record_content_sha256"], action["normalized_source_record_payload_sha256"], "vote source content hash")
    for selected_key, action_key in (
        ("vote_date", "action_occurred_at"),
        ("legislature", "legislature"),
        ("session_number", "session_number"),
        ("vote_number", "vote_number"),
        ("title", "vote_title"),
        ("initiative_id", "initiative_id"),
        ("link_method", "initiative_link_method"),
        ("link_confidence_decimal", "initiative_link_confidence_decimal"),
        ("link_evidence", "initiative_link_evidence"),
        ("source_id", "source_id"),
        ("source_record_id", "source_record_id"),
        ("source_snapshot_date", "source_snapshot_date"),
    ):
        assert_equal(
            selected[0][selected_key], action[action_key], f"selected action {action_key}"
        )
    assert_equal(
        selected[0]["totals"]["present"],
        action["totals"]["normalized_derived_counts"]["present"],
        "selected action present total",
    )
    for selected_key, action_key in (
        ("yes", "yes"),
        ("no", "no"),
        ("abstain", "abstain"),
        ("not_voting", "not_voting"),
    ):
        assert_equal(
            selected[0]["totals"][selected_key],
            action["totals"]["normalized_derived_counts"][action_key],
            f"selected action {action_key} total",
        )
    assert_equal(
        selected[0]["totals"]["absent_normalized"],
        action["totals"]["absent_normalized_database_column"],
        "selected action normalized absent",
    )
    assert_equal(
        selected[0]["totals"]["absent_source_record"],
        action["totals"]["absent_source_record_payload"],
        "selected action source absent",
    )
    source_pairs = (
        (
            action["source_id"],
            action["source_record_id"],
            action["source_snapshot_date"],
            action["normalized_source_record_payload_sha256"],
            action["normalized_source_record_payload_bytes"],
            action["source_record_pk_audit_locator"],
        ),
        (
            action["initiative_source_id"],
            action["initiative_source_record_id"],
            action["initiative_source_snapshot_date"],
            action["initiative_normalized_source_record_payload_sha256"],
            action["initiative_normalized_source_record_payload_bytes"],
            action["initiative_source_record_pk_audit_locator"],
        ),
    )
    source_rows = connection.execute(
        """
        SELECT source_record_pk, source_id, source_record_id,
               source_snapshot_date, content_sha256, raw_payload
        FROM source_records
        WHERE (source_id, source_record_id, source_snapshot_date) IN (
          SELECT json_extract(value, '$[0]'), json_extract(value, '$[1]'),
                 json_extract(value, '$[2]')
          FROM json_each(?)
        )
        ORDER BY source_id, source_record_id, source_snapshot_date
        """,
        (canonical_json([list(row[:3]) for row in source_pairs]),),
    ).fetchall()
    by_key = {
        (str(row["source_id"]), str(row["source_record_id"]), str(row["source_snapshot_date"])): dict(row)
        for row in source_rows
    }
    verified: list[dict[str, Any]] = []
    for source_id, record_id, snapshot, digest, byte_count, audit_pk in source_pairs:
        key = (source_id, record_id, snapshot)
        row = by_key.get(key)
        if row is None:
            raise RuntimeError(f"pinned source record missing: {key}")
        raw_bytes = row["raw_payload"].encode("utf-8")
        assert_equal(row["source_record_pk"], audit_pk, f"{source_id} audit PK")
        assert_equal(row["content_sha256"], digest, f"{source_id} stored hash")
        assert_equal(sha256_bytes(raw_bytes), digest, f"{source_id} payload hash")
        assert_equal(len(raw_bytes), byte_count, f"{source_id} payload bytes")
        verified.append(row)
    vote_record = next(row for row in verified if row["source_id"] == action["source_id"])
    initiative_record = next(
        row for row in verified if row["source_id"] == action["initiative_source_id"]
    )
    vote_payload = json.loads(
        vote_record["raw_payload"], object_pairs_hook=reject_duplicate_keys
    )
    for raw_key, action_key in (
        ("vote_file_url", "official_vote_file_url"),
        ("session_vote_file_url", "official_session_file_url"),
        ("vote_url", "official_vote_page_url"),
        ("iniciativa_url", "official_initiative_url"),
        ("iniciativa_title", "initiative_title"),
    ):
        assert_equal(vote_payload.get(raw_key), action[action_key], f"vote payload {raw_key}")
    assert_equal(
        f"{vote_payload.get('tipo_expediente')}/{vote_payload.get('numero_expediente')}",
        action["initiative_expediente"],
        "vote payload initiative expediente",
    )
    return projected, vote_record, initiative_record


def load_indicator_scope(
    connection: sqlite3.Connection,
    payload: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    closure = payload["selection_closure"]["indicator_scope"]["preimage"]
    query = closure["query_contract"]
    for key in (
        "definitions_and_releases",
        "series",
        "observations",
    ):
        verify_query_hash(
            query[f"{key}_sql_utf8"], query[f"{key}_sql_sha256"], f"indicator {key}"
        )
    definitions = [
        dict(row)
        for row in connection.execute(
            query["definitions_and_releases_sql_utf8"],
            query["definitions_and_releases_parameters"],
        ).fetchall()
    ]
    definition_bytes = canonical_bytes(definitions)
    assert_equal(len(definitions), closure["definitions_and_releases_count"], "indicator definitions count")
    assert_equal(len(definition_bytes), closure["definitions_and_releases_canonical_bytes"], "indicator definitions bytes")
    assert_equal(sha256_bytes(definition_bytes), closure["definitions_and_releases_sha256"], "indicator definitions SHA-256")
    series: list[dict[str, Any]] = []
    for raw in connection.execute(
        query["series_sql_utf8"], query["series_parameters"]
    ).fetchall():
        row = dict(raw)
        row["dimensions"] = json.loads(
            row.pop("dimensions_json"), object_pairs_hook=reject_duplicate_keys
        )
        series.append(row)
    series_bytes = canonical_bytes(series)
    assert_equal(len(series), closure["series_count"], "indicator series count")
    assert_equal(len(series_bytes), closure["series_universe_canonical_bytes"], "indicator series bytes")
    assert_equal(sha256_bytes(series_bytes), closure["series_universe_sha256"], "indicator series SHA-256")
    geography = closure["geography_filter"]
    eligible = [
        row
        for row in series
        if row["geography_code"] == geography["geography_code"]
        and row["geography_level"] == geography["geography_level"]
    ]
    eligible_bytes = canonical_bytes(eligible)
    assert_equal(len(eligible), closure["geography_eligible_series_count"], "eligible series count")
    assert_equal(len(eligible_bytes), closure["geography_eligible_series_canonical_bytes"], "eligible series bytes")
    assert_equal(sha256_bytes(eligible_bytes), closure["geography_eligible_series_sha256"], "eligible series SHA-256")
    action_date = closure["action_date"]
    observations: list[dict[str, Any]] = []
    for raw in connection.execute(
        query["observations_sql_utf8"], query["observation_parameters"]
    ).fetchall():
        row = dict(raw)
        if row["period_end"] < action_date:
            row["temporal_role"] = "strict_pre_eligible"
        elif row["period_start"] > action_date:
            row["temporal_role"] = "strict_post_eligible"
        else:
            row["temporal_role"] = "overlap_excluded"
        observations.append(row)
    observation_bytes = canonical_bytes(observations)
    assert_equal(len(observations), closure["observation_count"], "indicator observation count")
    assert_equal(len(observation_bytes), closure["observation_role_universe_canonical_bytes"], "indicator observations bytes")
    assert_equal(sha256_bytes(observation_bytes), closure["observation_role_universe_sha256"], "indicator observations SHA-256")
    role_counts = {role: 0 for role in ("strict_pre_eligible", "overlap_excluded", "strict_post_eligible")}
    for row in observations:
        role_counts[row["temporal_role"]] += 1
    for role, field in (
        ("strict_pre_eligible", "strict_pre_eligible_count"),
        ("overlap_excluded", "overlap_excluded_count"),
        ("strict_post_eligible", "strict_post_eligible_count"),
    ):
        assert_equal(role_counts[role], closure[field], f"{role} count")
    selected = candidate["temporal_assessment"]["selected_observations"]
    selected_rows = [
        ("pre", selected["pre"]),
        *(("overlap_excluded", row) for row in selected["overlap_excluded"]),
        ("post", selected["post"]),
    ]
    by_id = {str(row["indicator_observation_version_id"]): row for row in observations}
    source_role_by_selected_role = {
        "pre": "strict_pre_eligible",
        "overlap_excluded": "overlap_excluded",
        "post": "strict_post_eligible",
    }
    for expected_role, selected_row in selected_rows:
        assert_equal(selected_row.get("role"), expected_role, "selected observation role")
        source_row = by_id.get(str(selected_row["indicator_observation_version_id"]))
        if source_row is None:
            raise RuntimeError("selected indicator observation missing from pinned release")
        assert_equal(
            source_row["temporal_role"], source_role_by_selected_role[expected_role],
            f"selected {expected_role} source temporal role",
        )
        if expected_role == "overlap_excluded":
            if not selected_row.get("exclusion_reason"):
                raise RuntimeError("overlap-excluded observation requires an exclusion reason")
        else:
            assert_equal(selected_row.get("exclusion_reason"), None, f"selected {expected_role} exclusion reason")
        for key, value in selected_row.items():
            if key not in {"role", "exclusion_reason"}:
                assert_equal(source_row.get(key), value, f"selected observation {key}")
    assert_equal(
        definitions[0]["source_content_sha256"],
        candidate["indicator"]["source_content_sha256"],
        "indicator source content hash",
    )
    indicator = candidate["indicator"]
    for source_key, indicator_key in (
        ("source_id", "source_id"),
        ("dataset_code", "dataset_code"),
        ("indicator_id", "indicator_id"),
        ("indicator_code", "indicator_code"),
        ("frequency_code", "frequency_code"),
        ("unit_code", "unit_code"),
        ("methodology_version", "methodology_version"),
        ("revision_policy", "revision_policy"),
        ("indicator_release_id", "indicator_release_id"),
        ("source_snapshot_date", "source_snapshot_date"),
        ("source_updated_at", "source_updated_at"),
        ("source_url", "source_url"),
        ("source_bytes", "source_bytes"),
        ("comparison_state", "comparison_state"),
    ):
        assert_equal(
            definitions[0][source_key], indicator[indicator_key], f"indicator {indicator_key}"
        )
    selected_series = eligible[0]
    for source_key, indicator_key in (
        ("indicator_series_version_id", "indicator_series_version_id"),
        ("stable_series_key", "stable_series_key"),
        ("geography_code", "geography_code"),
        ("geography_name", "geography_name"),
        ("geography_system", "geography_system"),
        ("geography_level", "geography_level"),
        ("geography_version", "geography_version"),
        ("dimensions", "dimensions"),
    ):
        assert_equal(
            selected_series[source_key], indicator[indicator_key],
            f"indicator series {indicator_key}",
        )
    return observations, by_id


def rounded_fraction(value: Fraction, places: int) -> str:
    quantum = Decimal(1).scaleb(-places)
    with localcontext() as context:
        context.prec = max(100, len(str(abs(value.numerator))) + len(str(value.denominator)) + places + 20)
        decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
        return format(decimal_value.quantize(quantum, rounding=ROUND_HALF_EVEN), "f")


def rational_payload(value: Fraction, unit: str, places: int | None = None) -> dict[str, Any]:
    output: dict[str, Any] = {
        "numerator": str(value.numerator),
        "denominator": str(value.denominator),
        "unit": unit,
    }
    if places is not None:
        output.update(
            {
                "rounded_decimal": rounded_fraction(value, places),
                "rounded_decimal_places": places,
                "rounding_mode": "ROUND_HALF_EVEN",
            }
        )
    return output


def validate_exact_calculation(
    candidate: dict[str, Any], indicator_by_id: dict[str, dict[str, Any]]
) -> None:
    selected = candidate["temporal_assessment"]["selected_observations"]
    pre_row = indicator_by_id[str(selected["pre"]["indicator_observation_version_id"])]
    post_row = indicator_by_id[str(selected["post"]["indicator_observation_version_id"])]
    pre_text = pre_row["value_decimal"]
    post_text = post_row["value_decimal"]
    if pre_text is None or post_text is None:
        raise RuntimeError("two-point arithmetic requires real decimal pre/post observations")
    pre_decimal = Decimal(str(pre_text))
    post_decimal = Decimal(str(post_text))
    if not pre_decimal.is_finite() or not post_decimal.is_finite() or pre_decimal == 0:
        raise RuntimeError("two-point arithmetic requires finite values and non-zero pre value")
    pre_fraction = Fraction(pre_decimal)
    post_fraction = Fraction(post_decimal)
    difference = post_fraction - pre_fraction
    ratio = post_fraction / pre_fraction
    relative = difference / pre_fraction
    unit = candidate["indicator"]["unit_code"]
    expected = {
        "calculation_kind": "two_point_arithmetic_only",
        "pre_value_decimal": str(pre_text),
        "post_value_decimal": str(post_text),
        "absolute_difference": {
            **rational_payload(difference, unit),
            "exact_decimal": format(post_decimal - pre_decimal, "f"),
        },
        "post_to_pre_ratio": rational_payload(ratio, "ratio", 6),
        "relative_change": rational_payload(relative, "ratio", 6),
        "percent_change": rational_payload(relative * 100, "percent", 6),
        "basis_point_change": rational_payload(relative * 10_000, "basis_points", 6),
        "exact_rationals_authoritative": True,
        "rounded_decimals_authoritative": False,
        "statistical_test": "not_performed",
        "uncertainty_interval": "not_provided",
        "association_claim": "none",
        "causal_claim": "none",
        "effect_estimate": "not_computed",
    }
    assert_equal(candidate["calculation"], expected, "source-recomputed exact calculation")


def load_participant_scope(
    actions: sqlite3.Connection,
    actors: sqlite3.Connection,
    payload: dict[str, Any],
    candidate: dict[str, Any],
    vote_record: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    closure = payload["selection_closure"]["actor_reference_scope"]["preimage"]
    query = closure["query_contract"]
    verify_query_hash(query["participant_sql_utf8"], query["participant_sql_sha256"], "participant")
    verify_query_hash(query["actor_sql_utf8"], query["actor_sql_sha256"], "actor")
    participant_rows = [
        dict(row)
        for row in actions.execute(
            query["participant_sql_utf8"], query["participant_parameters"]
        ).fetchall()
    ]
    source_projection_bytes = canonical_bytes(participant_rows)
    participant_contract = candidate["participants"]
    assert_equal(len(participant_rows), participant_contract["records_total"], "participant count")
    assert_equal(len(source_projection_bytes), participant_contract["source_projection_canonical_bytes"], "participant source projection bytes")
    assert_equal(sha256_bytes(source_projection_bytes), participant_contract["source_projection_sha256"], "participant source projection SHA-256")
    actor_by_legacy: dict[str, dict[str, Any]] = {}
    for raw in actors.execute(query["actor_sql_utf8"], query["actor_parameters"]).fetchall():
        row = dict(raw)
        attributes = json.loads(
            row.pop("attributes_json"), object_pairs_hook=reject_duplicate_keys
        )
        legacy_person_id = attributes.get("legacy_person_id")
        if legacy_person_id is None:
            continue
        match_key = str(legacy_person_id)
        if match_key in actor_by_legacy:
            raise RuntimeError(f"ambiguous actor legacy_person_id: {match_key}")
        row["legacy_person_id"] = legacy_person_id
        actor_by_legacy[match_key] = row
    actor_projection: list[dict[str, Any]] = []
    export_projection: list[dict[str, Any]] = []
    raw_payload = json.loads(
        vote_record["raw_payload"], object_pairs_hook=reject_duplicate_keys
    )
    raw_members = raw_payload.get("member_votes")
    if not isinstance(raw_members, list):
        raise RuntimeError("vote source raw_payload.member_votes missing")
    raw_index: dict[tuple[str, str, str, str], int] = {}
    for index, member in enumerate(raw_members):
        key = (
            str(member.get("seat")),
            str(member.get("member_name")),
            str(member.get("group")),
            str(member.get("vote_choice")),
        )
        if key in raw_index:
            raise RuntimeError(f"ambiguous raw member vote locator: {key}")
        raw_index[key] = index
    for participant in participant_rows:
        match_key = str(participant["person_id"])
        actor = actor_by_legacy.get(match_key)
        if actor is None:
            raise RuntimeError(f"participant actor reference missing: {match_key}")
        raw_key = (
            str(participant["seat"]),
            str(participant["member_name"]),
            str(participant["group_code"]),
            str(participant["vote_choice"]),
        )
        if raw_key not in raw_index:
            raise RuntimeError(f"exact raw participant locator missing: {raw_key}")
        actor_projection.append(
            {
                "seat": participant["seat"],
                "official_member_name": participant["member_name"],
                "legacy_person_id": actor["legacy_person_id"],
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
        export_projection.append(
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
                "vote_source_record_id": candidate["action"]["source_record_id"],
                "vote_source_record_content_sha256": candidate["action"]["normalized_source_record_payload_sha256"],
                "vote_source_locator": f"/member_votes/{raw_index[raw_key]}",
                "vote_source_id": participant["source_id"],
                "vote_source_url": participant["source_url"],
                "vote_source_snapshot_date": participant["source_snapshot_date"],
            }
        )
    actor_bytes = canonical_bytes(actor_projection)
    export_bytes = canonical_bytes(export_projection)
    assert_equal(len(actor_projection), closure["actor_reference_count"], "actor reference count")
    assert_equal(len(actor_bytes), closure["actor_reference_canonical_bytes"], "actor reference bytes")
    assert_equal(sha256_bytes(actor_bytes), closure["actor_reference_sha256"], "actor reference SHA-256")
    assert_equal(len(export_bytes), participant_contract["export_projection_canonical_bytes"], "participant export bytes")
    assert_equal(sha256_bytes(export_bytes), participant_contract["export_projection_sha256"], "participant export SHA-256")
    assert_equal(export_projection, participant_contract["records"], "participant export records")
    assert_equal(len(raw_index), len(export_projection), "raw participant locator coverage")
    assert_equal(len({row["vote_source_locator"] for row in export_projection}), len(export_projection), "raw participant locator uniqueness")
    computed_counts = {
        "records_total": len(participant_rows),
        "distinct_seats": len({str(row["seat"]) for row in participant_rows}),
        "distinct_official_names": len({str(row["member_name"]) for row in participant_rows}),
        "distinct_upstream_person_ids": len({str(row["person_id"]) for row in participant_rows}),
        "missing_official_names": sum(
            row["member_name"] is None or not str(row["member_name"]).strip()
            for row in participant_rows
        ),
        "missing_official_vote_choices": sum(
            row["vote_choice"] is None or not str(row["vote_choice"]).strip()
            for row in participant_rows
        ),
    }
    for key, value in computed_counts.items():
        assert_equal(participant_contract[key], value, f"participant summary {key}")
    assert_equal(
        participant_contract["actor_reference_projection_canonical_bytes"],
        len(actor_bytes),
        "participant actor-reference bytes",
    )
    assert_equal(
        participant_contract["actor_reference_projection_sha256"],
        sha256_bytes(actor_bytes),
        "participant actor-reference SHA-256",
    )
    actor_release_ids = {row["actor_graph_release_id"] for row in export_projection}
    assert_equal(len(actor_release_ids), 1, "participant actor release cardinality")
    assert_equal(
        participant_contract["actor_graph_release_id"],
        next(iter(actor_release_ids)),
        "participant actor release",
    )
    mismatches = [
        {
            "seat": row["seat"],
            "official_member_name": row["official_member_name"],
            "actor_canonical_label": row["actor_canonical_label"],
            "upstream_person_id": row["upstream_person_id"],
            "actor_id": row["actor_id"],
            "actor_node_version_id": row["actor_node_version_id"],
        }
        for row in export_projection
        if row["official_member_name"] != row["actor_canonical_label"]
    ]
    assert_equal(
        participant_contract["actor_reference_label_mismatch_count"],
        len(mismatches),
        "participant actor-label mismatch count",
    )
    assert_equal(
        participant_contract["actor_reference_label_mismatches"],
        mismatches,
        "participant actor-label mismatch rows",
    )
    source_ids = {row["source_id"] for row in participant_rows}
    source_snapshots = {row["source_snapshot_date"] for row in participant_rows}
    assert_equal(source_ids, {participant_contract["vote_source_id"]}, "participant vote source")
    assert_equal(
        source_snapshots,
        {participant_contract["vote_source_snapshot_date"]},
        "participant vote snapshot",
    )
    for key, expected in {
        "official_names_and_ballot_labels_authoritative": True,
        "actor_labels_replace_official_labels": False,
        "aggregation_only_publication_forbidden": True,
        "pseudonymization_forbidden": True,
        "upstream_ids_are_opaque_text": True,
    }.items():
        assert_equal(participant_contract[key], expected, f"participant policy {key}")
    ballot_counts = dict(Counter(str(row["vote_choice"]) for row in participant_rows))
    assert_equal(
        candidate["action"]["totals"]["source_ballot_label_counts"],
        ballot_counts,
        "participant-recomputed source ballot labels",
    )
    normalized_counts = {
        "yes": ballot_counts.get("SÍ", 0),
        "no": ballot_counts.get("NO", 0),
        "abstain": ballot_counts.get("ABSTENCIÓN", 0),
        "not_voting": ballot_counts.get("NO VOTAN", 0),
        "present": len(participant_rows),
    }
    assert_equal(
        candidate["action"]["totals"]["normalized_derived_counts"],
        normalized_counts,
        "participant-recomputed normalized ballot totals",
    )
    expected_participant_contract = {
        "records_total": computed_counts["records_total"],
        "distinct_seats": computed_counts["distinct_seats"],
        "distinct_official_names": computed_counts["distinct_official_names"],
        "distinct_upstream_person_ids": computed_counts["distinct_upstream_person_ids"],
        "missing_official_names": computed_counts["missing_official_names"],
        "missing_official_vote_choices": computed_counts["missing_official_vote_choices"],
        "source_projection_canonicalization": (
            "UTF-8 JSON array; SQL order CAST(seat AS INTEGER), seat, member_name; "
            "sorted object keys; compact separators; fields seat, member_name, person_id, "
            "group_code, vote_choice, source_id, source_url, source_snapshot_date"
        ),
        "source_projection_canonical_bytes": len(source_projection_bytes),
        "source_projection_sha256": sha256_bytes(source_projection_bytes),
        "export_projection_canonicalization": (
            "UTF-8 JSON; sorted object keys; compact separators; Unicode not forced to "
            "escapes; no trailing LF; same participant SQL order"
        ),
        "export_projection_canonical_bytes": len(export_bytes),
        "export_projection_sha256": sha256_bytes(export_bytes),
        "actor_graph_release_id": next(iter(actor_release_ids)),
        "actor_reference_projection_canonical_bytes": len(actor_bytes),
        "actor_reference_projection_sha256": sha256_bytes(actor_bytes),
        "actor_reference_label_mismatch_count": len(mismatches),
        "actor_reference_label_mismatches": mismatches,
        "official_names_and_ballot_labels_authoritative": True,
        "actor_labels_replace_official_labels": False,
        "public_identity_retention": (
            f"all {len(participant_rows)} official names, seats, groups, ballot choices, "
            "source links, and logical actor references remain retained"
        ),
        "aggregation_only_publication_forbidden": True,
        "pseudonymization_forbidden": True,
        "upstream_ids_are_opaque_text": True,
        "cross_database_reference_contract": (
            "logical TEXT IDs plus actor_graph_release_id and actor reference digest; "
            "no SQLite foreign key crosses database files"
        ),
        "vote_source_locator_contract": (
            "RFC 6901 JSON Pointer to exact original raw_payload member_votes array index "
            "matched by seat, official_member_name, official_group_code, official_vote_choice"
        ),
        "vote_source_id": next(iter(source_ids)),
        "vote_source_snapshot_date": next(iter(source_snapshots)),
        "records": export_projection,
    }
    assert_equal(
        participant_contract,
        expected_participant_contract,
        "complete source-recomputed participant contract",
    )
    return actor_projection, export_projection


def stable_ref(
    prefix: str, contract_version: str, preimage: dict[str, Any]
) -> tuple[str, str, dict[str, Any]]:
    identity_preimage = {
        "identity_contract_version": contract_version,
        **preimage,
    }
    digest = sha256_bytes(canonical_bytes(identity_preimage))
    return f"vclc:{prefix}:{digest[:24]}", digest, identity_preimage


def build_observation_refs(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    selected = candidate["temporal_assessment"]["selected_observations"]
    source_rows = [selected["pre"], *selected["overlap_excluded"], selected["post"]]
    output: list[dict[str, Any]] = []
    for source in source_rows:
        preimage = {
            "outcome_link_version_id": candidate["outcome_link_version_id"],
            "role": source["role"],
            "exclusion_reason": source.get("exclusion_reason"),
            "indicator_id": candidate["indicator"]["indicator_id"],
            "indicator_release_id": candidate["indicator"]["indicator_release_id"],
            "indicator_series_version_id": candidate["indicator"]["indicator_series_version_id"],
            "indicator_observation_version_id": source["indicator_observation_version_id"],
            "indicator_observation_evidence_id": source["indicator_observation_evidence_id"],
            "period_label": source["period_label"],
            "period_start": source["period_start"],
            "period_end": source["period_end"],
            "value_decimal": source["value_decimal"],
            "value_text": source["value_text"],
            "source_status_code": source["source_status_code"],
            "uncertainty_state": source["uncertainty_state"],
            "revision_ordinal": source["revision_ordinal"],
            "revision_state": source["revision_state"],
            "source_content_sha256": source["source_content_sha256"],
            "raw_path": source["raw_path"],
            "value_json_pointer": source["value_json_pointer"],
            "status_json_pointer": source["status_json_pointer"],
        }
        ref_id, digest, identity_preimage = stable_ref(
            "outcome-link-observation-ref",
            "outcome_link_observation_ref_identity_v1",
            preimage,
        )
        output.append(
            {
                "outcome_link_observation_ref_id": ref_id,
                "identity_sha256": digest,
                "identity_contract_version": "outcome_link_observation_ref_identity_v1",
                **preimage,
                "identity_preimage": identity_preimage,
            }
        )
    output.sort(
        key=lambda row: (
            ROLE_RANK[row["role"]],
            row["indicator_observation_version_id"],
            row["indicator_observation_evidence_id"],
        )
    )
    return output


def build_participant_refs(
    candidate: dict[str, Any], participants: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for source in participants:
        preimage = {
            "outcome_link_version_id": candidate["outcome_link_version_id"],
            "action_id": candidate["action"]["action_id"],
            "seat": source["seat"],
            "official_member_name": source["official_member_name"],
            "upstream_person_id_text": source["upstream_person_id"],
            "official_group_code": source["official_group_code"],
            "official_vote_choice": source["official_vote_choice"],
            "vote_source_id": source["vote_source_id"],
            "vote_source_url": source["vote_source_url"],
            "vote_source_snapshot_date": source["vote_source_snapshot_date"],
            "vote_source_record_id": source["vote_source_record_id"],
            "vote_source_record_content_sha256": source["vote_source_record_content_sha256"],
            "vote_source_locator": source["vote_source_locator"],
            "actor_graph_release_id": source["actor_graph_release_id"],
            "actor_id": source["actor_id"],
            "actor_node_version_id": source["actor_node_version_id"],
            "actor_canonical_label": source["actor_canonical_label"],
            "actor_identity_state": source["actor_identity_state"],
            "actor_provenance_state": source["actor_provenance_state"],
            "actor_source_record_id": source["actor_source_record_id"],
            "actor_source_url": source["actor_source_url"],
            "actor_source_content_sha256": source["actor_source_content_sha256"],
        }
        ref_id, digest, identity_preimage = stable_ref(
            "outcome-link-participant-ref",
            "outcome_link_participant_ref_identity_v1",
            preimage,
        )
        output.append(
            {
                "outcome_link_participant_ref_id": ref_id,
                "participant_row_semantic_sha256": digest,
                "identity_contract_version": "outcome_link_participant_ref_identity_v1",
                "outcome_link_version_id": candidate["outcome_link_version_id"],
                "action_id": candidate["action"]["action_id"],
                "seat": source["seat"],
                "official_member_name": source["official_member_name"],
                "upstream_person_id": source["upstream_person_id"],
                "official_group_code": source["official_group_code"],
                "official_vote_choice": source["official_vote_choice"],
                "actor_graph_release_id": source["actor_graph_release_id"],
                "actor_id": source["actor_id"],
                "actor_node_version_id": source["actor_node_version_id"],
                "actor_canonical_label": source["actor_canonical_label"],
                "actor_identity_state": source["actor_identity_state"],
                "actor_provenance_state": source["actor_provenance_state"],
                "actor_source_record_id": source["actor_source_record_id"],
                "actor_source_url": source["actor_source_url"],
                "actor_source_content_sha256": source["actor_source_content_sha256"],
                "vote_source_id": source["vote_source_id"],
                "vote_source_url": source["vote_source_url"],
                "vote_source_snapshot_date": source["vote_source_snapshot_date"],
                "vote_source_record_id": source["vote_source_record_id"],
                "vote_source_record_content_sha256": source["vote_source_record_content_sha256"],
                "vote_source_locator": source["vote_source_locator"],
                "official_label_authoritative": True,
                "actor_label_mismatch": source["official_member_name"] != source["actor_canonical_label"],
                "identity_preimage": identity_preimage,
            }
        )
    output.sort(
        key=lambda row: (
            row["action_id"],
            int(row["seat"]),
            row["seat"],
            row["official_member_name"],
            row["upstream_person_id"],
            row["outcome_link_participant_ref_id"],
        )
    )
    return output


def build_evidence(
    candidate: dict[str, Any], observation_refs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    action = candidate["action"]
    indicator = candidate["indicator"]
    specifications: list[dict[str, Any]] = [
        {
            "evidence_role": "normalized_vote_source_record",
            "entity_version_id": action["action_id"],
            "source_id": action["source_id"],
            "source_record_id": action["source_record_id"],
            "official_url": action["official_vote_file_url"],
            "content_sha256": action["normalized_source_record_payload_sha256"],
            "bytes": action["normalized_source_record_payload_bytes"],
            "raw_path": None,
            "locator": (
                "source_records[source_id=senado_votaciones;"
                f"source_record_id={action['source_record_id']};"
                f"source_snapshot_date={action['source_snapshot_date']}]"
            ),
            "capture_state": "normalized_source_record_present",
            "normalized_record_is_original_bytes": False,
        },
        {
            "evidence_role": "normalized_initiative_source_record",
            "entity_version_id": action["initiative_id"],
            "source_id": action["initiative_source_id"],
            "source_record_id": action["initiative_source_record_id"],
            "official_url": action["official_initiative_url"],
            "content_sha256": action["initiative_normalized_source_record_payload_sha256"],
            "bytes": action["initiative_normalized_source_record_payload_bytes"],
            "raw_path": None,
            "locator": (
                "source_records[source_id=senado_iniciativas;"
                f"source_record_id={action['initiative_source_record_id']};"
                f"source_snapshot_date={action['initiative_source_snapshot_date']}]"
            ),
            "capture_state": "normalized_source_record_present",
            "normalized_record_is_original_bytes": False,
        },
        {
            "evidence_role": "original_vote_xml_gap",
            "entity_version_id": action["action_id"],
            "source_id": action["source_id"],
            "source_record_id": action["source_record_id"],
            "official_url": action["official_vote_file_url"],
            "content_sha256": None,
            "bytes": None,
            "raw_path": None,
            "locator": None,
            "capture_state": action["original_vote_xml"]["capture_state"],
            "normalized_record_is_original_bytes": False,
        },
        {
            "evidence_role": "indicator_source_bytes",
            "entity_version_id": indicator["indicator_release_id"],
            "source_id": indicator["source_id"],
            "source_record_id": None,
            "official_url": indicator["source_url"],
            "content_sha256": indicator["source_content_sha256"],
            "bytes": indicator["source_bytes"],
            "raw_path": indicator["raw_path"],
            "locator": "/",
            "capture_state": "original_source_bytes_present",
            "normalized_record_is_original_bytes": False,
        },
    ]
    for observation in observation_refs:
        specifications.append(
            {
                "evidence_role": f"indicator_observation_{observation['role']}",
                "entity_version_id": observation["indicator_observation_version_id"],
                "source_id": indicator["source_id"],
                "source_record_id": observation["indicator_observation_evidence_id"],
                "official_url": indicator["source_url"],
                "content_sha256": observation["source_content_sha256"],
                "bytes": indicator["source_bytes"],
                "raw_path": observation["raw_path"],
                "locator": observation["value_json_pointer"],
                "capture_state": "original_source_bytes_present",
                "normalized_record_is_original_bytes": False,
            }
        )
    output: list[dict[str, Any]] = []
    for specification in specifications:
        preimage = {
            "outcome_link_version_id": candidate["outcome_link_version_id"],
            **specification,
        }
        evidence_id, digest, identity_preimage = stable_ref(
            "outcome-link-evidence",
            "outcome_link_evidence_identity_v1",
            preimage,
        )
        output.append(
            {
                "outcome_link_evidence_id": evidence_id,
                "identity_sha256": digest,
                "identity_contract_version": "outcome_link_evidence_identity_v1",
                **preimage,
                "identity_preimage": identity_preimage,
            }
        )
    output.sort(
        key=lambda row: (
            row["evidence_role"],
            row["entity_version_id"],
            row["content_sha256"] or "",
            row["locator"] or "",
            row["outcome_link_evidence_id"],
        )
    )
    return output


def validate_raw_indicator(candidate: dict[str, Any]) -> None:
    indicator = candidate["indicator"]
    raw_path = REPO_ROOT / indicator["raw_path"]
    try:
        raw_path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise RuntimeError("indicator raw_path must be repo-relative") from exc
    if not raw_path.is_file():
        raise RuntimeError(f"indicator raw bytes missing: {indicator['raw_path']}")
    assert_equal(raw_path.stat().st_size, indicator["source_bytes"], "indicator raw bytes")
    assert_equal(sha256_file(raw_path), indicator["source_content_sha256"], "indicator raw SHA-256")


def extract_outcome_schema(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if text.count(SCHEMA_BEGIN) != 1 or text.count(SCHEMA_END) != 1:
        raise RuntimeError("outcome schema markers must occur exactly once")
    start = text.index(SCHEMA_BEGIN) + len(SCHEMA_BEGIN)
    end = text.index(SCHEMA_END, start)
    schema = text[start:end].strip()
    if schema.count("CREATE TABLE IF NOT EXISTS outcome_") != 9:
        raise RuntimeError("outcome schema block must define exactly nine outcome tables")
    return schema


def validate_outcome_schema_contract(schema: str) -> dict[str, Any]:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(schema)
        actual_tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                """
            ).fetchall()
        }
        assert_equal(actual_tables, set(OUTCOME_TABLE_COLUMNS), "exact outcome schema table set")
        actual_columns: dict[str, tuple[str, ...]] = {}
        for table, expected_columns in OUTCOME_TABLE_COLUMNS.items():
            columns = tuple(
                str(row[1])
                for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            )
            assert_equal(columns, expected_columns, f"exact {table} column contract")
            actual_columns[table] = columns
        actual_triggers = {
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'trigger' AND tbl_name LIKE 'outcome_%'
                """
            ).fetchall()
        }
        assert_equal(
            actual_triggers,
            APPEND_ONLY_TRIGGER_NAMES,
            "exact outcome append-only trigger set",
        )
        fk_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
        assert_equal(fk_rows, [], "empty outcome schema foreign keys")
    finally:
        connection.close()
    column_contract = {table: list(columns) for table, columns in sorted(actual_columns.items())}
    return {
        "table_count": len(actual_tables),
        "table_names": sorted(actual_tables),
        "column_contract_sha256": sha256_bytes(canonical_bytes(column_contract)),
        "append_only_trigger_count": len(actual_triggers),
        "append_only_trigger_names": sorted(actual_triggers),
    }


def build_semantic_output(
    payload: dict[str, Any],
    candidate: dict[str, Any],
    closures: list[dict[str, Any]],
    observation_refs: list[dict[str, Any]],
    participant_refs: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    identity = candidate["identity"]
    link_preimage = identity["outcome_link_identity_preimage"]
    participant_contract = {
        key: value for key, value in candidate["participants"].items() if key != "records"
    }
    link = {
        "outcome_link_id": candidate["outcome_link_id"],
        "identity_contract_version": link_preimage["identity_contract_version"],
        "link_kind": candidate["link_kind"],
        "action_id": link_preimage["action_id"],
        "indicator_id": link_preimage["indicator_id"],
        "stable_series_key": link_preimage["stable_series_key"],
        **link_preimage["geography_scope"],
        "identity_sha256": identity["outcome_link_identity_sha256"],
        "identity_canonical_bytes": identity["outcome_link_identity_canonical_bytes"],
        "identity_preimage": link_preimage,
    }
    action_semantic = {
        key: value
        for key, value in candidate["action"].items()
        if key
        not in {
            "source_record_pk_audit_locator",
            "initiative_source_record_pk_audit_locator",
        }
    }
    version = {
        "outcome_link_version_id": candidate["outcome_link_version_id"],
        "outcome_link_id": candidate["outcome_link_id"],
        "version_identity_sha256": identity["outcome_link_version_identity_sha256"],
        "version_identity_canonical_bytes": identity["outcome_link_version_identity_canonical_bytes"],
        "identity_contract_version": identity["outcome_link_version_identity_preimage"]["identity_contract_version"],
        "method_version": payload["method_version"],
        "evidence_package_kind": "real_bounded_outcome_context_candidate_v1",
        "version_state": candidate["version_state"],
        "evidence_level": candidate["evidence_level"],
        "candidate_status": candidate["candidate_status"],
        "machine_audit_state": candidate["machine_audit_state"],
        "human_review_required": candidate["human_review_required"],
        "human_review_completed": candidate["human_review_completed"],
        "published": candidate["published"],
        "directional_countable": candidate["directional_countable"],
        "ranking_eligible": candidate["ranking_eligible"],
        "action_scope_sha256": payload["selection_closure"]["action_scope"]["sha256"],
        "action_scope_kind": "action",
        "indicator_scope_sha256": payload["selection_closure"]["indicator_scope"]["sha256"],
        "indicator_scope_kind": "indicator",
        "actor_reference_scope_sha256": payload["selection_closure"]["actor_reference_scope"]["sha256"],
        "actor_reference_scope_kind": "actor_reference",
        "combined_scope_sha256": payload["selection_closure"]["combined_scope"]["sha256"],
        "combined_scope_kind": "combined",
        "participant_count": candidate["participants"]["records_total"],
        "version_identity_preimage": identity["outcome_link_version_identity_preimage"],
        "action": action_semantic,
        "participant_contract": participant_contract,
        "indicator": candidate["indicator"],
        "temporal_assessment": candidate["temporal_assessment"],
        "semantic_assessment": candidate["semantic_assessment"],
        "geography_assessment": candidate["geography_assessment"],
        "calculation": candidate["calculation"],
        "claim_policy": candidate["claim_policy"],
        "reason_codes": candidate["reason_codes"],
        "limitations": candidate["limitations"],
        "reader_wording": candidate["reader_wording"],
        "supersedes_outcome_link_version_id": candidate["supersedes_outcome_link_version_id"],
    }
    counts = {
        "scope_closures": len(closures),
        "links": 1,
        "link_versions": 1,
        "observation_refs": len(observation_refs),
        "participant_refs": len(participant_refs),
        "evidence": len(evidence),
        "reviews": 0,
        "releases": 0,
        "release_memberships": 0,
        "human_reviewed_pairs": 0,
        "published_links": 0,
        "synthetic_or_mock_rows": 0,
    }
    return {
        "format_version": SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "generated_at": payload["generated_at"],
        "generated_at_identity_authority": False,
        "artifact_role": "internal_preproduction_candidate_bundle_not_a_release",
        "scope_truth": payload["scope_truth"],
        "policy": payload["policy"],
        "counts": counts,
        "scope_closures": closures,
        "links": [link],
        "link_versions": [version],
        "observation_refs": observation_refs,
        "participant_refs": participant_refs,
        "evidence": evidence,
        "reviews": [],
        "releases": [],
        "release_memberships": [],
    }


def bundle_semantic_projection(output: dict[str, Any]) -> dict[str, Any]:
    return {
        "identity_contract_version": "outcome_context_bundle_semantic_identity_v1",
        "method_version": output["method_version"],
        "scope_truth": output["scope_truth"],
        "policy": output["policy"],
        "counts": output["counts"],
        "scope_closures": output["scope_closures"],
        "links": output["links"],
        "link_versions": output["link_versions"],
        "observation_refs": output["observation_refs"],
        "participant_refs": output["participant_refs"],
        "evidence": output["evidence"],
        "reviews": output["reviews"],
        "releases": output["releases"],
        "release_memberships": output["release_memberships"],
    }


def db_rows_from_output(
    connection: sqlite3.Connection,
    output: dict[str, Any],
    batch_size: int,
) -> dict[str, list[tuple[Any, ...]]]:
    generated_at = output["generated_at"]
    closures = output["scope_closures"]
    links = output["links"]
    versions = output["link_versions"]
    observations = output["observation_refs"]
    participants = output["participant_refs"]
    evidence = output["evidence"]
    for key in ("reviews", "releases", "release_memberships"):
        assert_equal(output[key], [], f"C0/L1 {key}")
    rows_by_table: dict[str, list[tuple[Any, ...]]] = {
        "outcome_link_scope_closures": [
            (
                row["scope_closure_sha256"], row["scope_kind"],
                row["closure_contract_version"], canonical_json(row["canonical_preimage"]),
                row["canonical_bytes"], int(row["bounded_scope_complete"]),
                int(row["all_possible_actions_searched"]),
                int(row["all_possible_indicators_searched"]),
                int(row["all_possible_actor_sources_searched"]),
                int(row["all_possible_action_indicator_pairs_searched"]),
            )
            for row in closures
        ],
        "outcome_links": [
            (
                row["outcome_link_id"], row["identity_contract_version"],
                row["link_kind"], row["action_id"], row["indicator_id"],
                row["stable_series_key"], row["geography_code"],
                row["geography_level"], row["geography_system"],
                row["identity_sha256"], row["identity_canonical_bytes"],
                canonical_json(row["identity_preimage"]), generated_at,
            )
            for row in links
        ],
    }
    version_rows: list[tuple[Any, ...]] = []
    for row in versions:
        action = row["action"]
        indicator = row["indicator"]
        participant = row["participant_contract"]
        version_rows.append(
            (
                row["outcome_link_version_id"], row["outcome_link_id"],
                row["version_identity_sha256"], row["version_identity_canonical_bytes"],
                row["identity_contract_version"], row["method_version"],
                row["evidence_package_kind"], row["version_state"],
                row["evidence_level"], row["candidate_status"],
                row["machine_audit_state"], int(row["human_review_required"]),
                int(row["human_review_completed"]), int(row["published"]),
                int(row["directional_countable"]), int(row["ranking_eligible"]),
                action["action_id"], action["action_occurred_at"], action["source_id"],
                action["source_record_id"], action["source_snapshot_date"],
                action["normalized_source_record_payload_sha256"], action["initiative_id"],
                action["initiative_source_id"], action["initiative_source_record_id"],
                action["initiative_normalized_source_record_payload_sha256"],
                action["original_vote_xml"]["capture_state"],
                action["original_vote_xml"]["content_sha256"], indicator["indicator_id"],
                indicator["indicator_release_id"], indicator["indicator_series_version_id"],
                indicator["source_content_sha256"], row["action_scope_sha256"],
                row["action_scope_kind"], row["indicator_scope_sha256"],
                row["indicator_scope_kind"], row["actor_reference_scope_sha256"],
                row["actor_reference_scope_kind"], row["combined_scope_sha256"],
                row["combined_scope_kind"], row["participant_count"],
                participant["source_projection_sha256"], participant["export_projection_sha256"],
                participant["actor_graph_release_id"], participant["actor_reference_projection_sha256"],
                participant["actor_reference_label_mismatch_count"],
                canonical_json(row["version_identity_preimage"]), canonical_json(action),
                canonical_json(participant), canonical_json(indicator),
                canonical_json(row["temporal_assessment"]), canonical_json(row["semantic_assessment"]),
                canonical_json(row["geography_assessment"]), canonical_json(row["calculation"]),
                canonical_json(row["claim_policy"]), canonical_json(row["reason_codes"]),
                canonical_json(row["limitations"]), canonical_json(row["reader_wording"]),
                row["supersedes_outcome_link_version_id"], generated_at,
            )
        )
    rows_by_table["outcome_link_versions"] = version_rows
    rows_by_table["outcome_link_observation_refs"] = [
            (
                row["outcome_link_observation_ref_id"], row["outcome_link_version_id"],
                row["identity_sha256"], row["identity_contract_version"], row["role"],
                row["exclusion_reason"], row["indicator_id"], row["indicator_release_id"],
                row["indicator_series_version_id"], row["indicator_observation_version_id"],
                row["indicator_observation_evidence_id"], row["period_label"],
                row["period_start"], row["period_end"], row["value_decimal"],
                row["value_text"], row["source_status_code"], row["uncertainty_state"],
                row["revision_ordinal"], row["revision_state"], row["source_content_sha256"],
                row["raw_path"], row["value_json_pointer"], row["status_json_pointer"],
                canonical_json(row["identity_preimage"]),
            )
            for row in observations
        ]
    rows_by_table["outcome_link_participant_refs"] = [
            (
                row["outcome_link_participant_ref_id"], row["outcome_link_version_id"],
                row["participant_row_semantic_sha256"], row["identity_contract_version"],
                row["action_id"], row["seat"], row["official_member_name"],
                row["upstream_person_id"], row["official_group_code"],
                row["official_vote_choice"], row["actor_graph_release_id"], row["actor_id"],
                row["actor_node_version_id"], row["actor_canonical_label"],
                row["actor_identity_state"], row["actor_provenance_state"],
                row["actor_source_record_id"], row["actor_source_url"],
                row["actor_source_content_sha256"], row["vote_source_id"],
                row["vote_source_url"], row["vote_source_snapshot_date"],
                row["vote_source_record_id"], row["vote_source_record_content_sha256"],
                row["vote_source_locator"], int(row["official_label_authoritative"]),
                int(row["actor_label_mismatch"]), canonical_json(row["identity_preimage"]),
            )
            for row in participants
        ]
    rows_by_table["outcome_link_evidence"] = [
            (
                row["outcome_link_evidence_id"], row["outcome_link_version_id"],
                row["identity_sha256"], row["identity_contract_version"],
                row["evidence_role"], row["entity_version_id"], row["source_id"],
                row["source_record_id"], row["official_url"], row["content_sha256"],
                row["bytes"], row["raw_path"], row["locator"], row["capture_state"],
                int(row["normalized_record_is_original_bytes"]),
                canonical_json(row["identity_preimage"]),
            )
            for row in evidence
        ]
    rows_by_table["outcome_link_reviews"] = []
    rows_by_table["outcome_link_releases"] = []
    rows_by_table["outcome_link_release_memberships"] = []
    insert_order = (
        "outcome_link_scope_closures", "outcome_links", "outcome_link_versions",
        "outcome_link_observation_refs", "outcome_link_participant_refs",
        "outcome_link_evidence", "outcome_link_reviews", "outcome_link_releases",
        "outcome_link_release_memberships",
    )
    assert_equal(set(rows_by_table), set(OUTCOME_TABLE_COLUMNS), "DB row table contract")
    for table in insert_order:
        rows = rows_by_table[table]
        columns = OUTCOME_TABLE_COLUMNS[table]
        for row in rows:
            assert_equal(len(row), len(columns), f"{table} insert tuple arity")
        quoted_columns = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        execute_batched(
            connection,
            f'INSERT INTO "{table}" ({quoted_columns}) VALUES ({placeholders})',
            rows,
            batch_size,
        )
    return rows_by_table


def validate_db_json_parity(
    connection: sqlite3.Connection,
    expected_rows_by_table: dict[str, list[tuple[Any, ...]]],
) -> dict[str, Any]:
    table_facts: dict[str, Any] = {}
    parity_projection: dict[str, list[list[Any]]] = {}
    for table, columns in OUTCOME_TABLE_COLUMNS.items():
        quoted_columns = ", ".join(f'"{column}"' for column in columns)
        actual = [
            tuple(row)
            for row in connection.execute(
                f'SELECT {quoted_columns} FROM "{table}" ORDER BY "{columns[0]}"'
            ).fetchall()
        ]
        expected = sorted(expected_rows_by_table[table], key=lambda row: str(row[0]))
        assert_equal(actual, expected, f"exhaustive {table} DB/JSON parity")
        serializable = [list(row) for row in actual]
        parity_projection[table] = serializable
        table_facts[table] = {
            "rows": len(actual),
            "ordered_rows_sha256": sha256_bytes(canonical_bytes(serializable)),
        }
    return {
        "status": "passed",
        "tables_checked": len(table_facts),
        "table_facts": table_facts,
        "whole_projection_sha256": sha256_bytes(canonical_bytes(parity_projection)),
    }


def create_database(
    path: Path,
    schema: str,
    output: dict[str, Any],
    batch_size: int,
) -> dict[str, Any]:
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA page_size = 4096")
        connection.execute("PRAGMA auto_vacuum = NONE")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(schema)
        connection.execute("PRAGMA user_version = 1")
        connection.execute("BEGIN IMMEDIATE")
        try:
            expected_rows_by_table = db_rows_from_output(connection, output, batch_size)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        fk_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if fk_rows or integrity != "ok":
            raise RuntimeError(
                f"candidate DB failed integrity: fk={len(fk_rows)}, integrity={integrity}"
            )
        db_json_parity = validate_db_json_parity(connection, expected_rows_by_table)
        table_counts = {
            row[0]: connection.execute(
                f'SELECT COUNT(*) FROM "{row[0]}"'
            ).fetchone()[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'outcome_%' ORDER BY name"
            ).fetchall()
        }
        connection.execute("VACUUM")
    finally:
        connection.close()
    with path.open("rb") as handle:
        os.fsync(handle.fileno())
    return {
        "integrity_check": integrity,
        "foreign_key_violations": len(fk_rows),
        "table_counts": table_counts,
        "db_json_parity": db_json_parity,
    }


def write_bytes_fsync(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def same_files(left: Path, right: Path, names: Iterable[str]) -> bool:
    for name in names:
        left_file = left / name
        right_file = right / name
        if not left_file.is_file() or not right_file.is_file():
            return False
        if left_file.stat().st_size != right_file.stat().st_size:
            return False
        if sha256_file(left_file) != sha256_file(right_file):
            return False
    return True


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), 0o644)
            handle.write(canonical_bytes(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        fsync_directory(path.parent)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def actor_lookup_scale_facts(
    connection: sqlite3.Connection, payload: dict[str, Any]
) -> dict[str, Any]:
    query = payload["selection_closure"]["actor_reference_scope"]["preimage"][
        "query_contract"
    ]
    plan_rows = connection.execute(
        f"EXPLAIN QUERY PLAN {query['actor_sql_utf8']}", query["actor_parameters"]
    ).fetchall()
    query_plan = [
        {"id": row[0], "parent": row[1], "not_used": row[2], "detail": row[3]}
        for row in plan_rows
    ]
    indexes = {
        str(row[1])
        for row in connection.execute(
            "PRAGMA index_list('actor_graph_node_versions')"
        ).fetchall()
    }
    required_index = "idx_actor_graph_node_versions_release_source_actor"
    index_present = required_index in indexes
    plan_uses_required_index = any(
        required_index in str(row["detail"]) for row in query_plan
    )
    return {
        "required_index": required_index,
        "required_index_declared_in_repository_schema": True,
        "required_index_present_in_current_source_database": index_present,
        "query_plan_uses_required_index": plan_uses_required_index,
        "current_source_actor_lookup_scale_gate_passed": (
            index_present and plan_uses_required_index
        ),
        "query_plan": query_plan,
    }


def materialize(args: argparse.Namespace) -> dict[str, Any]:
    if args.batch_size < 1:
        raise RuntimeError("--batch-size must be positive")
    started = time.monotonic()
    latest_path = args.out_root / "latest.json"
    if args.report_out.resolve() == latest_path.resolve():
        raise RuntimeError("--report-out and latest pointer must be different paths")
    payload, manual_raw = load_strict_json(args.manual_input)
    candidate = validate_manual_contract(payload, args.generated_at)
    closures = validate_closures(payload)
    identity = candidate["identity"]
    validate_canonical_identity(
        identity["outcome_link_identity_preimage"],
        identity["outcome_link_identity_canonical_bytes"],
        identity["outcome_link_identity_sha256"],
        candidate["outcome_link_id"],
        "vclc:outcome-link:",
        "outcome link",
    )
    validate_canonical_identity(
        identity["outcome_link_version_identity_preimage"],
        identity["outcome_link_version_identity_canonical_bytes"],
        identity["outcome_link_version_identity_sha256"],
        candidate["outcome_link_version_id"],
        "vclc:outcome-link-version:",
        "outcome link version",
    )
    assert_equal(identity["generated_at_included_in_identity"], False, "generated-at identity flag")
    assert_equal(identity["physical_database_hashes_included_in_identity"], False, "physical DB identity flag")
    assert_equal(identity["review_result_included_in_version_identity"], False, "review identity cycle flag")
    validate_raw_indicator(candidate)
    source_paths = {
        "actions_database": args.actions_db,
        "indicator_database": args.indicator_db,
        "actor_database": args.actor_db,
    }
    source_facts_pre = source_database_facts(source_paths)
    with closing(readonly_connection(args.actions_db)) as action_db, closing(
        readonly_connection(args.indicator_db)
    ) as indicator_db, closing(readonly_connection(args.actor_db)) as actor_db:
        action_projection, vote_record, _initiative_record = load_action_scope(
            action_db, payload, candidate
        )
        indicator_observations, indicator_by_id = load_indicator_scope(
            indicator_db, payload, candidate
        )
        actor_projection, participant_projection = load_participant_scope(
            action_db, actor_db, payload, candidate, vote_record
        )
        validate_exact_calculation(candidate, indicator_by_id)
        actor_scale_facts = actor_lookup_scale_facts(actor_db, payload)
        source_facts_post = source_database_facts(source_paths)
        assert_source_facts_stable(source_facts_pre, source_facts_post)
    observation_refs = build_observation_refs(candidate)
    participant_refs = build_participant_refs(candidate, participant_projection)
    evidence = build_evidence(candidate, observation_refs)
    assert_equal(len(observation_refs), 3, "materialized observation refs")
    assert_equal(len(participant_refs), 264, "materialized participant refs")
    assert_equal(sum(row["actor_label_mismatch"] for row in participant_refs), 2, "actor label mismatch count")
    assert_equal(len({row["official_member_name"] for row in participant_refs}), 264, "official name retention")
    output = build_semantic_output(
        payload,
        candidate,
        closures,
        observation_refs,
        participant_refs,
        evidence,
    )
    schema = extract_outcome_schema(args.schema)
    schema_contract = validate_outcome_schema_contract(schema)
    version_sha = identity["outcome_link_version_identity_sha256"]
    semantic_projection = bundle_semantic_projection(output)
    bundle_semantic_sha = sha256_bytes(canonical_bytes(semantic_projection))
    args.out_root.mkdir(parents=True, exist_ok=True)
    versions_root = args.out_root / "versions"
    versions_root.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(
        tempfile.mkdtemp(prefix=f".{bundle_semantic_sha[:12]}.", dir=versions_root)
    )
    final_dir: Path | None = None
    artifact_set_sha: str | None = None
    artifact_names = (
        "outcome-context-candidates-v1.db",
        "outcome-context-candidates-v1.json",
        "manifest.json",
    )
    reused = False
    db_checks: dict[str, Any]
    try:
        db_path = temp_dir / artifact_names[0]
        json_path = temp_dir / artifact_names[1]
        db_checks = create_database(db_path, schema, output, args.batch_size)
        write_bytes_fsync(json_path, canonical_bytes(output) + b"\n")
        artifacts = {
            "database": {
                "path": artifact_names[0],
                "bytes": db_path.stat().st_size,
                "sha256": sha256_file(db_path),
            },
            "semantic_json": {
                "path": artifact_names[1],
                "bytes": json_path.stat().st_size,
                "sha256": sha256_file(json_path),
            },
        }
        artifact_set_descriptor = {
            "identity_contract_version": "outcome_context_artifact_set_identity_v1",
            "schema_version": SCHEMA_VERSION,
            "method_version": METHOD_VERSION,
            "outcome_schema_ddl_sha256": sha256_bytes(schema.encode("utf-8")),
            "candidate_version_identity_sha256": version_sha,
            "bundle_semantic_identity_contract_version": semantic_projection[
                "identity_contract_version"
            ],
            "bundle_semantic_sha256": bundle_semantic_sha,
            "artifacts": [
                {
                    "artifact_kind": artifact_kind,
                    "bytes": artifact["bytes"],
                    "sha256": artifact["sha256"],
                }
                for artifact_kind, artifact in sorted(artifacts.items())
            ],
        }
        artifact_set_sha = sha256_bytes(canonical_bytes(artifact_set_descriptor))
        version_root = versions_root / version_sha
        version_root.mkdir(parents=True, exist_ok=True)
        fsync_directory(versions_root)
        final_dir = version_root / artifact_set_sha
        manifest = {
            "format_version": "outcome_context_candidate_bundle_manifest_v1",
            "method_version": METHOD_VERSION,
            "generated_at": args.generated_at,
            "artifact_role": "internal_preproduction_candidate_bundle_not_a_release",
            "candidate_version_id": candidate["outcome_link_version_id"],
            "candidate_version_identity_sha256": version_sha,
            "bundle_semantic_identity_contract_version": semantic_projection[
                "identity_contract_version"
            ],
            "bundle_semantic_sha256": bundle_semantic_sha,
            "artifact_set_sha256": artifact_set_sha,
            "artifact_set_descriptor": artifact_set_descriptor,
            "combined_scope_sha256": payload["selection_closure"]["combined_scope"]["sha256"],
            "counts": output["counts"],
            "artifacts": artifacts,
            "physical_artifact_facts_are_semantic_identity_inputs": False,
            "human_review_completed": False,
            "release_created": False,
            "published": False,
        }
        manifest_path = temp_dir / artifact_names[2]
        write_bytes_fsync(manifest_path, canonical_bytes(manifest) + b"\n")
        fsync_directory(temp_dir)
        if final_dir.exists():
            if not final_dir.is_dir() or not same_files(temp_dir, final_dir, artifact_names):
                raise RuntimeError(
                    "immutable candidate version already exists with different bytes: "
                    f"{report_path(final_dir)}"
                )
            reused = True
            shutil.rmtree(temp_dir)
        else:
            os.rename(temp_dir, final_dir)
            fsync_directory(version_root)
        final_manifest = final_dir / "manifest.json"
        pointer = {
            "format_version": "outcome_context_candidate_pointer_v1",
            "generated_at": args.generated_at,
            "candidate_version_id": candidate["outcome_link_version_id"],
            "candidate_version_identity_sha256": version_sha,
            "bundle_semantic_sha256": bundle_semantic_sha,
            "artifact_set_sha256": artifact_set_sha,
            "immutable_bundle_path": f"versions/{version_sha}/{artifact_set_sha}",
            "manifest_sha256": sha256_file(final_manifest),
            "publication_state": "not_released",
        }
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    if final_dir is None or artifact_set_sha is None:
        raise RuntimeError("artifact set promotion did not resolve an immutable target")
    source_facts = {
        "manual_input": {
            "path": report_path(args.manual_input),
            "bytes": len(manual_raw),
            "sha256": sha256_bytes(manual_raw),
        },
        "indicator_raw_source": file_fact(REPO_ROOT / candidate["indicator"]["raw_path"]),
        **source_facts_post,
        "source_database_stability": {
            "fingerprint_contract_version": "sqlite_source_file_fingerprint_v1",
            "pre_query": source_facts_pre,
            "post_query": source_facts_post,
            "pre_post_exact_match": True,
            "content_hashes_and_stat_identities_checked": True,
            "non_empty_wal_rejected": True,
        },
    }
    final_files = {name: file_fact(final_dir / name) for name in artifact_names}
    pointer_bytes = canonical_bytes(pointer) + b"\n"
    final_files["latest.json"] = {
        "path": report_path(latest_path),
        "bytes": len(pointer_bytes),
        "sha256": sha256_bytes(pointer_bytes),
        "fact_state": "payload_precomputed_before_final_atomic_write",
    }
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_mb = peak_rss / (1024 * 1024) if sys.platform == "darwin" else peak_rss / 1024
    report = {
        "schema_version": "outcome_context_materialization_report_v1",
        "method_version": METHOD_VERSION,
        "status": "passed",
        "generated_at": args.generated_at,
        "truth": {
            "scale_stage": "C0",
            "evidence_level": "L1",
            "candidate_status": "pending_human_review",
            "human_reviews": 0,
            "releases": 0,
            "release_memberships": 0,
            "publications": 0,
            "synthetic_or_mock_rows": 0,
            "official_public_names_retained": 264,
        },
        "semantic": {
            "outcome_link_id": candidate["outcome_link_id"],
            "outcome_link_version_id": candidate["outcome_link_version_id"],
            "outcome_link_version_identity_sha256": version_sha,
            "bundle_semantic_identity_contract_version": semantic_projection[
                "identity_contract_version"
            ],
            "bundle_semantic_projection_excludes_generated_at": True,
            "reference_identity_preimages_include_contract_version": True,
            "bundle_semantic_sha256": bundle_semantic_sha,
            "artifact_set_sha256": artifact_set_sha,
            "combined_scope_sha256": payload["selection_closure"]["combined_scope"]["sha256"],
            "counts": output["counts"],
            "evidence_roles": [row["evidence_role"] for row in evidence],
        },
        "source_replay": {
            "action_candidate_rows": len(action_projection),
            "indicator_observation_rows": len(indicator_observations),
            "actor_reference_rows": len(actor_projection),
            "participant_rows": len(participant_projection),
            "source_databases_opened_read_only": True,
            "source_databases_opened_with_explicit_read_transactions": True,
            "source_pre_post_physical_facts_match": True,
            "exact_fraction_decimal_calculation_recomputed": True,
            "complete_participant_contract_recomputed": True,
            "source_ballot_counts_recomputed_from_named_participants": True,
        },
        "database": {**db_checks, "schema_contract": schema_contract},
        "inputs": source_facts,
        "outputs": final_files,
        "promotion": {
            "immutable_version_path": report_path(final_dir),
            "immutable_version_reused_after_byte_parity": reused,
            "atomic_latest_pointer": report_path(latest_path),
            "directory_replace_gap_used": False,
            "fsync_before_promotion": True,
            "report_fsynced_before_latest_pointer": True,
            "latest_pointer_is_final_materialization_operation": True,
            "failure_prone_work_after_latest_pointer": False,
        },
        "scale": {
            "multi_candidate_supported": False,
            "source_reads_streaming": False,
            "source_reads_use_fetchall": True,
            "semantic_json_monolithic": True,
            "resume_or_checkpoint_supported": False,
            "batch_size_bounds_source_reads": False,
            "batch_size_bounds_sqlite_writes_only": True,
            "million_scale_ready": False,
            "actor_lookup": actor_scale_facts,
        },
        "execution": {
            "batch_size": args.batch_size,
            "single_sqlite_writer": True,
            "current_slice_uses_bulk_participant_reads": True,
            "write_batching_does_not_bound_source_read_memory": True,
            "pre_pointer_wall_time_seconds": round(time.monotonic() - started, 6),
            "peak_rss_mb": round(peak_rss_mb, 3),
            "physical_database_hashes_are_semantic_identity_inputs": False,
        },
    }
    atomic_write_json(args.report_out, report)
    atomic_write_json(latest_path, pointer)
    return report


def main() -> int:
    args = parse_args()
    try:
        report = materialize(args)
    except (OSError, ValueError, KeyError, sqlite3.Error, RuntimeError) as exc:
        print(f"outcome context materialization failed: {exc}", file=sys.stderr)
        return 2
    print(canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
