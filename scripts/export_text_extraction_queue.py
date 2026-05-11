#!/usr/bin/env python3
"""Export a deterministic text extraction queue from `text_documents`.

Primary goal: enable mechanical extraction runs over downloaded PDFs/HTML/XML
without upstream network calls. Queue items are deduped by checksum by default
so one extraction can hydrate multiple `source_record_pk` references.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from publicdata_docs.extraction_queue import _parse_csv_set, build_queue_rows


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")












def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export text extraction queue from text_documents")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument(
        "--source-ids",
        default="",
        help="Comma-separated filter for text_documents.source_id. Empty means all.",
    )
    p.add_argument(
        "--formats",
        default="pdf,html,xml",
        help="Comma-separated formats to include (pdf,html,xml,other)",
    )
    p.add_argument(
        "--only-missing-excerpt",
        action="store_true",
        help="Only include references with empty/null text_excerpt",
    )
    p.add_argument(
        "--dedupe-by",
        default="content_sha256",
        choices=["content_sha256", "raw_path", "source_record_pk"],
        help="Queue dedupe key strategy",
    )
    p.add_argument("--limit", type=int, default=0, help="0 means no limit")
    p.add_argument("--out", required=True, help="Output CSV path")
    p.add_argument("--summary-out", default="", help="Optional JSON summary output path")
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

    src_ids = _parse_csv_set(str(args.source_ids))
    formats = _parse_csv_set(str(args.formats))

    with open_db(db_path) as conn:
        queue_rows, summary = build_queue_rows(
            conn,
            source_ids=src_ids,
            allowed_formats=formats,
            only_missing_excerpt=bool(args.only_missing_excerpt),
            dedupe_by=str(args.dedupe_by),
            limit=int(args.limit or 0),
        )

    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "queue_key",
                "queue_status",
                "doc_format",
                "content_sha256",
                "representative_source_id",
                "representative_source_record_pk",
                "representative_source_url",
                "bytes",
                "raw_path",
                "has_raw_file",
                "fetched_at",
                "refs_total",
                "refs_missing_excerpt",
                "refs_missing_raw_file",
                "source_ids",
                "source_record_pks_json",
            ]
        )
        for r in queue_rows:
            w.writerow(
                [
                    str(r["queue_key"]),
                    str(r["queue_status"]),
                    str(r["doc_format"]),
                    str(r["content_sha256"]),
                    str(r["representative_source_id"]),
                    str(r["representative_source_record_pk"]),
                    str(r["representative_source_url"]),
                    str(r["bytes"]),
                    str(r["raw_path"]),
                    str(r["has_raw_file"]),
                    str(r["fetched_at"]),
                    str(r["refs_total"]),
                    str(r["refs_missing_excerpt"]),
                    str(r["refs_missing_raw_file"]),
                    str(r["source_ids"]),
                    str(r["source_record_pks_json"]),
                ]
            )

    summary_payload = dict(summary)
    summary_payload.update(
        {
            "db": str(db_path),
            "out": str(out_path),
            "source_ids_filter": sorted(src_ids),
        }
    )

    if str(args.summary_out or "").strip():
        summary_out_path = Path(str(args.summary_out)).resolve()
        summary_out_path.parent.mkdir(parents=True, exist_ok=True)
        summary_out_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
