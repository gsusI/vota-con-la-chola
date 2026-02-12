#!/usr/bin/env python3
"""Publica una instantanea canónica de Infoelectoral.

Salida: `etl/data/published/infoelectoral-es-<snapshot>.json`.

La salida es determinista y queda trazable por fuente (source_record_id /
source_record_pk / source_hash) para facilitar auditoría y debug.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Ensure repo root is importable when executing this file directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.infoelectoral_es.publish import build_infoelectoral_snapshot, write_json_if_changed
from etl.politicos_es.db import open_db


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_OUT_DIR = Path("etl/data/published")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Publicar snapshot canónico de Infoelectoral")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Ruta del SQLite de entrada")
    p.add_argument(
        "--snapshot-date",
        required=True,
        help="Fecha ISO YYYY-MM-DD (se usa como fecha de referencia del snapshot)",
    )
    p.add_argument(
        "--json-out",
        default="",
        help="Ruta exacta del JSON de salida (si no se da, usa etl/data/published/infoelectoral-es-<snapshot>.json)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB no existe: {db_path}", file=sys.stderr)
        return 2

    snapshot_date = str(args.snapshot_date).strip()
    if not snapshot_date:
        print("ERROR: snapshot-date vacio", file=sys.stderr)
        return 2

    if args.json_out:
        out_path = Path(args.json_out)
    else:
        out_path = DEFAULT_OUT_DIR / f"infoelectoral-es-{snapshot_date}.json"

    conn: sqlite3.Connection = open_db(db_path)
    try:
        snapshot = build_infoelectoral_snapshot(conn, snapshot_date=snapshot_date)
    finally:
        conn.close()

    changed = write_json_if_changed(out_path, snapshot)
    if changed:
        print(f"OK wrote: {out_path}")
    else:
        print(f"OK unchanged: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
