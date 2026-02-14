#!/usr/bin/env python3
"""Exporta una instantánea estática (preview) de votaciones para GitHub Pages.

Objetivo: que /explorer-votaciones/ funcione sin /api (preview), y que opcionalmente
pueda apuntar a un API real via ?api=...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Exporta snapshot (preview) de votaciones para explorer-votaciones (GitHub Pages)")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Ruta a la base SQLite")
    p.add_argument("--out", required=True, help="Ruta de salida JSON")
    p.add_argument("--limit", type=int, default=200, help="Numero de eventos a exportar (ordenado por fecha desc)")
    p.add_argument("--offset", type=int, default=0, help="Offset (para paginar exports)")
    p.add_argument("--source-id", default="", help="Filtrar por source_id (opcional)")
    p.add_argument("--q", default="", help="Filtro de busqueda (opcional)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"ERROR: no existe el DB -> {db_path}")
        return 2

    # Import local module from repo root.
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts import graph_ui_server as g  # noqa: WPS433

    payload = g.build_vote_summary_payload(
        db_path,
        source_filter=(args.source_id or None),
        party_filter=None,
        q=(args.q or None),
        limit=max(1, int(args.limit)),
        offset=max(0, int(args.offset)),
    )

    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    meta = payload.get("meta") or {}
    events = payload.get("events") or []
    print(
        f"OK votes preview -> {out_path} (events={len(events)} total={meta.get('total')} limit={meta.get('limit')} offset={meta.get('offset')})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

