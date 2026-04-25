#!/usr/bin/env python3
"""Exporta la cobertura north-star para explorer-sources (Cloudflare Pages)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exporta coverage-capacity.json para explorer-sources")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Ruta de la base SQLite")
    parser.add_argument("--out", required=True, help="Ruta de salida para coverage-capacity.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts import graph_ui_server as g  # noqa: WPS433

    payload = g.build_sources_status_payload(db_path)
    coverage_payload = payload.get("coverage_capacity") if isinstance(payload, dict) else None
    out_path.write_text(
        json.dumps(coverage_payload or {"error": "coverage_capacity_missing"}, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    print(f"OK coverage capacity snapshot -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
