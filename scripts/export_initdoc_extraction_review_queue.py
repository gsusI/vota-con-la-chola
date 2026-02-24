#!/usr/bin/env python3
"""Export review queue from `parl_initiative_doc_extractions`.

Designed for subagent/manual adjudication packets after heuristic extraction.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export initiative-doc extraction review queue")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--source-id", default="parl_initiative_docs")
    p.add_argument("--only-needs-review", action="store_true", help="Only rows flagged needs_review=1")
    p.add_argument("--limit", type=int, default=0, help="0 means no limit")
    p.add_argument("--offset", type=int, default=0, help="Row offset (for deterministic batch paging)")
    p.add_argument("--out", required=True, help="Output CSV path")
    return p.parse_args()


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def fetch_review_rows(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    only_needs_review: bool,
    limit: int,
    offset: int,
) -> list[sqlite3.Row]:
    where = ["ex.source_id = ?"]
    params: list[object] = [str(source_id)]
    if bool(only_needs_review):
        where.append("ex.needs_review = 1")

    limit_sql = ""
    limit_i = max(0, int(limit or 0))
    offset_i = max(0, int(offset or 0))
    if limit_i > 0:
        limit_sql = "LIMIT ? OFFSET ?"
        params.extend([limit_i, offset_i])
    elif offset_i > 0:
        limit_sql = "LIMIT -1 OFFSET ?"
        params.append(offset_i)

    sql = f"""
    SELECT
      ex.source_record_pk,
      ex.sample_initiative_id,
      i.source_id AS initiative_source_id,
      i.title AS initiative_title,
      ex.doc_format,
      ex.doc_kinds_csv,
      ex.initiatives_count,
      ex.doc_refs_count,
      ex.extractor_version,
      json_extract(ex.analysis_payload_json, '$.subject_method') AS subject_method,
      ex.confidence,
      ex.needs_review,
      ex.extracted_subject,
      ex.extracted_title,
      ex.extracted_excerpt,
      td.source_url,
      td.raw_path
    FROM parl_initiative_doc_extractions ex
    LEFT JOIN parl_initiatives i ON i.initiative_id = ex.sample_initiative_id
    LEFT JOIN text_documents td ON td.source_record_pk = ex.source_record_pk AND td.source_id = ex.source_id
    WHERE {' AND '.join(where)}
    ORDER BY
      ex.needs_review DESC,
      ex.confidence ASC,
      ex.source_record_pk ASC
    {limit_sql}
    """
    return conn.execute(sql, params).fetchall()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    with open_db(db_path) as conn:
        rows = fetch_review_rows(
            conn,
            source_id=str(args.source_id),
            only_needs_review=bool(args.only_needs_review),
            limit=int(args.limit or 0),
            offset=int(args.offset or 0),
        )

    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "source_record_pk",
                "sample_initiative_id",
                "initiative_source_id",
                "initiative_title",
                "doc_format",
                "doc_kinds_csv",
                "initiatives_count",
                "doc_refs_count",
                "extractor_version",
                "subject_method",
                "confidence",
                "needs_review",
                "extracted_subject",
                "extracted_title",
                "extracted_excerpt",
                "source_url",
                "raw_path",
                "review_status",
                "final_subject",
                "final_title",
                "final_confidence",
                "review_note",
                "reviewer",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    str(r["source_record_pk"] or ""),
                    str(r["sample_initiative_id"] or ""),
                    str(r["initiative_source_id"] or ""),
                    str(r["initiative_title"] or ""),
                    str(r["doc_format"] or ""),
                    str(r["doc_kinds_csv"] or ""),
                    str(r["initiatives_count"] or ""),
                    str(r["doc_refs_count"] or ""),
                    str(r["extractor_version"] or ""),
                    str(r["subject_method"] or ""),
                    str(r["confidence"] or ""),
                    str(r["needs_review"] or ""),
                    str(r["extracted_subject"] or ""),
                    str(r["extracted_title"] or ""),
                    str(r["extracted_excerpt"] or ""),
                    str(r["source_url"] or ""),
                    str(r["raw_path"] or ""),
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )

    print(f"OK wrote {out_path} (rows={len(rows)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
