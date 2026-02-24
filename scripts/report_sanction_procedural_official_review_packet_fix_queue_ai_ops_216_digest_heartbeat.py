#!/usr/bin/env python3
"""AI-OPS-216 append-only heartbeat continuity over AI-OPS-215 compact digest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts.report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat import (
        _normalize_status,
        _safe_obj,
        _safe_text,
        append_heartbeat,
        build_heartbeat,
        history_has_heartbeat,
        now_utc_iso,
        read_history_entries,
        validate_heartbeat,
    )
except ModuleNotFoundError:  # pragma: no cover - script-path invocation fallback
    from report_sanction_procedural_official_review_packet_fix_queue_heartbeat_compaction_window_digest_heartbeat import (
        _normalize_status,
        _safe_obj,
        _safe_text,
        append_heartbeat,
        build_heartbeat,
        history_has_heartbeat,
        now_utc_iso,
        read_history_entries,
        validate_heartbeat,
    )

DEFAULT_DIGEST_JSON = Path(
    "docs/etl/sprints/AI-OPS-215/evidence/ai_ops_215_digest_latest.json"
)
DEFAULT_HEARTBEAT_JSONL = Path(
    "docs/etl/runs/ai_ops_216_digest_heartbeat.jsonl"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AI-OPS-216 append heartbeat JSONL for AI-OPS-215 digest")
    p.add_argument(
        "--digest-json",
        default=str(DEFAULT_DIGEST_JSON),
        help=f"Input digest JSON path (default: {DEFAULT_DIGEST_JSON})",
    )
    p.add_argument(
        "--heartbeat-jsonl",
        default=str(DEFAULT_HEARTBEAT_JSONL),
        help=f"Heartbeat JSONL path (default: {DEFAULT_HEARTBEAT_JSONL})",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 4 when heartbeat is invalid or status=failed.",
    )
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    digest_path = Path(str(args.digest_json))
    if not digest_path.exists():
        print(json.dumps({"error": f"digest json not found: {digest_path}"}, ensure_ascii=False))
        return 2

    try:
        digest_payload = json.loads(digest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"invalid digest json: {exc}"}, ensure_ascii=False))
        return 3

    if not isinstance(digest_payload, dict):
        print(json.dumps({"error": "invalid digest json: root must be object"}, ensure_ascii=False))
        return 3

    heartbeat_path = Path(str(args.heartbeat_jsonl))
    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "strict": bool(args.strict),
        "input_path": str(digest_path),
        "heartbeat_path": str(heartbeat_path),
        "history_size_before": 0,
        "history_size_after": 0,
        "history_malformed_lines_before": 0,
        "appended": False,
        "duplicate_detected": False,
        "validation_errors": [],
        "heartbeat": {},
    }

    try:
        heartbeat = build_heartbeat(digest_payload, digest_path=str(digest_path))
        report["heartbeat"] = heartbeat
        report["validation_errors"] = validate_heartbeat(heartbeat)

        history_before = read_history_entries(heartbeat_path)
        report["history_size_before"] = len(history_before)
        report["history_malformed_lines_before"] = sum(1 for row in history_before if bool(row.get("malformed_line")))

        if not report["validation_errors"]:
            report["duplicate_detected"] = history_has_heartbeat(history_before, _safe_text(heartbeat.get("heartbeat_id")))
            if not report["duplicate_detected"]:
                append_heartbeat(heartbeat_path, heartbeat)
                report["appended"] = True

        report["history_size_after"] = int(report["history_size_before"]) + (1 if report["appended"] else 0)
    except Exception as exc:  # noqa: BLE001
        report["validation_errors"] = [f"runtime_error:{type(exc).__name__}:{exc}"]
        report["history_size_after"] = int(report["history_size_before"])

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out).strip()) if str(args.out).strip() else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    status = _normalize_status(_safe_obj(report.get("heartbeat")).get("status"))
    if bool(args.strict) and (len(list(report.get("validation_errors") or [])) > 0 or status == "failed"):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
