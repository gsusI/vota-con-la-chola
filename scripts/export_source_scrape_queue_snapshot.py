#!/usr/bin/env python3
"""Exporta una cola accionable de scraping derivada del catalogo de fuentes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exporta cola accionable de scraping")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Ruta de la base SQLite")
    parser.add_argument("--snapshot-date", default="", help="Fecha ISO YYYY-MM-DD del snapshot")
    parser.add_argument("--out", required=True, help="Ruta de salida principal")
    parser.add_argument("--published-out", default="", help="Ruta opcional snapshot published")
    parser.add_argument("--latest-out", default="", help="Ruta opcional latest published")
    return parser.parse_args()


def write_payload(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from scripts import graph_ui_server as g  # noqa: WPS433

    payload = g.build_source_scrape_queue_payload(
        Path(args.db),
        snapshot_date=str(args.snapshot_date or "").strip(),
    )

    outputs = [Path(args.out)]
    if str(args.published_out or "").strip():
        outputs.append(Path(args.published_out))
    if str(args.latest_out or "").strip():
        outputs.append(Path(args.latest_out))

    for output_path in outputs:
        write_payload(output_path, payload)

    print("OK source scrape queue snapshot -> " + ", ".join(str(path) for path in outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
