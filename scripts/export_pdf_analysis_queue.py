#!/usr/bin/env python3
"""Export a deterministic queue of downloaded initiative docs for text/PDF analysis.

This helps L1/L2 subagents process already-downloaded documents without hitting
upstream endpoints again.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export initiative-doc analysis queue")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument(
        "--initiative-source-id",
        default="senado_iniciativas",
        help="Filter by initiative source_id (e.g. senado_iniciativas)",
    )
    p.add_argument(
        "--doc-source-id",
        default="parl_initiative_docs",
        help="text_documents.source_id for downloaded docs",
    )
    p.add_argument(
        "--only-missing-excerpt",
        action="store_true",
        help="Only rows with empty/null text_excerpt",
    )
    p.add_argument("--limit", type=int, default=0, help="0 means no limit")
    p.add_argument("--out", required=True, help="Output CSV path")
    return p.parse_args()


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    where = [
        "i.source_id = ?",
        "td.source_id = ?",
        "pid.source_record_pk IS NOT NULL",
    ]
    params: list[object] = [str(args.initiative_source_id), str(args.doc_source_id)]

    if bool(args.only_missing_excerpt):
        where.append("(td.text_excerpt IS NULL OR TRIM(td.text_excerpt) = '')")

    limit_sql = ""
    if int(args.limit or 0) > 0:
        limit_sql = "LIMIT ?"
        params.append(int(args.limit))

    sql = f"""
    SELECT
      pid.initiative_id,
      pid.doc_kind,
      pid.doc_url,
      td.source_record_pk,
      td.source_url,
      td.content_type,
      td.bytes,
      td.raw_path,
      td.fetched_at,
      CASE
        WHEN td.text_excerpt IS NULL OR TRIM(td.text_excerpt) = '' THEN 1
        ELSE 0
      END AS needs_text_extraction
    FROM parl_initiative_documents pid
    JOIN parl_initiatives i ON i.initiative_id = pid.initiative_id
    JOIN text_documents td ON td.source_record_pk = pid.source_record_pk
    WHERE {' AND '.join(where)}
    ORDER BY
      needs_text_extraction DESC,
      td.bytes DESC,
      pid.initiative_id ASC,
      pid.doc_kind ASC,
      pid.doc_url ASC
    {limit_sql}
    """

    with open_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()

    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "initiative_id",
                "doc_kind",
                "doc_url",
                "source_record_pk",
                "source_url",
                "content_type",
                "bytes",
                "raw_path",
                "fetched_at",
                "needs_text_extraction",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    str(r["initiative_id"] or ""),
                    str(r["doc_kind"] or ""),
                    str(r["doc_url"] or ""),
                    str(r["source_record_pk"] or ""),
                    str(r["source_url"] or ""),
                    str(r["content_type"] or ""),
                    str(r["bytes"] or ""),
                    str(r["raw_path"] or ""),
                    str(r["fetched_at"] or ""),
                    str(r["needs_text_extraction"] or "0"),
                ]
            )

    print(f"OK wrote {out_path} (rows={len(rows)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
