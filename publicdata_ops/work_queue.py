"""Durable SQLite work queue for large public-data pipelines.

Queue keeps orchestration state small and transactional. Large payloads stay in
raw/object storage; work items contain stable references only. Workers claim a
bounded lease, perform idempotent work, then complete or retry the item.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, wait
from datetime import datetime, timedelta, timezone
from time import monotonic
from typing import Any, TypeVar


PENDING = "pending"
LEASED = "leased"
SUCCEEDED = "succeeded"
DEAD = "dead"
WORK_ITEM_STATES = {PENDING, LEASED, SUCCEEDED, DEAD}
T = TypeVar("T")


WORK_QUEUE_SCHEMA = """
CREATE TABLE IF NOT EXISTS pipeline_work_items (
  work_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
  pipeline_id TEXT NOT NULL,
  item_key TEXT NOT NULL,
  partition_key TEXT NOT NULL DEFAULT '',
  priority INTEGER NOT NULL DEFAULT 0,
  state TEXT NOT NULL DEFAULT 'pending'
    CHECK (state IN ('pending', 'leased', 'succeeded', 'dead')),
  payload_json TEXT NOT NULL DEFAULT '{}',
  available_at TEXT NOT NULL,
  lease_owner TEXT,
  lease_expires_at TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 5 CHECK (max_attempts >= 1),
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT,
  UNIQUE (pipeline_id, item_key)
);

CREATE TABLE IF NOT EXISTS pipeline_work_attempts (
  work_attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
  work_item_id INTEGER NOT NULL
    REFERENCES pipeline_work_items(work_item_id) ON DELETE CASCADE,
  attempt_number INTEGER NOT NULL,
  worker_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL DEFAULT 'running'
    CHECK (status IN ('running', 'succeeded', 'retry', 'dead', 'lease_expired')),
  error TEXT,
  UNIQUE (work_item_id, attempt_number)
);

CREATE INDEX IF NOT EXISTS idx_pipeline_work_claim
  ON pipeline_work_items (
    pipeline_id,
    state,
    available_at,
    priority DESC,
    work_item_id
  );
CREATE INDEX IF NOT EXISTS idx_pipeline_work_claim_v2
  ON pipeline_work_items (
    pipeline_id,
    state,
    priority DESC,
    work_item_id,
    available_at
  );
CREATE INDEX IF NOT EXISTS idx_pipeline_work_lease
  ON pipeline_work_items (state, lease_expires_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_work_partition
  ON pipeline_work_items (pipeline_id, partition_key, state, work_item_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_work_attempt_item
  ON pipeline_work_attempts (work_item_id, attempt_number);
"""


def utc_now_iso(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat(timespec="seconds")


def ensure_work_queue_schema(conn: sqlite3.Connection) -> None:
    required = {
        "pipeline_work_items",
        "pipeline_work_attempts",
        "idx_pipeline_work_claim",
        "idx_pipeline_work_claim_v2",
        "idx_pipeline_work_lease",
        "idx_pipeline_work_partition",
        "idx_pipeline_work_attempt_item",
    }
    existing = {
        str(row[0])
        for row in conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE name IN (
              'pipeline_work_items',
              'pipeline_work_attempts',
              'idx_pipeline_work_claim',
              'idx_pipeline_work_claim_v2',
              'idx_pipeline_work_lease',
              'idx_pipeline_work_partition',
              'idx_pipeline_work_attempt_item'
            )
            """
        ).fetchall()
    }
    if existing == required:
        return
    conn.executescript(WORK_QUEUE_SCHEMA)
    conn.commit()


