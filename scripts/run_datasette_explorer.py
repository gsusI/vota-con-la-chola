#!/usr/bin/env python3
"""Run Datasette against the project SQLite."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.integrations.datasette import run_datasette, write_metadata  # noqa: E402
from etl.ops.source_scrape_queue import DEFAULT_DB  # noqa: E402


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8011


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Datasette against the project SQLite")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite DB path")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--metadata-out", default="", help="Optional metadata JSON output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2
    metadata_path = Path(str(args.metadata_out)) if str(args.metadata_out or "").strip() else None
    if metadata_path is not None:
        write_metadata(db_path, metadata_path)
    return run_datasette(db_path, host=str(args.host), port=int(args.port), metadata_path=metadata_path)


if __name__ == "__main__":
    raise SystemExit(main())
