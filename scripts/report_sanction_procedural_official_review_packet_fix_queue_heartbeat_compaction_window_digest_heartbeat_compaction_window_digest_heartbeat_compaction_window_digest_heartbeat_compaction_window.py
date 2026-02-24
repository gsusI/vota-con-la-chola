#!/usr/bin/env python3
"""Parity report for raw vs compacted packet-fix compact parity digest-heartbeat stream (last-N window)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window import (
        DEFAULT_LAST,
        build_compaction_window_report_from_paths,
    )
except ModuleNotFoundError:  # pragma: no cover - script-path invocation fallback
    from report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window import (
        DEFAULT_LAST,
        build_compaction_window_report_from_paths,
    )

DEFAULT_HEARTBEAT_JSONL = Path(
    "docs/etl/runs/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.jsonl"
)
DEFAULT_COMPACTED_JSONL = Path(
    "docs/etl/runs/sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat_compaction_window_digest_heartbeat.compacted.jsonl"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Packet-fix compact parity digest-heartbeat compaction-window report")
    p.add_argument(
        "--heartbeat-jsonl",
        default=str(DEFAULT_HEARTBEAT_JSONL),
        help=f"Raw heartbeat JSONL path (default: {DEFAULT_HEARTBEAT_JSONL})",
    )
    p.add_argument(
        "--compacted-jsonl",
        default=str(DEFAULT_COMPACTED_JSONL),
        help=f"Compacted heartbeat JSONL path (default: {DEFAULT_COMPACTED_JSONL})",
    )
    p.add_argument("--last", type=int, default=DEFAULT_LAST, help=f"Trailing raw rows to compare (default: {DEFAULT_LAST})")
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 4 when strict checks fail.",
    )
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        report = build_compaction_window_report_from_paths(
            Path(str(args.heartbeat_jsonl)),
            Path(str(args.compacted_jsonl)),
            window_last=int(args.last),
            strict=bool(args.strict),
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"runtime_error:{type(exc).__name__}:{exc}"}, ensure_ascii=False))
        return 3

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out).strip()) if str(args.out).strip() else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and len(list(report.get("strict_fail_reasons") or [])) > 0:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