def _stable_payload(value: object) -> str:
    if isinstance(value, str):
        parsed = json.loads(value)
    elif value is None:
        parsed = {}
    else:
        parsed = value
    return json.dumps(parsed, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _chunks(values: Iterable[tuple[Any, ...]], size: int) -> Iterable[list[tuple[Any, ...]]]:
    batch: list[tuple[Any, ...]] = []
    for value in values:
        batch.append(value)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def enqueue_work_items(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    items: Iterable[Mapping[str, object]],
    batch_size: int = 1_000,
    now: datetime | None = None,
    commit: bool = True,
) -> dict[str, int]:
    """Insert/update work references without materializing the input iterable."""

    normalized_pipeline = str(pipeline_id or "").strip()
    if not normalized_pipeline:
        raise ValueError("pipeline_id is required")
    if int(batch_size) < 1:
        raise ValueError("batch_size must be >= 1")

    ensure_work_queue_schema(conn)
    now_iso = utc_now_iso(now)
    before = int(
        conn.execute(
            "SELECT COUNT(*) FROM pipeline_work_items WHERE pipeline_id = ?",
            (normalized_pipeline,),
        ).fetchone()[0]
    )
    input_total = 0

    def rows() -> Iterable[tuple[Any, ...]]:
        nonlocal input_total
        for item in items:
            item_key = str(item.get("item_key") or "").strip()
            if not item_key:
                raise ValueError("work item item_key is required")
            input_total += 1
            max_attempts = int(item.get("max_attempts") or 5)
            if max_attempts < 1:
                raise ValueError("max_attempts must be >= 1")
            available_at = str(item.get("available_at") or now_iso).strip()
            yield (
                normalized_pipeline,
                item_key,
                str(item.get("partition_key") or "").strip(),
                int(item.get("priority") or 0),
                _stable_payload(item.get("payload")),
                available_at,
                max_attempts,
                now_iso,
                now_iso,
            )

    for batch in _chunks(rows(), int(batch_size)):
        conn.executemany(
            """
            INSERT INTO pipeline_work_items (
              pipeline_id,
              item_key,
              partition_key,
              priority,
              payload_json,
              available_at,
              max_attempts,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pipeline_id, item_key) DO UPDATE SET
              partition_key=excluded.partition_key,
              priority=excluded.priority,
              payload_json=excluded.payload_json,
              max_attempts=excluded.max_attempts,
              updated_at=excluded.updated_at
            """,
            batch,
        )
        if commit:
            conn.commit()

    after = int(
        conn.execute(
            "SELECT COUNT(*) FROM pipeline_work_items WHERE pipeline_id = ?",
            (normalized_pipeline,),
        ).fetchone()[0]
    )
    return {
        "input_total": input_total,
        "inserted_total": max(0, after - before),
        "existing_total": max(0, input_total - max(0, after - before)),
        "pipeline_total": after,
    }


def requeue_expired_leases(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str = "",
    now: datetime | None = None,
) -> int:
    """Release expired leases and close their attempt audit rows."""

    now_iso = utc_now_iso(now)
    where_pipeline = " AND pipeline_id = ?" if pipeline_id else ""
    params: tuple[object, ...] = (now_iso, pipeline_id) if pipeline_id else (now_iso,)
    expired = conn.execute(
        f"""
        SELECT work_item_id, attempts
        FROM pipeline_work_items
        WHERE state = 'leased'
          AND lease_expires_at <= ?
          {where_pipeline}
        """,
        params,
    ).fetchall()
    if not expired:
        return 0

    conn.executemany(
        """
        UPDATE pipeline_work_attempts
        SET status = 'lease_expired', finished_at = ?
        WHERE work_item_id = ? AND attempt_number = ? AND status = 'running'
        """,
        [(now_iso, int(row["work_item_id"]), int(row["attempts"])) for row in expired],
    )
    ids = [int(row["work_item_id"]) for row in expired]
    marks = ",".join("?" for _ in ids)
    conn.execute(
        f"""
        UPDATE pipeline_work_items
        SET state = CASE WHEN attempts >= max_attempts THEN 'dead' ELSE 'pending' END,
            lease_owner = NULL,
            lease_expires_at = NULL,
            available_at = ?,
            updated_at = ?,
            completed_at = CASE WHEN attempts >= max_attempts THEN ? ELSE NULL END,
            last_error = 'lease_expired'
        WHERE work_item_id IN ({marks})
        """,
        (now_iso, now_iso, now_iso, *ids),
    )
    return len(ids)


def claim_work_items(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str,
    worker_id: str,
    limit: int,
    lease_seconds: int = 300,
    partition_key: str | None = None,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    """Atomically claim a bounded, priority-ordered batch."""

    normalized_pipeline = str(pipeline_id or "").strip()
    normalized_worker = str(worker_id or "").strip()
    if not normalized_pipeline or not normalized_worker:
        raise ValueError("pipeline_id and worker_id are required")
    if int(limit) < 1 or int(limit) > 10_000:
        raise ValueError("limit must be between 1 and 10000")
    if int(lease_seconds) < 1:
        raise ValueError("lease_seconds must be >= 1")

    ensure_work_queue_schema(conn)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    now_iso = utc_now_iso(current)
    lease_expires_at = utc_now_iso(current + timedelta(seconds=int(lease_seconds)))

    conn.execute("BEGIN IMMEDIATE")
    try:
        requeue_expired_leases(conn, pipeline_id=normalized_pipeline, now=current)
        where_partition = " AND partition_key = ?" if partition_key is not None else ""
        params: list[object] = [normalized_pipeline, now_iso]
        if partition_key is not None:
            params.append(str(partition_key))
        params.append(int(limit))
        selected = conn.execute(
            f"""
            SELECT work_item_id
            FROM pipeline_work_items
            WHERE pipeline_id = ?
              AND state = 'pending'
              AND available_at <= ?
              {where_partition}
            ORDER BY priority DESC, work_item_id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        ids = [int(row["work_item_id"]) for row in selected]
        if not ids:
            conn.commit()
            return []

        marks = ",".join("?" for _ in ids)
        conn.execute(
            f"""
            UPDATE pipeline_work_items
            SET state = 'leased',
                lease_owner = ?,
                lease_expires_at = ?,
                attempts = attempts + 1,
                updated_at = ?
            WHERE work_item_id IN ({marks}) AND state = 'pending'
            """,
            (normalized_worker, lease_expires_at, now_iso, *ids),
        )
        rows = conn.execute(
            f"""
            SELECT *
            FROM pipeline_work_items
            WHERE work_item_id IN ({marks}) AND lease_owner = ? AND state = 'leased'
            ORDER BY priority DESC, work_item_id ASC
            """,
            (*ids, normalized_worker),
        ).fetchall()
        conn.executemany(
            """
            INSERT INTO pipeline_work_attempts (
              work_item_id, attempt_number, worker_id, started_at, status
            ) VALUES (?, ?, ?, ?, 'running')
            """,
            [
                (
                    int(row["work_item_id"]),
                    int(row["attempts"]),
                    normalized_worker,
                    now_iso,
                )
                for row in rows
            ],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return [
        {
            **dict(row),
            "payload": json.loads(str(row["payload_json"] or "{}")),
        }
        for row in rows
    ]


def heartbeat_work_items(
    conn: sqlite3.Connection,
    *,
    worker_id: str,
    work_item_ids: Sequence[int],
    lease_seconds: int = 300,
    now: datetime | None = None,
) -> int:
    ids = [int(value) for value in work_item_ids]
    if not ids:
        return 0
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    now_iso = utc_now_iso(current)
    lease_expires_at = utc_now_iso(current + timedelta(seconds=max(1, int(lease_seconds))))
    marks = ",".join("?" for _ in ids)
    cursor = conn.execute(
        f"""
        UPDATE pipeline_work_items
        SET lease_expires_at = ?, updated_at = ?
        WHERE work_item_id IN ({marks})
          AND state = 'leased'
          AND lease_owner = ?
        """,
        (lease_expires_at, now_iso, *ids, str(worker_id)),
    )
    conn.commit()
    return int(cursor.rowcount)


def collect_futures_with_heartbeat(
    conn: sqlite3.Connection,
    *,
    futures: Mapping[Future[T], int],
    worker_id: str,
    lease_seconds: int,
    heartbeat_interval_seconds: float | None = None,
) -> list[T]:
    """Collect a leased batch while extending unfinished work-item leases.

    Heartbeats run on the caller thread, so the SQLite connection is never used
    by executor threads. Long downloads and OCR jobs remain leased without
    weakening bounded batch behavior.
    """

    if int(lease_seconds) < 1:
        raise ValueError("lease_seconds must be >= 1")
    interval = (
        float(heartbeat_interval_seconds)
        if heartbeat_interval_seconds is not None
        else max(1.0, min(60.0, float(lease_seconds) / 3.0))
    )
    if interval <= 0:
        raise ValueError("heartbeat_interval_seconds must be > 0")

    pending = set(futures)
    outcomes: list[T] = []
    next_heartbeat = monotonic() + interval
    while pending:
        timeout = max(0.0, next_heartbeat - monotonic())
        done, pending = wait(pending, timeout=timeout, return_when=FIRST_COMPLETED)
        for future in done:
            outcomes.append(future.result())
        current = monotonic()
        if pending and current >= next_heartbeat:
            heartbeat_work_items(
                conn,
                worker_id=worker_id,
                work_item_ids=[int(futures[future]) for future in pending],
                lease_seconds=lease_seconds,
            )
            next_heartbeat = current + interval
    return outcomes


def complete_work_items(
    conn: sqlite3.Connection,
    *,
    worker_id: str,
    work_item_ids: Sequence[int],
    now: datetime | None = None,
) -> int:
    ids = [int(value) for value in work_item_ids]
    if not ids:
        return 0
    now_iso = utc_now_iso(now)
    marks = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT work_item_id, attempts
        FROM pipeline_work_items
        WHERE work_item_id IN ({marks}) AND state = 'leased' AND lease_owner = ?
        """,
        (*ids, str(worker_id)),
    ).fetchall()
    owned_ids = [int(row["work_item_id"]) for row in rows]
    if not owned_ids:
        return 0
    owned_marks = ",".join("?" for _ in owned_ids)
    conn.execute(
        f"""
        UPDATE pipeline_work_items
        SET state = 'succeeded', lease_owner = NULL, lease_expires_at = NULL,
            updated_at = ?, completed_at = ?, last_error = NULL
        WHERE work_item_id IN ({owned_marks})
        """,
        (now_iso, now_iso, *owned_ids),
    )
    conn.executemany(
        """
        UPDATE pipeline_work_attempts
        SET status = 'succeeded', finished_at = ?, error = NULL
        WHERE work_item_id = ? AND attempt_number = ? AND status = 'running'
        """,
        [(now_iso, int(row["work_item_id"]), int(row["attempts"])) for row in rows],
    )
    conn.commit()
    return len(owned_ids)


def fail_work_items(
    conn: sqlite3.Connection,
    *,
    worker_id: str,
    work_item_ids: Sequence[int],
    error: str,
    retry_delay_seconds: int = 0,
    retryable: bool = True,
    now: datetime | None = None,
) -> dict[str, int]:
    ids = [int(value) for value in work_item_ids]
    if not ids:
        return {"retry_total": 0, "dead_total": 0}
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    now_iso = utc_now_iso(current)
    available_at = utc_now_iso(current + timedelta(seconds=max(0, int(retry_delay_seconds))))
    marks = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT work_item_id, attempts, max_attempts
        FROM pipeline_work_items
        WHERE work_item_id IN ({marks}) AND state = 'leased' AND lease_owner = ?
        """,
        (*ids, str(worker_id)),
    ).fetchall()
    retry_ids = [
        int(row["work_item_id"])
        for row in rows
        if retryable and int(row["attempts"]) < int(row["max_attempts"])
    ]
    dead_ids = [
        int(row["work_item_id"])
        for row in rows
        if not retryable or int(row["attempts"]) >= int(row["max_attempts"])
    ]
    clean_error = str(error or "unknown_error")[:2_000]

    if retry_ids:
        retry_marks = ",".join("?" for _ in retry_ids)
        conn.execute(
            f"""
            UPDATE pipeline_work_items
            SET state = 'pending', lease_owner = NULL, lease_expires_at = NULL,
                available_at = ?, updated_at = ?, last_error = ?
            WHERE work_item_id IN ({retry_marks})
            """,
            (available_at, now_iso, clean_error, *retry_ids),
        )
    if dead_ids:
        dead_marks = ",".join("?" for _ in dead_ids)
        conn.execute(
            f"""
            UPDATE pipeline_work_items
            SET state = 'dead', lease_owner = NULL, lease_expires_at = NULL,
                updated_at = ?, completed_at = ?, last_error = ?
            WHERE work_item_id IN ({dead_marks})
            """,
            (now_iso, now_iso, clean_error, *dead_ids),
        )

    conn.executemany(
        """
        UPDATE pipeline_work_attempts
        SET status = ?, finished_at = ?, error = ?
        WHERE work_item_id = ? AND attempt_number = ? AND status = 'running'
        """,
        [
            (
                "dead" if int(row["work_item_id"]) in dead_ids else "retry",
                now_iso,
                clean_error,
                int(row["work_item_id"]),
                int(row["attempts"]),
            )
            for row in rows
        ],
    )
    conn.commit()
    return {"retry_total": len(retry_ids), "dead_total": len(dead_ids)}


def work_queue_stats(conn: sqlite3.Connection, *, pipeline_id: str = "") -> dict[str, object]:
    where = "WHERE pipeline_id = ?" if pipeline_id else ""
    params: tuple[object, ...] = (pipeline_id,) if pipeline_id else ()
    state_rows = conn.execute(
        f"""
        SELECT state, COUNT(*) AS total
        FROM pipeline_work_items
        {where}
        GROUP BY state
        """,
        params,
    ).fetchall()
    state_counts = {state: 0 for state in sorted(WORK_ITEM_STATES)}
    state_counts.update({str(row["state"]): int(row["total"]) for row in state_rows})
    total = sum(state_counts.values())
    return {
        "pipeline_id": pipeline_id,
        "items_total": total,
        "state_counts": state_counts,
        "unfinished_total": state_counts[PENDING] + state_counts[LEASED],
        "terminal_total": state_counts[SUCCEEDED] + state_counts[DEAD],
    }


def work_queue_observability(
    conn: sqlite3.Connection,
    *,
    pipeline_id: str = "",
    top_limit: int = 20,
    now: datetime | None = None,
) -> dict[str, object]:
    """Build a bounded operational snapshot for one queue or all queues."""

    if int(top_limit) < 1 or int(top_limit) > 1_000:
        raise ValueError("top_limit must be between 1 and 1000")
    ensure_work_queue_schema(conn)
    now_iso = utc_now_iso(now)
    where = "WHERE pipeline_id = ?" if pipeline_id else ""
    and_filter = "AND pipeline_id = ?" if pipeline_id else ""
    params: tuple[object, ...] = (pipeline_id,) if pipeline_id else ()

    attempts = conn.execute(
        f"""
        SELECT COALESCE(SUM(attempts), 0) AS attempts_total,
               COALESCE(SUM(CASE WHEN attempts > 1 THEN attempts - 1 ELSE 0 END), 0)
                 AS retry_attempts_total,
               COALESCE(MAX(attempts), 0) AS max_attempts_observed,
               MIN(CASE WHEN state = 'pending' THEN available_at END) AS oldest_pending_at,
               MIN(CASE WHEN state = 'leased' THEN lease_expires_at END) AS earliest_lease_expiry
        FROM pipeline_work_items
        {where}
        """,
        params,
    ).fetchone()
    overdue_leases = int(
        conn.execute(
            f"""
            SELECT COUNT(*)
            FROM pipeline_work_items
            WHERE state = 'leased' AND lease_expires_at <= ? {and_filter}
            """,
            (now_iso, *params),
        ).fetchone()[0]
    )
    attempt_status_rows = conn.execute(
        f"""
        SELECT a.status, COUNT(*) AS total
        FROM pipeline_work_attempts a
        JOIN pipeline_work_items i ON i.work_item_id = a.work_item_id
        {('WHERE i.pipeline_id = ?' if pipeline_id else '')}
        GROUP BY a.status
        ORDER BY a.status
        """,
        params,
    ).fetchall()
    partition_rows = conn.execute(
        f"""
        SELECT partition_key, state, COUNT(*) AS total
        FROM pipeline_work_items
        {where}
        GROUP BY partition_key, state
        ORDER BY total DESC, partition_key, state
        LIMIT ?
        """,
        (*params, int(top_limit)),
    ).fetchall()
    worker_rows = conn.execute(
        f"""
        SELECT lease_owner, COUNT(*) AS leased_total,
               MIN(lease_expires_at) AS earliest_lease_expiry,
               MAX(updated_at) AS last_heartbeat_at
        FROM pipeline_work_items
        WHERE state = 'leased' {and_filter}
        GROUP BY lease_owner
        ORDER BY leased_total DESC, lease_owner
        LIMIT ?
        """,
        (*params, int(top_limit)),
    ).fetchall()
    error_rows = conn.execute(
        f"""
        SELECT SUBSTR(last_error, 1, 160) AS error, COUNT(*) AS total
        FROM pipeline_work_items
        WHERE last_error IS NOT NULL {and_filter}
        GROUP BY SUBSTR(last_error, 1, 160)
        ORDER BY total DESC, error
        LIMIT ?
        """,
        (*params, int(top_limit)),
    ).fetchall()
    base = work_queue_stats(conn, pipeline_id=pipeline_id)
    terminal_total = int(base["terminal_total"])
    dead_total = int(dict(base["state_counts"])[DEAD])
    return {
        "schema_version": "pipeline_work_queue_observability_v1",
        "generated_at": now_iso,
        **base,
        "attempts_total": int(attempts["attempts_total"]),
        "retry_attempts_total": int(attempts["retry_attempts_total"]),
        "max_attempts_observed": int(attempts["max_attempts_observed"]),
        "oldest_pending_at": attempts["oldest_pending_at"],
        "earliest_lease_expiry": attempts["earliest_lease_expiry"],
        "overdue_leases_total": overdue_leases,
        "dead_letter_rate": round(dead_total / terminal_total, 6) if terminal_total else 0.0,
        "attempt_status_counts": {
            str(row["status"]): int(row["total"]) for row in attempt_status_rows
        },
        "top_partitions": [dict(row) for row in partition_rows],
        "active_workers": [dict(row) for row in worker_rows],
        "top_errors": [dict(row) for row in error_rows],
    }
