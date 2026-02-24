#!/usr/bin/env python3
"""Deterministic status report for declared-evidence sources.

Primary use case:
- Track `programas_partidos` health (ingest -> evidence -> reviews -> declared positions)
  with a single machine-readable JSON artifact.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Declared source status report")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--source-id", required=True, help="Declared evidence source_id (e.g. programas_partidos)")
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args()


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (str(table),),
    ).fetchone()
    return row is not None


def _count(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        return 0
    try:
        return int(row[0] or 0)
    except Exception:  # noqa: BLE001
        return 0


def _declared_positions_scope_cte() -> str:
    return """
        WITH source_keys AS (
          SELECT DISTINCT
            topic_id,
            person_id,
            COALESCE(topic_set_id, -1) AS topic_set_key
          FROM topic_evidence
          WHERE source_id = ?
            AND evidence_type LIKE 'declared:%'
            AND topic_id IS NOT NULL
        )
    """


def build_report(conn: sqlite3.Connection, *, source_id: str) -> dict[str, Any]:
    source_id = str(source_id or "").strip()

    source_records = _count(
        conn,
        "SELECT COUNT(*) AS c FROM source_records WHERE source_id = ?",
        (source_id,),
    )
    text_documents = _count(
        conn,
        "SELECT COUNT(*) AS c FROM text_documents WHERE source_id = ?",
        (source_id,),
    )
    topic_evidence_total = _count(
        conn,
        """
        SELECT COUNT(*) AS c
        FROM topic_evidence
        WHERE source_id = ?
          AND evidence_type LIKE 'declared:%'
        """,
        (source_id,),
    )

    evidence_by_stance_rows = conn.execute(
        """
        SELECT
          COALESCE(NULLIF(TRIM(stance), ''), 'unknown') AS stance,
          COUNT(*) AS c
        FROM topic_evidence
        WHERE source_id = ?
          AND evidence_type LIKE 'declared:%'
        GROUP BY COALESCE(NULLIF(TRIM(stance), ''), 'unknown')
        ORDER BY c DESC, stance ASC
        """,
        (source_id,),
    ).fetchall()
    evidence_by_stance = {str(r["stance"] or "unknown"): int(r["c"] or 0) for r in evidence_by_stance_rows}

    topic_sets_touched = _count(
        conn,
        """
        SELECT COUNT(DISTINCT topic_set_id) AS c
        FROM topic_evidence
        WHERE source_id = ?
          AND evidence_type LIKE 'declared:%'
          AND topic_set_id IS NOT NULL
        """,
        (source_id,),
    )

    snapshot_dates = [
        str(r["source_snapshot_date"] or "")
        for r in conn.execute(
            """
            SELECT DISTINCT source_snapshot_date
            FROM source_records
            WHERE source_id = ?
              AND source_snapshot_date IS NOT NULL
              AND TRIM(source_snapshot_date) <> ''
            ORDER BY source_snapshot_date DESC
            """,
            (source_id,),
        ).fetchall()
    ]

    # Review queue metrics are optional for forward-compat on older DBs.
    review_total = 0
    review_pending = 0
    review_resolved = 0
    review_ignored = 0
    review_pending_by_reason: dict[str, int] = {}
    if _table_exists(conn, "topic_evidence_reviews"):
        review_total = _count(
            conn,
            "SELECT COUNT(*) AS c FROM topic_evidence_reviews WHERE source_id = ?",
            (source_id,),
        )
        review_pending = _count(
            conn,
            "SELECT COUNT(*) AS c FROM topic_evidence_reviews WHERE source_id = ? AND status = 'pending'",
            (source_id,),
        )
        review_resolved = _count(
            conn,
            "SELECT COUNT(*) AS c FROM topic_evidence_reviews WHERE source_id = ? AND status = 'resolved'",
            (source_id,),
        )
        review_ignored = _count(
            conn,
            "SELECT COUNT(*) AS c FROM topic_evidence_reviews WHERE source_id = ? AND status = 'ignored'",
            (source_id,),
        )
        rows = conn.execute(
            """
            SELECT
              COALESCE(NULLIF(TRIM(review_reason), ''), 'unknown') AS reason,
              COUNT(*) AS c
            FROM topic_evidence_reviews
            WHERE source_id = ?
              AND status = 'pending'
            GROUP BY COALESCE(NULLIF(TRIM(review_reason), ''), 'unknown')
            ORDER BY c DESC, reason ASC
            """,
            (source_id,),
        ).fetchall()
        review_pending_by_reason = {str(r["reason"] or "unknown"): int(r["c"] or 0) for r in rows}

    declared_positions_total = 0
    declared_positions_latest_as_of_date: str | None = None
    declared_positions_by_stance: dict[str, int] = {}
    if _table_exists(conn, "topic_positions"):
        scope_cte = _declared_positions_scope_cte()
        declared_positions_total = _count(
            conn,
            scope_cte
            + """
            SELECT COUNT(*) AS c
            FROM topic_positions tp
            JOIN source_keys sk
              ON sk.topic_id = tp.topic_id
             AND sk.person_id = tp.person_id
             AND sk.topic_set_key = COALESCE(tp.topic_set_id, -1)
            WHERE tp.computed_method = 'declared'
            """,
            (source_id,),
        )
        row = conn.execute(
            scope_cte
            + """
            SELECT MAX(tp.as_of_date) AS max_as_of
            FROM topic_positions tp
            JOIN source_keys sk
              ON sk.topic_id = tp.topic_id
             AND sk.person_id = tp.person_id
             AND sk.topic_set_key = COALESCE(tp.topic_set_id, -1)
            WHERE tp.computed_method = 'declared'
            """,
            (source_id,),
        ).fetchone()
        declared_positions_latest_as_of_date = (
            str(row["max_as_of"]) if row and row["max_as_of"] is not None and str(row["max_as_of"]).strip() else None
        )

        rows = conn.execute(
            scope_cte
            + """
            SELECT
              COALESCE(NULLIF(TRIM(tp.stance), ''), 'unknown') AS stance,
              COUNT(*) AS c
            FROM topic_positions tp
            JOIN source_keys sk
              ON sk.topic_id = tp.topic_id
             AND sk.person_id = tp.person_id
             AND sk.topic_set_key = COALESCE(tp.topic_set_id, -1)
            WHERE tp.computed_method = 'declared'
            GROUP BY COALESCE(NULLIF(TRIM(tp.stance), ''), 'unknown')
            ORDER BY c DESC, stance ASC
            """,
            (source_id,),
        ).fetchall()
        declared_positions_by_stance = {str(r["stance"] or "unknown"): int(r["c"] or 0) for r in rows}

    party_proxy_count = 0
    if _table_exists(conn, "person_identifiers"):
        party_proxy_count = _count(
            conn,
            """
            SELECT COUNT(DISTINCT pid.value) AS c
            FROM person_identifiers pid
            JOIN (
              SELECT DISTINCT person_id
              FROM topic_evidence
              WHERE source_id = ?
                AND evidence_type LIKE 'declared:%'
            ) s ON s.person_id = pid.person_id
            WHERE pid.namespace = 'party_id'
              AND pid.value IS NOT NULL
              AND TRIM(pid.value) <> ''
            """,
            (source_id,),
        )

    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "source_id": source_id,
        "source_records": source_records,
        "text_documents": text_documents,
        "topic_evidence_total": topic_evidence_total,
        "topic_evidence_by_stance": evidence_by_stance,
        "topic_sets_touched": topic_sets_touched,
        "source_snapshot_dates": snapshot_dates,
        "review_total": review_total,
        "review_pending": review_pending,
        "review_resolved": review_resolved,
        "review_ignored": review_ignored,
        "review_pending_by_reason": review_pending_by_reason,
        "declared_positions_total": declared_positions_total,
        "declared_positions_latest_as_of_date": declared_positions_latest_as_of_date,
        "declared_positions_by_stance": declared_positions_by_stance,
        "party_proxy_count": party_proxy_count,
    }
    return report


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
    try:
        report = build_report(conn, source_id=str(args.source_id))
    finally:
        conn.close()

    if args.out:
        out_path = Path(str(args.out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OK wrote: {out_path}")
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

