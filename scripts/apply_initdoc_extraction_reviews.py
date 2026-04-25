#!/usr/bin/env python3
"""Apply review decisions to `parl_initiative_doc_extractions` from CSV."""

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
    apply_review_decisions,
    open_db,
    read_review_csv,
)
from etl.politicos_es.util import normalize_ws  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply initiative-doc extraction review decisions")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    parser.add_argument("--in", dest="in_file", required=True, help="Input CSV with review decisions")
    parser.add_argument("--source-id", default=DEFAULT_SOURCE_ID, help="Extraction source_id scope")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default="", help="Optional JSON summary output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    in_path = Path(args.in_file)

    if not db_path.exists():
        print(json.dumps({"error": f"db not found: {db_path}"}, ensure_ascii=False))
        return 2
    if not in_path.exists():
        print(json.dumps({"error": f"input csv not found: {in_path}"}, ensure_ascii=False))
        return 2

    rows = read_review_csv(in_path)
    with open_db(db_path) as conn:
        result = apply_review_decisions(
            conn,
            source_id=normalize_ws(str(args.source_id or "")) or DEFAULT_SOURCE_ID,
            rows=rows,
            dry_run=bool(args.dry_run),
        )

    result.update({"db": str(db_path), "input_csv": str(in_path)})
    if normalize_ws(str(args.out or "")):
        out_path = Path(str(args.out)).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
