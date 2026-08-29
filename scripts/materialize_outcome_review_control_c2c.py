#!/usr/bin/env python3
"""Materialize the bounded C2C real-human-review control plane.

This creates review capacity only. It does not create humans, authorizations,
assignments, decisions, promotions, publication events, or substantive claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sqlite3
import stat
import sys
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.outcome_pair_identity_safety import (
    bound_regular_file,
    fsync_directory,
    fsync_regular_file,
    identity_companion_leases,
    paths_overlap,
    preflight_control_target,
    secure_atomic_write_json,
    secure_unlink_regular,
)

DEFAULT_CONFIG = (
    REPO_ROOT / "etl/data/manual/outcome_links/review_control_scope_c2c_v1.json"
)
DEFAULT_SCHEMA = REPO_ROOT / "etl/load/sqlite_schema.sql"
DEFAULT_OUT_DB = REPO_ROOT / "etl/data/staging/outcome-review-control-c2c-v1.db"
DEFAULT_REPORT = (
    REPO_ROOT / "etl/data/staging/outcome-review-control-c2c-v1-report.json"
)
DEFAULT_MANIFEST = (
    REPO_ROOT / "etl/data/staging/outcome-review-control-c2c-v1-manifest.json"
)

CONTROL_CONTRACT = "outcome_review_control_c2c_v1"
CHECKPOINT_CONTRACT = "outcome_review_control_checkpoint_c2c_v1"
REPORT_FORMAT = "outcome_review_control_c2c_materialization_report_v1"
MANIFEST_FORMAT = "outcome_review_control_c2c_manifest_v1"
SCHEMA_BEGIN = "-- BEGIN OUTCOME REVIEW CONTROL C2C SCHEMA"
SCHEMA_END = "-- END OUTCOME REVIEW CONTROL C2C SCHEMA"
EMPTY_CHAIN = hashlib.sha256(b"").hexdigest()
DISCOVERY_COHORT_ID = "vclc:outcome-review-cohort:c2b-l0-v1"
CANARY_COHORT_ID = "vclc:outcome-review-cohort:c1-l1-canary-v1"
ACTOR_ID = "vclc:outcome-review-control-materializer-c2c-v1"
EXPECTED_CONFIG_SHA256 = (
    "fad0866a59bf8e007f4084b64d964c7344dcd396ac7ba505b86e601ceef1608d"
)
EXPECTED_SOURCE_ROOT_SHA256 = (
    "06264ed14d824753a7fc3ddc4ddff799939708a8b662bd7128eff680b426cf93"
)
EXPECTED_SCHEMA_ROOT_SHA256 = (
    "62d31fb97ce7580797d77ce9ebd95fc5768d10c40f985ca7d3449206cb8e5a3c"
)
EXPECTED_PIPELINE_KEY = "vclc:outcome-review-control-c2c:ca4078b5235ea4d8a894cdea"

DISCOVERY_COLUMNS = (
    "pair_plan_id",
    "action_plan_pk",
    "series_plan_pk",
    "evidence_level",
    "link_state",
    "association_assessment",
    "causal_assessment",
    "effect_estimate_state",
    "political_merit_or_blame",
    "corruption_assessment",
    "ranking_eligible",
    "publication_eligible",
    "row_semantic_sha256",
)

OPERATIONAL_TABLES = (
    "outcome_review_trust_roots",
    "outcome_review_reviewer_identities",
    "outcome_review_auth_events",
    "outcome_review_conflict_events",
    "outcome_review_assignment_events",
    "outcome_review_claim_events",
    "outcome_review_decisions",
    "outcome_review_adjudications",
    "outcome_review_semantic_eligibility_events",
    "outcome_review_semantic_promotions",
    "outcome_review_release_bindings",
    "outcome_review_publication_eligibility_events",
    "outcome_review_publication_events",
    "outcome_review_operation_requests",
    "outcome_review_operational_audit_events",
)


class ControlledInterruption(RuntimeError):
    """A testable committed stop, distinct from a failed transaction."""


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(
            handle,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_json_constant,
        )


def load_json_bytes(payload: bytes) -> Any:
    return json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_json_constant,
    )


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


def chain_add(previous: str, row_sha256: str) -> str:
    return hashlib.sha256(
        bytes.fromhex(previous) + bytes.fromhex(row_sha256)
    ).hexdigest()


def persisted_row_sha256(contract_version: str, row: dict[str, Any]) -> str:
    return sha256_bytes(
        canonical_bytes({"contract_version": contract_version, "persisted_row": row})
    )


def stable_identity(path: Path) -> tuple[int, int, int, int, int]:
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def reject_nonempty_wal(path: Path) -> None:
    resolved = Path(path).resolve(strict=True)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{resolved}{suffix}")
        if sidecar.exists() or sidecar.is_symlink():
            value = sidecar.lstat()
            if not stat.S_ISREG(value.st_mode) or value.st_size:
                raise RuntimeError(f"database has an unsafe sidecar: {repo_path(path)}")


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError("source paths must be repo-relative and traversal-free")
    return REPO_ROOT / path


def atomic_write_json(path: Path, value: Any) -> None:
    secure_atomic_write_json(path, value)


def invalidate_stale_success(path: Path, error: BaseException) -> None:
    previous_passed = False
    if path.exists():
        try:
            previous_passed = load_json(path).get("status") == "passed"
        except (OSError, ValueError, AttributeError):
            previous_passed = False
    atomic_write_json(
        path,
        {
            "format_version": REPORT_FORMAT,
            "status": "failed",
            "error_type": type(error).__name__,
            "success_report_invalidated": previous_passed,
        },
    )


def extract_schema(schema_path: Path) -> tuple[str, str]:
    text = schema_path.read_text(encoding="utf-8")
    if text.count(SCHEMA_BEGIN) != 1 or text.count(SCHEMA_END) != 1:
        raise RuntimeError("C2C schema markers are missing or duplicated")
    start = text.index(SCHEMA_BEGIN)
    end = text.index(SCHEMA_END, start) + len(SCHEMA_END)
    block = text[start:end]
    return block, sha256_bytes(block.encode("utf-8"))


def extract_schema_text(text: str) -> tuple[str, str]:
    if text.count(SCHEMA_BEGIN) != 1 or text.count(SCHEMA_END) != 1:
        raise RuntimeError("C2C schema markers are missing or duplicated")
    start = text.index(SCHEMA_BEGIN)
    end = text.index(SCHEMA_END, start) + len(SCHEMA_END)
    block = text[start:end]
    return block, sha256_bytes(block.encode("utf-8"))


def validate_config(config: dict[str, Any]) -> None:
    expected_keys = {
        "format_version",
        "scope_revision",
        "control_contract_version",
        "checkpoint_contract_version",
        "contract_date",
        "canonicalization",
        "policy",
        "trust_root_contract",
        "operational_lifecycle_contract",
        "sources",
        "query_contract",
        "expected",
    }
    if set(config) != expected_keys:
        raise RuntimeError("C2C config root keys do not match the contract")
    if config["format_version"] != "outcome_review_control_scope_c2c_v1":
        raise RuntimeError("unsupported C2C config format")
    if config["control_contract_version"] != CONTROL_CONTRACT:
        raise RuntimeError("unsupported C2C control contract")
    if config["checkpoint_contract_version"] != CHECKPOINT_CONTRACT:
        raise RuntimeError("unsupported C2C checkpoint contract")
    expected_policy = {
        "real_data_only": True,
        "synthetic_or_mock_decisions": 0,
        "official_public_identities_retained": True,
        "control_plane_capacity_status": "PASS",
        "human_review_status": "OPEN",
        "semantic_promotion_status": "OPEN",
        "public_release_status": "OPEN",
        "assignment_requires_verified_identity": True,
        "assignment_requires_active_scoped_authorization": True,
        "assignment_rejects_active_conflicts": True,
        "dual_semantic_review_requires_distinct_humans": True,
        "disagreement_requires_independent_adjudication": True,
        "semantic_promotion_requires_completed_review": True,
        "publication_requires_semantic_promotion": True,
    }
    if config["policy"] != expected_policy:
        raise RuntimeError("C2C policy is not the mandatory real-human-review policy")
    empty_trust_root_sha = sha256_bytes(
        canonical_bytes(
            {
                "contract_version": "outcome_review_trust_root_set_c2c_v1",
                "row_chain_sha256": EMPTY_CHAIN,
                "trust_root_count": 0,
            }
        )
    )
    if config["trust_root_contract"] != {
        "contract_version": "outcome_review_trust_root_set_c2c_v1",
        "state": "pinned_empty_requires_real_unpublished_operational_working_database",
        "trust_root_count": 0,
        "trust_root_sha256": empty_trust_root_sha,
    }:
        raise RuntimeError("C2C trust-root contract is not the pinned empty set")
    empty_operational_root_sha = sha256_bytes(
        canonical_bytes(
            {
                "contract_version": "outcome_review_operational_root_c2c_v1",
                "table_roots": {},
            }
        )
    )
    if config["operational_lifecycle_contract"] != {
        "capacity_artifact_scope": "capacity_only",
        "capacity_operational_state": "not_materialized",
        "working_artifact_scope": "operational_working",
        "working_operational_state": "working_unpublished",
        "working_rows_are_unpublished": True,
        "capacity_root_excludes_operational_rows": True,
        "immutable_content_addressed_export_required_before_use": True,
        "operational_export_implemented": False,
        "empty_operational_root_sha256": empty_operational_root_sha,
        "claim_lease_contract_version": "outcome_review_claim_lease_c2c_v1",
        "release_binding_contract_version": "outcome_review_release_binding_c2c_v1",
    }:
        raise RuntimeError("C2C operational lifecycle contract drifted")
    expected = config["expected"]
    if expected["discovery_tasks"] != 2_865_602:
        raise RuntimeError("C2C discovery cardinality drifted")
    if expected["total_tasks"] != expected["discovery_tasks"] + 1:
        raise RuntimeError("C2C total task cardinality is inconsistent")
    if expected["total_slots"] != expected["discovery_primary_slots"] + 2:
        raise RuntimeError("C2C total slot cardinality is inconsistent")
    batch_size = expected["materialization_batch_size"]
    if type(batch_size) is not int or not 1 <= batch_size <= 25_000:
        raise RuntimeError("C2C batch size exceeds the bounded hard contract")
    batches = (expected["discovery_tasks"] + batch_size - 1) // batch_size
    if batches != expected["committed_discovery_batches"]:
        raise RuntimeError("C2C checkpoint batch count is inconsistent")
    if expected["audit_events"] != batches + 1:
        raise RuntimeError("C2C audit event count is inconsistent")
    for source in config["sources"].values():
        for key, value in source.items():
            if key.endswith("_path") or key == "path":
                resolve_repo_path(value)


def source_root(config: dict[str, Any]) -> str:
    return sha256_bytes(
        canonical_bytes(
            {
                "contract_version": "outcome_review_control_source_root_c2c_v1",
                "sources": config["sources"],
            }
        )
    )


def pipeline_key(config_sha: str, source_sha: str, schema_sha: str) -> str:
    digest = sha256_bytes(
        canonical_bytes(
            {
                "contract_version": CONTROL_CONTRACT,
                "config_sha256": config_sha,
                "source_root_sha256": source_sha,
                "schema_root_sha256": schema_sha,
            }
        )
    )
    return f"vclc:outcome-review-control-c2c:{digest[:24]}"


def verify_file_pin(
    path: Path, expected_bytes: int, expected_sha: str
) -> tuple[int, int, int, int, int]:
    identity = stable_identity(path)
    if identity[2] != expected_bytes:
        raise RuntimeError(f"source byte-size mismatch: {repo_path(path)}")
    if sha256_file(path) != expected_sha:
        raise RuntimeError(f"source SHA-256 mismatch: {repo_path(path)}")
    if stable_identity(path) != identity:
        raise RuntimeError(f"source changed while hashing: {repo_path(path)}")
    return identity


def _bound_key(path: Path) -> Path:
    return Path(path).resolve(strict=True)


def _bound_input(bound_inputs: dict[Path, Any], path: Path) -> Any:
    try:
        return bound_inputs[_bound_key(path)]
    except KeyError as error:
        raise RuntimeError("immutable evidence descriptor is missing") from error


def _bound_identity(bound: Any) -> tuple[int, int, int, int, int]:
    value = bound.identity
    return (
        value.device,
        value.inode,
        value.size,
        value.modified_ns,
        value.changed_ns,
    )


def verify_bound_pin(
    bound: Any, expected_bytes: int, expected_sha: str
) -> tuple[int, int, int, int, int]:
    identity = _bound_identity(bound)
    if identity[2] != expected_bytes:
        raise RuntimeError("immutable evidence byte-size mismatch")
    if bound.sha256() != expected_sha:
        raise RuntimeError("immutable evidence SHA-256 mismatch")
    return identity


def load_bound_json_input(bound: Any, *, max_bytes: int = 2 * 1024 * 1024) -> Any:
    return load_json_bytes(bound.read_bytes(max_bytes=max_bytes))


def open_bound_immutable_db(
    bound: Any,
) -> tuple[sqlite3.Connection, tuple[int, int, int, int, int]]:
    descriptor = bound.handle.fileno()
    connection = sqlite3.connect(
        f"file:/dev/fd/{descriptor}?mode=ro&immutable=1", uri=True
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.execute("BEGIN")
    return connection, _bound_identity(bound)


def verify_json_source(
    path: Path, expected_bytes: int, expected_sha: str
) -> tuple[Any, tuple[int, int, int, int, int]]:
    identity = verify_file_pin(path, expected_bytes, expected_sha)
    return load_json(path), identity


def open_immutable_db(
    path: Path,
) -> tuple[sqlite3.Connection, tuple[int, int, int, int, int]]:
    reject_nonempty_wal(path)
    identity = stable_identity(path)
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro&immutable=1", uri=True
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.execute("BEGIN")
    return connection, identity


def close_immutable_db(
    connection: sqlite3.Connection,
    path: Path,
    identity: tuple[int, int, int, int, int],
) -> None:
    if connection.total_changes:
        raise RuntimeError("immutable source connection wrote data")
    connection.commit()
    connection.close()
    reject_nonempty_wal(path)
    if stable_identity(path) != identity:
        raise RuntimeError(f"source changed during run: {repo_path(path)}")


def verify_source_artifacts(
    config: dict[str, Any], bound_inputs: dict[Path, Any]
) -> dict[str, Any]:
    discovery = config["sources"]["discovery_pairs"]
    discovery_db = resolve_repo_path(discovery["path"])
    discovery_manifest_path = resolve_repo_path(discovery["manifest_path"])
    discovery_db_bound = _bound_input(bound_inputs, discovery_db)
    verify_bound_pin(discovery_db_bound, discovery["bytes"], discovery["sha256"])
    discovery_manifest_bound = _bound_input(bound_inputs, discovery_manifest_path)
    discovery_manifest_identity = verify_bound_pin(
        discovery_manifest_bound,
        discovery["manifest_bytes"],
        discovery["manifest_sha256"],
    )
    discovery_manifest = load_bound_json_input(discovery_manifest_bound)
    if (
        discovery_manifest.get("manifest_root_sha256")
        != discovery["manifest_root_sha256"]
    ):
        raise RuntimeError("C2B manifest root mismatch")
    if (
        discovery_manifest.get("roots", {}).get("semantic_root_sha256")
        != discovery["semantic_root_sha256"]
    ):
        raise RuntimeError("C2B semantic root mismatch")
    if discovery_manifest.get("pipeline_key") != discovery["pipeline_key"]:
        raise RuntimeError("C2B pipeline identity mismatch")
    if discovery_manifest.get("counts", {}).get("pairs") != 2_865_602:
        raise RuntimeError("C2B manifest pair count mismatch")
    shards = discovery_manifest.get("shards")
    if not isinstance(shards, list) or len(shards) != 1:
        raise RuntimeError("C2B manifest shard set mismatch")
    if (
        shards[0].get("bytes") != discovery["bytes"]
        or shards[0].get("sha256") != discovery["sha256"]
    ):
        raise RuntimeError("C2B manifest shard identity mismatch")

    canary = config["sources"]["semantic_canary"]
    pointer_path = resolve_repo_path(canary["pointer_path"])
    pointer_bound = _bound_input(bound_inputs, pointer_path)
    pointer_identity = verify_bound_pin(
        pointer_bound, canary["pointer_bytes"], canary["pointer_sha256"]
    )
    pointer = load_bound_json_input(pointer_bound)
    pointer_expected = {
        "artifact_set_sha256": canary["artifact_set_sha256"],
        "bundle_semantic_sha256": canary["bundle_semantic_sha256"],
        "candidate_version_id": canary["candidate_version_id"],
        "candidate_version_identity_sha256": canary[
            "candidate_version_identity_sha256"
        ],
        "manifest_sha256": canary["manifest_sha256"],
        "publication_state": "not_released",
    }
    for key, value in pointer_expected.items():
        if pointer.get(key) != value:
            raise RuntimeError(f"C1 pointer mismatch: {key}")
    canary_db = resolve_repo_path(canary["database_path"])
    canary_manifest_path = resolve_repo_path(canary["manifest_path"])
    canary_db_bound = _bound_input(bound_inputs, canary_db)
    verify_bound_pin(
        canary_db_bound, canary["database_bytes"], canary["database_sha256"]
    )
    canary_manifest_bound = _bound_input(bound_inputs, canary_manifest_path)
    canary_manifest_identity = verify_bound_pin(
        canary_manifest_bound, canary["manifest_bytes"], canary["manifest_sha256"]
    )
    canary_manifest = load_bound_json_input(canary_manifest_bound)
    if canary_manifest.get("artifact_set_sha256") != canary["artifact_set_sha256"]:
        raise RuntimeError("C1 manifest artifact-set mismatch")
    if (
        canary_manifest.get("bundle_semantic_sha256")
        != canary["bundle_semantic_sha256"]
    ):
        raise RuntimeError("C1 manifest semantic root mismatch")

    return {
        "discovery_db": discovery_db,
        "discovery_db_bound": discovery_db_bound,
        "discovery_manifest_path": discovery_manifest_path,
        "discovery_manifest_identity": discovery_manifest_identity,
        "canary_db": canary_db,
        "canary_db_bound": canary_db_bound,
        "pointer_path": pointer_path,
        "pointer_identity": pointer_identity,
        "canary_manifest_path": canary_manifest_path,
        "canary_manifest_identity": canary_manifest_identity,
    }


def require_canary_support(
    connection: sqlite3.Connection, config: dict[str, Any]
) -> sqlite3.Row:
    canary = config["sources"]["semantic_canary"]
    policy = config["query_contract"]["semantic_canary_policy"]
    rows = list(
        connection.execute(
            "SELECT outcome_link_version_id,version_identity_sha256,version_state,"
            "evidence_level,candidate_status,machine_audit_state,human_review_required,"
            "human_review_completed,published,directional_countable,ranking_eligible "
            "FROM outcome_link_versions ORDER BY outcome_link_version_id LIMIT 2"
        )
    )
    if len(rows) != 1:
        raise RuntimeError("C1 semantic canary source must contain exactly one version")
    row = rows[0]
    expected = {
        "outcome_link_version_id": canary["candidate_version_id"],
        "version_identity_sha256": canary["candidate_version_identity_sha256"],
        "version_state": policy["version_state"],
        "evidence_level": policy["evidence_level"],
        "candidate_status": policy["candidate_status"],
        "machine_audit_state": policy["machine_audit_state"],
        "human_review_required": policy["human_review_required"],
        "human_review_completed": policy["human_review_completed"],
        "published": policy["published"],
        "directional_countable": policy["directional_countable"],
        "ranking_eligible": policy["ranking_eligible"],
    }
    for key, value in expected.items():
        if row[key] != value:
            raise RuntimeError(f"C1 semantic canary policy mismatch: {key}")
    counts = {
        "existing_review_rows": connection.execute(
            "SELECT COUNT(*) FROM outcome_link_reviews"
        ).fetchone()[0],
        "existing_release_rows": connection.execute(
            "SELECT COUNT(*) FROM outcome_link_releases"
        ).fetchone()[0],
        "existing_release_membership_rows": connection.execute(
            "SELECT COUNT(*) FROM outcome_link_release_memberships"
        ).fetchone()[0],
    }
    for key, value in counts.items():
        if value != policy[key]:
            raise RuntimeError(f"C1 semantic canary human-state mismatch: {key}")
    return row


def require_discovery_support(
    connection: sqlite3.Connection, config: dict[str, Any]
) -> None:
    source = config["sources"]["discovery_pairs"]
    policy = config["query_contract"]["discovery_pair_policy"]
    plan_details = " ".join(
        str(row[3])
        for row in connection.execute(
            f"EXPLAIN QUERY PLAN SELECT {','.join(DISCOVERY_COLUMNS)} "
            "FROM outcome_pair_plan_pairs WHERE pipeline_key=? AND "
            "(action_plan_pk>? OR (action_plan_pk=? AND series_plan_pk>?)) "
            "ORDER BY action_plan_pk,series_plan_pk LIMIT ?",
            (source["pipeline_key"], 0, 0, 0, 1),
        )
    )
    if (
        "SEARCH outcome_pair_plan_pairs USING" not in plan_details
        or "SCAN outcome_pair_plan_pairs" in plan_details
        or "USE TEMP B-TREE" in plan_details
    ):
        raise RuntimeError("C2B source keyset query is not index-backed")
    checkpoint = connection.execute(
        "SELECT rows_written,completed,semantic_chain_sha256 FROM pipeline_keyset_checkpoints "
        "WHERE pipeline_key=? AND stage='pairs' AND partition_key=''",
        (source["pipeline_key"],),
    ).fetchone()
    if checkpoint is None:
        raise RuntimeError("C2B pair checkpoint is absent")
    if checkpoint["rows_written"] != config["expected"]["discovery_tasks"]:
        raise RuntimeError("C2B checkpoint cardinality mismatch")
    if checkpoint["completed"] != 1:
        raise RuntimeError("C2B pair checkpoint is incomplete")
    count = connection.execute(
        "SELECT COUNT(*) FROM outcome_pair_plan_pairs WHERE pipeline_key=?",
        (source["pipeline_key"],),
    ).fetchone()[0]
    if count != config["expected"]["discovery_tasks"]:
        raise RuntimeError("C2B pair physical cardinality mismatch")
    aggregate = connection.execute(
        "SELECT COUNT(*) AS n,MIN(evidence_level),MAX(evidence_level),"
        "MIN(link_state),MAX(link_state),"
        "SUM(ranking_eligible),SUM(publication_eligible) "
        "FROM outcome_pair_plan_pairs WHERE pipeline_key=?",
        (source["pipeline_key"],),
    ).fetchone()
    if tuple(aggregate) != (
        count,
        policy["evidence_level"],
        policy["evidence_level"],
        policy["link_state"],
        policy["link_state"],
        0,
        0,
    ):
        raise RuntimeError("C2B discovery cohort policy mismatch")


def task_identity(cohort_id: str, source_row_id: str) -> str:
    digest = sha256_bytes(
        canonical_bytes(
            {
                "contract_version": "outcome_review_task_identity_c2c_v1",
                "cohort_id": cohort_id,
                "source_row_id": source_row_id,
            }
        )
    )
    return f"vclc:outcome-review-task:{digest[:24]}"


def slot_identity(task_id: str, slot_kind: str) -> str:
    digest = sha256_bytes(
        canonical_bytes(
            {
                "contract_version": "outcome_review_slot_identity_c2c_v1",
                "task_id": task_id,
                "slot_kind": slot_kind,
            }
        )
    )
    return f"vclc:outcome-review-slot:{digest[:24]}"


def meta_row(
    *,
    config: dict[str, Any],
    pipeline: str,
    config_sha: str,
    source_sha: str,
    schema_sha: str,
    snapshot_effective_at: str,
    capacity_status: str,
) -> tuple[Any, ...]:
    row = {
        "pipeline_key": pipeline,
        "contract_version": CONTROL_CONTRACT,
        "config_sha256": config_sha,
        "source_root_sha256": source_sha,
        "schema_root_sha256": schema_sha,
        "artifact_scope": config["operational_lifecycle_contract"][
            "capacity_artifact_scope"
        ],
        "trust_root_contract_sha256": config["trust_root_contract"][
            "trust_root_sha256"
        ],
        "operational_state": config["operational_lifecycle_contract"][
            "capacity_operational_state"
        ],
        "control_plane_capacity_status": capacity_status,
        "human_review_status": "OPEN",
        "semantic_promotion_status": "OPEN",
        "public_release_status": "OPEN",
        "real_data_only": 1,
        "synthetic_or_mock_decisions": 0,
        "capacity_snapshot_effective_at": snapshot_effective_at,
    }
    row_sha = persisted_row_sha256("outcome_review_control_meta_row_c2c_v1", row)
    return tuple(row.values()) + (row_sha,)


def cohort_rows(config: dict[str, Any], pipeline: str) -> list[tuple[Any, ...]]:
    discovery = config["sources"]["discovery_pairs"]
    canary = config["sources"]["semantic_canary"]
    definitions = [
        {
            "cohort_id": DISCOVERY_COHORT_ID,
            "pipeline_key": pipeline,
            "cohort_kind": "c2b_l0_discovery",
            "source_artifact_path": discovery["path"],
            "source_artifact_sha256": discovery["sha256"],
            "source_manifest_sha256": discovery["manifest_sha256"],
            "source_semantic_root_sha256": discovery["semantic_root_sha256"],
            "evidence_level": "L0",
            "expected_task_count": config["expected"]["discovery_tasks"],
            "required_slots_per_task": 1,
            "assignment_eligible": 1,
            "requires_dual_review": 0,
            "adjudication_on_disagreement": 0,
            "semantic_promotion_requires_review": 1,
            "public_release_requires_promotion": 1,
            "eligibility_policy_json": canonical_json(
                {
                    "assignment": "pending_verified_identity_authorization_and_conflict_gates",
                    "claim_state": "internal_L0_discovery_only",
                    "human_review": "open",
                    "publication": "closed",
                    "semantic_promotion": "closed",
                }
            ),
        },
        {
            "cohort_id": CANARY_COHORT_ID,
            "pipeline_key": pipeline,
            "cohort_kind": "c1_l1_semantic_canary",
            "source_artifact_path": canary["database_path"],
            "source_artifact_sha256": canary["database_sha256"],
            "source_manifest_sha256": canary["manifest_sha256"],
            "source_semantic_root_sha256": canary["bundle_semantic_sha256"],
            "evidence_level": "L1",
            "expected_task_count": 1,
            "required_slots_per_task": 2,
            "assignment_eligible": 1,
            "requires_dual_review": 1,
            "adjudication_on_disagreement": 1,
            "semantic_promotion_requires_review": 1,
            "public_release_requires_promotion": 1,
            "eligibility_policy_json": canonical_json(
                {
                    "assignment": "pending_two_distinct_verified_semantic_reviewers",
                    "adjudication": "independent_authority_only_after_disagreement",
                    "human_review": "open",
                    "publication": "closed",
                    "semantic_promotion": "closed",
                }
            ),
        },
    ]
    rows: list[tuple[Any, ...]] = []
    for row in definitions:
        row_sha = persisted_row_sha256("outcome_review_cohort_row_c2c_v1", row)
        rows.append(tuple(row.values()) + (row_sha,))
    return rows


def canary_task_and_slots(
    config: dict[str, Any], canary_row: sqlite3.Row
) -> tuple[tuple[Any, ...], list[tuple[Any, ...]]]:
    task_pk = config["expected"]["total_tasks"]
    task_id = task_identity(CANARY_COHORT_ID, canary_row["outcome_link_version_id"])
    task = {
        "task_pk": task_pk,
        "task_id": task_id,
        "cohort_id": CANARY_COHORT_ID,
        "task_kind": "semantic_canary",
        "source_row_id": canary_row["outcome_link_version_id"],
        "source_row_semantic_sha256": canary_row["version_identity_sha256"],
        "source_action_plan_pk": None,
        "source_series_plan_pk": None,
        "evidence_level": "L1",
        "task_state": "pending_human_review",
        "assignment_eligible": 1,
        "initial_semantic_promotion_eligible": 0,
        "initial_publication_eligible": 0,
    }
    task_sha = persisted_row_sha256("outcome_review_task_row_c2c_v1", task)
    slots: list[tuple[Any, ...]] = []
    for ordinal, kind in ((1, "semantic_primary"), (2, "semantic_secondary")):
        slot = {
            "slot_pk": config["expected"]["discovery_primary_slots"] + ordinal,
            "slot_id": slot_identity(task_id, kind),
            "task_pk": task_pk,
            "slot_kind": kind,
            "slot_ordinal": ordinal,
            "review_dimension": "semantic",
            "required_reviewer_role": "semantic_reviewer",
            "independent_reviewer_required": 1,
            "adjudication_rule": "on_disagreement_after_dual_review",
            "slot_state": "pending_unassigned",
        }
        slot_sha = persisted_row_sha256("outcome_review_slot_row_c2c_v1", slot)
        slots.append(tuple(slot.values()) + (slot_sha,))
    return tuple(task.values()) + (task_sha,), slots


def audit_event(
    *,
    event_pk: int,
    pipeline: str,
    event_kind: str,
    batch_ordinal: int,
    source_rows: int,
    slots: int,
    previous: str,
    payload: dict[str, Any],
    snapshot_effective_at: str,
) -> tuple[tuple[Any, ...], str]:
    event_id = (
        f"vclc:outcome-review-audit:{pipeline.rsplit(':', 1)[-1]}:{batch_ordinal:06d}"
    )
    row = {
        "audit_event_pk": event_pk,
        "audit_event_id": event_id,
        "pipeline_key": pipeline,
        "event_kind": event_kind,
        "batch_ordinal": batch_ordinal,
        "source_rows_committed": source_rows,
        "slots_committed": slots,
        "previous_event_sha256": previous,
        "event_payload_json": canonical_json(payload),
        "actor_kind": "system_materializer",
        "actor_id": ACTOR_ID,
        "snapshot_effective_at": snapshot_effective_at,
    }
    event_sha = persisted_row_sha256("outcome_review_audit_event_c2c_v1", row)
    return tuple(row.values()) + (event_sha,), event_sha


def connect_target(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA temp_store=MEMORY")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def initialize_target(
    connection: sqlite3.Connection,
    *,
    schema_block: str,
    pipeline: str,
    config: dict[str, Any],
    config_sha: str,
    source_sha: str,
    schema_sha: str,
    canary_row: sqlite3.Row,
) -> bool:
    existing_tables = connection.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
        "AND name='outcome_review_control_meta'"
    ).fetchone()[0]
    if existing_tables:
        return False
    connection.executescript("BEGIN IMMEDIATE;\n" + schema_block)
    snapshot_effective_at = f"{config['contract_date']}T00:00:00Z"
    canary_task, canary_slots = canary_task_and_slots(config, canary_row)
    meta = meta_row(
        config=config,
        pipeline=pipeline,
        config_sha=config_sha,
        source_sha=source_sha,
        schema_sha=schema_sha,
        snapshot_effective_at=snapshot_effective_at,
        capacity_status="BUILDING",
    )
    initial_payload = {
        "canary_semantic_slots": 2,
        "canary_tasks": 1,
        "control_plane_capacity_status": "BUILDING",
        "human_review_status": "OPEN",
        "semantic_promotion_status": "OPEN",
        "public_release_status": "OPEN",
        "synthetic_or_mock_decisions": 0,
    }
    event, event_sha = audit_event(
        event_pk=1,
        pipeline=pipeline,
        event_kind="control_initialized",
        batch_ordinal=0,
        source_rows=0,
        slots=2,
        previous=EMPTY_CHAIN,
        payload=initial_payload,
        snapshot_effective_at=snapshot_effective_at,
    )
    try:
        connection.execute(
            "INSERT INTO outcome_review_control_meta VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            meta,
        )
        connection.executemany(
            "INSERT INTO outcome_review_cohorts VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            cohort_rows(config, pipeline),
        )
        connection.execute(
            "INSERT INTO outcome_review_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            canary_task,
        )
        connection.executemany(
            "INSERT INTO outcome_review_slots VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            canary_slots,
        )
        connection.execute(
            "INSERT INTO outcome_review_control_checkpoints VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                pipeline,
                "discovery_tasks",
                CHECKPOINT_CONTRACT,
                config_sha,
                source_sha,
                schema_sha,
                0,
                0,
                0,
                0,
                0,
                EMPTY_CHAIN,
                EMPTY_CHAIN,
                event_sha,
                0,
                snapshot_effective_at,
            ),
        )
        connection.execute(
            "INSERT INTO outcome_review_audit_events VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            event,
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    return True


def load_checkpoint(
    connection: sqlite3.Connection,
    *,
    pipeline: str,
    config_sha: str,
    source_sha: str,
    schema_sha: str,
) -> sqlite3.Row:
    meta = connection.execute("SELECT * FROM outcome_review_control_meta").fetchone()
    if meta is None or meta["pipeline_key"] != pipeline:
        raise RuntimeError("target database pipeline identity mismatch")
    for key, value in (
        ("config_sha256", config_sha),
        ("source_root_sha256", source_sha),
        ("schema_root_sha256", schema_sha),
    ):
        if meta[key] != value:
            raise RuntimeError(f"target database {key} mismatch")
    checkpoint = connection.execute(
        "SELECT * FROM outcome_review_control_checkpoints "
        "WHERE pipeline_key=? AND stage='discovery_tasks'",
        (pipeline,),
    ).fetchone()
    if checkpoint is None:
        raise RuntimeError("target database checkpoint is absent")
    for key, value in (
        ("checkpoint_contract_version", CHECKPOINT_CONTRACT),
        ("config_sha256", config_sha),
        ("source_root_sha256", source_sha),
        ("schema_root_sha256", schema_sha),
    ):
        if checkpoint[key] != value:
            raise RuntimeError(f"checkpoint {key} mismatch")
    return checkpoint


def verify_target_schema(connection: sqlite3.Connection, schema_block: str) -> None:
    # Schema-only scratch database: it receives production DDL and no control rows.
    with tempfile.TemporaryDirectory(prefix="vclc-c2c-schema-check-") as directory:
        expected = sqlite3.connect(Path(directory) / "schema-only.db")
        expected.execute("PRAGMA foreign_keys=ON")
        expected.executescript(schema_block)
        try:
            expected_objects = {
                (row[0], row[1]): row[2]
                for row in expected.execute(
                    "SELECT type,name,sql FROM sqlite_master "
                    "WHERE tbl_name LIKE 'outcome_review_%' AND sql IS NOT NULL"
                )
            }
            actual_objects = {
                (row[0], row[1]): row[2]
                for row in connection.execute(
                    "SELECT type,name,sql FROM sqlite_master "
                    "WHERE tbl_name LIKE 'outcome_review_%' AND sql IS NOT NULL"
                )
            }
            if actual_objects != expected_objects:
                raise RuntimeError(
                    "target C2C schema objects differ from the pinned schema"
                )
        finally:
            expected.close()


def verify_target_state(
    connection: sqlite3.Connection,
    *,
    checkpoint: sqlite3.Row,
    config: dict[str, Any],
) -> None:
    discovery_tasks = connection.execute(
        "SELECT COUNT(*) FROM outcome_review_tasks WHERE cohort_id=?",
        (DISCOVERY_COHORT_ID,),
    ).fetchone()[0]
    discovery_slots = connection.execute(
        "SELECT COUNT(*) FROM outcome_review_slots WHERE slot_kind='discovery_primary'"
    ).fetchone()[0]
    audit_events = table_count(connection, "outcome_review_audit_events")
    if discovery_tasks != checkpoint["tasks_written"]:
        raise RuntimeError("checkpoint task count differs from physical rows")
    if discovery_slots != checkpoint["slots_written"]:
        raise RuntimeError("checkpoint slot count differs from physical rows")
    if audit_events != checkpoint["batches_committed"] + 1:
        raise RuntimeError("checkpoint batch count differs from audit rows")
    if table_count(connection, "outcome_review_tasks") != discovery_tasks + 1:
        raise RuntimeError("C1 canary task cardinality differs from contract")
    if table_count(connection, "outcome_review_slots") != discovery_slots + 2:
        raise RuntimeError("C1 canary slot cardinality differs from contract")
    for table in OPERATIONAL_TABLES:
        if table_count(connection, table):
            raise RuntimeError("human operational rows exist in capacity-only artifact")
    meta_status = connection.execute(
        "SELECT control_plane_capacity_status FROM outcome_review_control_meta"
    ).fetchone()[0]
    expected_status = "PASS" if checkpoint["completed"] else "BUILDING"
    if meta_status != expected_status:
        raise RuntimeError("control-plane capacity status differs from checkpoint")
    if discovery_tasks:
        last = connection.execute(
            "SELECT source_action_plan_pk,source_series_plan_pk "
            "FROM outcome_review_tasks WHERE cohort_id=? ORDER BY task_pk DESC LIMIT 1",
            (DISCOVERY_COHORT_ID,),
        ).fetchone()
        if tuple(last) != (
            checkpoint["last_action_plan_pk"],
            checkpoint["last_series_plan_pk"],
        ):
            raise RuntimeError("checkpoint key differs from physical task tail")
    elif checkpoint["last_action_plan_pk"] or checkpoint["last_series_plan_pk"]:
        raise RuntimeError("empty checkpoint has a non-empty source key")

    task_chain = EMPTY_CHAIN
    for row in connection.execute(
        "SELECT row_semantic_sha256 FROM outcome_review_tasks "
        "WHERE cohort_id=? ORDER BY task_pk",
        (DISCOVERY_COHORT_ID,),
    ):
        task_chain = chain_add(task_chain, row[0])
    if task_chain != checkpoint["task_chain_sha256"]:
        raise RuntimeError("checkpoint task chain differs from physical rows")
    slot_chain = EMPTY_CHAIN
    for row in connection.execute(
        "SELECT row_semantic_sha256 FROM outcome_review_slots "
        "WHERE slot_kind='discovery_primary' ORDER BY slot_pk"
    ):
        slot_chain = chain_add(slot_chain, row[0])
    if slot_chain != checkpoint["slot_chain_sha256"]:
        raise RuntimeError("checkpoint slot chain differs from physical rows")
    previous = EMPTY_CHAIN
    expected_ordinal = 0
    for row in connection.execute(
        "SELECT * FROM outcome_review_audit_events ORDER BY batch_ordinal"
    ):
        if row["batch_ordinal"] != expected_ordinal:
            raise RuntimeError("audit event ordinals are not contiguous")
        if row["previous_event_sha256"] != previous:
            raise RuntimeError("audit event chain is discontinuous")
        persisted = {key: row[key] for key in row.keys() if key != "event_sha256"}
        event_sha = persisted_row_sha256("outcome_review_audit_event_c2c_v1", persisted)
        if event_sha != row["event_sha256"]:
            raise RuntimeError("audit event semantic digest mismatch")
        previous = event_sha
        expected_ordinal += 1
    if previous != checkpoint["audit_chain_sha256"]:
        raise RuntimeError("checkpoint audit chain differs from physical rows")

    if checkpoint["completed"]:
        expected = config["expected"]
        if (
            discovery_tasks != expected["discovery_tasks"]
            or discovery_slots != expected["discovery_primary_slots"]
            or checkpoint["batches_committed"]
            != expected["committed_discovery_batches"]
        ):
            raise RuntimeError("completed C2C state has incorrect cardinalities")


def discovery_page(
    source: sqlite3.Connection,
    *,
    source_pipeline: str,
    last_action: int,
    last_series: int,
    batch_size: int,
) -> list[sqlite3.Row]:
    columns = ",".join(DISCOVERY_COLUMNS)
    cursor = source.execute(
        f"SELECT {columns} FROM outcome_pair_plan_pairs "
        "WHERE pipeline_key=? AND (action_plan_pk>? OR "
        "(action_plan_pk=? AND series_plan_pk>?)) "
        "ORDER BY action_plan_pk,series_plan_pk LIMIT ?",
        (source_pipeline, last_action, last_action, last_series, batch_size),
    )
    rows = list(cursor)
    cursor.close()
    return rows


def check_discovery_row(row: sqlite3.Row, policy: dict[str, Any]) -> None:
    for key in (
        "evidence_level",
        "link_state",
        "association_assessment",
        "causal_assessment",
        "effect_estimate_state",
        "political_merit_or_blame",
        "corruption_assessment",
        "ranking_eligible",
        "publication_eligible",
    ):
        if row[key] != policy[key]:
            raise RuntimeError(f"C2B discovery row violates zero-claim policy: {key}")


def build_discovery_rows(
    rows: Iterable[sqlite3.Row],
    *,
    start_pk: int,
    task_chain: str,
    slot_chain: str,
    policy: dict[str, Any],
) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]], str, str]:
    tasks: list[tuple[Any, ...]] = []
    slots: list[tuple[Any, ...]] = []
    task_pk = start_pk
    for source_row in rows:
        task_pk += 1
        check_discovery_row(source_row, policy)
        task_id = task_identity(DISCOVERY_COHORT_ID, source_row["pair_plan_id"])
        task = {
            "task_pk": task_pk,
            "task_id": task_id,
            "cohort_id": DISCOVERY_COHORT_ID,
            "task_kind": "discovery_triage",
            "source_row_id": source_row["pair_plan_id"],
            "source_row_semantic_sha256": source_row["row_semantic_sha256"],
            "source_action_plan_pk": source_row["action_plan_pk"],
            "source_series_plan_pk": source_row["series_plan_pk"],
            "evidence_level": "L0",
            "task_state": "pending_human_review",
            "assignment_eligible": 1,
            "initial_semantic_promotion_eligible": 0,
            "initial_publication_eligible": 0,
        }
        task_sha = persisted_row_sha256("outcome_review_task_row_c2c_v1", task)
        task_chain = chain_add(task_chain, task_sha)
        tasks.append(tuple(task.values()) + (task_sha,))

        slot = {
            "slot_pk": task_pk,
            "slot_id": slot_identity(task_id, "discovery_primary"),
            "task_pk": task_pk,
            "slot_kind": "discovery_primary",
            "slot_ordinal": 1,
            "review_dimension": "discovery_triage",
            "required_reviewer_role": "discovery_reviewer",
            "independent_reviewer_required": 0,
            "adjudication_rule": "not_applicable",
            "slot_state": "pending_unassigned",
        }
        slot_sha = persisted_row_sha256("outcome_review_slot_row_c2c_v1", slot)
        slot_chain = chain_add(slot_chain, slot_sha)
        slots.append(tuple(slot.values()) + (slot_sha,))
    return tasks, slots, task_chain, slot_chain


def commit_discovery_batch(
    connection: sqlite3.Connection,
    *,
    pipeline: str,
    config: dict[str, Any],
    checkpoint: sqlite3.Row,
    source_rows: list[sqlite3.Row],
    fault_before_checkpoint: bool,
) -> None:
    policy = config["query_contract"]["discovery_pair_policy"]
    tasks, slots, task_chain, slot_chain = build_discovery_rows(
        source_rows,
        start_pk=checkpoint["tasks_written"],
        task_chain=checkpoint["task_chain_sha256"],
        slot_chain=checkpoint["slot_chain_sha256"],
        policy=policy,
    )
    batch_ordinal = checkpoint["batches_committed"] + 1
    tasks_written = checkpoint["tasks_written"] + len(tasks)
    slots_written = checkpoint["slots_written"] + len(slots)
    expected = config["expected"]
    completed = int(tasks_written == expected["discovery_tasks"])
    if tasks_written > expected["discovery_tasks"]:
        raise RuntimeError("C2C materializer exceeded the discovery cardinality")
    last = source_rows[-1]
    snapshot_effective_at = f"{config['contract_date']}T00:00:00Z"
    payload = {
        "batch_ordinal": batch_ordinal,
        "cumulative_discovery_slots": slots_written,
        "cumulative_discovery_tasks": tasks_written,
        "last_action_plan_pk": last["action_plan_pk"],
        "last_series_plan_pk": last["series_plan_pk"],
        "source_rows_committed": len(source_rows),
    }
    event, event_sha = audit_event(
        event_pk=batch_ordinal + 1,
        pipeline=pipeline,
        event_kind="discovery_batch_committed",
        batch_ordinal=batch_ordinal,
        source_rows=len(source_rows),
        slots=len(slots),
        previous=checkpoint["audit_chain_sha256"],
        payload=payload,
        snapshot_effective_at=snapshot_effective_at,
    )
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.executemany(
            "INSERT INTO outcome_review_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            tasks,
        )
        connection.executemany(
            "INSERT INTO outcome_review_slots VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            slots,
        )
        connection.execute(
            "INSERT INTO outcome_review_audit_events VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            event,
        )
        if fault_before_checkpoint:
            raise RuntimeError("injected failure before C2C checkpoint commit")
        connection.execute(
            "UPDATE outcome_review_control_checkpoints SET "
            "last_action_plan_pk=?,last_series_plan_pk=?,tasks_written=?,"
            "slots_written=?,batches_committed=?,task_chain_sha256=?,"
            "slot_chain_sha256=?,audit_chain_sha256=?,completed=?,"
            "checkpoint_snapshot_effective_at=? "
            "WHERE pipeline_key=? AND stage='discovery_tasks'",
            (
                last["action_plan_pk"],
                last["series_plan_pk"],
                tasks_written,
                slots_written,
                batch_ordinal,
                task_chain,
                slot_chain,
                event_sha,
                completed,
                snapshot_effective_at,
                pipeline,
            ),
        )
        if completed:
            passed_meta = meta_row(
                config=config,
                pipeline=pipeline,
                config_sha=checkpoint["config_sha256"],
                source_sha=checkpoint["source_root_sha256"],
                schema_sha=checkpoint["schema_root_sha256"],
                snapshot_effective_at=snapshot_effective_at,
                capacity_status="PASS",
            )
            connection.execute(
                "UPDATE outcome_review_control_meta SET "
                "control_plane_capacity_status=?,row_semantic_sha256=? "
                "WHERE pipeline_key=?",
                (passed_meta[8], passed_meta[-1], pipeline),
            )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


def materialize(
    *,
    config_path: Path,
    schema_path: Path,
    out_db: Path,
    report_out: Path,
    manifest_out: Path,
    batch_size: int | None,
    stop_after_batches: int | None,
    fault_before_checkpoint_batch: int | None,
    bound_inputs: dict[Path, Any],
) -> tuple[int, dict[str, Any]]:
    started = time.monotonic()
    discovery_rows_committed_this_run = 0
    config_bound = _bound_input(bound_inputs, config_path)
    config = load_bound_json_input(config_bound)
    validate_config(config)
    configured_batch = config["expected"]["materialization_batch_size"]
    if batch_size is not None and batch_size != configured_batch:
        raise RuntimeError("runtime batch size differs from immutable C2C config")
    batch_size = configured_batch
    maximum_batches = config["expected"]["committed_discovery_batches"]
    for name, value in (
        ("stop_after_batches", stop_after_batches),
        ("fault_before_checkpoint_batch", fault_before_checkpoint_batch),
    ):
        if value is not None and (
            type(value) is not int or not 1 <= value <= maximum_batches
        ):
            raise RuntimeError(f"{name} exceeds the bounded batch contract")
    config_sha = sha256_bytes(canonical_bytes(config))
    schema_bound = _bound_input(bound_inputs, schema_path)
    schema_block, schema_sha = extract_schema_text(
        schema_bound.read_bytes(max_bytes=2 * 1024 * 1024).decode("utf-8")
    )
    source_sha = source_root(config)
    pipeline = pipeline_key(config_sha, source_sha, schema_sha)
    if (
        config_sha != EXPECTED_CONFIG_SHA256
        or source_sha != EXPECTED_SOURCE_ROOT_SHA256
        or schema_sha != EXPECTED_SCHEMA_ROOT_SHA256
        or pipeline != EXPECTED_PIPELINE_KEY
    ):
        raise RuntimeError("C2C canonical config, sources, or schema drifted")
    paths = verify_source_artifacts(config, bound_inputs)

    discovery_connection, discovery_identity = open_bound_immutable_db(
        paths["discovery_db_bound"]
    )
    canary_connection, canary_identity = open_bound_immutable_db(
        paths["canary_db_bound"]
    )
    target: sqlite3.Connection | None = None
    initialized = False
    resumed = False
    replayed = False
    try:
        require_discovery_support(discovery_connection, config)
        canary_row = require_canary_support(canary_connection, config)
        target = connect_target(out_db)
        initialized = initialize_target(
            target,
            schema_block=schema_block,
            pipeline=pipeline,
            config=config,
            config_sha=config_sha,
            source_sha=source_sha,
            schema_sha=schema_sha,
            canary_row=canary_row,
        )
        checkpoint = load_checkpoint(
            target,
            pipeline=pipeline,
            config_sha=config_sha,
            source_sha=source_sha,
            schema_sha=schema_sha,
        )
        verify_target_schema(target, schema_block)
        verify_target_state(target, checkpoint=checkpoint, config=config)
        if checkpoint["completed"]:
            replayed = True
        else:
            resumed = checkpoint["batches_committed"] > 0
            committed_this_run = 0
            while not checkpoint["completed"]:
                source_rows = discovery_page(
                    discovery_connection,
                    source_pipeline=config["sources"]["discovery_pairs"][
                        "pipeline_key"
                    ],
                    last_action=checkpoint["last_action_plan_pk"],
                    last_series=checkpoint["last_series_plan_pk"],
                    batch_size=batch_size,
                )
                if not source_rows:
                    raise RuntimeError(
                        "C2B discovery source ended before expected cardinality"
                    )
                next_batch = checkpoint["batches_committed"] + 1
                commit_discovery_batch(
                    target,
                    pipeline=pipeline,
                    config=config,
                    checkpoint=checkpoint,
                    source_rows=source_rows,
                    fault_before_checkpoint=(
                        fault_before_checkpoint_batch is not None
                        and next_batch == fault_before_checkpoint_batch
                    ),
                )
                discovery_rows_committed_this_run += len(source_rows)
                committed_this_run += 1
                checkpoint = load_checkpoint(
                    target,
                    pipeline=pipeline,
                    config_sha=config_sha,
                    source_sha=source_sha,
                    schema_sha=schema_sha,
                )
                if (
                    stop_after_batches is not None
                    and committed_this_run >= stop_after_batches
                    and not checkpoint["completed"]
                ):
                    interrupted = build_report(
                        target,
                        config=config,
                        config_sha=config_sha,
                        source_sha=source_sha,
                        schema_sha=schema_sha,
                        pipeline=pipeline,
                        status="interrupted",
                        execution="fresh" if initialized else "resumed",
                        database=None,
                        manifest=None,
                        execution_metrics=measured_execution(
                            started, discovery_rows_committed_this_run
                        ),
                    )
                    atomic_write_json(report_out, interrupted)
                    raise ControlledInterruption("committed C2C interruption requested")

        checkpoint = load_checkpoint(
            target,
            pipeline=pipeline,
            config_sha=config_sha,
            source_sha=source_sha,
            schema_sha=schema_sha,
        )
        if not checkpoint["completed"]:
            raise RuntimeError("C2C checkpoint did not complete")
        if (
            checkpoint["batches_committed"]
            != config["expected"]["committed_discovery_batches"]
        ):
            raise RuntimeError("C2C checkpoint batch cardinality mismatch")
        if not replayed:
            verify_target_state(target, checkpoint=checkpoint, config=config)
        target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        target.close()
        target = None
        database = {
            "filename": out_db.name,
            "bytes": out_db.stat().st_size,
            "sha256": sha256_file(out_db),
        }
        manifest = build_manifest(
            config=config,
            config_sha=config_sha,
            source_sha=source_sha,
            schema_sha=schema_sha,
            pipeline=pipeline,
            database=database,
            out_db=out_db,
        )
        atomic_write_json(manifest_out, manifest)
        manifest_descriptor = {
            "filename": manifest_out.name,
            "bytes": manifest_out.stat().st_size,
            "sha256": sha256_file(manifest_out),
            "manifest_root_sha256": manifest["manifest_root_sha256"],
        }
        verification = connect_target(out_db)
        try:
            execution = (
                "replayed_noop" if replayed else "resumed" if resumed else "fresh"
            )
            report = build_report(
                verification,
                config=config,
                config_sha=config_sha,
                source_sha=source_sha,
                schema_sha=schema_sha,
                pipeline=pipeline,
                status="passed",
                execution=execution,
                database=database,
                manifest=manifest_descriptor,
                execution_metrics=measured_execution(
                    started, discovery_rows_committed_this_run
                ),
            )
        finally:
            verification.close()
        atomic_write_json(report_out, report)
        return 0, report
    finally:
        if target is not None:
            target.close()
        close_immutable_db(
            discovery_connection, paths["discovery_db"], discovery_identity
        )
        close_immutable_db(canary_connection, paths["canary_db"], canary_identity)
        for path_key, identity_key in (
            ("discovery_manifest_path", "discovery_manifest_identity"),
            ("pointer_path", "pointer_identity"),
            ("canary_manifest_path", "canary_manifest_identity"),
        ):
            if stable_identity(paths[path_key]) != paths[identity_key]:
                raise RuntimeError(
                    f"source changed during run: {repo_path(paths[path_key])}"
                )


def table_count(connection: sqlite3.Connection, table: str) -> int:
    return connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def semantic_root(connection: sqlite3.Connection, pipeline: str) -> str:
    meta = connection.execute(
        "SELECT row_semantic_sha256 FROM outcome_review_control_meta WHERE pipeline_key=?",
        (pipeline,),
    ).fetchone()[0]
    cohort_chain = EMPTY_CHAIN
    for row in connection.execute(
        "SELECT row_semantic_sha256 FROM outcome_review_cohorts ORDER BY cohort_id"
    ):
        cohort_chain = chain_add(cohort_chain, row[0])
    checkpoint = connection.execute(
        "SELECT task_chain_sha256,slot_chain_sha256,audit_chain_sha256 "
        "FROM outcome_review_control_checkpoints WHERE pipeline_key=?",
        (pipeline,),
    ).fetchone()
    canary_task = connection.execute(
        "SELECT row_semantic_sha256 FROM outcome_review_tasks WHERE cohort_id=?",
        (CANARY_COHORT_ID,),
    ).fetchone()[0]
    canary_slot_chain = EMPTY_CHAIN
    for row in connection.execute(
        "SELECT s.row_semantic_sha256 FROM outcome_review_slots s "
        "JOIN outcome_review_tasks t USING(task_pk) WHERE t.cohort_id=? "
        "ORDER BY s.slot_ordinal",
        (CANARY_COHORT_ID,),
    ):
        canary_slot_chain = chain_add(canary_slot_chain, row[0])
    return sha256_bytes(
        canonical_bytes(
            {
                "contract_version": "outcome_review_control_semantic_root_c2c_v1",
                "meta_row_sha256": meta,
                "cohort_chain_sha256": cohort_chain,
                "discovery_task_chain_sha256": checkpoint[0],
                "discovery_slot_chain_sha256": checkpoint[1],
                "canary_task_sha256": canary_task,
                "canary_slot_chain_sha256": canary_slot_chain,
                "audit_chain_sha256": checkpoint[2],
            }
        )
    )


def max_rss_bytes() -> int:
    # Linux ru_maxrss can retain the parent's pre-exec high-water mark. VmHWM
    # measures this process image, so composed validation keeps a truthful cap.
    if sys.platform.startswith("linux"):
        try:
            for line in (
                Path("/proc/self/status").read_text(encoding="ascii").splitlines()
            ):
                parts = line.split()
                if len(parts) == 3 and parts[0] == "VmHWM:" and parts[2] == "kB":
                    return int(parts[1]) * 1024
        except (OSError, ValueError):
            pass
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if sys.platform == "darwin" else value * 1024


def measured_execution(started: float, rows: int) -> dict[str, Any]:
    elapsed = max(time.monotonic() - started, 0.000001)
    return {
        "elapsed_seconds": round(elapsed, 6),
        "discovery_rows_committed_this_run": rows,
        "discovery_rows_per_second": (round(rows / elapsed, 3) if rows else None),
    }


def counts(connection: sqlite3.Connection) -> dict[str, int]:
    result = {
        "cohorts": table_count(connection, "outcome_review_cohorts"),
        "tasks": table_count(connection, "outcome_review_tasks"),
        "slots": table_count(connection, "outcome_review_slots"),
        "audit_events": table_count(connection, "outcome_review_audit_events"),
    }
    for table in OPERATIONAL_TABLES:
        result[table.removeprefix("outcome_review_")] = table_count(connection, table)
    return result


def build_manifest(
    *,
    config: dict[str, Any],
    config_sha: str,
    source_sha: str,
    schema_sha: str,
    pipeline: str,
    database: dict[str, Any],
    out_db: Path,
) -> dict[str, Any]:
    connection = connect_target(out_db)
    try:
        body = {
            "format_version": MANIFEST_FORMAT,
            "contract_date": config["contract_date"],
            "pipeline_key": pipeline,
            "config_sha256": config_sha,
            "source_root_sha256": source_sha,
            "schema_root_sha256": schema_sha,
            "semantic_root_sha256": semantic_root(connection, pipeline),
            "database": database,
            "counts": counts(connection),
            "statuses": {
                "control_plane_capacity": "PASS",
                "human_review": "OPEN",
                "semantic_promotion": "OPEN",
                "public_release": "OPEN",
            },
            "root_scope": "capacity_only_excludes_future_operational_rows",
            "trust_root_contract": config["trust_root_contract"],
            "operational_lifecycle": config["operational_lifecycle_contract"],
            "publication_state": "local_control_artifact_not_public_release",
            "real_data_only": True,
            "synthetic_or_mock_decisions": 0,
        }
    finally:
        connection.close()
    body["manifest_root_sha256"] = sha256_bytes(
        canonical_bytes(
            {
                "contract_version": "outcome_review_control_manifest_root_c2c_v1",
                "manifest": body,
            }
        )
    )
    return body


def build_report(
    connection: sqlite3.Connection,
    *,
    config: dict[str, Any],
    config_sha: str,
    source_sha: str,
    schema_sha: str,
    pipeline: str,
    status: str,
    execution: str,
    database: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
    execution_metrics: dict[str, Any],
) -> dict[str, Any]:
    checkpoint = connection.execute(
        "SELECT * FROM outcome_review_control_checkpoints WHERE pipeline_key=?",
        (pipeline,),
    ).fetchone()
    meta = connection.execute(
        "SELECT * FROM outcome_review_control_meta WHERE pipeline_key=?", (pipeline,)
    ).fetchone()
    report: dict[str, Any] = {
        "format_version": REPORT_FORMAT,
        "status": status,
        "execution": execution,
        "contract_date": config["contract_date"],
        "pipeline_key": pipeline,
        "config_sha256": config_sha,
        "source_root_sha256": source_sha,
        "schema_root_sha256": schema_sha,
        "counts": counts(connection),
        "checkpoint": {
            "tasks_written": checkpoint["tasks_written"],
            "slots_written": checkpoint["slots_written"],
            "batches_committed": checkpoint["batches_committed"],
            "completed": checkpoint["completed"],
            "last_action_plan_pk": checkpoint["last_action_plan_pk"],
            "last_series_plan_pk": checkpoint["last_series_plan_pk"],
        },
        "statuses": {
            "control_plane_capacity": meta["control_plane_capacity_status"],
            "human_review": meta["human_review_status"],
            "semantic_promotion": meta["semantic_promotion_status"],
            "public_release": meta["public_release_status"],
        },
        "root_scope": "capacity_only_excludes_future_operational_rows",
        "trust_root_contract": config["trust_root_contract"],
        "operational_lifecycle": config["operational_lifecycle_contract"],
        "real_data_only": True,
        "synthetic_or_mock_decisions": 0,
        "maximum_resident_set_bytes": max_rss_bytes(),
        "execution_metrics": execution_metrics,
    }
    if checkpoint["completed"]:
        report["semantic_root_sha256"] = semantic_root(connection, pipeline)
    if database is not None:
        report["database"] = database
    if manifest is not None:
        report["manifest"] = manifest
    return report


def validate_path_separation(paths: Sequence[Path]) -> None:
    resolved = [Path(path).resolve(strict=False) for path in paths]
    for index, left in enumerate(resolved):
        for right in resolved[index + 1 :]:
            if paths_overlap(left, right):
                raise RuntimeError(
                    "all C2C command paths must be pairwise ancestor-disjoint"
                )


def validate_report_separation(report: Path, others: Sequence[Path]) -> None:
    for other in others:
        if paths_overlap(report, other):
            raise RuntimeError("C2C report path overlaps another command path")


def preflight_regular_input(path: Path) -> None:
    path = Path(path)
    if path.is_symlink() or not path.exists():
        raise RuntimeError("C2C immutable input is missing or linked")
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        raise RuntimeError("C2C immutable input is not a private regular file")


def configured_source_paths(config: dict[str, Any]) -> list[tuple[Path, bool]]:
    discovery = config["sources"]["discovery_pairs"]
    canary = config["sources"]["semantic_canary"]
    return [
        (resolve_repo_path(discovery["path"]), True),
        (resolve_repo_path(discovery["manifest_path"]), False),
        (resolve_repo_path(canary["pointer_path"]), False),
        (resolve_repo_path(canary["database_path"]), True),
        (resolve_repo_path(canary["manifest_path"]), False),
    ]


def load_bound_json(path: Path, *, max_bytes: int = 2 * 1024 * 1024) -> dict[str, Any]:
    with bound_regular_file(path) as bound:
        value = json.loads(
            bound.read_bytes(max_bytes=max_bytes).decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_json_constant,
        )
    if not isinstance(value, dict):
        raise RuntimeError("C2C JSON input must be an object")
    return value


def running_report() -> dict[str, Any]:
    return {
        "format_version": REPORT_FORMAT,
        "status": "running",
        "success_report_invalidated": True,
        "success_manifest_invalidated": True,
        "human_review": "OPEN",
        "semantic_promotion": "OPEN",
        "public_release": "OPEN",
    }


def failure_report(error: BaseException) -> dict[str, Any]:
    return {
        "format_version": REPORT_FORMAT,
        "status": "failed",
        "error_type": type(error).__name__,
        "success_report_invalidated": True,
        "success_manifest_invalidated": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--out-db", type=Path, default=DEFAULT_OUT_DB)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--stop-after-batches", type=int)
    parser.add_argument("--fault-before-checkpoint-batch", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    schema_path = Path(args.schema)
    out_db = Path(args.out_db)
    report_raw = Path(args.report_out)
    manifest_raw = Path(args.manifest_out)
    initial_paths = [config_path, schema_path, out_db, report_raw, manifest_raw]
    try:
        report_out = preflight_control_target(report_raw)
        validate_report_separation(
            report_out, [config_path, schema_path, out_db, manifest_raw]
        )
    except BaseException as error:
        print(
            f"ERROR: {type(error).__name__}: unsafe C2C command paths", file=sys.stderr
        )
        return 2
    initial_leases = identity_companion_leases(initial_paths, namespace="command")
    try:
        initial_leases.__enter__()
    except BaseException as error:
        # A shared evidence lease can collide even when this invocation owns
        # distinct control targets. In that case, replace any stale PASS and
        # remove its stale manifest. Never touch controls held by the winner.
        try:
            manifest_out = preflight_control_target(manifest_raw)
            validate_path_separation(initial_paths)
            with identity_companion_leases(
                [report_out, manifest_out], namespace="command"
            ):
                secure_unlink_regular(manifest_out)
                atomic_write_json(report_out, failure_report(error))
        except BaseException:
            pass
        print(
            f"ERROR: {type(error).__name__}: C2C command lease unavailable",
            file=sys.stderr,
        )
        return 1
    try:
        atomic_write_json(report_out, running_report())
        manifest_out: Path | None = None
        try:
            manifest_out = preflight_control_target(manifest_raw)
            out_db = preflight_control_target(out_db)
            validate_path_separation(initial_paths)
            secure_unlink_regular(manifest_out)
            preflight_regular_input(config_path)
            preflight_regular_input(schema_path)
            if out_db.exists():
                reject_nonempty_wal(out_db)
            config = load_bound_json(config_path)
            validate_config(config)
            source_paths = configured_source_paths(config)
            all_paths = [*initial_paths, *(path for path, _database in source_paths)]
            validate_path_separation(all_paths)
            for path, _database in source_paths:
                preflight_regular_input(path)
            source_leases = identity_companion_leases(
                [path for path, _database in source_paths], namespace="evidence"
            )
            source_leases.__enter__()
            try:
                with ExitStack() as evidence:
                    bound_inputs: dict[Path, Any] = {}

                    def bind(path: Path, *, database: bool = False) -> None:
                        bound = evidence.enter_context(
                            bound_regular_file(path, database=database)
                        )
                        bound_inputs[bound.path] = bound

                    bind(config_path)
                    bind(schema_path)
                    for path, database in source_paths:
                        bind(path, database=database)
                    code, report = materialize(
                        config_path=config_path,
                        schema_path=schema_path,
                        out_db=out_db,
                        report_out=report_out,
                        manifest_out=manifest_out,
                        batch_size=args.batch_size,
                        stop_after_batches=args.stop_after_batches,
                        fault_before_checkpoint_batch=args.fault_before_checkpoint_batch,
                        bound_inputs=bound_inputs,
                    )
                    if out_db.exists():
                        fsync_regular_file(out_db)
                        fsync_directory(out_db.parent)
            finally:
                source_leases.__exit__(None, None, None)
            print(canonical_json(report))
            return code
        except ControlledInterruption:
            report = load_json(report_out)
            print(canonical_json(report))
            return 3
        except BaseException as error:
            try:
                if manifest_out is not None:
                    secure_unlink_regular(manifest_out)
                atomic_write_json(report_out, failure_report(error))
                print(canonical_json(load_json(report_out)), file=sys.stderr)
            except BaseException:
                pass
            return 1
    finally:
        initial_leases.__exit__(None, None, None)


if __name__ == "__main__":
    raise SystemExit(main())
