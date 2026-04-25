#!/usr/bin/env python3
"""Export initiative-doc extraction review tasks for Label Studio."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.initdoc_review import (  # noqa: E402
    DEFAULT_DB,
    DEFAULT_SOURCE_ID,
    LABEL_STUDIO_CONFIG_XML,
    export_label_studio_tasks,
    fetch_review_rows,
    open_db,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export initiative-doc review tasks for Label Studio")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    parser.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    parser.add_argument("--only-needs-review", action="store_true", help="Only rows flagged needs_review=1")
    parser.add_argument("--limit", type=int, default=0, help="0 means no limit")
    parser.add_argument("--offset", type=int, default=0, help="Row offset (for deterministic batch paging)")
    parser.add_argument("--out", required=True, help="Output JSON task file")
    parser.add_argument("--config-out", default="", help="Optional Label Studio XML config output")
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

    tasks = export_label_studio_tasks(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if str(args.config_out or "").strip():
        config_path = Path(str(args.config_out))
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(LABEL_STUDIO_CONFIG_XML, encoding="utf-8")

    print(json.dumps({"out": str(out_path), "rows": len(rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
