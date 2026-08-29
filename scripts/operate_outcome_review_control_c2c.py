#!/usr/bin/env python3
"""Operate the bounded C2C review-control core without inventing human facts.

The canonical capacity database is intentionally immutable and rejects every
mutation. Core event commands accept only caller-supplied real events and work
only against a separately rooted operational snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import stat
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.outcome_pair_identity_safety import (
    bound_regular_file,
    fsync_directory,
    fsync_regular_file,
    identity_companion_leases,
    paths_overlap,
)

DEFAULT_DB = REPO_ROOT / "etl/data/staging/outcome-review-control-c2c-v1.db"
CONTROL_CONTRACT = "outcome_review_control_c2c_v1"
EVENT_FORMAT = "outcome_review_core_event_c2c_v1"
EMPTY_CHAIN = hashlib.sha256(b"").hexdigest()
MAX_EVENT_BYTES = 16_384
MAX_IDEMPOTENCY_BYTES = 200
MAX_PUBLIC_ID_BYTES = 256

CORE_TRIGGER_NAMES = {
    "trg_outcome_review_claim_events_snapshot_guard",
    "trg_outcome_review_claim_guard",
    "trg_outcome_review_decision_guard",
    "trg_outcome_review_operation_requests_snapshot_guard",
    "trg_outcome_review_operation_request_target_guard",
    "trg_outcome_review_operational_audit_snapshot_guard",
    "trg_outcome_review_operational_audit_chain_guard",
    "trg_outcome_review_claim_events_no_update",
    "trg_outcome_review_claim_events_no_delete",
    "trg_outcome_review_decisions_no_update",
    "trg_outcome_review_decisions_no_delete",
    "trg_outcome_review_operation_requests_no_update",
    "trg_outcome_review_operation_requests_no_delete",
    "trg_outcome_review_operational_audit_events_no_update",
    "trg_outcome_review_operational_audit_events_no_delete",
}

CLAIM_INPUT_KEYS = {
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
}
DECISION_INPUT_KEYS = {
    "decision_id",
    "task_pk",
    "slot_pk",
    "assignment_event_id",
    "claim_event_id",
    "reviewer_public_id",
    "decision_value",
    "evidence_examined",
    "rationale",
    "decided_at",
}

CLAIM_COLUMNS = (
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
)
DECISION_COLUMNS = (
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
)

CAPABILITIES = {
    "status": {
        "state": "available",
        "command": "status",
    },
    "claim": {
        "state": "conditional_unpublished_operational_working_database_only",
        "command": "claim",
    },
    "heartbeat": {
        "state": "conditional_unpublished_operational_working_database_only",
        "command": "heartbeat",
    },
    "claim_release": {
        "state": "conditional_unpublished_operational_working_database_only",
        "command": "release",
    },
    "claim_completion": {
        "state": "conditional_unpublished_operational_working_database_only",
        "command": "complete",
    },
    "claim_reclaim": {
        "state": "conditional_unpublished_operational_working_database_only",
        "command": "reclaim",
    },
    "decision": {
        "state": "conditional_unpublished_operational_working_database_only",
        "command": "decision",
    },
    "trust_root_registration": {
        "state": "unavailable",
        "reason": "requires a separately reviewed operational snapshot builder",
    },
    "reviewer_registration": {
        "state": "unavailable",
        "reason": "requires a separately reviewed operational snapshot builder",
    },
    "authorization": {
        "state": "unavailable",
        "reason": "requires a separately reviewed operational snapshot builder",
    },
    "conflict": {
        "state": "unavailable",
        "reason": "requires a separately reviewed operational snapshot builder",
    },
    "assignment": {
        "state": "unavailable",
        "reason": "requires a separately reviewed operational snapshot builder",
    },
    "adjudication": {
        "state": "unavailable",
        "reason": "requires full operational source-root validation",
    },
    "semantic_eligibility": {
        "state": "unavailable",
        "reason": "requires full operational source-root validation",
    },
    "promotion": {
        "state": "unavailable",
        "reason": "requires full operational source-root validation",
    },
    "publication": {
        "state": "unavailable",
        "reason": "requires exact release and membership validation against the pinned C1 database",
    },
    "immutable_operational_export": {
        "state": "unavailable",
        "reason": "content-addressed operational snapshot builder is not implemented",
    },
}


class OperationError(RuntimeError):
    """Stable fail-closed operation error."""


class PostCommitOperationError(OperationError):
    """The database committed, but durable post-commit proof failed."""

    mutation_committed = True


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OperationError("event JSON contains a duplicate key")
        result[key] = value
    return result


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def persisted_row_sha256(contract_version: str, row: dict[str, Any]) -> str:
    return sha256_bytes(
        canonical_bytes({"contract_version": contract_version, "persisted_row": row})
    )


def require_string(
    name: str, value: Any, *, minimum: int = 1, maximum: int = 256
) -> str:
    if type(value) is not str or not minimum <= len(value.encode("utf-8")) <= maximum:
        raise OperationError(f"{name} is outside the bounded string contract")
    return value


def require_nullable_string(name: str, value: Any, *, maximum: int = 256) -> str | None:
    if value is None:
        return None
    return require_string(name, value, maximum=maximum)


def require_integer(name: str, value: Any, *, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise OperationError(f"{name} is outside the bounded integer contract")
    return value


def require_sha256(name: str, value: Any) -> str:
    value = require_string(name, value, minimum=64, maximum=64)
    if any(character not in "0123456789abcdef" for character in value):
        raise OperationError(f"{name} is not lowercase SHA-256")
    return value


def require_utc(name: str, value: Any) -> str:
    value = require_string(name, value, minimum=20, maximum=20)
    if (
        value[4:5] != "-"
        or value[7:8] != "-"
        or value[10:11] != "T"
        or value[13:14] != ":"
        or value[16:17] != ":"
        or value[-1:] != "Z"
    ):
        raise OperationError(f"{name} is not strict second-resolution UTC")
    return value


def validate_no_path_alias(left: Path, right: Path) -> None:
    if paths_overlap(left, right):
        raise OperationError("database and event paths must be ancestor-disjoint")


def preflight_regular_input(path: Path) -> None:
    path = Path(path)
    if path.is_symlink() or not path.exists():
        raise OperationError("required input is missing or linked")
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        raise OperationError("required input is not a private regular file")


def _reject_sidecars(path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{path}{suffix}")
        if sidecar.exists() or sidecar.is_symlink():
            sidecar_stat = sidecar.lstat()
            if not stat.S_ISREG(sidecar_stat.st_mode) or sidecar_stat.st_size:
                raise OperationError("database has an unsafe or non-empty sidecar")


@contextmanager
def writable_database_binding(path: Path) -> Iterator[Path]:
    raw = Path(path)
    if raw.is_symlink():
        raise OperationError("database path is a symlink")
    try:
        resolved = raw.resolve(strict=True)
    except FileNotFoundError as error:
        raise OperationError("database does not exist") from error
    if resolved.is_symlink():
        raise OperationError("database resolved to a symlink")
    _reject_sidecars(resolved)
    flags = os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(resolved, flags)
    try:
        opened = os.fstat(descriptor)
        named = resolved.lstat()
        inode = (opened.st_dev, opened.st_ino)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or inode != (named.st_dev, named.st_ino)
        ):
            raise OperationError("database inode is not a private regular file")
        yield resolved
        final_opened = os.fstat(descriptor)
        final_named = resolved.lstat()
        if (
            not stat.S_ISREG(final_opened.st_mode)
            or final_opened.st_nlink != 1
            or inode != (final_opened.st_dev, final_opened.st_ino)
            or inode != (final_named.st_dev, final_named.st_ino)
        ):
            raise OperationError("database inode changed during operation")
        _reject_sidecars(resolved)
    finally:
        os.close(descriptor)


def connect_read_only(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro&immutable=1", uri=True
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.execute("BEGIN")
    return connection


def connect_writable(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("PRAGMA trusted_schema=OFF")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def require_core_schema(connection: sqlite3.Connection) -> sqlite3.Row:
    meta_rows = connection.execute(
        "SELECT * FROM outcome_review_control_meta LIMIT 2"
    ).fetchall()
    if len(meta_rows) != 1 or meta_rows[0]["contract_version"] != CONTROL_CONTRACT:
        raise OperationError("database is not an exact C2C review-control artifact")
    triggers = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND name IN ("
            + ",".join("?" for _ in CORE_TRIGGER_NAMES)
            + ")",
            tuple(sorted(CORE_TRIGGER_NAMES)),
        )
    }
    if triggers != CORE_TRIGGER_NAMES:
        raise OperationError("database lacks mandatory core operation guards")
    return meta_rows[0]


def status_payload(
    connection: sqlite3.Connection, slot_pk: int | None
) -> dict[str, Any]:
    meta = require_core_schema(connection)
    checkpoint = connection.execute(
        "SELECT tasks_written,slots_written,batches_committed,completed "
        "FROM outcome_review_control_checkpoints WHERE pipeline_key=? "
        "AND stage='discovery_tasks'",
        (meta["pipeline_key"],),
    ).fetchone()
    if checkpoint is None:
        raise OperationError("database lacks its capacity checkpoint")
    audit_head = connection.execute(
        "SELECT operational_audit_pk,event_sha256 FROM "
        "outcome_review_operational_audit_events "
        "ORDER BY operational_audit_pk DESC LIMIT 1"
    ).fetchone()
    trust_root_present = connection.execute(
        "SELECT EXISTS(SELECT 1 FROM outcome_review_trust_roots LIMIT 1)"
    ).fetchone()[0]
    payload: dict[str, Any] = {
        "format_version": "outcome_review_control_c2c_operation_status_v1",
        "status": "ok",
        "pipeline_key": meta["pipeline_key"],
        "artifact_scope": meta["artifact_scope"],
        "operational_state": meta["operational_state"],
        "mutation_enabled": (
            meta["artifact_scope"] == "operational_working"
            and meta["operational_state"] == "working_unpublished"
            and bool(trust_root_present)
        ),
        "trust_root_present": bool(trust_root_present),
        "capacity": {
            "discovery_tasks": checkpoint["tasks_written"],
            "discovery_slots": checkpoint["slots_written"],
            "batches_committed": checkpoint["batches_committed"],
            "completed": bool(checkpoint["completed"]),
        },
        "operational_event_count": audit_head[0] if audit_head else 0,
        "operational_event_head_sha256": audit_head[1] if audit_head else EMPTY_CHAIN,
        "capabilities": CAPABILITIES,
        "real_events_only": True,
        "synthetic_or_mock_events": 0,
    }
    if slot_pk is not None:
        current = connection.execute(
            "SELECT claim_event_id,assignment_event_id,reviewer_public_id,"
            "actor_public_id,claim_state,attempt_ordinal,lease_expires_at,recorded_at "
            "FROM outcome_review_claim_events WHERE slot_pk=? "
            "ORDER BY claim_event_pk DESC LIMIT 1",
            (slot_pk,),
        ).fetchone()
        payload["slot_pk"] = slot_pk
        payload["latest_claim_event"] = dict(current) if current else None
    return payload


def normalize_claim(
    event: dict[str, Any], expected_state: str, actor_public_id: str
) -> tuple[dict[str, Any], str, str]:
    row = event["row"]
    if set(row) != CLAIM_INPUT_KEYS:
        raise OperationError("claim row keys do not match the exact contract")
    if row["claim_state"] != expected_state:
        raise OperationError("claim state does not match the selected command")
    normalized = {
        "claim_event_id": require_string("claim_event_id", row["claim_event_id"]),
        "assignment_event_id": require_string(
            "assignment_event_id", row["assignment_event_id"]
        ),
        "slot_pk": require_integer(
            "slot_pk", row["slot_pk"], minimum=1, maximum=10**12
        ),
        "reviewer_public_id": require_string(
            "reviewer_public_id", row["reviewer_public_id"]
        ),
        "actor_public_id": require_string("actor_public_id", row["actor_public_id"]),
        "actor_auth_event_id": require_nullable_string(
            "actor_auth_event_id", row["actor_auth_event_id"]
        ),
        "claim_state": expected_state,
        "supersedes_claim_event_id": require_nullable_string(
            "supersedes_claim_event_id", row["supersedes_claim_event_id"]
        ),
        "lease_token_sha256": require_sha256(
            "lease_token_sha256", row["lease_token_sha256"]
        ),
        "attempt_ordinal": require_integer(
            "attempt_ordinal", row["attempt_ordinal"], minimum=1, maximum=100
        ),
        "lease_expires_at": require_utc("lease_expires_at", row["lease_expires_at"]),
        "recorded_at": require_utc("recorded_at", row["recorded_at"]),
    }
    if normalized["actor_public_id"] != actor_public_id:
        raise OperationError("external actor does not match the claim event")
    return normalized, normalized["claim_event_id"], normalized["recorded_at"]


def normalize_decision(
    event: dict[str, Any], actor_public_id: str
) -> tuple[dict[str, Any], str, str]:
    row = event["row"]
    if set(row) != DECISION_INPUT_KEYS:
        raise OperationError("decision row keys do not match the exact contract")
    evidence = row["evidence_examined"]
    if type(evidence) is not list or not 1 <= len(evidence) <= 128:
        raise OperationError(
            "decision evidence list is empty or exceeds the hard bound"
        )
    normalized_evidence = [
        require_string(f"evidence_examined[{index}]", value, maximum=2048)
        for index, value in enumerate(evidence)
    ]
    normalized = {
        "decision_id": require_string("decision_id", row["decision_id"]),
        "task_pk": require_integer(
            "task_pk", row["task_pk"], minimum=1, maximum=10**12
        ),
        "slot_pk": require_integer(
            "slot_pk", row["slot_pk"], minimum=1, maximum=10**12
        ),
        "assignment_event_id": require_string(
            "assignment_event_id", row["assignment_event_id"]
        ),
        "claim_event_id": require_string("claim_event_id", row["claim_event_id"]),
        "reviewer_public_id": require_string(
            "reviewer_public_id", row["reviewer_public_id"]
        ),
        "decision_value": require_string(
            "decision_value", row["decision_value"], maximum=64
        ),
        "evidence_examined_json": canonical_json(normalized_evidence),
        "rationale": require_string("rationale", row["rationale"], maximum=4000),
        "decided_at": require_utc("decided_at", row["decided_at"]),
    }
    if normalized["reviewer_public_id"] != actor_public_id:
        raise OperationError("external actor does not match the decision reviewer")
    return normalized, normalized["decision_id"], normalized["decided_at"]


def operation_identity(idempotency_key: str) -> str:
    return (
        "vclc:outcome-review-operational-audit:"
        + sha256_bytes(idempotency_key.encode("utf-8"))[:32]
    )


def apply_core_event(
    connection: sqlite3.Connection,
    *,
    event: dict[str, Any],
    command: str,
    idempotency_key: str,
    actor_public_id: str,
) -> dict[str, Any]:
    if command == "decision":
        normalized, target_row_id, occurred_at = normalize_decision(
            event, actor_public_id
        )
        target_table = "outcome_review_decisions"
        operation_kind = "decision"
        pk_column = "decision_pk"
        id_column = "decision_id"
        columns = DECISION_COLUMNS
        row_contract = "outcome_review_decision_row_c2c_v1"
    else:
        state_by_command = {
            "claim": "claimed",
            "heartbeat": "heartbeat",
            "release": "released",
            "complete": "completed",
            "reclaim": "reclaimed",
        }
        normalized, target_row_id, occurred_at = normalize_claim(
            event, state_by_command[command], actor_public_id
        )
        target_table = "outcome_review_claim_events"
        operation_kind = "claim"
        pk_column = "claim_event_pk"
        id_column = "claim_event_id"
        columns = CLAIM_COLUMNS
        row_contract = "outcome_review_claim_event_row_c2c_v1"

    payload_sha = sha256_bytes(
        canonical_bytes(
            {
                "contract_version": EVENT_FORMAT,
                "command": command,
                "row": event["row"],
            }
        )
    )
    connection.execute("BEGIN IMMEDIATE")
    try:
        meta = require_core_schema(connection)
        if (
            meta["artifact_scope"] != "operational_working"
            or meta["operational_state"] != "working_unpublished"
        ):
            raise OperationError("capacity artifact rejects operational mutation")
        existing = connection.execute(
            "SELECT * FROM outcome_review_operation_requests WHERE idempotency_key=?",
            (idempotency_key,),
        ).fetchone()
        if existing is not None:
            existing_target = connection.execute(
                f'SELECT * FROM "{target_table}" WHERE "{id_column}"=?',
                (target_row_id,),
            ).fetchone()
            existing_audit = connection.execute(
                "SELECT * FROM "
                "outcome_review_operational_audit_events WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if (
                existing["operation_kind"] != operation_kind
                or existing["payload_sha256"] != payload_sha
                or existing["target_table"] != target_table
                or existing["target_row_id"] != target_row_id
                or existing["applied_at"] != occurred_at
                or existing_target is None
                or existing_audit is None
                or existing_audit["actor_public_id"] != actor_public_id
            ):
                raise OperationError(
                    "idempotency key was already used for another event"
                )
            persisted = {column: existing_target[column] for column in columns}
            target_sha = persisted_row_sha256(row_contract, persisted)
            if (
                any(existing_target[key] != value for key, value in normalized.items())
                or existing_target["row_semantic_sha256"] != target_sha
                or existing["row_semantic_sha256"] != target_sha
            ):
                raise OperationError("idempotent target row integrity check failed")
            previous_event_sha = EMPTY_CHAIN
            if existing_audit["operational_audit_pk"] > 1:
                predecessor = connection.execute(
                    "SELECT event_sha256 FROM outcome_review_operational_audit_events "
                    "WHERE operational_audit_pk=?",
                    (existing_audit["operational_audit_pk"] - 1,),
                ).fetchone()
                if predecessor is None:
                    raise OperationError("idempotent audit predecessor is missing")
                previous_event_sha = predecessor["event_sha256"]
            audit = {
                "operational_audit_pk": existing_audit["operational_audit_pk"],
                "operational_audit_id": existing_audit["operational_audit_id"],
                "idempotency_key": existing_audit["idempotency_key"],
                "operation_kind": existing_audit["operation_kind"],
                "target_table": existing_audit["target_table"],
                "target_row_id": existing_audit["target_row_id"],
                "payload_sha256": existing_audit["payload_sha256"],
                "previous_event_sha256": existing_audit["previous_event_sha256"],
                "actor_public_id": existing_audit["actor_public_id"],
                "occurred_at": existing_audit["occurred_at"],
            }
            audit_sha = persisted_row_sha256(
                "outcome_review_operational_audit_event_c2c_v1", audit
            )
            if (
                existing_audit["operational_audit_id"]
                != operation_identity(idempotency_key)
                or existing_audit["operation_kind"] != operation_kind
                or existing_audit["target_table"] != target_table
                or existing_audit["target_row_id"] != target_row_id
                or existing_audit["payload_sha256"] != payload_sha
                or existing_audit["occurred_at"] != occurred_at
                or existing_audit["previous_event_sha256"] != previous_event_sha
                or existing_audit["event_sha256"] != audit_sha
            ):
                raise OperationError(
                    "idempotent operational audit integrity check failed"
                )
            connection.rollback()
            return {
                "format_version": "outcome_review_control_c2c_operation_result_v1",
                "status": "ok",
                "execution": "idempotent_replay",
                "operation": command,
                "target_table": target_table,
                "target_row_id": target_row_id,
                "row_semantic_sha256": target_sha,
                "event_sha256": audit_sha,
            }

        next_pk = connection.execute(
            f'SELECT COALESCE(MAX("{pk_column}"),0)+1 FROM "{target_table}"'
        ).fetchone()[0]
        require_integer("next primary key", next_pk, minimum=1, maximum=10**12)
        persisted = {pk_column: next_pk, **normalized}
        target_sha = persisted_row_sha256(row_contract, persisted)
        insert_columns = (*columns, "row_semantic_sha256")
        connection.execute(
            f'INSERT INTO "{target_table}" ('
            + ",".join(f'"{column}"' for column in insert_columns)
            + ") VALUES ("
            + ",".join("?" for _ in insert_columns)
            + ")",
            tuple(persisted[column] for column in columns) + (target_sha,),
        )
        connection.execute(
            "INSERT INTO outcome_review_operation_requests "
            "(idempotency_key,operation_kind,payload_sha256,target_table,"
            "target_row_id,applied_at,row_semantic_sha256) VALUES (?,?,?,?,?,?,?)",
            (
                idempotency_key,
                operation_kind,
                payload_sha,
                target_table,
                target_row_id,
                occurred_at,
                target_sha,
            ),
        )
        previous = connection.execute(
            "SELECT operational_audit_pk,event_sha256 FROM "
            "outcome_review_operational_audit_events "
            "ORDER BY operational_audit_pk DESC LIMIT 1"
        ).fetchone()
        audit_pk = previous["operational_audit_pk"] + 1 if previous else 1
        audit = {
            "operational_audit_pk": audit_pk,
            "operational_audit_id": operation_identity(idempotency_key),
            "idempotency_key": idempotency_key,
            "operation_kind": operation_kind,
            "target_table": target_table,
            "target_row_id": target_row_id,
            "payload_sha256": payload_sha,
            "previous_event_sha256": previous["event_sha256"]
            if previous
            else EMPTY_CHAIN,
            "actor_public_id": actor_public_id,
            "occurred_at": occurred_at,
        }
        audit_sha = persisted_row_sha256(
            "outcome_review_operational_audit_event_c2c_v1", audit
        )
        connection.execute(
            "INSERT INTO outcome_review_operational_audit_events VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?)",
            tuple(audit.values()) + (audit_sha,),
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    return {
        "format_version": "outcome_review_control_c2c_operation_result_v1",
        "status": "ok",
        "execution": "applied",
        "operation": command,
        "target_table": target_table,
        "target_row_id": target_row_id,
        "row_semantic_sha256": target_sha,
        "event_sha256": audit_sha,
    }


def add_event_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--event-json", required=True, type=Path)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument("--actor-public-id", required=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    subparsers = parser.add_subparsers(dest="command", required=True)
    status = subparsers.add_parser("status")
    status.add_argument("--slot-pk", type=int)
    for command in ("claim", "heartbeat", "release", "complete", "reclaim", "decision"):
        add_event_arguments(subparsers.add_parser(command))
    return parser.parse_args()


def run_status(db_path: Path, slot_pk: int | None) -> dict[str, Any]:
    if slot_pk is not None:
        require_integer("slot_pk", slot_pk, minimum=1, maximum=10**12)
    preflight_regular_input(db_path)
    with identity_companion_leases([db_path], namespace="evidence"):
        with bound_regular_file(db_path, database=True) as bound:
            connection = connect_read_only(bound.path)
            try:
                payload = status_payload(connection, slot_pk)
                connection.rollback()
            finally:
                connection.close()
    return payload


def run_mutation(args: argparse.Namespace) -> dict[str, Any]:
    db_path = Path(args.db)
    event_path = Path(args.event_json)
    validate_no_path_alias(db_path, event_path)
    preflight_regular_input(db_path)
    preflight_regular_input(event_path)
    idempotency_key = require_string(
        "idempotency_key",
        args.idempotency_key,
        minimum=16,
        maximum=MAX_IDEMPOTENCY_BYTES,
    )
    actor_public_id = require_string(
        "actor_public_id", args.actor_public_id, maximum=MAX_PUBLIC_ID_BYTES
    )
    mutation_committed = False
    try:
        with identity_companion_leases([db_path, event_path], namespace="command"):
            with bound_regular_file(event_path) as bound_event:
                with writable_database_binding(db_path) as resolved_db:
                    scope_check = connect_read_only(resolved_db)
                    try:
                        meta = require_core_schema(scope_check)
                        if (
                            meta["artifact_scope"] != "operational_working"
                            or meta["operational_state"] != "working_unpublished"
                        ):
                            raise OperationError(
                                "capacity artifact rejects operational mutation"
                            )
                    finally:
                        scope_check.close()
                    try:
                        event = json.loads(
                            bound_event.read_bytes(max_bytes=MAX_EVENT_BYTES).decode(
                                "utf-8"
                            ),
                            object_pairs_hook=reject_duplicate_keys,
                            parse_constant=lambda _value: (_ for _ in ()).throw(
                                OperationError(
                                    "event JSON contains a non-finite number"
                                )
                            ),
                        )
                    except UnicodeDecodeError as error:
                        raise OperationError("event JSON is not UTF-8") from error
                    if type(event) is not dict or set(event) != {
                        "format_version",
                        "row",
                    }:
                        raise OperationError(
                            "event JSON root does not match the exact contract"
                        )
                    if (
                        event["format_version"] != EVENT_FORMAT
                        or type(event["row"]) is not dict
                    ):
                        raise OperationError("event JSON format is unsupported")
                    connection = connect_writable(resolved_db)
                    try:
                        result = apply_core_event(
                            connection,
                            event=event,
                            command=args.command,
                            idempotency_key=idempotency_key,
                            actor_public_id=actor_public_id,
                        )
                        mutation_committed = result["execution"] == "applied"
                    finally:
                        connection.close()
                    fsync_regular_file(resolved_db)
                    fsync_directory(resolved_db.parent)
        return result
    except BaseException as error:
        if mutation_committed:
            raise PostCommitOperationError(
                "operation committed but post-commit verification failed"
            ) from error
        raise


def main() -> int:
    args = parse_args()
    try:
        if args.command == "status":
            result = run_status(Path(args.db), args.slot_pk)
        else:
            result = run_mutation(args)
        print(canonical_json(result))
        return 0
    except BaseException as error:
        failure = {
            "format_version": "outcome_review_control_c2c_operation_result_v1",
            "status": "failed",
            "error_type": type(error).__name__,
            "mutation_committed": bool(getattr(error, "mutation_committed", False)),
        }
        print(canonical_json(failure), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
