#!/usr/bin/env python3
"""Independently validate the complete C2C real-human-review control plane."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import sqlite3
import stat
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.outcome_pair_identity_safety import (
    bound_regular_file,
    identity_companion_leases,
    paths_overlap,
    preflight_control_target,
    secure_atomic_write_json,
)

DEFAULT_CONFIG = (
    REPO_ROOT / "etl/data/manual/outcome_links/review_control_scope_c2c_v1.json"
)
DEFAULT_SCHEMA = REPO_ROOT / "etl/load/sqlite_schema.sql"
DEFAULT_PLAN_DB = REPO_ROOT / "etl/data/staging/outcome-review-control-c2c-v1.db"
DEFAULT_MATERIALIZATION_REPORT = (
    REPO_ROOT / "etl/data/staging/outcome-review-control-c2c-v1-report.json"
)
DEFAULT_MANIFEST = (
    REPO_ROOT / "etl/data/staging/outcome-review-control-c2c-v1-manifest.json"
)
DEFAULT_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/"
    / "outcome-review-control-c2c-v1-validation.json"
)

CONTROL_CONTRACT = "outcome_review_control_c2c_v1"
CHECKPOINT_CONTRACT = "outcome_review_control_checkpoint_c2c_v1"
VALIDATION_FORMAT = "outcome_review_control_c2c_validation_report_v1"
MATERIALIZATION_FORMAT = "outcome_review_control_c2c_materialization_report_v1"
MANIFEST_FORMAT = "outcome_review_control_c2c_manifest_v1"
SCHEMA_BEGIN = "-- BEGIN OUTCOME REVIEW CONTROL C2C SCHEMA"
SCHEMA_END = "-- END OUTCOME REVIEW CONTROL C2C SCHEMA"
EMPTY_CHAIN = hashlib.sha256(b"").hexdigest()
DISCOVERY_COHORT_ID = "vclc:outcome-review-cohort:c2b-l0-v1"
CANARY_COHORT_ID = "vclc:outcome-review-cohort:c1-l1-canary-v1"
ACTOR_ID = "vclc:outcome-review-control-materializer-c2c-v1"

# Canonical artifact identity pins are filled only after a clean real-data build.
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
EXPECTED_SEMANTIC_ROOT_SHA256 = (
    "21acddf2e8e29dbce637069abcc16c2fb4baf7d976a4167599285cbaf9a6960f"
)
EXPECTED_DATABASE_BYTES = 2864201728
EXPECTED_DATABASE_SHA256 = (
    "a97f99410672a1d2fc4c52866062c311f56da712333d58efa5ac6629f3c200fa"
)
EXPECTED_MANIFEST_BYTES = 2699
EXPECTED_MANIFEST_SHA256 = (
    "7ddc000f4ebd860423e0d8ef37490365aff890f0706321c1163bf0822052767e"
)
EXPECTED_MANIFEST_ROOT_SHA256 = (
    "131cff9f4829a5ef8007d5f9d67db042c7d184e9619394100877a27e301a4684"
)

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

TABLE_COLUMNS = {
    "outcome_review_control_meta": (
        "pipeline_key",
        "contract_version",
        "config_sha256",
        "source_root_sha256",
        "schema_root_sha256",
        "artifact_scope",
        "trust_root_contract_sha256",
        "operational_state",
        "control_plane_capacity_status",
        "human_review_status",
        "semantic_promotion_status",
        "public_release_status",
        "real_data_only",
        "synthetic_or_mock_decisions",
        "capacity_snapshot_effective_at",
        "row_semantic_sha256",
    ),
    "outcome_review_control_checkpoints": (
        "pipeline_key",
        "stage",
        "checkpoint_contract_version",
        "config_sha256",
        "source_root_sha256",
        "schema_root_sha256",
        "last_action_plan_pk",
        "last_series_plan_pk",
        "tasks_written",
        "slots_written",
        "batches_committed",
        "task_chain_sha256",
        "slot_chain_sha256",
        "audit_chain_sha256",
        "completed",
        "checkpoint_snapshot_effective_at",
    ),
    "outcome_review_cohorts": (
        "cohort_id",
        "pipeline_key",
        "cohort_kind",
        "source_artifact_path",
        "source_artifact_sha256",
        "source_manifest_sha256",
        "source_semantic_root_sha256",
        "evidence_level",
        "expected_task_count",
        "required_slots_per_task",
        "assignment_eligible",
        "requires_dual_review",
        "adjudication_on_disagreement",
        "semantic_promotion_requires_review",
        "public_release_requires_promotion",
        "eligibility_policy_json",
        "row_semantic_sha256",
    ),
    "outcome_review_tasks": (
        "task_pk",
        "task_id",
        "cohort_id",
        "task_kind",
        "source_row_id",
        "source_row_semantic_sha256",
        "source_action_plan_pk",
        "source_series_plan_pk",
        "evidence_level",
        "task_state",
        "assignment_eligible",
        "initial_semantic_promotion_eligible",
        "initial_publication_eligible",
        "row_semantic_sha256",
    ),
    "outcome_review_slots": (
        "slot_pk",
        "slot_id",
        "task_pk",
        "slot_kind",
        "slot_ordinal",
        "review_dimension",
        "required_reviewer_role",
        "independent_reviewer_required",
        "adjudication_rule",
        "slot_state",
        "row_semantic_sha256",
    ),
    "outcome_review_trust_roots": (
        "trust_root_id",
        "authority_public_id",
        "identity_provider",
        "provider_subject_sha256",
        "evidence_sha256",
        "effective_at",
        "expires_at",
        "row_semantic_sha256",
    ),
    "outcome_review_reviewer_identities": (
        "reviewer_public_id",
        "identity_provider",
        "provider_subject_sha256",
        "human_identity_sha256",
        "verified_by_trust_root_id",
        "registered_at",
        "identity_state",
        "row_semantic_sha256",
    ),
    "outcome_review_auth_events": (
        "auth_event_pk",
        "auth_event_id",
        "reviewer_public_id",
        "cohort_id",
        "reviewer_role",
        "auth_state",
        "supersedes_auth_event_id",
        "effective_at",
        "expires_at",
        "issuer_public_id",
        "issuer_trust_root_id",
        "evidence_sha256",
        "row_semantic_sha256",
    ),
    "outcome_review_conflict_events": (
        "conflict_event_pk",
        "conflict_event_id",
        "reviewer_public_id",
        "cohort_id",
        "task_pk",
        "conflict_kind",
        "conflict_state",
        "supersedes_conflict_event_id",
        "recorded_at",
        "evidence_json",
        "row_semantic_sha256",
    ),
    "outcome_review_assignment_events": (
        "assignment_event_pk",
        "assignment_event_id",
        "slot_pk",
        "reviewer_public_id",
        "auth_event_id",
        "assignment_state",
        "supersedes_assignment_event_id",
        "recorded_at",
        "row_semantic_sha256",
    ),
    "outcome_review_claim_events": (
        "claim_event_pk",
        "claim_event_id",
        "assignment_event_id",
        "slot_pk",
        "reviewer_public_id",
        "actor_public_id",
        "actor_auth_event_id",
        "claim_state",
        "supersedes_claim_event_id",
        "lease_token_sha256",
        "attempt_ordinal",
        "lease_expires_at",
        "recorded_at",
        "row_semantic_sha256",
    ),
    "outcome_review_decisions": (
        "decision_pk",
        "decision_id",
        "task_pk",
        "slot_pk",
        "assignment_event_id",
        "claim_event_id",
        "reviewer_public_id",
        "decision_value",
        "evidence_examined_json",
        "rationale",
        "decided_at",
        "row_semantic_sha256",
    ),
    "outcome_review_adjudications": (
        "adjudication_pk",
        "adjudication_id",
        "task_pk",
        "primary_decision_id",
        "secondary_decision_id",
        "adjudicator_public_id",
        "auth_event_id",
        "adjudicated_value",
        "evidence_examined_json",
        "rationale",
        "adjudicated_at",
        "row_semantic_sha256",
    ),
    "outcome_review_semantic_eligibility_events": (
        "eligibility_event_id",
        "task_pk",
        "eligibility_state",
        "primary_decision_id",
        "secondary_decision_id",
        "adjudication_id",
        "computed_at",
        "row_semantic_sha256",
    ),
    "outcome_review_semantic_promotions": (
        "promotion_id",
        "task_pk",
        "promotion_authority_public_id",
        "auth_event_id",
        "eligibility_event_id",
        "selected_value",
        "selected_evidence_level",
        "promoted_at",
        "row_semantic_sha256",
    ),
    "outcome_review_release_bindings": (
        "release_binding_id",
        "task_pk",
        "source_database_sha256",
        "outcome_link_release_id",
        "outcome_link_release_membership_id",
        "outcome_link_version_id",
        "release_descriptor_sha256",
        "membership_row_sha256",
        "verified_at",
        "row_semantic_sha256",
    ),
    "outcome_review_publication_eligibility_events": (
        "publication_eligibility_event_id",
        "task_pk",
        "promotion_id",
        "release_binding_id",
        "eligibility_state",
        "computed_at",
        "row_semantic_sha256",
    ),
    "outcome_review_publication_events": (
        "publication_event_id",
        "task_pk",
        "promotion_id",
        "publication_eligibility_event_id",
        "release_binding_id",
        "publisher_public_id",
        "auth_event_id",
        "outcome_link_release_id",
        "outcome_link_release_membership_id",
        "published_at",
        "row_semantic_sha256",
    ),
    "outcome_review_operation_requests": (
        "idempotency_key",
        "operation_kind",
        "payload_sha256",
        "target_table",
        "target_row_id",
        "applied_at",
        "row_semantic_sha256",
    ),
    "outcome_review_operational_audit_events": (
        "operational_audit_pk",
        "operational_audit_id",
        "idempotency_key",
        "operation_kind",
        "target_table",
        "target_row_id",
        "payload_sha256",
        "previous_event_sha256",
        "actor_public_id",
        "occurred_at",
        "event_sha256",
    ),
    "outcome_review_audit_events": (
        "audit_event_pk",
        "audit_event_id",
        "pipeline_key",
        "event_kind",
        "batch_ordinal",
        "source_rows_committed",
        "slots_committed",
        "previous_event_sha256",
        "event_payload_json",
        "actor_kind",
        "actor_id",
        "snapshot_effective_at",
        "event_sha256",
    ),
}

OPERATIONAL_TABLES = tuple(
    name
    for name in TABLE_COLUMNS
    if name
    in {
        "outcome_review_reviewer_identities",
        "outcome_review_trust_roots",
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
    }
)


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


def reject_nonempty_wal(path: Path) -> None:
    resolved = Path(path).resolve(strict=True)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{resolved}{suffix}")
        if sidecar.exists() or sidecar.is_symlink():
            value = sidecar.lstat()
            if not stat.S_ISREG(value.st_mode) or value.st_size:
                raise RuntimeError(f"database has an unsafe sidecar: {repo_path(path)}")


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
        raise RuntimeError("immutable connection wrote data")
    connection.commit()
    connection.close()
    reject_nonempty_wal(path)
    if stable_identity(path) != identity:
        raise RuntimeError(f"source changed during validation: {repo_path(path)}")


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
            "format_version": VALIDATION_FORMAT,
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
    if set(config) != {
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
    }:
        raise RuntimeError("C2C config root keys do not match the contract")
    if config["format_version"] != "outcome_review_control_scope_c2c_v1":
        raise RuntimeError("unsupported C2C config format")
    if config["control_contract_version"] != CONTROL_CONTRACT:
        raise RuntimeError("unsupported C2C control contract")
    if config["checkpoint_contract_version"] != CHECKPOINT_CONTRACT:
        raise RuntimeError("unsupported C2C checkpoint contract")
    required_statuses = {
        "control_plane_capacity_status": "PASS",
        "human_review_status": "OPEN",
        "semantic_promotion_status": "OPEN",
        "public_release_status": "OPEN",
    }
    for key, value in required_statuses.items():
        if config["policy"].get(key) != value:
            raise RuntimeError(f"C2C policy status mismatch: {key}")
    if config["policy"].get("real_data_only") is not True:
        raise RuntimeError("C2C real-data-only policy is absent")
    if config["policy"].get("synthetic_or_mock_decisions") != 0:
        raise RuntimeError("C2C synthetic/mock decision count is not zero")
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
        raise RuntimeError("C2C trust-root contract drifted")
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
    exact = {
        "cohorts": 2,
        "discovery_tasks": 2_865_602,
        "discovery_primary_slots": 2_865_602,
        "semantic_canary_tasks": 1,
        "semantic_canary_slots": 2,
        "total_tasks": 2_865_603,
        "total_slots": 2_865_604,
        "reviewer_identities": 0,
        "trust_roots": 0,
        "auth_events": 0,
        "conflict_events": 0,
        "assignment_events": 0,
        "claim_events": 0,
        "decisions": 0,
        "adjudications": 0,
        "semantic_eligibility_events": 0,
        "semantic_promotions": 0,
        "release_bindings": 0,
        "publication_eligibility_events": 0,
        "publication_events": 0,
        "operation_requests": 0,
        "operational_audit_events": 0,
        "materialization_batch_size": 25_000,
        "committed_discovery_batches": 115,
        "audit_events": 116,
        "maximum_validator_rss_bytes": 536_870_912,
    }
    if expected != exact:
        raise RuntimeError("C2C expected cardinalities drifted")
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


def row_tuple(row: sqlite3.Row) -> tuple[Any, ...]:
    return tuple(row)


def expected_meta(
    pipeline: str,
    config_sha: str,
    source_sha: str,
    schema_sha: str,
    snapshot_effective_at: str,
) -> tuple[Any, ...]:
    row = {
        "pipeline_key": pipeline,
        "contract_version": CONTROL_CONTRACT,
        "config_sha256": config_sha,
        "source_root_sha256": source_sha,
        "schema_root_sha256": schema_sha,
        "artifact_scope": "capacity_only",
        "trust_root_contract_sha256": "ce76316802e222eafe5a4823bb52cc17c76167f22a3ffcef240ad67c267c16c8",
        "operational_state": "not_materialized",
        "control_plane_capacity_status": "PASS",
        "human_review_status": "OPEN",
        "semantic_promotion_status": "OPEN",
        "public_release_status": "OPEN",
        "real_data_only": 1,
        "synthetic_or_mock_decisions": 0,
        "capacity_snapshot_effective_at": snapshot_effective_at,
    }
    return tuple(row.values()) + (
        persisted_row_sha256("outcome_review_control_meta_row_c2c_v1", row),
    )


def expected_cohorts(config: dict[str, Any], pipeline: str) -> list[tuple[Any, ...]]:
    discovery = config["sources"]["discovery_pairs"]
    canary = config["sources"]["semantic_canary"]
    rows = [
        {
            "cohort_id": DISCOVERY_COHORT_ID,
            "pipeline_key": pipeline,
            "cohort_kind": "c2b_l0_discovery",
            "source_artifact_path": discovery["path"],
            "source_artifact_sha256": discovery["sha256"],
            "source_manifest_sha256": discovery["manifest_sha256"],
            "source_semantic_root_sha256": discovery["semantic_root_sha256"],
            "evidence_level": "L0",
            "expected_task_count": 2_865_602,
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
    result = [
        tuple(row.values())
        + (persisted_row_sha256("outcome_review_cohort_row_c2c_v1", row),)
        for row in rows
    ]
    return sorted(result, key=lambda row: row[0])


def expected_canary(
    config: dict[str, Any], canary_source: sqlite3.Row
) -> tuple[tuple[Any, ...], list[tuple[Any, ...]]]:
    task_pk = 2_865_603
    task_id = task_identity(CANARY_COHORT_ID, canary_source["outcome_link_version_id"])
    task = {
        "task_pk": task_pk,
        "task_id": task_id,
        "cohort_id": CANARY_COHORT_ID,
        "task_kind": "semantic_canary",
        "source_row_id": canary_source["outcome_link_version_id"],
        "source_row_semantic_sha256": canary_source["version_identity_sha256"],
        "source_action_plan_pk": None,
        "source_series_plan_pk": None,
        "evidence_level": "L1",
        "task_state": "pending_human_review",
        "assignment_eligible": 1,
        "initial_semantic_promotion_eligible": 0,
        "initial_publication_eligible": 0,
    }
    task_tuple = tuple(task.values()) + (
        persisted_row_sha256("outcome_review_task_row_c2c_v1", task),
    )
    slots: list[tuple[Any, ...]] = []
    for ordinal, kind in ((1, "semantic_primary"), (2, "semantic_secondary")):
        slot = {
            "slot_pk": 2_865_602 + ordinal,
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
        slots.append(
            tuple(slot.values())
            + (persisted_row_sha256("outcome_review_slot_row_c2c_v1", slot),)
        )
    return task_tuple, slots


def expected_discovery_task(source: sqlite3.Row, task_pk: int) -> tuple[Any, ...]:
    task_id = task_identity(DISCOVERY_COHORT_ID, source["pair_plan_id"])
    row = {
        "task_pk": task_pk,
        "task_id": task_id,
        "cohort_id": DISCOVERY_COHORT_ID,
        "task_kind": "discovery_triage",
        "source_row_id": source["pair_plan_id"],
        "source_row_semantic_sha256": source["row_semantic_sha256"],
        "source_action_plan_pk": source["action_plan_pk"],
        "source_series_plan_pk": source["series_plan_pk"],
        "evidence_level": "L0",
        "task_state": "pending_human_review",
        "assignment_eligible": 1,
        "initial_semantic_promotion_eligible": 0,
        "initial_publication_eligible": 0,
    }
    return tuple(row.values()) + (
        persisted_row_sha256("outcome_review_task_row_c2c_v1", row),
    )


def expected_discovery_slot(task: tuple[Any, ...]) -> tuple[Any, ...]:
    task_pk, task_id = task[0], task[1]
    row = {
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
    return tuple(row.values()) + (
        persisted_row_sha256("outcome_review_slot_row_c2c_v1", row),
    )


def expected_audit_event(
    *,
    pipeline: str,
    event_kind: str,
    batch_ordinal: int,
    source_rows: int,
    slots: int,
    previous: str,
    payload: dict[str, Any],
    snapshot_effective_at: str,
) -> tuple[Any, ...]:
    row = {
        "audit_event_pk": batch_ordinal + 1,
        "audit_event_id": f"vclc:outcome-review-audit:{pipeline.rsplit(':', 1)[-1]}:{batch_ordinal:06d}",
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
    return tuple(row.values()) + (
        persisted_row_sha256("outcome_review_audit_event_c2c_v1", row),
    )


def validate_schema(
    target: sqlite3.Connection, schema_block: str, audit: Audit
) -> None:
    # Schema-only scratch database: it receives production DDL and no control rows.
    with tempfile.TemporaryDirectory(prefix="vclc-c2c-schema-validation-") as directory:
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
                for row in target.execute(
                    "SELECT type,name,sql FROM sqlite_master "
                    "WHERE tbl_name LIKE 'outcome_review_%' AND sql IS NOT NULL"
                )
            }
            audit.equal(
                "schema_object_names_exact", set(actual_objects), set(expected_objects)
            )
            audit.equal("schema_object_sql_exact", actual_objects, expected_objects)
            for table, columns in TABLE_COLUMNS.items():
                actual_columns = tuple(
                    row[1] for row in target.execute(f'PRAGMA table_info("{table}")')
                )
                audit.equal(f"columns_exact_{table}", actual_columns, columns)
        finally:
            expected.close()


def verify_external_sources(
    config: dict[str, Any], audit: Audit, bound_inputs: dict[Path, Any]
) -> tuple[sqlite3.Connection, sqlite3.Connection, dict[str, Any]]:
    discovery = config["sources"]["discovery_pairs"]
    discovery_path = resolve_repo_path(discovery["path"])
    discovery_bound = _bound_input(bound_inputs, discovery_path)
    discovery_identity = verify_bound_pin(
        discovery_bound, discovery["bytes"], discovery["sha256"]
    )
    discovery_manifest_path = resolve_repo_path(discovery["manifest_path"])
    discovery_manifest_bound = _bound_input(bound_inputs, discovery_manifest_path)
    discovery_manifest_identity = verify_bound_pin(
        discovery_manifest_bound,
        discovery["manifest_bytes"],
        discovery["manifest_sha256"],
    )
    discovery_manifest = load_bound_json_input(discovery_manifest_bound)
    audit.equal(
        "source_c2b_manifest_root",
        discovery_manifest.get("manifest_root_sha256"),
        discovery["manifest_root_sha256"],
    )
    audit.equal(
        "source_c2b_semantic_root",
        discovery_manifest.get("roots", {}).get("semantic_root_sha256"),
        discovery["semantic_root_sha256"],
    )
    audit.equal(
        "source_c2b_manifest_pairs",
        discovery_manifest.get("counts", {}).get("pairs"),
        2_865_602,
    )

    canary = config["sources"]["semantic_canary"]
    canary_path = resolve_repo_path(canary["database_path"])
    canary_bound = _bound_input(bound_inputs, canary_path)
    canary_identity = verify_bound_pin(
        canary_bound, canary["database_bytes"], canary["database_sha256"]
    )
    pointer_path = resolve_repo_path(canary["pointer_path"])
    pointer_bound = _bound_input(bound_inputs, pointer_path)
    pointer_identity = verify_bound_pin(
        pointer_bound, canary["pointer_bytes"], canary["pointer_sha256"]
    )
    pointer = load_bound_json_input(pointer_bound)
    for key in (
        "artifact_set_sha256",
        "bundle_semantic_sha256",
        "candidate_version_id",
        "candidate_version_identity_sha256",
        "manifest_sha256",
    ):
        audit.equal(f"source_c1_pointer_{key}", pointer.get(key), canary[key])
    audit.equal(
        "source_c1_pointer_publication",
        pointer.get("publication_state"),
        "not_released",
    )
    canary_manifest_path = resolve_repo_path(canary["manifest_path"])
    canary_manifest_bound = _bound_input(bound_inputs, canary_manifest_path)
    canary_manifest_identity = verify_bound_pin(
        canary_manifest_bound,
        canary["manifest_bytes"],
        canary["manifest_sha256"],
    )
    canary_manifest = load_bound_json_input(canary_manifest_bound)
    audit.equal(
        "source_c1_manifest_artifact_set",
        canary_manifest.get("artifact_set_sha256"),
        canary["artifact_set_sha256"],
    )
    audit.equal(
        "source_c1_manifest_semantic_root",
        canary_manifest.get("bundle_semantic_sha256"),
        canary["bundle_semantic_sha256"],
    )
    discovery_connection, opened_discovery_identity = open_bound_immutable_db(
        discovery_bound
    )
    canary_connection, opened_canary_identity = open_bound_immutable_db(canary_bound)
    audit.equal(
        "source_c2b_identity_stable_before_open",
        opened_discovery_identity,
        discovery_identity,
    )
    audit.equal(
        "source_c1_identity_stable_before_open", opened_canary_identity, canary_identity
    )
    return (
        discovery_connection,
        canary_connection,
        {
            "discovery_path": discovery_path,
            "discovery_identity": discovery_identity,
            "discovery_manifest_path": discovery_manifest_path,
            "discovery_manifest_identity": discovery_manifest_identity,
            "canary_path": canary_path,
            "canary_identity": canary_identity,
            "pointer_path": pointer_path,
            "pointer_identity": pointer_identity,
            "canary_manifest_path": canary_manifest_path,
            "canary_manifest_identity": canary_manifest_identity,
        },
    )


def source_page(
    connection: sqlite3.Connection,
    pipeline: str,
    last_action: int,
    last_series: int,
    batch_size: int,
) -> list[sqlite3.Row]:
    cursor = connection.execute(
        f"SELECT {','.join(DISCOVERY_COLUMNS)} FROM outcome_pair_plan_pairs "
        "WHERE pipeline_key=? AND (action_plan_pk>? OR "
        "(action_plan_pk=? AND series_plan_pk>?)) "
        "ORDER BY action_plan_pk,series_plan_pk LIMIT ?",
        (pipeline, last_action, last_action, last_series, batch_size),
    )
    rows = list(cursor)
    cursor.close()
    return rows


def target_page(
    connection: sqlite3.Connection, table: str, pk: str, last_pk: int, batch_size: int
) -> list[sqlite3.Row]:
    cursor = connection.execute(
        f'SELECT * FROM "{table}" WHERE "{pk}">? ORDER BY "{pk}" LIMIT ?',
        (last_pk, batch_size),
    )
    rows = list(cursor)
    cursor.close()
    return rows


def validate_canary_source(
    connection: sqlite3.Connection, config: dict[str, Any], audit: Audit
) -> sqlite3.Row:
    rows = list(
        connection.execute(
            "SELECT outcome_link_version_id,version_identity_sha256,version_state,"
            "evidence_level,candidate_status,machine_audit_state,human_review_required,"
            "human_review_completed,published,directional_countable,ranking_eligible "
            "FROM outcome_link_versions ORDER BY outcome_link_version_id LIMIT 2"
        )
    )
    audit.equal("source_c1_version_count", len(rows), 1)
    row = rows[0]
    canary = config["sources"]["semantic_canary"]
    policy = config["query_contract"]["semantic_canary_policy"]
    expected = {
        "outcome_link_version_id": canary["candidate_version_id"],
        "version_identity_sha256": canary["candidate_version_identity_sha256"],
        "version_state": policy["version_state"],
        "evidence_level": policy["evidence_level"],
        "candidate_status": policy["candidate_status"],
        "machine_audit_state": policy["machine_audit_state"],
        "human_review_required": 1,
        "human_review_completed": 0,
        "published": 0,
        "directional_countable": 0,
        "ranking_eligible": 0,
    }
    for key, value in expected.items():
        audit.equal(f"source_c1_version_{key}", row[key], value)
    for table, expected_count in (
        ("outcome_link_reviews", 0),
        ("outcome_link_releases", 0),
        ("outcome_link_release_memberships", 0),
    ):
        audit.equal(
            f"source_c1_empty_{table}",
            connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0],
            expected_count,
        )
    return row


def validate_rows(
    target: sqlite3.Connection,
    discovery: sqlite3.Connection,
    canary: sqlite3.Connection,
    *,
    config: dict[str, Any],
    pipeline: str,
    config_sha: str,
    source_sha: str,
    schema_sha: str,
    audit: Audit,
) -> dict[str, str]:
    source_plan_details = " ".join(
        str(row[3])
        for row in discovery.execute(
            f"EXPLAIN QUERY PLAN SELECT {','.join(DISCOVERY_COLUMNS)} "
            "FROM outcome_pair_plan_pairs WHERE pipeline_key=? AND "
            "(action_plan_pk>? OR (action_plan_pk=? AND series_plan_pk>?)) "
            "ORDER BY action_plan_pk,series_plan_pk LIMIT ?",
            (config["sources"]["discovery_pairs"]["pipeline_key"], 0, 0, 0, 1),
        )
    )
    audit.check(
        "source_c2b_keyset_plan_indexed",
        "SEARCH outcome_pair_plan_pairs USING" in source_plan_details
        and "SCAN outcome_pair_plan_pairs" not in source_plan_details
        and "USE TEMP B-TREE" not in source_plan_details,
    )
    snapshot_effective_at = f"{config['contract_date']}T00:00:00Z"
    meta_rows = list(target.execute("SELECT * FROM outcome_review_control_meta"))
    audit.equal("meta_row_count", len(meta_rows), 1)
    audit.equal(
        "meta_row_reconstruction",
        row_tuple(meta_rows[0]),
        expected_meta(
            pipeline, config_sha, source_sha, schema_sha, snapshot_effective_at
        ),
    )
    actual_cohorts = [
        row_tuple(row)
        for row in target.execute(
            "SELECT * FROM outcome_review_cohorts ORDER BY cohort_id"
        )
    ]
    audit.equal(
        "cohort_row_reconstruction", actual_cohorts, expected_cohorts(config, pipeline)
    )

    canary_source = validate_canary_source(canary, config, audit)
    expected_canary_task, expected_canary_slots = expected_canary(config, canary_source)
    actual_canary_task = target.execute(
        "SELECT * FROM outcome_review_tasks WHERE cohort_id=?", (CANARY_COHORT_ID,)
    ).fetchone()
    audit.check("canary_task_present", actual_canary_task is not None)
    audit.equal(
        "canary_task_reconstruction",
        row_tuple(actual_canary_task),
        expected_canary_task,
    )
    actual_canary_slots = [
        row_tuple(row)
        for row in target.execute(
            "SELECT s.* FROM outcome_review_slots s JOIN outcome_review_tasks t USING(task_pk) "
            "WHERE t.cohort_id=? ORDER BY s.slot_ordinal",
            (CANARY_COHORT_ID,),
        )
    ]
    audit.equal(
        "canary_slot_reconstruction", actual_canary_slots, expected_canary_slots
    )

    policy = config["query_contract"]["discovery_pair_policy"]
    batch_size = config["expected"]["materialization_batch_size"]
    source_pipeline = config["sources"]["discovery_pairs"]["pipeline_key"]
    task_chain = EMPTY_CHAIN
    slot_chain = EMPTY_CHAIN
    audit_chain = EMPTY_CHAIN
    initial_payload = {
        "canary_semantic_slots": 2,
        "canary_tasks": 1,
        "control_plane_capacity_status": "BUILDING",
        "human_review_status": "OPEN",
        "semantic_promotion_status": "OPEN",
        "public_release_status": "OPEN",
        "synthetic_or_mock_decisions": 0,
    }
    initial_event = expected_audit_event(
        pipeline=pipeline,
        event_kind="control_initialized",
        batch_ordinal=0,
        source_rows=0,
        slots=2,
        previous=EMPTY_CHAIN,
        payload=initial_payload,
        snapshot_effective_at=snapshot_effective_at,
    )
    actual_initial = target.execute(
        "SELECT * FROM outcome_review_audit_events WHERE batch_ordinal=0"
    ).fetchone()
    audit.check("initial_audit_present", actual_initial is not None)
    audit.equal(
        "initial_audit_reconstruction", row_tuple(actual_initial), initial_event
    )
    audit_chain = initial_event[-1]

    last_action = 0
    last_series = 0
    task_pk = 0
    batch_ordinal = 0
    policy_keys = tuple(policy)
    policy_values = tuple(policy[key] for key in policy_keys)
    while True:
        sources = source_page(
            discovery, source_pipeline, last_action, last_series, batch_size
        )
        if not sources:
            break
        targets = target_page(
            target, "outcome_review_tasks", "task_pk", task_pk, len(sources)
        )
        slots = target_page(
            target, "outcome_review_slots", "slot_pk", task_pk, len(sources)
        )
        audit.equal(
            f"batch_{batch_ordinal + 1}_task_page_size", len(targets), len(sources)
        )
        audit.equal(
            f"batch_{batch_ordinal + 1}_slot_page_size", len(slots), len(sources)
        )
        for source_row, target_row, slot_row in zip(
            sources, targets, slots, strict=True
        ):
            if tuple(source_row[key] for key in policy_keys) != policy_values:
                raise RuntimeError(
                    "C2B discovery source violates the zero-claim policy"
                )
            task_pk += 1
            expected_task = expected_discovery_task(source_row, task_pk)
            expected_slot = expected_discovery_slot(expected_task)
            if row_tuple(target_row) != expected_task:
                raise RuntimeError(f"discovery task row mismatch at task_pk={task_pk}")
            if row_tuple(slot_row) != expected_slot:
                raise RuntimeError(f"discovery slot row mismatch at slot_pk={task_pk}")
            task_chain = chain_add(task_chain, expected_task[-1])
            slot_chain = chain_add(slot_chain, expected_slot[-1])
        batch_ordinal += 1
        last_action = sources[-1]["action_plan_pk"]
        last_series = sources[-1]["series_plan_pk"]
        payload = {
            "batch_ordinal": batch_ordinal,
            "cumulative_discovery_slots": task_pk,
            "cumulative_discovery_tasks": task_pk,
            "last_action_plan_pk": last_action,
            "last_series_plan_pk": last_series,
            "source_rows_committed": len(sources),
        }
        event = expected_audit_event(
            pipeline=pipeline,
            event_kind="discovery_batch_committed",
            batch_ordinal=batch_ordinal,
            source_rows=len(sources),
            slots=len(sources),
            previous=audit_chain,
            payload=payload,
            snapshot_effective_at=snapshot_effective_at,
        )
        actual_event = target.execute(
            "SELECT * FROM outcome_review_audit_events WHERE batch_ordinal=?",
            (batch_ordinal,),
        ).fetchone()
        if actual_event is None or row_tuple(actual_event) != event:
            raise RuntimeError(f"audit event mismatch at batch={batch_ordinal}")
        audit_chain = event[-1]

    audit.check("source_zero_claim_policy_all_rows", True)
    audit.equal("discovery_rows_reconstructed", task_pk, 2_865_602)
    audit.equal("discovery_batches_derived", batch_ordinal, 115)
    audit.equal("discovery_last_action", last_action, 458)
    audit.equal("discovery_last_series", last_series, 6400)
    audit.equal(
        "no_extra_discovery_task",
        target.execute(
            "SELECT COUNT(*) FROM outcome_review_tasks WHERE task_pk>? AND cohort_id=?",
            (task_pk, DISCOVERY_COHORT_ID),
        ).fetchone()[0],
        0,
    )
    audit.equal(
        "no_extra_discovery_slot",
        target.execute(
            "SELECT COUNT(*) FROM outcome_review_slots WHERE slot_pk>? AND slot_pk<=?",
            (task_pk, 2_865_602),
        ).fetchone()[0],
        0,
    )
    audit.equal(
        "no_extra_audit_event",
        target.execute(
            "SELECT COUNT(*) FROM outcome_review_audit_events WHERE batch_ordinal>?",
            (batch_ordinal,),
        ).fetchone()[0],
        0,
    )
    return {
        "task_chain_sha256": task_chain,
        "slot_chain_sha256": slot_chain,
        "audit_chain_sha256": audit_chain,
        "canary_task_sha256": expected_canary_task[-1],
        "canary_slot_chain_sha256": chain_add(
            chain_add(EMPTY_CHAIN, expected_canary_slots[0][-1]),
            expected_canary_slots[1][-1],
        ),
    }


def semantic_root(
    meta_sha: str, cohort_rows: Iterable[tuple[Any, ...]], roots: dict[str, str]
) -> str:
    cohort_chain = EMPTY_CHAIN
    for row in cohort_rows:
        cohort_chain = chain_add(cohort_chain, row[-1])
    return sha256_bytes(
        canonical_bytes(
            {
                "contract_version": "outcome_review_control_semantic_root_c2c_v1",
                "meta_row_sha256": meta_sha,
                "cohort_chain_sha256": cohort_chain,
                "discovery_task_chain_sha256": roots["task_chain_sha256"],
                "discovery_slot_chain_sha256": roots["slot_chain_sha256"],
                "canary_task_sha256": roots["canary_task_sha256"],
                "canary_slot_chain_sha256": roots["canary_slot_chain_sha256"],
                "audit_chain_sha256": roots["audit_chain_sha256"],
            }
        )
    )


def expected_counts() -> dict[str, int]:
    return {
        "cohorts": 2,
        "tasks": 2_865_603,
        "slots": 2_865_604,
        "audit_events": 116,
        "trust_roots": 0,
        "reviewer_identities": 0,
        "auth_events": 0,
        "conflict_events": 0,
        "assignment_events": 0,
        "claim_events": 0,
        "decisions": 0,
        "adjudications": 0,
        "semantic_eligibility_events": 0,
        "semantic_promotions": 0,
        "release_bindings": 0,
        "publication_eligibility_events": 0,
        "publication_events": 0,
        "operation_requests": 0,
        "operational_audit_events": 0,
    }


def table_count(connection: sqlite3.Connection, table: str) -> int:
    return connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def validate_control_counts(target: sqlite3.Connection, audit: Audit) -> dict[str, int]:
    counts = {
        "cohorts": table_count(target, "outcome_review_cohorts"),
        "tasks": table_count(target, "outcome_review_tasks"),
        "slots": table_count(target, "outcome_review_slots"),
        "audit_events": table_count(target, "outcome_review_audit_events"),
    }
    for table in OPERATIONAL_TABLES:
        counts[table.removeprefix("outcome_review_")] = table_count(target, table)
    audit.equal("all_table_counts_exact", counts, expected_counts())
    audit.equal(
        "all_tasks_pending",
        target.execute(
            "SELECT COUNT(*) FROM outcome_review_tasks WHERE task_state='pending_human_review'"
        ).fetchone()[0],
        counts["tasks"],
    )
    audit.equal(
        "all_slots_pending_unassigned",
        target.execute(
            "SELECT COUNT(*) FROM outcome_review_slots WHERE slot_state='pending_unassigned'"
        ).fetchone()[0],
        counts["slots"],
    )
    audit.equal(
        "no_claim_or_publication_elevation",
        target.execute(
            "SELECT SUM(initial_semantic_promotion_eligible)+SUM(initial_publication_eligible) "
            "FROM outcome_review_tasks"
        ).fetchone()[0],
        0,
    )
    return counts


def validate_checkpoint(
    target: sqlite3.Connection,
    *,
    pipeline: str,
    config_sha: str,
    source_sha: str,
    schema_sha: str,
    roots: dict[str, str],
    snapshot_effective_at: str,
    audit: Audit,
) -> None:
    rows = list(target.execute("SELECT * FROM outcome_review_control_checkpoints"))
    audit.equal("checkpoint_row_count", len(rows), 1)
    expected = (
        pipeline,
        "discovery_tasks",
        CHECKPOINT_CONTRACT,
        config_sha,
        source_sha,
        schema_sha,
        458,
        6400,
        2_865_602,
        2_865_602,
        115,
        roots["task_chain_sha256"],
        roots["slot_chain_sha256"],
        roots["audit_chain_sha256"],
        1,
        snapshot_effective_at,
    )
    audit.equal("checkpoint_exact_reconstruction", row_tuple(rows[0]), expected)


def expected_manifest(
    *,
    config: dict[str, Any],
    pipeline: str,
    config_sha: str,
    source_sha: str,
    schema_sha: str,
    semantic_sha: str,
    database: dict[str, Any],
    counts: dict[str, int],
) -> dict[str, Any]:
    body = {
        "format_version": MANIFEST_FORMAT,
        "contract_date": config["contract_date"],
        "pipeline_key": pipeline,
        "config_sha256": config_sha,
        "source_root_sha256": source_sha,
        "schema_root_sha256": schema_sha,
        "semantic_root_sha256": semantic_sha,
        "database": database,
        "counts": counts,
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
    body["manifest_root_sha256"] = sha256_bytes(
        canonical_bytes(
            {
                "contract_version": "outcome_review_control_manifest_root_c2c_v1",
                "manifest": body,
            }
        )
    )
    return body


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


def validate(
    *,
    config_path: Path,
    schema_path: Path,
    plan_db_path: Path,
    materialization_report_path: Path,
    manifest_path: Path,
    report_out: Path,
    bound_inputs: dict[Path, Any],
) -> dict[str, Any]:
    audit = Audit()
    config_bound = _bound_input(bound_inputs, config_path)
    config = load_bound_json_input(config_bound)
    validate_config(config)
    config_sha = sha256_bytes(canonical_bytes(config))
    schema_bound = _bound_input(bound_inputs, schema_path)
    schema_block, schema_sha = extract_schema_text(
        schema_bound.read_bytes(max_bytes=2 * 1024 * 1024).decode("utf-8")
    )
    source_sha = source_root(config)
    pipeline = pipeline_key(config_sha, source_sha, schema_sha)
    audit.equal("config_sha256_pin", config_sha, EXPECTED_CONFIG_SHA256)
    audit.equal("source_root_sha256_pin", source_sha, EXPECTED_SOURCE_ROOT_SHA256)
    audit.equal("schema_root_sha256_pin", schema_sha, EXPECTED_SCHEMA_ROOT_SHA256)
    audit.equal("pipeline_key_pin", pipeline, EXPECTED_PIPELINE_KEY)

    manifest_bound = _bound_input(bound_inputs, manifest_path)
    manifest_identity = verify_bound_pin(
        manifest_bound, EXPECTED_MANIFEST_BYTES, EXPECTED_MANIFEST_SHA256
    )
    materialization_bound = _bound_input(bound_inputs, materialization_report_path)
    materialization_identity = _bound_identity(materialization_bound)
    manifest = load_bound_json_input(manifest_bound)
    materialization_report = load_bound_json_input(materialization_bound)
    audit.equal(
        "materialization_report_format",
        materialization_report.get("format_version"),
        MATERIALIZATION_FORMAT,
    )
    audit.equal(
        "materialization_report_status", materialization_report.get("status"), "passed"
    )
    audit.check(
        "materialization_execution_enum",
        materialization_report.get("execution")
        in {"fresh", "resumed", "replayed_noop"},
    )
    serialized_reports = canonical_json(
        {"manifest": manifest, "materialization": materialization_report}
    )
    audit.check(
        "reports_have_no_workstation_paths",
        all(
            marker not in serialized_reports
            for marker in ("/Users/", "/home/", "file://")
        ),
    )
    plan_bound = _bound_input(bound_inputs, plan_db_path)
    plan_identity = verify_bound_pin(
        plan_bound, EXPECTED_DATABASE_BYTES, EXPECTED_DATABASE_SHA256
    )
    discovery, canary, source_facts = verify_external_sources(
        config, audit, bound_inputs
    )

    target, opened_plan_identity = open_bound_immutable_db(plan_bound)
    audit.equal("plan_identity_stable_before_open", opened_plan_identity, plan_identity)
    try:
        validate_schema(target, schema_block, audit)
        audit.equal(
            "quick_check", target.execute("PRAGMA quick_check").fetchone()[0], "ok"
        )
        audit.equal(
            "foreign_key_check_first_violation",
            target.execute("PRAGMA foreign_key_check").fetchone(),
            None,
        )
        counts = validate_control_counts(target, audit)
        roots = validate_rows(
            target,
            discovery,
            canary,
            config=config,
            pipeline=pipeline,
            config_sha=config_sha,
            source_sha=source_sha,
            schema_sha=schema_sha,
            audit=audit,
        )
        snapshot_effective_at = f"{config['contract_date']}T00:00:00Z"
        validate_checkpoint(
            target,
            pipeline=pipeline,
            config_sha=config_sha,
            source_sha=source_sha,
            schema_sha=schema_sha,
            roots=roots,
            snapshot_effective_at=snapshot_effective_at,
            audit=audit,
        )
        meta_sha = expected_meta(
            pipeline, config_sha, source_sha, schema_sha, snapshot_effective_at
        )[-1]
        semantic_sha = semantic_root(
            meta_sha, expected_cohorts(config, pipeline), roots
        )
        audit.equal("semantic_root_pin", semantic_sha, EXPECTED_SEMANTIC_ROOT_SHA256)
        database = {
            "filename": plan_db_path.name,
            "bytes": EXPECTED_DATABASE_BYTES,
            "sha256": EXPECTED_DATABASE_SHA256,
        }
        expected_manifest_value = expected_manifest(
            config=config,
            pipeline=pipeline,
            config_sha=config_sha,
            source_sha=source_sha,
            schema_sha=schema_sha,
            semantic_sha=semantic_sha,
            database=database,
            counts=counts,
        )
        audit.equal("manifest_full_reconstruction", manifest, expected_manifest_value)
        audit.equal(
            "manifest_root_pin",
            manifest["manifest_root_sha256"],
            EXPECTED_MANIFEST_ROOT_SHA256,
        )
        expected_report_semantic = {
            "format_version": MATERIALIZATION_FORMAT,
            "status": "passed",
            "contract_date": config["contract_date"],
            "pipeline_key": pipeline,
            "config_sha256": config_sha,
            "source_root_sha256": source_sha,
            "schema_root_sha256": schema_sha,
            "counts": counts,
            "checkpoint": {
                "tasks_written": 2_865_602,
                "slots_written": 2_865_602,
                "batches_committed": 115,
                "completed": 1,
                "last_action_plan_pk": 458,
                "last_series_plan_pk": 6400,
            },
            "statuses": {
                "control_plane_capacity": "PASS",
                "human_review": "OPEN",
                "semantic_promotion": "OPEN",
                "public_release": "OPEN",
            },
            "root_scope": "capacity_only_excludes_future_operational_rows",
            "trust_root_contract": config["trust_root_contract"],
            "operational_lifecycle": config["operational_lifecycle_contract"],
            "real_data_only": True,
            "synthetic_or_mock_decisions": 0,
            "semantic_root_sha256": semantic_sha,
            "database": database,
            "manifest": {
                "filename": manifest_path.name,
                "bytes": EXPECTED_MANIFEST_BYTES,
                "sha256": EXPECTED_MANIFEST_SHA256,
                "manifest_root_sha256": EXPECTED_MANIFEST_ROOT_SHA256,
            },
        }
        actual_report_semantic = {
            key: value
            for key, value in materialization_report.items()
            if key
            not in {"execution", "maximum_resident_set_bytes", "execution_metrics"}
        }
        audit.equal(
            "materialization_report_full_semantic_parity",
            actual_report_semantic,
            expected_report_semantic,
        )
        audit.check(
            "producer_reported_rss_bounded",
            type(materialization_report.get("maximum_resident_set_bytes")) is int
            and 0
            < materialization_report["maximum_resident_set_bytes"]
            <= config["expected"]["maximum_validator_rss_bytes"],
        )
        execution_metrics = materialization_report.get("execution_metrics")
        audit.check(
            "producer_execution_metrics_object",
            type(execution_metrics) is dict
            and set(execution_metrics)
            == {
                "elapsed_seconds",
                "discovery_rows_committed_this_run",
                "discovery_rows_per_second",
            },
        )
        elapsed_seconds = execution_metrics.get("elapsed_seconds")
        audit.check(
            "producer_elapsed_positive",
            type(elapsed_seconds) in {int, float}
            and math.isfinite(float(elapsed_seconds))
            and 0 < elapsed_seconds <= 86_400,
        )
        committed_this_run = execution_metrics.get("discovery_rows_committed_this_run")
        audit.check(
            "producer_committed_rows_honest",
            type(committed_this_run) is int
            and 0 <= committed_this_run <= 2_865_602
            and (
                materialization_report["execution"] != "replayed_noop"
                or committed_this_run == 0
            ),
        )
        measured_throughput = execution_metrics.get("discovery_rows_per_second")
        audit.check(
            "producer_throughput_honest",
            (committed_this_run == 0 and measured_throughput is None)
            or (
                committed_this_run > 0
                and type(measured_throughput) in {int, float}
                and math.isfinite(float(measured_throughput))
                and 0 < measured_throughput <= 10_000_000
                and abs(
                    measured_throughput
                    - committed_this_run / execution_metrics["elapsed_seconds"]
                )
                <= 1.0
            ),
        )
    finally:
        close_immutable_db(target, plan_db_path, plan_identity)
        close_immutable_db(
            discovery,
            source_facts["discovery_path"],
            source_facts["discovery_identity"],
        )
        close_immutable_db(
            canary, source_facts["canary_path"], source_facts["canary_identity"]
        )

    for path_key, identity_key in (
        ("discovery_manifest_path", "discovery_manifest_identity"),
        ("pointer_path", "pointer_identity"),
        ("canary_manifest_path", "canary_manifest_identity"),
    ):
        audit.equal(
            f"stable_{path_key}",
            stable_identity(source_facts[path_key]),
            source_facts[identity_key],
        )
    audit.equal(
        "manifest_identity_stable", stable_identity(manifest_path), manifest_identity
    )
    audit.equal(
        "materialization_report_identity_stable",
        stable_identity(materialization_report_path),
        materialization_identity,
    )
    rss = max_rss_bytes()
    audit.check(
        "validator_rss_bounded",
        rss <= config["expected"]["maximum_validator_rss_bytes"],
    )
    report = {
        "format_version": VALIDATION_FORMAT,
        "status": "passed",
        "checks_passed": len(audit.checks),
        "checks_failed": 0,
        "pipeline_key": pipeline,
        "config_sha256": config_sha,
        "source_root_sha256": source_sha,
        "schema_root_sha256": schema_sha,
        "semantic_root_sha256": EXPECTED_SEMANTIC_ROOT_SHA256,
        "database_sha256": EXPECTED_DATABASE_SHA256,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "counts": expected_counts(),
        "statuses": {
            "control_plane_capacity": "PASS",
            "human_review": "OPEN",
            "semantic_promotion": "OPEN",
            "public_release": "OPEN",
        },
        "root_scope": "capacity_only_excludes_future_operational_rows",
        "trust_root_contract": config["trust_root_contract"],
        "operational_lifecycle": config["operational_lifecycle_contract"],
        "real_data_only": True,
        "synthetic_or_mock_decisions": 0,
        "maximum_resident_set_bytes": rss,
    }
    atomic_write_json(report_out, report)
    return report


def validate_path_separation(paths: Iterable[Path]) -> None:
    resolved = [Path(path).resolve(strict=False) for path in paths]
    for index, left in enumerate(resolved):
        for right in resolved[index + 1 :]:
            if paths_overlap(left, right):
                raise RuntimeError(
                    "all C2C validation paths must be pairwise ancestor-disjoint"
                )


def validate_report_separation(report: Path, others: Iterable[Path]) -> None:
    for other in others:
        if paths_overlap(report, other):
            raise RuntimeError("C2C validation report overlaps an evidence path")


def preflight_regular_input(path: Path) -> None:
    path = Path(path)
    if path.is_symlink() or not path.exists():
        raise RuntimeError("C2C immutable evidence is missing or linked")
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        raise RuntimeError("C2C immutable evidence is not a private regular file")


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
        "format_version": VALIDATION_FORMAT,
        "status": "running",
        "success_report_invalidated": True,
        "publication_gate_passed": False,
        "semantic_promotion_gate_passed": False,
    }


def failure_report(error: BaseException) -> dict[str, Any]:
    return {
        "format_version": VALIDATION_FORMAT,
        "status": "failed",
        "error_type": type(error).__name__,
        "success_report_invalidated": True,
        "publication_gate_passed": False,
        "semantic_promotion_gate_passed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--plan-db", type=Path, default=DEFAULT_PLAN_DB)
    parser.add_argument(
        "--materialization-report", type=Path, default=DEFAULT_MATERIALIZATION_REPORT
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    schema_path = Path(args.schema)
    plan_db_path = Path(args.plan_db)
    materialization_path = Path(args.materialization_report)
    manifest_path = Path(args.manifest)
    report_raw = Path(args.report_out)
    initial_paths = [
        config_path,
        schema_path,
        plan_db_path,
        materialization_path,
        manifest_path,
        report_raw,
    ]
    try:
        report_out = preflight_control_target(report_raw)
        validate_report_separation(
            report_out,
            [
                config_path,
                schema_path,
                plan_db_path,
                materialization_path,
                manifest_path,
            ],
        )
    except BaseException as error:
        print(
            f"ERROR: {type(error).__name__}: unsafe C2C validation paths",
            file=sys.stderr,
        )
        return 2
    command_leases = identity_companion_leases(initial_paths, namespace="command")
    try:
        command_leases.__enter__()
    except BaseException as error:
        # Invalidate a stale result only when this invocation can separately
        # acquire its report target. A concurrent writer using the same report
        # retains exclusive ownership and is never clobbered.
        try:
            with identity_companion_leases([report_out], namespace="command"):
                atomic_write_json(report_out, failure_report(error))
        except BaseException:
            pass
        print(
            f"ERROR: {type(error).__name__}: C2C validation lease unavailable",
            file=sys.stderr,
        )
        return 1
    try:
        atomic_write_json(report_out, running_report())
        try:
            validate_path_separation(initial_paths)
            for path in (
                config_path,
                schema_path,
                plan_db_path,
                materialization_path,
                manifest_path,
            ):
                preflight_regular_input(path)
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
                    bind(plan_db_path, database=True)
                    bind(materialization_path)
                    bind(manifest_path)
                    for path, database in source_paths:
                        bind(path, database=database)
                    report = validate(
                        config_path=config_path,
                        schema_path=schema_path,
                        plan_db_path=plan_db_path,
                        materialization_report_path=materialization_path,
                        manifest_path=manifest_path,
                        report_out=report_out,
                        bound_inputs=bound_inputs,
                    )
            finally:
                source_leases.__exit__(None, None, None)
            print(canonical_json(report))
            return 0
        except BaseException as error:
            try:
                atomic_write_json(report_out, failure_report(error))
                print(canonical_json(load_json(report_out)), file=sys.stderr)
            except BaseException:
                pass
            return 1
    finally:
        command_leases.__exit__(None, None, None)


if __name__ == "__main__":
    raise SystemExit(main())
