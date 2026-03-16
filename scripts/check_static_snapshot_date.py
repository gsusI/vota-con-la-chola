#!/usr/bin/env python3
"""Check whether a static JSON artifact already matches a target snapshot date."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Checks meta.snapshot_date for a static JSON artifact.")
    parser.add_argument("--path", required=True, help="Artifact JSON path")
    parser.add_argument("--snapshot-date", required=True, help="Expected snapshot date YYYY-MM-DD")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.path)
    if not path.exists():
        print(f"MISSING {path}")
        return 1

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR {path} {exc}")
        return 2

    meta = payload.get("meta") if isinstance(payload, dict) else None
    snapshot_date = ""
    if isinstance(meta, dict):
        snapshot_date = str(meta.get("snapshot_date") or "").strip()

    if snapshot_date == args.snapshot_date:
        print(f"OK {path} snapshot_date={snapshot_date}")
        return 0

    print(f"MISMATCH {path} expected={args.snapshot_date} actual={snapshot_date or 'missing'}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
