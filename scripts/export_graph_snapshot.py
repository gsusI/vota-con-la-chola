#!/usr/bin/env python3
"""Exporta un snapshot estatico del grafo para GitHub Pages (sin /api)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Exporta snapshot estatico del grafo (/api/graph) para GitHub Pages")
    p.add_argument("--db", required=True, help="Ruta a la base SQLite")
    p.add_argument("--out", required=True, help="Ruta de salida JSON")
    p.add_argument("--limit", type=int, default=350, help="Limite de mandatos usados para construir el grafo")
    p.add_argument("--include-inactive", action="store_true", help="Incluir mandatos inactivos")
    p.add_argument("--source-id", default="", help="Filtrar por source_id (opcional)")
    p.add_argument("--q", default="", help="Buscar persona (opcional)")
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

    payload = g.build_graph_payload(
        db_path,
        source_filter=(args.source_id or None),
        q=(args.q or None),
        limit=int(args.limit),
        include_inactive=bool(args.include_inactive),
    )

    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    meta = payload.get("meta") or {}
    nodes = payload.get("nodes") or []
    edges = payload.get("edges") or []
    print(f"OK graph snapshot -> {out_path} (nodes={len(nodes)} edges={len(edges)} rows={meta.get('rows')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

