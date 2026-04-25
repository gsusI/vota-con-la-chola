#!/usr/bin/env python3
"""Thin CLI wrapper for the source scrape queue runner."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.ops.source_scrape_queue import (  # noqa: E402
    DEFAULT_DB,
    MANUAL_STATES,
    REPEATABLE_NOW_STATES,
    _latest_ingestion_run_id,
    _load_queue,
    _normalize_command,
    _pre_commands,
    _prerequisite_source_ids,
    _render_command,
    _run_command,
    _set_cli_arg,
    _sort_items_by_dependencies,
    _validate_ingest_run,
    execute_item,
    execute_queue,
    main,
    parse_args,
    select_command,
    should_run_item,
    subprocess,
)


if __name__ == "__main__":
    raise SystemExit(main())
