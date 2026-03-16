#!/usr/bin/env python3
"""Seed scalable measure candidates/clusters from reviewed measure points."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws
from scripts.measure_scale_layer import seed_measure_scale_layer


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill scalable measure candidates from reviewed measure points")
    p.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    p.add_argument("--source-id", default="", help="Optional parl_initiative_measure_points.source_id scope")
    p.add_argument(
        "--measure-point-id",
        action="append",
        default=[],
        help="Specific measure_point_id to seed (repeatable)",
    )
    p.add_argument("--task-id", action="append", default=[], help="Specific task_id to seed (repeatable)")
    p.add_argument(
        "--initiative-id",
        action="append",
        default=[],
        help="Specific initiative_id to seed (repeatable)",
    )
    p.add_argument(
        "--only-missing",
        action="store_true",
        help="Only seed reviewed points that do not yet exist in parl_measure_candidates",
    )
    p.add_argument("--limit", type=int, default=0, help="0 means no limit")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args()


def _norm(value: object) -> str:
    return normalize_ws(str(value or ""))


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    with open_db(db_path) as conn:
        apply_schema(conn, DEFAULT_SCHEMA)
        with conn:
            result = seed_measure_scale_layer(
                conn,
                source_id=_norm(args.source_id),
                measure_point_ids=tuple(args.measure_point_id or ()),
                task_ids=tuple(args.task_id or ()),
                initiative_ids=tuple(args.initiative_id or ()),
                only_missing=bool(args.only_missing),
                limit=max(0, int(args.limit or 0)),
                dry_run=bool(args.dry_run),
            )

    if _norm(args.out):
        Path(args.out).write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
