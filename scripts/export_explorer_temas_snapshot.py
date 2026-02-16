#!/usr/bin/env python3
"""Exporta una instantánea estática (preview) de temas/posiciones para GitHub Pages.

Objetivo: que /explorer-temas/ funcione sin /api (preview), y que opcionalmente
pueda apuntar a un API real via ?api=...
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Exporta snapshot (preview) para explorer-temas (GitHub Pages)")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Ruta a la base SQLite")
    p.add_argument("--out", required=True, help="Ruta de salida JSON (p.ej. docs/gh-pages/explorer-temas/data/temas-preview.json)")
    p.add_argument("--limit-topic-sets", type=int, default=250, help="Max filas a exportar de topic_sets")
    p.add_argument("--limit-topics", type=int, default=500, help="Max filas a exportar de topics")
    p.add_argument("--limit-topic-set-topics", type=int, default=2000, help="Max filas a exportar de topic_set_topics")
    p.add_argument("--limit-positions", type=int, default=400, help="Max filas a exportar de topic_positions")
    p.add_argument("--limit-evidence", type=int, default=400, help="Max filas a exportar de topic_evidence")
    p.add_argument("--limit-evidence-reviews", type=int, default=300, help="Max filas a exportar de topic_evidence_reviews")
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

    def rows_payload(table: str, limit: int, *, latest: bool = False) -> dict:
        # For huge tables (topic_positions/topic_evidence), exporting the newest rows makes preview
        # more useful (it includes freshly backfilled evidence/positions instead of the oldest rows).
        lim = max(1, int(limit))
        if not latest:
            return g.build_explorer_rows_payload(
                db_path,
                table=table,
                q="",
                where_columns=[],
                where_values=[],
                limit=lim,
                offset=0,
            )

        meta_only = g.build_explorer_rows_payload(
            db_path,
            table=table,
            q="",
            where_columns=[],
            where_values=[],
            limit=1,
            offset=0,
        )
        total = int(((meta_only.get("meta") or {}).get("total") or 0))
        offset = max(0, total - lim)
        return g.build_explorer_rows_payload(
            db_path,
            table=table,
            q="",
            where_columns=[],
            where_values=[],
            limit=lim,
            offset=offset,
        )

    snapshot = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "db_path": str(db_path),
            "limits": {
                "topic_sets": int(args.limit_topic_sets),
                "topics": int(args.limit_topics),
                "topic_set_topics": int(args.limit_topic_set_topics),
                "topic_positions": int(args.limit_positions),
                "topic_evidence": int(args.limit_evidence),
                "topic_evidence_reviews": int(args.limit_evidence_reviews),
            },
        },
        "tables": {
            "topic_sets": rows_payload("topic_sets", args.limit_topic_sets),
            "topics": rows_payload("topics", args.limit_topics),
            "topic_set_topics": rows_payload("topic_set_topics", args.limit_topic_set_topics),
            "topic_positions": rows_payload("topic_positions", args.limit_positions, latest=True),
            "topic_evidence": rows_payload("topic_evidence", args.limit_evidence, latest=True),
            "topic_evidence_reviews": rows_payload("topic_evidence_reviews", args.limit_evidence_reviews, latest=True),
        },
    }

    out_path.write_text(json.dumps(snapshot, ensure_ascii=True, indent=2), encoding="utf-8")
    meta = snapshot.get("meta") or {}
    print(f"OK temas preview -> {out_path} (generated_at={meta.get('generated_at')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
