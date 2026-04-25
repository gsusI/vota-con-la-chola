#!/usr/bin/env python3
"""Validate citizen snapshot JSON for the static citizen app."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.citizen_snapshot_schema import validate_snapshot_payload  # noqa: E402


def die(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def warn(message: str) -> None:
    print(f"WARN: {message}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida snapshot JSON para app ciudadana (GH Pages)")
    parser.add_argument(
        "--path",
        required=True,
        help="Ruta al citizen.json (p.ej. ui/gh-pages-next/public/citizen/data/citizen.json)",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=None,
        help="Fail si el archivo supera este tamaño (bytes). Si se omite, usa meta.guards.max_bytes si existe.",
    )
    parser.add_argument(
        "--strict-grid",
        action="store_true",
        help="Fail si party_topic_positions no cubre topics x parties exactamente.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = str(args.path)
    if not os.path.exists(path):
        die(f"File not found: {path}")

    size = os.path.getsize(path)
    with open(path, "rb") as file_obj:
        try:
            data = json.load(file_obj)
        except json.JSONDecodeError as exc:
            die(f"Invalid JSON: {exc}")

    try:
        result = validate_snapshot_payload(
            data,
            strict_grid=bool(args.strict_grid),
            size_bytes=size,
            max_bytes=args.max_bytes,
        )
    except ValueError as exc:
        die(str(exc))

    for message in result["warnings"]:
        warn(str(message))

    summary = dict(result["summary"])
    summary["path"] = path
    print(json.dumps(summary, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
