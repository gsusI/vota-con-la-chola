#!/usr/bin/env python3
"""Helpers to tune SQLite connections for read-heavy static exports."""

from __future__ import annotations

import sqlite3
from typing import Any

EXPORT_PRAGMAS: tuple[tuple[str, str], ...] = (
    ("query_only", "1"),
    ("temp_store", "MEMORY"),
    ("cache_size", "-131072"),
)


def tune_sqlite_export_connection(conn: sqlite3.Connection) -> dict[str, Any]:
    """Apply read-only/export-friendly pragmas and return their read-back values.

    These exporters run large grouping queries that spill temp B-trees. Keeping
    temp state in memory and using a larger cache reduces churn on slow or
    cloud-synced worktrees without changing query semantics.
    """

    applied: dict[str, Any] = {}
    for pragma_name, pragma_value in EXPORT_PRAGMAS:
        try:
            conn.execute(f"PRAGMA {pragma_name}={pragma_value}")
            row = conn.execute(f"PRAGMA {pragma_name}").fetchone()
        except sqlite3.DatabaseError:
            continue
        if row:
            applied[pragma_name] = row[0]
    return applied
