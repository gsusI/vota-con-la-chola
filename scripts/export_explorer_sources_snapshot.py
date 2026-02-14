#!/usr/bin/env python3
"""Exporta una instantánea estática para explorer-sources (GitHub Pages).

Genera el payload de /api/sources/status y lo escribe a JSON.
El inventario ideal se copia desde docs/ideal_sources_say_do.json en el build.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Exporta snapshot para explorer-sources (GitHub Pages)")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Ruta de la base SQLite")
    p.add_argument("--out", required=True, help="Ruta de salida para status.json")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Import local module from repo root.
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts import graph_ui_server as g  # noqa: WPS433

    payload = g.build_sources_status_payload(db_path)
    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"OK sources status snapshot -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
