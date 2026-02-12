#!/usr/bin/env python3
"""Smoke gate for a minimal E2E path (1 source de representantes + 1 fuente de votos)."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def _ensure_positive(conn: sqlite3.Connection, query: str, label: str) -> None:
    row = conn.execute(query).fetchone()
    value = int(row[0]) if row else 0
    if value <= 0:
        raise SystemExit(f"[smoke] {label} no tiene datos: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path, help="Ruta del SQLite ETL (ej: etl/data/staging/politicos-es.db)")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    try:
        _ensure_positive(conn, "SELECT COUNT(*) FROM mandates WHERE source_id='congreso_diputados'", "representantes")
        _ensure_positive(conn, "SELECT COUNT(*) FROM parl_vote_events WHERE source_id='congreso_votaciones'", "votaciones")
        _ensure_positive(conn, "SELECT COUNT(*) FROM parl_vote_member_votes WHERE source_id='congreso_votaciones'", "votos nominales")
    finally:
        conn.close()

    print("[smoke] E2E mínimo OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
