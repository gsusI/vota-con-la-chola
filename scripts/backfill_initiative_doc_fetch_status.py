#!/usr/bin/env python3
"""Backfill document_fetches rows for already-downloaded initiative docs.

Use this to restore traceability on historical DBs where `text_documents` and
`parl_initiative_documents` rows exist but `document_fetches` was not populated.
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
    p = argparse.ArgumentParser(description="Backfill document_fetches for initiative docs already in text_documents")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--source-id", default="parl_initiative_docs", help="text_documents/document_fetches source_id")
    p.add_argument(
        "--initiative-source-id",
        default="",
        help="Optional parl_initiatives.source_id filter (e.g. senado_iniciativas, congreso_iniciativas)",
    )
    p.add_argument("--limit", type=int, default=0, help="0 means no limit")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _coverage(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    initiative_source_id: str,
) -> dict[str, int]:
    where = ["td.source_id = ?"]
    params: list[Any] = [source_id]
    if initiative_source_id:
        where.append("i.source_id = ?")
        params.append(initiative_source_id)

    row = conn.execute(
        f"""
        SELECT
          COUNT(*) AS total_doc_links,
          SUM(CASE WHEN df.doc_url IS NOT NULL THEN 1 ELSE 0 END) AS with_fetch_status
        FROM parl_initiative_documents d
        JOIN parl_initiatives i ON i.initiative_id = d.initiative_id
        JOIN text_documents td ON td.source_record_pk = d.source_record_pk
        LEFT JOIN document_fetches df ON df.doc_url = d.doc_url
        WHERE {' AND '.join(where)}
        """,
        params,
    ).fetchone()
    total = int(row["total_doc_links"] or 0) if row else 0
    with_status = int(row["with_fetch_status"] or 0) if row else 0
    return {
        "total_doc_links": total,
        "with_fetch_status": with_status,
        "missing_fetch_status": max(0, total - with_status),
    }


def _build_candidates_query(
    *,
    has_initiative_filter: bool,
    has_limit: bool,
) -> str:
    where = [
        "td.source_id = ?",
        "d.doc_url IS NOT NULL",
        "TRIM(d.doc_url) <> ''",
        "d.doc_url LIKE 'http%'",
        "df.doc_url IS NULL",
    ]
    if has_initiative_filter:
        where.append("i.source_id = ?")

    limit_sql = " LIMIT ?" if has_limit else ""
    return f"""
    SELECT
      d.doc_url,
      MAX(COALESCE(td.fetched_at, td.updated_at, td.created_at, '')) AS fetched_at,
      MAX(COALESCE(td.content_type, '')) AS content_type,
      MAX(COALESCE(td.content_sha256, '')) AS content_sha256,
      MAX(COALESCE(td.bytes, 0)) AS bytes,
      MAX(COALESCE(td.raw_path, '')) AS raw_path,
      COUNT(*) AS refs
    FROM parl_initiative_documents d
    JOIN parl_initiatives i ON i.initiative_id = d.initiative_id
    JOIN text_documents td ON td.source_record_pk = d.source_record_pk
    LEFT JOIN document_fetches df ON df.doc_url = d.doc_url
    WHERE {' AND '.join(where)}
    GROUP BY d.doc_url
    ORDER BY d.doc_url ASC
    {limit_sql}
    """


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(json.dumps({"error": f"db not found: {db_path}"}, ensure_ascii=False))
        return 2

    source_id = str(args.source_id or "").strip() or "parl_initiative_docs"
    initiative_source_id = str(args.initiative_source_id or "").strip()
    has_limit = int(args.limit or 0) > 0

    sql = _build_candidates_query(
        has_initiative_filter=bool(initiative_source_id),
        has_limit=has_limit,
    )
    params: list[Any] = [source_id]
    if initiative_source_id:
        params.append(initiative_source_id)
    if has_limit:
        params.append(int(args.limit))

    now_iso = now_utc_iso()
    inserted = 0
    refs_total = 0
    sample_urls: list[str] = []

    with open_db(db_path) as conn:
        before = _coverage(
            conn,
            source_id=source_id,
            initiative_source_id=initiative_source_id,
        )
        rows = conn.execute(sql, params).fetchall()
        refs_total = int(sum(int(r["refs"] or 0) for r in rows))
        sample_urls = [str(r["doc_url"]) for r in rows[:10]]

        insert_rows: list[tuple[Any, ...]] = []
        for r in rows:
            doc_url = str(r["doc_url"] or "").strip()
            if not doc_url:
                continue
            fetched_at = str(r["fetched_at"] or "").strip() or now_iso
            content_type = str(r["content_type"] or "").strip() or None
            content_sha = str(r["content_sha256"] or "").strip() or None
            raw_path = str(r["raw_path"] or "").strip() or None
            try:
                bytes_len = int(r["bytes"] or 0)
            except Exception:
                bytes_len = 0

            insert_rows.append(
                (
                    doc_url,
                    source_id,
                    fetched_at,
                    fetched_at,
                    1,
                    1,
                    200,
                    None,
                    content_type,
                    content_sha,
                    bytes_len if bytes_len > 0 else None,
                    raw_path,
                )
            )

        if not args.dry_run and insert_rows:
            with conn:
                conn.executemany(
                    """
                    INSERT INTO document_fetches (
                      doc_url,
                      source_id,
                      first_attempt_at,
                      last_attempt_at,
                      attempts,
                      fetched_ok,
                      last_http_status,
                      last_error,
                      content_type,
                      content_sha256,
                      bytes,
                      raw_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(doc_url) DO NOTHING
                    """,
                    insert_rows,
                )
            inserted = len(insert_rows)
        else:
            inserted = len(insert_rows)

        after = _coverage(
            conn,
            source_id=source_id,
            initiative_source_id=initiative_source_id,
        )

    result = {
        "db": str(db_path),
        "source_id": source_id,
        "initiative_source_id": initiative_source_id,
        "dry_run": bool(args.dry_run),
        "candidate_urls": len(rows),
        "candidate_refs_total": refs_total,
        "inserted_or_would_insert": inserted,
        "coverage_before": before,
        "coverage_after": after,
        "sample_urls": sample_urls,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
