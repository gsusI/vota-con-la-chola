#!/usr/bin/env python3
"""Export review queue from `parl_initiative_doc_extractions`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.initdoc_review import (  # noqa: E402
    DEFAULT_DB,
    DEFAULT_SOURCE_ID,
    fetch_review_rows,
    open_db,
    write_review_queue_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export initiative-doc extraction review queue")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    parser.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    parser.add_argument("--only-needs-review", action="store_true", help="Only rows flagged needs_review=1")
    parser.add_argument("--limit", type=int, default=0, help="0 means no limit")
    parser.add_argument("--offset", type=int, default=0, help="Row offset (for deterministic batch paging)")
    parser.add_argument("--out", required=True, help="Output CSV path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)
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

    written = write_review_queue_csv(rows, out_path)
    print(f"OK wrote {out_path} (rows={written})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
