#!/usr/bin/env python3
"""Compaction reporter for initdoc compact-window-digest heartbeat JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from scripts.report_initdoc_actionable_tail_digest_heartbeat_compaction import (
        DEFAULT_KEEP_MID_EVERY,
        DEFAULT_KEEP_MID_SPAN,
        DEFAULT_KEEP_OLD_EVERY,
        DEFAULT_KEEP_RECENT,
        DEFAULT_MIN_RAW_FOR_DROPPED_CHECK,
        build_compaction_report,
        read_heartbeat_rows,
        write_compacted_jsonl,
    )
except ModuleNotFoundError:  # pragma: no cover - script-path invocation fallback
    from report_initdoc_actionable_tail_digest_heartbeat_compaction import (
        DEFAULT_KEEP_MID_EVERY,
        DEFAULT_KEEP_MID_SPAN,
        DEFAULT_KEEP_OLD_EVERY,
        DEFAULT_KEEP_RECENT,
        DEFAULT_MIN_RAW_FOR_DROPPED_CHECK,
        build_compaction_report,
        read_heartbeat_rows,
        write_compacted_jsonl,
    )

DEFAULT_HEARTBEAT_JSONL = Path(
    "docs/etl/runs/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.jsonl"
)
DEFAULT_COMPACTED_JSONL = Path(
    "docs/etl/runs/initdoc_actionable_tail_digest_heartbeat_compaction_window_digest_heartbeat.compacted.jsonl"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Initdoc compact-window-digest heartbeat compaction report")
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
    p.add_argument(
        "--keep-recent",
        type=int,
        default=DEFAULT_KEEP_RECENT,
        help=f"Keep every row for recent window (default: {DEFAULT_KEEP_RECENT})",
    )
    p.add_argument(
        "--keep-mid-span",
        type=int,
        default=DEFAULT_KEEP_MID_SPAN,
        help=f"Mid window size after recent window (default: {DEFAULT_KEEP_MID_SPAN})",
    )
    p.add_argument(
        "--keep-mid-every",
        type=int,
        default=DEFAULT_KEEP_MID_EVERY,
        help=f"Cadence in mid window (default: {DEFAULT_KEEP_MID_EVERY})",
    )
    p.add_argument(
        "--keep-old-every",
        type=int,
        default=DEFAULT_KEEP_OLD_EVERY,
        help=f"Cadence in old window (default: {DEFAULT_KEEP_OLD_EVERY})",
    )
    p.add_argument(
        "--min-raw-for-dropped-check",
        type=int,
        default=DEFAULT_MIN_RAW_FOR_DROPPED_CHECK,
        help=f"Require at least one dropped row when raw >= N (default: {DEFAULT_MIN_RAW_FOR_DROPPED_CHECK})",
    )
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
        rows = read_heartbeat_rows(Path(str(args.heartbeat_jsonl)))
        report, selected_rows = build_compaction_report(
            rows,
            heartbeat_path=str(args.heartbeat_jsonl),
            compacted_path=str(args.compacted_jsonl),
            keep_recent=int(args.keep_recent),
            keep_mid_span=int(args.keep_mid_span),
            keep_mid_every=int(args.keep_mid_every),
            keep_old_every=int(args.keep_old_every),
            min_raw_for_dropped_check=int(args.min_raw_for_dropped_check),
            strict=bool(args.strict),
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"runtime_error:{type(exc).__name__}:{exc}"}, ensure_ascii=False))
        return 3

    compacted_path = Path(str(args.compacted_jsonl))
    write_compacted_jsonl(compacted_path, selected_rows)

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
