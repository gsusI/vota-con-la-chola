#!/usr/bin/env python3
"""Compact digest for packet-fix compact parity digest-heartbeat continuity compaction-window parity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest import (
        build_compaction_window_digest,
    )
except ModuleNotFoundError:  # pragma: no cover - script-path invocation fallback
    from report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest import (
        build_compaction_window_digest,
    )


DEFAULT_COMPACTION_WINDOW_JSON = Path(
    "docs/etl/sprints/AI-OPS-206/evidence/"
    "sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_latest.json"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Packet-fix compact parity digest-heartbeat continuity compaction-window digest report")
    p.add_argument(
        "--compaction-window-json",
        default=str(DEFAULT_COMPACTION_WINDOW_JSON),
        help=f"Path to compaction-window JSON input (default: {DEFAULT_COMPACTION_WINDOW_JSON})",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 4 when digest status is failed.",
    )
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    parity_path = Path(str(args.compaction_window_json))
    if not parity_path.exists():
        print(json.dumps({"error": f"compaction-window json not found: {parity_path}"}, ensure_ascii=False))
        return 2

    try:
        parity = json.loads(parity_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"invalid compaction-window json: {exc}"}, ensure_ascii=False))
        return 3
    if not isinstance(parity, dict):
        print(json.dumps({"error": "invalid compaction-window json: root must be object"}, ensure_ascii=False))
        return 3

    digest = build_compaction_window_digest(
        parity,
        compaction_window_json_path=str(parity_path),
        strict=bool(args.strict),
    )
    payload = json.dumps(digest, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out or "").strip()) if str(args.out or "").strip() else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and _safe_text(digest.get("status")).lower() == "failed":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
