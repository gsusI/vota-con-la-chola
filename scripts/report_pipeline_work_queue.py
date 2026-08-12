#!/usr/bin/env python3
"""Emit bounded operational metrics for durable pipeline work queues."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_ops import work_queue_observability  # noqa: E402
from publicdata_sqlite import open_db  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report durable work queue health")
    parser.add_argument("--db", default="etl/data/staging/politicos-es.db")
    parser.add_argument("--pipeline-id", default="")
    parser.add_argument("--top-limit", type=int, default=20)
    parser.add_argument("--out", default="")
    parser.add_argument("--max-dead-letter-rate", type=float, default=1.0)
    parser.add_argument("--max-overdue-leases", type=int, default=0)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return path.name


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"ERROR: DB not found: {_display_path(db_path)}", file=sys.stderr)
        return 2
    if not 1 <= int(args.top_limit) <= 1_000:
        print("ERROR: top-limit must be between 1 and 1000", file=sys.stderr)
        return 2
    if not 0.0 <= float(args.max_dead_letter_rate) <= 1.0:
        print("ERROR: max-dead-letter-rate must be between 0 and 1", file=sys.stderr)
        return 2
    if int(args.max_overdue_leases) < 0:
        print("ERROR: max-overdue-leases must be >= 0", file=sys.stderr)
        return 2

    conn = open_db(db_path, wal=False)
    try:
        report = work_queue_observability(
            conn,
            pipeline_id=str(args.pipeline_id or "").strip(),
            top_limit=int(args.top_limit),
        )
    finally:
        conn.close()
    checks = {
        "dead_letter_rate": float(report["dead_letter_rate"])
        <= float(args.max_dead_letter_rate),
        "overdue_leases": int(report["overdue_leases_total"])
        <= int(args.max_overdue_leases),
    }
    report["checks"] = checks
    report["status"] = "ok" if all(checks.values()) else "failed"
    if str(args.out or "").strip():
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 1 if args.enforce and report["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
