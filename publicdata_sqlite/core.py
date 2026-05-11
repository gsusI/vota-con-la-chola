from __future__ import annotations

import sqlite3
from pathlib import Path


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return {str(r["name"]) for r in rows}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def table_create_sql(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return str(row[0] or "") if row is not None else ""


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition_sql: str) -> None:
    if not table_exists(conn, table):
        return
    if column in table_columns(conn, table):
        return
    conn.execute(f'ALTER TABLE "{table}" ADD COLUMN {definition_sql}')
