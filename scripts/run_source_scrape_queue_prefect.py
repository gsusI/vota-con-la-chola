#!/usr/bin/env python3
"""Run the source scrape queue via Prefect."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.integrations.prefect_source_scrape_queue import run_prefect_queue  # noqa: E402
from etl.ops.source_scrape_queue import DEFAULT_DB  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run source scrape queue with Prefect")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Target SQLite DB")
    parser.add_argument("--queue", default="", help="Existing queue JSON (optional)")
    parser.add_argument("--snapshot-date", default="", help="Optional YYYY-MM-DD override for ingest commands")
    parser.add_argument("--mode", choices=("preferred", "network", "sample"), default="preferred")
    parser.add_argument("--only-repeatable-now", action="store_true")
    parser.add_argument("--fallback-on-failure", choices=("none",), default="none")
    parser.add_argument("--include-logs", action="store_true")
    parser.add_argument("--command-timeout-seconds", type=int, default=90)
    parser.add_argument("--summary-out", default="")
    parser.add_argument("--allow-failures", action="store_true")
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--retry-delay-seconds", type=int, default=15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    summary = run_prefect_queue(
        db_path=db_path,
        queue_path=str(args.queue or "").strip(),
        snapshot_date=str(args.snapshot_date or "").strip(),
        mode=str(args.mode or "preferred"),
        only_repeatable_now=bool(args.only_repeatable_now),
        fallback_on_failure=str(args.fallback_on_failure or "none"),
        include_logs=bool(args.include_logs),
        command_timeout_seconds=int(args.command_timeout_seconds or 90),
        summary_out=str(args.summary_out or "").strip(),
        retries=int(args.retries or 0),
        retry_delay_seconds=int(args.retry_delay_seconds or 15),
    )
    print(json.dumps({"db_path": summary.get("db_path"), "totals": summary.get("totals")}, ensure_ascii=True))
    failed_total = int(((summary.get("totals") or {}).get("failed_total")) or 0)
    if failed_total and not args.allow_failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
